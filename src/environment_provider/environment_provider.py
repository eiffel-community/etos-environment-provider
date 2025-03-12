# Copyright Axis Communications AB.
#
# For a full list of individual contributors, please see the commit history.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""ETOS Environment Provider module."""

import sys
import json
import logging
import os
import time
import traceback
import uuid
from datetime import datetime
from tempfile import NamedTemporaryFile
from typing import Any, Optional

from etos_lib.etos import ETOS
from etos_lib.lib.events import EiffelEnvironmentDefinedEvent
from etos_lib.logging.logger import FORMAT_CONFIG
from etos_lib.opentelemetry.semconv import Attributes as SemConvAttributes
from etos_lib.kubernetes import Kubernetes, Environment, Provider
from etos_lib.kubernetes.schemas.common import OwnerReference
from etos_lib.kubernetes.schemas import Environment as EnvironmentSchema, EnvironmentSpec, Metadata
from etos_lib.kubernetes.schemas import Test
from etos_lib.kubernetes.schemas import Provider as ProviderSchema
from etos_lib.kubernetes.schemas import EnvironmentRequest as EnvironmentRequestSchema
from jsontas.jsontas import JsonTas
from packageurl import PackageURL
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from execution_space_provider.execution_space import ExecutionSpace
from log_area_provider.log_area import LogArea

from .lib.config import Config
from .lib.encrypt import Encrypt
from .lib.graphql import request_main_suite
from .lib.join import Join
from .lib.json_dumps import JsonDumps
from .lib.log_area import LogArea
from .lib.registry import ProviderRegistry
from .lib.database import ETCDPath
from .lib.test_suite import TestSuite
from .lib.uuid_generate import UuidGenerate
from .splitter.split import Splitter

logging.getLogger("pika").setLevel(logging.WARNING)


class NoEventDataFound(Exception):
    """Could not fetch events from event storage."""


class EnvironmentProviderNotConfigured(Exception):
    """Environment provider was not configured prior to request."""


class EnvironmentProviderError(Exception):
    """Environment provider got an error."""


