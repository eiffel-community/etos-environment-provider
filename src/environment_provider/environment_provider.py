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
"""ETOS Environment Provider celery task module."""
import json
import logging
import os
import time
import traceback
import uuid
from copy import deepcopy
from datetime import datetime
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any, Union

from etos_lib.etos import ETOS
from etos_lib.lib.events import EiffelEnvironmentDefinedEvent
from etos_lib.logging.logger import FORMAT_CONFIG
from etos_lib.opentelemetry.semconv import Attributes as SemConvAttributes
from jsontas.jsontas import JsonTas
import opentelemetry
from opentelemetry.trace import SpanKind

from execution_space_provider.execution_space import ExecutionSpace
from log_area_provider.log_area import LogArea

from .lib.celery import APP
from .lib.config import Config
from .lib.database import ETCDPath
from .lib.encrypt import Encrypt
from .lib.graphql import request_main_suite
from .lib.join import Join
from .lib.json_dumps import JsonDumps
from .lib.log_area import LogArea
from .lib.registry import ProviderRegistry
from .lib.test_suite import TestSuite
from .lib.uuid_generate import UuidGenerate
from .splitter.split import Splitter

logging.getLogger("pika").setLevel(logging.WARNING)


class NoEventDataFound(Exception):
    """Could not fetch events from event storage."""


class EnvironmentProviderNotConfigured(Exception):
    """Environment provider was not configured prior to request."""


