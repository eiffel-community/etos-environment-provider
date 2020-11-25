# Copyright 2020 Axis Communications AB.
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
import sys
import uuid
import logging
import traceback
import json
from copy import deepcopy
from etos_lib.etos import ETOS
from jsontas.jsontas import JsonTas
from environment_provider.splitter.split import Splitter
from .lib.celery import APP
from .lib.config import Config
from .lib.test_suite import TestSuite
from .lib.registry import ProviderRegistry
from .lib.json_dumps import JsonDumps
from .lib.uuid_generate import UuidGenerate
from .lib.join import Join

LOGFORMAT = "[%(asctime)s] %(levelname)s:%(name)-22s: %(message)s"
logging.basicConfig(
    level=logging.INFO, stream=sys.stdout, format=LOGFORMAT, datefmt="%Y-%m-%d %H:%M:%S"
)
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
    task_track_started = True

    def __init__(self):
        """Initialize ETOS, dataset, provider registry and splitter."""
        self.logger.info("Initializing EnvironmentProvider task.")
        self.etos = ETOS(
            "ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider"
        )
        # Since celery workers can share memory between them we need to make the configuration
        # of ETOS library unique as it uses the memory sharing feature with the internal
        # configuration dictionary.
        # The impact of not doing this is that the environment provider would re-use
        # another workers configuration instead of using its own.
        self.etos.config.config = deepcopy(
            self.etos.config.config
        )  # pylint:disable=protected-access
        self.jsontas = JsonTas()
        self.dataset = self.jsontas.dataset

        self.dataset.add("json_dumps", JsonDumps)
        self.dataset.add("uuid_generate", UuidGenerate)
        self.dataset.add("join", Join)
        self.registry = ProviderRegistry(self.etos, self.jsontas)
        self.splitter = Splitter(self.etos, {})

    def configure(self, suite_id):
        """Configure environment provider and start RabbitMQ publisher.

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
        self.iut_provider = self.registry.iut_provider(suite_id)
        self.log_area_provider = self.registry.log_area_provider(suite_id)
        self.execution_space_provider = self.registry.execution_space_provider(suite_id)

        self.etos.config.set("EVENT_DATA_TIMEOUT", 10)
        self.etos.config.set("WAIT_FOR_IUT_TIMEOUT", 10)
        self.etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 10)
        self.etos.config.set("WAIT_FOR_LOG_AREA_TIMEOUT", 10)

        self.etos.config.rabbitmq_publisher_from_environment()
        self.etos.start_publisher()
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
            raise NoEventDataFound("Missing: {}".format(", ".join(missing)))

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
        self.dataset.merge(self.registry.dataset(suite_id))

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

    def checkout_and_assign_iuts_to_test_runners(self, test_runners):
        """Checkout IUTs from the IUT provider and assign them to the test_runners dictionary.

        :param test_runners: Dictionary with test_runners as keys.
        :type test_runners: dict
        """
        iuts = self.iut_provider.wait_for_and_checkout_iuts(
            minimum_amount=self.etos.config.get("NUMBER_OF_TESTRUNNERS"),
            maximum_amount=self.etos.config.get("TOTAL_TEST_COUNT"),
        )
        self.etos.config.set("NUMBER_OF_IUTS", len(iuts))

        unused_iuts = self.splitter.assign_iuts(test_runners, self.dataset.get("iuts"))
        for iut in unused_iuts:
            self.iut_provider.checkin(iut)

    def checkout_log_area(self):
        """Checkout a log area.

        Called for each executor so only a single log area needs to be checked out.
        """
        return self.log_area_provider.wait_for_and_checkout_log_areas(
            minimum_amount=1, maximum_amount=1
        )

    def checkout_and_assign_executors_to_iuts(self, test_runner, iuts):
        """Checkout and assign executors to each available IUT.

        :param test_runner: Test runner which will be added to dataset in order for
                            JSONTas to get more information when running.
        :type test_runner: dict
        :param iuts: Dictionary of IUTs to assign executors to.
        :type iuts: dict
        """
        self.dataset.add("test_runner", test_runner)
        executors = (
            self.execution_space_provider.wait_for_and_checkout_execution_spaces(
                minimum_amount=len(iuts),
                maximum_amount=len(iuts),
            )
        )
        for iut, suite in iuts.items():
            try:
                suite["executor"] = executors.pop(0)
            except IndexError:
                break
            self.dataset.add("executor", suite["executor"])
            self.dataset.add("iut", iut)
            # This index will always exist or 'checkout' would raise an exception.
            suite["log_area"] = self.checkout_log_area()[0]

        # Checkin the unassigned executors.
        for executor in executors:
            self.execution_space_provider.checkin(executor)

    def checkin_iuts_without_executors(self, iuts):
        """Find all IUTs without an assigned executor and check them in.

        :param iuts: IUTs to check for executors.
        :type iuts: dict
        :return: IUTs that were removed.
        :rtype: list
        """
        remove = []
        for iut, suite in iuts.items():
            if suite.get("executor") is None:
                self.iut_provider.checkin(iut)
                remove.append(iut)
        return remove

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

    def run(self, suite_id):
        """Run the environment provider task.

        :param suite_id: Suite ID to get an environment for
        :type suite_id: str
        :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
        :rtype: dict
        """
        try:
            self.configure(suite_id)
            test_suites = self.create_test_suite_dict()
            for test_suite_name, test_runners in test_suites.items():
                self.set_total_test_count_and_test_runners(test_runners)
                self.logger.info(
                    "Total test count : %r", self.etos.config.get("TOTAL_TEST_COUNT")
                )
                self.logger.info(
                    "Total testrunners: %r",
                    self.etos.config.get("NUMBER_OF_TESTRUNNERS"),
                )

                self.checkout_and_assign_iuts_to_test_runners(test_runners)
                for test_runner, values in test_runners.items():
                    self.checkout_and_assign_executors_to_iuts(
                        test_runner, values["iuts"]
                    )
                    for iut in self.checkin_iuts_without_executors(values["iuts"]):
                        values["iuts"].remove(iut)

                for sub_suite in test_runners.values():
                    self.splitter.split(sub_suite)

                test_suite = TestSuite(
                    test_suite_name, test_runners, self.environment_provider_config
                )
                # This is where the resulting test suite is generated.
                # The resulting test suite will be a dictionary with test runners, IUTs
                # execution spaces and log areas with tests split up over as many as
                # possible. The resulting test suite definition is further explained in
                # :obj:`environment_provider.lib.test_suite.TestSuite`
                test_suite.generate()
                test_suite_json = test_suite.to_json()

                # Test that the test suite JSON is serializable so that the
                # exception is caught here and not by the webserver.
                # This makes sure that we can cleanup if anything breaks.
                self.verify_json(test_suite_json)

                # TODO: Handle multiple test suites.
                return test_suite_json
        except Exception as exception:  # pylint:disable=broad-except
            self.cleanup()
            traceback.print_exc()
            return {"error": str(exception), "details": traceback.format_exc()}
        finally:
            if self.etos.publisher is not None:
                self.etos.publisher.stop()


@APP.task(name="EnvironmentProvider")
def get_environment(suite_id):
    """Get an environment for ETOS test executions.

    :param suite_id: Suite ID to get an environment for
    :type suite_id: str
    :return: Test suite JSON with assigned IUTs, execution spaces and log areas.
    :rtype: dict
    """
    environment_provider = EnvironmentProvider()
    return environment_provider.run(suite_id)