class EnvironmentProvider:  # pylint:disable=too-many-instance-attributes
    """Environment provider."""

    logger = logging.getLogger("EnvironmentProvider")
    iut_provider = None
    log_area_provider = None
    execution_space_provider = None
    testrun = None

    def __init__(self, suite_runner_ids: Optional[list[str]] = None) -> None:
        """Initialize ETOS, dataset, provider registry and splitter.

        :param suite_runner_ids: IDs from the suite runner to correlate sub suites.
        """
        self.etos = ETOS(
            "ETOS Environment Provider", os.getenv("HOSTNAME", "Unknown"), "Environment Provider"
        )
        self.kubernetes = Kubernetes()
        self.environment_provider_config = Config(self.etos, self.kubernetes, suite_runner_ids)

        FORMAT_CONFIG.identifier = self.environment_provider_config.requests[0].spec.identifier
        self.suite_id = self.environment_provider_config.requests[0].spec.identifier

        self.logger.info("Initializing EnvironmentProvider.")
        self.tracer = trace.get_tracer(__name__)

        self.suite_runner_ids = suite_runner_ids

        self.reset()

    def reset(self) -> None:
        """Create a new dataset and provider registry."""
        self.jsontas = JsonTas()
        self.dataset = self.jsontas.dataset
        self.dataset.add("json_dumps", JsonDumps)
        self.dataset.add("uuid_generate", UuidGenerate)
        self.dataset.add("join", Join)
        self.dataset.add("encrypt", Encrypt)
        self.registry = ProviderRegistry(self.etos, self.jsontas, self.suite_id)

    def new_dataset(self, request: EnvironmentRequestSchema) -> None:
        """Load a new dataset.

        :param dataset: Dataset to use for this configuration.
        """
        self.reset()
        self.dataset.add("identity", PackageURL.from_string(request.spec.identity))

        self.dataset.add("artifact_id", request.spec.artifact)
        self.dataset.add("context", self.environment_provider_config.context)

        dataset = request.spec.dataset or {}
        self.dataset.add("dataset", dataset)
        self.dataset.merge(dataset)

        self.iut_provider = self.registry.iut_provider()
        self.log_area_provider = self.registry.log_area_provider()
        self.execution_space_provider = self.registry.execution_space_provider()

    def configure(self, request: EnvironmentRequestSchema) -> None:
        """Configure environment provider."""
        self.logger.info("Configure environment provider.")
        if not self.registry.wait_for_configuration():
            # TODO: Add link ref to docs that describe how the config is done.
            raise EnvironmentProviderNotConfigured(
                "Please do a proper configuration of "
                "EnvironmentProvider before requesting an "
                "environment."
            )
        self.logger.info("Registry is configured.")
        self.etos.config.set("SUITE_ID", request.spec.identifier)

        self.etos.config.set("EVENT_DATA_TIMEOUT", int(os.getenv("ETOS_EVENT_DATA_TIMEOUT", "10")))
        self.etos.config.set(
            "WAIT_FOR_IUT_TIMEOUT", int(os.getenv("ETOS_WAIT_FOR_IUT_TIMEOUT", "10"))
        )
        self.etos.config.set(
            "WAIT_FOR_EXECUTION_SPACE_TIMEOUT",
            int(os.getenv("ETOS_WAIT_FOR_EXECUTION_SPACE_TIMEOUT", "10")),
        )
        self.etos.config.set(
            "WAIT_FOR_LOG_AREA_TIMEOUT",
            int(os.getenv("ETOS_WAIT_FOR_LOG_AREA_TIMEOUT", "10")),
        )

        self.logger.info("Connect to RabbitMQ")
        self.etos.config.rabbitmq_publisher_from_environment()
        self.etos.start_publisher()
        if not self.etos.debug.disable_sending_events:
            self.etos.publisher.wait_start()
        self.logger.info("Connected")

    def cleanup(self) -> None:
        """Clean up by checkin in all checked out providers."""
        self.logger.info("Cleanup by checking in all checked out providers.")
        for provider in self.etos.config.get("PROVIDERS"):
            try:
                provider.checkin_all()
            except:  # noqa pylint:disable=bare-except
                pass

    @staticmethod
    def get_constraint(recipe: dict, key: str) -> Any:
        """Get a constraint key from an ETOS recipe.

        :param recipe: Recipe to get key from.
        :param key: Key to get value from, from the constraints.
        :return: Constraint value.
        """
        for constraint in recipe.get("constraints", []):
            if constraint.get("key") == key:
                return constraint.get("value")
        return None

    def set_total_test_count_and_test_runners(self, test_runners: dict) -> None:
        """Set total test count and test runners to be used by the splitter algorithm.

        :param test_runners: Dictionary with test_runners as keys.
        """
        total_test_count = 0
        for _, data in test_runners.items():
            total_test_count += len(data["unsplit_recipes"])
        self.etos.config.set("TOTAL_TEST_COUNT", total_test_count)
        self.etos.config.set("NUMBER_OF_TESTRUNNERS", len(test_runners.keys()))

    def send_environment_events(self, url: str, sub_suite: dict) -> None:
        """Send environment defined events for the created sub suites.

        :param url: URL to where the sub suite is uploaded.
        :param sub_suite: Test suite to send environment defined for.
        """
        # In a valid sub suite all of these keys must exist
        # making this a safe assumption
        event_id = sub_suite["executor"]["instructions"]["environment"]["ENVIRONMENT_ID"]
        event = EiffelEnvironmentDefinedEvent()
        event.meta.event_id = event_id
        self.etos.events.send(
            event,
            {"CONTEXT": self.etos.config.get("environment_provider_context")},
            {"name": sub_suite.get("name"), "uri": url},
        )

        suite = self.registry.testrun.join(f"suite/{sub_suite['test_suite_started_id']}")
        suite.join(f"/subsuite/{event_id}/suite").write(json.dumps(sub_suite))

    def upload_sub_suite(self, sub_suite: dict) -> tuple[str, dict]:
        """Upload sub suite to log area.

        :param sub_suite: Sub suite to upload to log area.
        :return: URI to file uploaded.
        """
        sub_suite = sub_suite.copy()
        sub_suite["recipes"] = self.recipes_from_tests(sub_suite["recipes"])
        try:
            with NamedTemporaryFile(mode="w", delete=False) as sub_suite_file:
                json.dump(sub_suite, sub_suite_file)
            log_area = LogArea(self.etos, sub_suite)
            return (
                log_area.upload(
                    sub_suite_file.name,
                    f"{sub_suite['name']}.json",
                    sub_suite["test_suite_started_id"],
                    sub_suite["sub_suite_id"],
                ),
                sub_suite,
            )
        finally:
            os.remove(sub_suite_file.name)

    def recipes_from_tests(self, tests: list[Test]) -> list[dict]:
        """Load Eiffel TERCC recipes from test.

        :param tests: The tests defined in a Test model.
        :return: A list of Eiffel TERCC recipes.
        """
        recipes: list[dict] = []
        for test in tests:
            recipes.append(
                {
                    "id": test.id,
                    "testCase": test.testCase.model_dump(),
                    "constraints": [
                        {
                            "key": "ENVIRONMENT",
                            "value": test.execution.environment,
                        },
                        {
                            "key": "COMMAND",
                            "value": test.execution.command,
                        },
                        {
                            "key": "EXECUTE",
                            "value": test.execution.execute,
                        },
                        {
                            "key": "CHECKOUT",
                            "value": test.execution.checkout,
                        },
                        {
                            "key": "PARAMETERS",
                            "value": test.execution.parameters,
                        },
                        {
                            "key": "TEST_RUNNER",
                            "value": test.execution.testRunner,
                        },
                    ],
                }
            )
        return recipes

    def create_environment_resource(
        self, request: EnvironmentRequestSchema, sub_suite: dict
    ) -> tuple[str, dict]:
        """Create an environment resource in Kubernetes.

        :param sub_suite: Sub suite to add to Environment resource.
        :return: URI to ETOS API for ETR to fetch resource.
        """
        # In a valid sub suite all of these keys must exist
        # making this a safe assumption
        environment_id = sub_suite["executor"]["instructions"]["environment"]["ENVIRONMENT_ID"]
        labels = request.metadata.labels or {}
        labels["etos.eiffel-community.github.io/suite-id"] = sub_suite["test_suite_started_id"]
        labels["etos.eiffel-community.github.io/sub-suite-id"] = sub_suite["sub_suite_id"]
        owners = request.metadata.ownerReferences
        owners.append(
            OwnerReference(
                kind="EnvironmentRequest",
                name=request.metadata.name,
                uid=request.metadata.uid,
                apiVersion="etos.eiffel-community.github.io/v1alpha1",
                controller=False,
                blockOwnerDeletion=True,
            )
        )
        environment = EnvironmentSchema(
            metadata=Metadata(
                name=environment_id,
                namespace=request.metadata.namespace,
                labels=labels,
                ownerReferences=owners,
            ),
            spec=EnvironmentSpec(**sub_suite.copy()),
        )
        environment_client = Environment(self.kubernetes)
        if not environment_client.create(environment):
            raise RuntimeError("Failed to create the environment for an etos testrun")
        return (
            f"{os.getenv('ETOS_API')}/v1alpha/testrun/{environment_id}",
            environment.spec.model_dump(),
        )

    def checkout_an_execution_space(self) -> ExecutionSpace:
        """Check out a single execution space.

        :return: An execution space
        """
        return self.execution_space_provider.wait_for_and_checkout_execution_spaces(1, 1)[0]

    def checkout_a_log_area(self) -> LogArea:
        """Check out a single log area.

        :return: A log area
        """
        return self.log_area_provider.wait_for_and_checkout_log_areas(1, 1)[0]

    def checkout_timeout(self) -> int:
        """Get timeout for checkout."""
        iut_timeout = self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
        exec_timeout = self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")
        log_timeout = self.etos.config.get("WAIT_FOR_LOG_AREA_TIMEOUT")
        timeout = iut_timeout + exec_timeout + log_timeout + 10
        minutes, seconds = divmod(timeout, 60)
        hours, minutes = divmod(minutes, 60)

        endtime = time.time() + timeout
        strtime = datetime.fromtimestamp(endtime).strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(
            "Timeout for checkout at: %s (%sh %sm %ss)",
            strtime,
            hours,
            minutes,
            seconds,
            extra={"user_log": True},
        )
        return endtime

    def checkout(self, request: EnvironmentRequestSchema) -> None:
        """Checkout an environment for a test suite.

        A request can have multiple environments due to IUT availability or the amount of
        unique test runners in the request.
        """
        # pylint:disable=too-many-statements
        self.logger.info("Checkout environment for %r", request.spec.name, extra={"user_log": True})
        self.new_dataset(request)
        splitter = Splitter(self.etos, request.spec.splitter)

        # TODO: This is a hack to make the controller environment work without too many changes
        # to the original code, since we want to run them at the same time.
        test_runners = {}
        for test in request.spec.splitter.tests:
            test_runners.setdefault(
                test.execution.testRunner,
                {"docker": test.execution.testRunner, "priority": 1, "unsplit_recipes": []},
            )
            test_runners[test.execution.testRunner]["unsplit_recipes"].append(test)

        self.set_total_test_count_and_test_runners(test_runners)

        self.logger.info(
            "Total test count: %d",
            self.etos.config.get("TOTAL_TEST_COUNT"),
            extra={"user_log": True},
        )

        self.logger.info(
            "Total testrunners: %r",
            self.etos.config.get("NUMBER_OF_TESTRUNNERS"),
            extra={"user_log": True},
        )

        self.logger.info(
            "Checking out IUTs from %r", self.iut_provider.id, extra={"user_log": True}
        )
        self.logger.info(
            "Checking out execution spaces from %r",
            self.execution_space_provider.id,
            extra={"user_log": True},
        )
        self.logger.info(
            "Checking out log areas from %r",
            self.log_area_provider.id,
            extra={"user_log": True},
        )

        test_suite = TestSuite(
            request.spec.name or "NoSuite",
            request.spec.id,
            self.environment_provider_config,
        )
        finished = []
        timeout = self.checkout_timeout()
        while time.time() < timeout:
            self.set_total_test_count_and_test_runners(test_runners)

            with self.tracer.start_as_current_span("request_iuts", kind=SpanKind.CLIENT) as span:
                # Check out and assign IUTs to test runners.
                iuts = self.iut_provider.wait_for_and_checkout_iuts(
                    minimum_amount=request.spec.minimumAmount,
                    # maximum_amount=request.spec.maximumAmount,
                    # TODO: Total test count changes, must check
                    maximum_amount=self.dataset.get(
                        "maximum_amount",
                        os.getenv(
                            "ETOS_MAX_PARALLEL_IUTS",
                            self.etos.config.get("TOTAL_TEST_COUNT"),
                        ),
                    ),
                )
                splitter.assign_iuts(test_runners, iuts)
                span.set_attribute(SemConvAttributes.IUT_DESCRIPTION, str(iuts))

            for test_runner in test_runners:  # pylint:disable=consider-using-dict-items
                self.dataset.add("test_runner", test_runner)

                # No IUTs assigned to test runner
                if not test_runners[test_runner].get("iuts"):
                    continue

                # Check out an executor and log area for each IUT.
                for iut, suite in test_runners[test_runner].get("iuts", {}).items():
                    self.dataset.add("iut", iut)
                    self.dataset.add("suite", suite)
                    suite["sub_suite_id"] = str(uuid.uuid4())

                    with self.tracer.start_as_current_span(
                        "request_execution_space", kind=SpanKind.CLIENT
                    ) as span:
                        span.set_attribute(SemConvAttributes.TEST_RUNNER_ID, test_runner)
                        suite["executor"] = self.checkout_an_execution_space()
                        self.dataset.add("executor", suite["executor"])

                    with self.tracer.start_as_current_span(
                        "request_log_area", kind=SpanKind.CLIENT
                    ) as span:
                        span.set_attribute(SemConvAttributes.TEST_RUNNER_ID, test_runner)
                        suite["log_area"] = self.checkout_a_log_area()

                # Split the tests into sub suites
                splitter.split(test_runners[test_runner])

                # Add sub suites to test suite structure and send environment events to the ESR.
                for iut, suite in test_runners[test_runner].get("iuts", {}).items():
                    sub_suite = test_suite.add(
                        request, test_runner, iut, suite, test_runners[test_runner]["priority"]
                    )
                    if self.environment_provider_config.etos_controller:
                        self.send_environment_events(
                            *self.create_environment_resource(request, sub_suite)
                        )
                    else:
                        self.send_environment_events(*self.upload_sub_suite(sub_suite))

                    self.logger.info(
                        "Environment for %r checked out and is ready for use",
                        sub_suite["name"],
                        extra={"user_log": True},
                    )
                finished.append(test_runner)

            # Remove finished sub suites.
            for test_runner in finished:
                try:
                    test_runners.pop(test_runner)
                except KeyError:
                    pass

            # Exit only if there are no sub suites left to assign
            if not test_runners:
                break
            time.sleep(5)
        else:
            raise TimeoutError("Could not check out an environment before timeout.")

        self.logger.info(
            "All environments for test suite %r have been checked out",
            request.spec.name,
            extra={"user_log": True},
        )

    def wait_for_main_suite(self, test_suite_id: str) -> dict:
        """Wait for main test suite started to be available in ER.

        :param test_suite_id: The ID of the test suite started.
        :return: a test suite started event.
        """
        main_suite = request_main_suite(self.etos, test_suite_id)
        timeout = time.time() + 30
        while main_suite is None and time.time() < timeout:
            main_suite = request_main_suite(self.etos, test_suite_id)
            time.sleep(5)
        return main_suite

    def _run(self, request: EnvironmentRequestSchema) -> None:
        """Run the environment provider task."""
        error = None

        triggered = None
        try:
            main_suite_id = None
            # When running as ETOS controller, we expect the suite runner to receive the
            # Environment resource instead of relying on Eiffel.
            if not self.environment_provider_config.etos_controller:
                main_suite = self.wait_for_main_suite(request.spec.id)
                if main_suite is None:
                    raise TimeoutError("Timed out while waiting for test suite started from ESR")
                main_suite_id = main_suite["meta"]["id"]
            else:
                # If running as ETOS controller, we will need to get the request ID for
                # the suite runner to use when sending main suites. The main suite ID
                # is sent to the Test Runner, so that the test runner can send its sub
                # suite started events in a way that the suite runner can pick them up.
                # TODO: This main suite id should be removed as in the future we cannot
                # guarantee that it is allowed as a CONTEXT link or even an eiffel event
                # id. It is currently required for ESR.
                main_suite_id = request.spec.id

            links = {"CONTEXT": main_suite_id} if main_suite_id is not None else None
            triggered = self.etos.events.send_activity_triggered(
                f"Checkout environment for {request.spec.name}",
                links,
                executionType="AUTOMATED",
            )

            self.etos.config.set("environment_provider_context", triggered)
            self.etos.events.send_activity_started(triggered)
            self.checkout(request)
        except Exception as exception:  # pylint:disable=broad-except
            error = exception
            raise
        finally:
            if error is None:
                outcome = {"conclusion": "SUCCESSFUL"}
            else:
                outcome = {"conclusion": "UNSUCCESSFUL", "description": str(error)}
            if triggered is not None:
                self.etos.events.send_activity_finished(triggered, outcome)

    def _configure_provider(self, provider_db: ETCDPath, provider_spec: dict, name: str):
        """Configure a single provider for a testrun."""
        self.logger.info("Saving provider with name %r in %r", name, provider_db)
        provider_model = ProviderSchema.model_validate(provider_spec)
        if provider_model.spec.jsontas:
            ruleset = json.dumps({name: provider_model.to_jsontas()})
        else:
            ruleset = json.dumps({name: provider_model.to_external()})
        provider_db.write(ruleset)

    def _configure_iut(self, provider_spec: dict):
        """Configure iut provider for a testrun."""
        db = self.registry.testrun.join("provider/iut")  # type: ignore
        self._configure_provider(db, provider_spec, "iut")

    def _configure_log_area(self, provider_spec: dict):
        """Configure log area provider for a testrun."""
        db = self.registry.testrun.join("provider/log-area")  # type: ignore
        self._configure_provider(db, provider_spec, "log")

    def _configure_execution_space(self, provider_spec: dict):
        """Configure execution space provider for a testrun."""
        db = self.registry.testrun.join("provider/execution-space")  # type: ignore
        self._configure_provider(db, provider_spec, "execution_space")

    def _configure_dataset(self, datasets: list[dict]):
        """Configure dataset for a testrun."""
        db = self.registry.testrun.join("provider/dataset")  # type: ignore
        db.write(json.dumps(datasets))

    def configure_environment_provider(self, request: EnvironmentRequestSchema):
        """Configure the environment provider if run as a part of the ETOS kubernetes controller."""
        self.logger.info("Running in an ETOS cluster - Configuring testrun")
        provider_client = Provider(self.kubernetes)

        iut = provider_client.get(request.spec.providers.iut.id).to_dict()  # type: ignore
        self._configure_iut(iut)  # type: ignore
        log_area = provider_client.get(request.spec.providers.logArea.id).to_dict()  # type: ignore
        self._configure_log_area(log_area)  # type: ignore
        provider_id = request.spec.providers.executionSpace.id  # type: ignore
        execution_space = provider_client.get(provider_id).to_dict()  # type: ignore
        self._configure_execution_space(execution_space)  # type: ignore

    def get_environment(self) -> dict:
        """Run the environment provider.

        See: `_run`

        :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
        :rtype: dict
        """
        try:
            for request in self.environment_provider_config.requests:
                if self.environment_provider_config.etos_controller:
                    self.configure_environment_provider(request)
                self.configure(request)
                self._run(request)
            return {"error": None}
        except Exception as exception:  # pylint:disable=broad-except
            self.cleanup()
            traceback.print_exc()
            self.logger.error(
                "Failed creating environment for test. %r", exception, extra={"user_log": True}
            )
            raise
        finally:
            if self.etos.publisher is not None and not self.etos.debug.disable_sending_events:
                self.etos.publisher.wait_for_unpublished_events()
                self.etos.publisher.stop()

    def run(self) -> dict:
        """Run the environment provider task.

        See: `_run`

        This method catches all exceptions and returns a result dict instead.

        :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
        :rtype: dict
        """
        try:
            return self.get_environment()
        except Exception as exception:  # pylint:disable=broad-except
            return {"error": str(exception), "details": traceback.format_exc()}


def get_environment():
    """Entrypoint for getting an environment."""
    logformat = "[%(asctime)s] %(levelname)s:%(message)s"
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.getLogger("gql").setLevel(logging.WARNING)
    try:
        status = EnvironmentProvider().get_environment()
        if status.get("error") is not None:
            raise EnvironmentProviderError(status.get("error"))
        result = {
            "conclusion": "Successful",
            "description": "Successfully provisioned an environment",
        }
        with open("/dev/termination-log", "w", encoding="utf-8") as termination_log:
            json.dump(result, termination_log)
    except:
        try:
            result = {"conclusion": "Failed", "description": traceback.format_exc()}
            with open("/dev/termination-log", "w", encoding="utf-8") as termination_log:
                json.dump(result, termination_log)
        except PermissionError:
            pass
        raise


if __name__ == "__main__":
    get_environment()