class EnvironmentProvider:  # pylint:disable=too-many-instance-attributes
    """Environment provider celery Task."""

    logger = logging.getLogger("EnvironmentProvider")
    environment_provider_config = None
    iut_provider = None
    log_area_provider = None
    execution_space_provider = None
    task_track_started = True  # Make celery task report 'STARTED' state
    lock = Lock()

    def __init__(self, suite_id: str, suite_runner_ids: list[str], copy: bool = True) -> None:
        """Initialize ETOS, dataset, provider registry and splitter.

        :param suite_id: Suite ID to get an environment for
        :param suite_runner_ids: IDs from the suite runner to correlate sub suites.
        :param copy: Whether or not to copy the etos config. Set to False if not running celery.
        """
        FORMAT_CONFIG.identifier = suite_id
        self.logger.info("Initializing EnvironmentProvider task.")
        self.tracer = opentelemetry.trace.get_tracer(__name__)

        self.etos = ETOS("ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider")

        self.suite_id = suite_id
        self.suite_runner_ids = suite_runner_ids

        with self.lock:
            # Since celery workers can share memory between them we need to make the configuration
            # of ETOS library unique as it uses the memory sharing feature with the internal
            # configuration dictionary.
            # The impact of not doing this is that the environment provider would re-use
            # another workers configuration instead of using its own.
            if copy:
                self.etos.config.config = deepcopy(self.etos.config.config)
            self.reset()
        self.splitter = Splitter(self.etos, {})

    def reset(self) -> None:
        """Create a new dataset and provider registry."""
        self.jsontas = JsonTas()
        self.dataset = self.jsontas.dataset
        self.dataset.add("json_dumps", JsonDumps)
        self.dataset.add("uuid_generate", UuidGenerate)
        self.dataset.add("join", Join)
        self.dataset.add("encrypt", Encrypt)
        self.registry = ProviderRegistry(self.etos, self.jsontas, self.suite_id)

    def new_dataset(self, dataset: dict) -> None:
        """Load a new dataset.

        :param dataset: Dataset to use for this configuration.
        """
        self.reset()
        self.dataset.add("environment", os.environ)
        self.dataset.add("config", self.etos.config)
        self.dataset.add("identity", self.environment_provider_config.identity)

        self.dataset.add("artifact_id", self.environment_provider_config.artifact_id)
        self.dataset.add("context", self.environment_provider_config.context)
        self.dataset.add("uuid", str(uuid.uuid4()))

        self.dataset.add("artifact_created", self.environment_provider_config.artifact_created)
        self.dataset.add("artifact_published", self.environment_provider_config.artifact_published)
        self.dataset.add("tercc", self.environment_provider_config.tercc)

        self.dataset.add("dataset", dataset)
        self.dataset.merge(dataset)

        self.iut_provider = self.registry.iut_provider()
        self.log_area_provider = self.registry.log_area_provider()
        self.execution_space_provider = self.registry.execution_space_provider()

    def configure(self, suite_id: str) -> None:
        """Configure environment provider.

        :param suite_id: Suite ID for this task.
        """
        self.logger.info("Configure environment provider.")
        if not self.registry.wait_for_configuration():
            # TODO: Add link ref to docs that describe how the config is done.
            raise EnvironmentProviderNotConfigured(
                "Please do a proper configuration of "
                "EnvironmentProvider before requesting an "
                "environment."
            )
        self.logger.info("Registry is configured.")
        self.etos.config.set("SUITE_ID", suite_id)

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

        self.environment_provider_config = Config(self.etos, suite_id)
        if not self.environment_provider_config.generated:
            missing = [
                name
                for name, value in [
                    ("tercc", self.environment_provider_config.tercc),
                    (
                        "artifact_created",
                        self.environment_provider_config.artifact_created,
                    ),
                    (
                        "activity_triggered",
                        self.environment_provider_config.activity_triggered,
                    ),
                ]
                if value is None
            ]
            raise NoEventDataFound(f"Missing: {', '.join(missing)}")

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

    def create_test_suite_dict(self) -> dict:
        """Create a test suite dictionary based on test runners.

        I.e. If there is only one test_runner the dictionary would be::

            {
                "test_suite_name": {
                    "MyTestrunner": {
                        "docker": "MyTestrunner",
                        "priority": 1,
                        "unsplit_recipes": [...]
                    }
                }
            }

        Or two::

            {
                "test_suite_name": {
                    "MyTestrunner": {
                        "docker": "MyTestrunner",
                        "priority": 1,
                        "unsplit_recipes": [...]
                    },
                    "MyOtherTestrunner": {
                        "docker": "MyOtherTestrunner",
                        "priority": 1,
                        "unsplit_recipes": [...]
                    }
                }
            }

        etc.

        :return: A test suite dictionary based on test runners.
        :rtype: dict
        """
        self.logger.info("Create new test suite dictionary.")
        test_suites = {}
        for test_suite in self.environment_provider_config.test_suite:
            test_runners = test_suites.setdefault(test_suite.get("name"), {})

            for recipe in test_suite.get("recipes", []):
                test_runner = self.get_constraint(recipe, "TEST_RUNNER")
                test_runners.setdefault(
                    test_runner,
                    {
                        "docker": test_runner,
                        "priority": test_suite.get("priority"),
                        "unsplit_recipes": [],
                    },
                )
                test_runners[test_runner]["unsplit_recipes"].append(recipe)
        return test_suites

    def set_total_test_count_and_test_runners(self, test_runners: dict) -> None:
        """Set total test count and test runners to be used by the splitter algorithm.

        :param test_runners: Dictionary with test_runners as keys.
        """
        total_test_count = 0
        for _, data in test_runners.items():
            total_test_count += len(data["unsplit_recipes"])
        self.etos.config.set("TOTAL_TEST_COUNT", total_test_count)
        self.etos.config.set("NUMBER_OF_TESTRUNNERS", len(test_runners.keys()))

    def verify_json(self, json_data: Union[str, dict]) -> None:
        """Verify that JSON data can be serialized properly.

        :param json_data: JSON data to test.
        """
        try:
            if isinstance(json_data, dict):
                json_data = json.dumps(json_data)
            json.loads(json_data)
        except (json.decoder.JSONDecodeError, TypeError):
            self.logger.error(json_data)
            raise

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

        # TODO: These shall be removed when API version v1 is used by the ESR and API.
        environment = ETCDPath("/environment")
        environment.join(f"{event_id}/testrun-id").write(self.suite_id)
        environment.join(f"{event_id}/suite-id").write(sub_suite["test_suite_started_id"])

        suite = self.registry.testrun.join(f"suite/{sub_suite['test_suite_started_id']}")
        suite.join(f"/subsuite/{event_id}/suite").write(json.dumps(sub_suite))

    def upload_sub_suite(self, sub_suite: dict) -> str:
        """Upload sub suite to log area.

        :param sub_suite: Sub suite to upload to log area.
        :return: URI to file uploaded.
        """
        try:
            with NamedTemporaryFile(mode="w", delete=False) as sub_suite_file:
                json.dump(sub_suite, sub_suite_file)
            log_area = LogArea(self.etos, sub_suite)
            return log_area.upload(
                sub_suite_file.name, f"{sub_suite['name']}.json", sub_suite["test_suite_started_id"]
            )
        finally:
            os.remove(sub_suite_file.name)

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
        timeout = (
            self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
            + self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")
            + self.etos.config.get("WAIT_FOR_LOG_AREA_TIMEOUT")
            + 10
        )
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

    def checkout(
        self, test_suite_name: str, test_runners: dict, dataset: dict, main_suite_id: str
    ) -> dict:
        """Checkout an environment for a test suite.

        :param test_suite_name: Name of the test suite.
        :param test_runners: The test runners and corresponding unassigned tests.
        :param dataset: The dataset for this particular checkout.
        :param main_suite_id: The ID of the main suite that initiated this checkout.
        :return: The test suite and environment json for this checkout.
        """
        self.logger.info("Checkout environment for %r", test_suite_name, extra={"user_log": True})
        self.new_dataset(dataset)

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
            test_suite_name,
            main_suite_id,
            self.environment_provider_config,
        )
        finished = []
        timeout = self.checkout_timeout()
        while time.time() < timeout:
            self.set_total_test_count_and_test_runners(test_runners)
            # Check out and assign IUTs to test runners.
            iuts = self.iut_provider.wait_for_and_checkout_iuts(
                minimum_amount=1,
                maximum_amount=self.dataset.get(
                    "maximum_amount",
                    os.getenv(
                        "ETOS_MAX_PARALLEL_IUTS",
                        self.etos.config.get("TOTAL_TEST_COUNT"),
                    ),
                ),
            )
            self.splitter.assign_iuts(test_runners, iuts)

            for test_runner in test_runners.keys():
                self.dataset.add("test_runner", test_runner)

                # No IUTs assigned to test runner
                if not test_runners[test_runner].get("iuts"):
                    continue

                # Check out an executor and log area for each IUT.
                for iut, suite in test_runners[test_runner].get("iuts", {}).items():
                    self.dataset.add("iut", iut)
                    self.dataset.add("suite", suite)

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
                self.splitter.split(test_runners[test_runner])

                # Add sub suites to test suite structure and send environment events to the ESR.
                for iut, suite in test_runners[test_runner].get("iuts", {}).items():
                    sub_suite = test_suite.add(
                        test_runner, iut, suite, test_runners[test_runner]["priority"]
                    )
                    self.send_environment_events(self.upload_sub_suite(sub_suite), sub_suite)

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

        test_suite_json = test_suite.to_json()
        # Test that the test suite JSON is serializable so that the
        # exception is caught here and not by the webserver.
        # This makes sure that we can cleanup if anything breaks.
        self.verify_json(test_suite_json)

        self.logger.info(
            "All environments for test suite %r have been checked out",
            test_suite_name,
            extra={"user_log": True},
        )
        return test_suite_json

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

    def _run(self) -> dict:
        """Run the environment provider task.

        :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
        """
        suites = []
        error = None

        test_suites = self.create_test_suite_dict()

        datasets = self.registry.dataset()
        if isinstance(datasets, list):
            assert len(datasets) == len(
                test_suites
            ), "If multiple datasets are provided it must correspond with number of test suites"
        else:
            datasets = [datasets] * len(test_suites)

        for test_suite_name, test_runners in test_suites.items():
            triggered = None
            try:
                main_suite = self.wait_for_main_suite(self.suite_runner_ids.pop(0))
                if main_suite is None:
                    raise TimeoutError("Timed out while waiting for test suite started from ESR")
                main_suite_id = main_suite["meta"]["id"]

                triggered = self.etos.events.send_activity_triggered(
                    f"Checkout environment for {test_suite_name}",
                    {"CONTEXT": main_suite_id},
                    executionType="AUTOMATED",
                )

                self.etos.config.set("environment_provider_context", triggered)
                self.etos.events.send_activity_started(triggered)

                suites.append(
                    self.checkout(test_suite_name, test_runners, datasets.pop(0), main_suite_id)
                )
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
        return {"suites": suites, "error": None}

    def run(self) -> dict:
        """Run the environment provider task.

        See: `_run`

        :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
        :rtype: dict
        """
        try:
            self.configure(self.suite_id)
            return self._run()
        except Exception as exception:  # pylint:disable=broad-except
            self.cleanup()
            traceback.print_exc()
            self.logger.error("Failed creating environment for test. %r", extra={"user_log": True})
            return {"error": str(exception), "details": traceback.format_exc()}
        finally:
            if self.etos.publisher is not None and not self.etos.debug.disable_sending_events:
                self.etos.publisher.wait_for_unpublished_events()
                self.etos.publisher.stop()


@APP.task(name="EnvironmentProvider")
def get_environment(suite_id: str, suite_runner_ids: list[str]) -> dict:
    """Get an environment for ETOS test executions.

    :param suite_id: Suite ID to get an environment for
    :param suite_runner_ids: Suite runner correlation IDs.
    :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
    """
    environment_provider = EnvironmentProvider(suite_id, suite_runner_ids)
    return environment_provider.run()
