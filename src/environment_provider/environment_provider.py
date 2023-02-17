# Copyright 2020-2023 Axis Communications AB.
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
import os
import uuid
import logging
import traceback
import json
import time
from threading import Lock
from copy import deepcopy
from etos_lib.etos import ETOS
from etos_lib.lib.database import Database
from etos_lib.logging.logger import FORMAT_CONFIG
from jsontas.jsontas import JsonTas
from .splitter.split import Splitter
from .lib.celery import APP
from .lib.graphql import request_main_suite
from .lib.config import Config
from .lib.test_suite import TestSuite
from .lib.registry import ProviderRegistry
from .lib.json_dumps import JsonDumps
from .lib.uuid_generate import UuidGenerate
from .lib.join import Join

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

    def __init__(self, suite_id, suite_runner_ids, test_db=None):
        """Initialize ETOS, dataset, provider registry and splitter.

        :param suite_id: Suite ID to get an environment for
        :type suite_id: str
        :param suite_runner_ids: IDs from the suite runner to correlate sub suites.
        :type suite_runner_ids: list
        :param test_db: Override the database with a test database.
        :type test_db: obj
        """
        self.suite_id = suite_id
        self.test_db = test_db
        FORMAT_CONFIG.identifier = suite_id
        self.suite_runner_ids = suite_runner_ids
        self.logger.info("Initializing EnvironmentProvider task.")
        self.etos = ETOS(
            "ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider"
        )
        with self.lock:
            # Since celery workers can share memory between them we need to make the configuration
            # of ETOS library unique as it uses the memory sharing feature with the internal
            # configuration dictionary.
            # The impact of not doing this is that the environment provider would re-use
            # another workers configuration instead of using its own.
            self.etos.config.config = deepcopy(self.etos.config.config)
            self.reset()
        self.splitter = Splitter(self.etos, {})

    def reset(self):
        """Create a new dataset and provider registry."""
        self.jsontas = JsonTas()
        self.dataset = self.jsontas.dataset
        self.dataset.add("json_dumps", JsonDumps)
        self.dataset.add("uuid_generate", UuidGenerate)
        self.dataset.add("join", Join)
        self.database = self.test_db or Database()
        self.registry = ProviderRegistry(self.etos, self.jsontas, self.database)

    def new_dataset(self, dataset):
        """Load a new dataset.

        :param dataset: Dataset to use for this configuration.
        :type dataset: dict
        """
        self.reset()
        self.dataset.add("environment", os.environ)
        self.dataset.add("config", self.etos.config)
        self.dataset.add("identity", self.environment_provider_config.identity)
        self.dataset.add("artifact_id", self.environment_provider_config.artifact_id)
        self.dataset.add("context", self.environment_provider_config.context)
        self.dataset.add("custom_data", self.environment_provider_config.custom_data)
        self.dataset.add("uuid", str(uuid.uuid4()))
        self.dataset.add(
            "artifact_created", self.environment_provider_config.artifact_created
        )
        self.dataset.add(
            "artifact_published", self.environment_provider_config.artifact_published
        )
        self.dataset.add("tercc", self.environment_provider_config.tercc)

        self.dataset.add("dataset", dataset)
        self.dataset.merge(dataset)

        self.iut_provider = self.registry.iut_provider(self.suite_id)
        self.log_area_provider = self.registry.log_area_provider(self.suite_id)
        self.execution_space_provider = self.registry.execution_space_provider(
            self.suite_id
        )

    def configure(self, suite_id):
        """Configure environment provider.

        :param suite_id: Suite ID for this task.
        :type suite_id: str
        """
        self.logger.info("Configure environment provider.")
        if not self.registry.wait_for_configuration(suite_id):
            # TODO: Add link ref to docs that describe how the config is done.
            raise EnvironmentProviderNotConfigured(
                "Please do a proper configuration of "
                "EnvironmentProvider before requesting an "
                "environment."
            )
        self.logger.info("Registry is configured.")
        self.etos.config.set("SUITE_ID", suite_id)

        self.etos.config.set(
            "EVENT_DATA_TIMEOUT", int(os.getenv("ETOS_EVENT_DATA_TIMEOUT", "10"))
        )
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

    def cleanup(self):
        """Clean up by checkin in all checked out providers."""
        self.logger.info("Cleanup by checking in all checked out providers.")
        for provider in self.etos.config.get("PROVIDERS"):
            try:
                provider.checkin_all()
            except:  # noqa pylint:disable=bare-except
                pass

    @staticmethod
    def get_constraint(recipe, key):
        """Get a constraint key from an ETOS recipe.

        :param recipe: Recipe to get key from.
        :type recipe: dict
        :param key: Key to get value from, from the constraints.
        :type key: str
        :return: Constraint value.
        :rtype: any
        """
        for constraint in recipe.get("constraints", []):
            if constraint.get("key") == key:
                return constraint.get("value")
        return None

    def create_test_suite_dict(self):
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

    def set_total_test_count_and_test_runners(self, test_runners):
        """Set total test count and test runners to be used by the splitter algorithm.

        :param test_runners: Dictionary with test_runners as keys.
        :type test_runners: dict
        """
        total_test_count = 0
        for _, data in test_runners.items():
            total_test_count += len(data["unsplit_recipes"])
        self.etos.config.set("TOTAL_TEST_COUNT", total_test_count)
        self.etos.config.set("NUMBER_OF_TESTRUNNERS", len(test_runners.keys()))

    def verify_json(self, json_data):
        """Verify that JSON data can be serialized properly.

        :param json_data: JSON data to test.
        :type json_data: str or dict
        """
        try:
            if isinstance(json_data, dict):
                json_data = json.dumps(json_data)
            json.loads(json_data)
        except (json.decoder.JSONDecodeError, TypeError):
            self.logger.error(json_data)
            raise

    def send_environment_events(self, sub_suite):
        """Send environment defined events for the created sub suites.

        :param sub_suite: Test suite to send environment defined for.
        :type sub_suite: dict
        """
        base_url = os.getenv("ETOS_ENVIRONMENT_PROVIDER")

        # In a valid sub suite all of these keys must exist
        # making this a safe assumption
        identifier = sub_suite["executor"]["instructions"]["identifier"]
        event = self.etos.events.send_environment_defined(
            sub_suite.get("name"),
            uri=f"{base_url}/sub_suite?id={identifier}",
            links={"CONTEXT": self.etos.config.get("environment_provider_context")},
        )
        self.database.write(event.meta.event_id, identifier)
        self.database.writer.hset(
            f"SubSuite:{identifier}", "EventID", event.meta.event_id
        )
        self.database.writer.hset(
            f"SubSuite:{identifier}", "Suite", json.dumps(sub_suite)
        )

    def checkout_an_execution_space(self):
        """Check out a single execution space.

        :return: An execution space
        :rtype: obj:`execution_space_provider.execution_space`
        """
        return self.execution_space_provider.wait_for_and_checkout_execution_spaces(
            1, 1
        )[0]

    def checkout_a_log_area(self):
        """Check out a single log area.

        :return: A log area
        :rtype: obj:`log_area_provider.log_area`
        """
        return self.log_area_provider.wait_for_and_checkout_log_areas(1, 1)[0]

    def checkout(self, test_suite_name, test_runners, dataset, main_suite_id):
        """Checkout an environment for a test suite.

        :param test_suite_name: Name of the test suite.
        :type test_suite_name: str
        :param test_runners: The test runners and corresponding unassigned tests.
        :type test_runners: dict
        :param dataset: The dataset for this particular checkout.
        :type dataset: dict
        :param main_suite_id: The ID of the main suite that initiated this checkout.
        :type main_suite_id: str
        :return: The test suite and environment json for this checkout.
        :rtype: dict
        """
        self.new_dataset(dataset)

        self.set_total_test_count_and_test_runners(test_runners)
        self.logger.info(
            "Total test count : %r", self.etos.config.get("TOTAL_TEST_COUNT")
        )
        self.logger.info(
            "Total testrunners: %r",
            self.etos.config.get("NUMBER_OF_TESTRUNNERS"),
        )
        test_suite = TestSuite(
            test_suite_name,
            main_suite_id,
            self.environment_provider_config,
            self.database,
        )

        timeout = time.time() + (
            self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
            + self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")
            + self.etos.config.get("WAIT_FOR_LOG_AREA_TIMEOUT")
            + 10
        )
        finished = []
        while time.time() < timeout:
            self.set_total_test_count_and_test_runners(test_runners)
            # Check out and assign IUTs to test runners.
            iuts = self.iut_provider.wait_for_and_checkout_iuts(
                minimum_amount=1,
                maximum_amount=self.etos.config.get("TOTAL_TEST_COUNT"),
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
                    suite["executor"] = self.checkout_an_execution_space()
                    self.dataset.add("executor", suite["executor"])
                    suite["log_area"] = self.checkout_a_log_area()

                # Split the tests into sub suites
                self.splitter.split(test_runners[test_runner])

                # Add sub suites to test suite structure and send environment events to the ESR.
                for iut, suite in test_runners[test_runner].get("iuts", {}).items():
                    sub_suite = test_suite.add(
                        test_runner, iut, suite, test_runners[test_runner]["priority"]
                    )
                    self.send_environment_events(sub_suite)
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

        return test_suite_json

    def wait_for_main_suite(self, test_suite_id):
        """Wait for main test suite started to be available in ER.

        :param test_suite_id: The ID of the test suite started.
        :type test_suite_id: str
        :return: a test suite started event.
        :rtype: dict
        """
        main_suite = request_main_suite(self.etos, test_suite_id)
        timeout = time.time() + 30
        while main_suite is None and time.time() < timeout:
            main_suite = request_main_suite(self.etos, test_suite_id)
            time.sleep(5)
        return main_suite

    def _run(self):
        """Run the environment provider task.

        :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
        :rtype: dict
        """
        suites = []
        error = None

        test_suites = self.create_test_suite_dict()

        datasets = self.registry.dataset(self.suite_id)
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
                    raise TimeoutError(
                        "Timed out while waiting for test suite started from ESR"
                    )
                main_suite_id = main_suite["meta"]["id"]

                triggered = self.etos.events.send_activity_triggered(
                    f"Checkout environment for {test_suite_name}",
                    {"CONTEXT": main_suite_id},
                    executionType="AUTOMATED",
                )
                self.etos.config.set("environment_provider_context", triggered)
                self.etos.events.send_activity_started(triggered)
                dataset = datasets.pop(0)
                test_suite_json = self.checkout(
                    test_suite_name, test_runners, dataset, main_suite_id
                )
                suites.append(test_suite_json)
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

    def run(self):
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
            return {"error": str(exception), "details": traceback.format_exc()}
        finally:
            if (
                self.etos.publisher is not None
                and not self.etos.debug.disable_sending_events
            ):
                self.etos.publisher.wait_for_unpublished_events()
                self.etos.publisher.stop()


@APP.task(name="EnvironmentProvider")
def get_environment(suite_id, suite_runner_ids, test_db=None):
    """Get an environment for ETOS test executions.

    :param suite_id: Suite ID to get an environment for
    :type suite_id: str
    :param suite_runner_ids: Suite runner correlation IDs.
    :type suite_runner_ids: list
    :param test_db: Override the database with a test database.
    :type test_db: obj
    :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
    :rtype: dict
    """
    environment_provider = EnvironmentProvider(suite_id, suite_runner_ids, test_db)
    return environment_provider.run()
