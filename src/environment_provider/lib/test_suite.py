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
"""Test suite module."""
from etos_lib.kubernetes.schemas.environment_request import EnvironmentRequest
from iut_provider.iut import Iut

from .config import Config

# pylint:disable=line-too-long
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments


class TestSuite:  # pylint:disable=too-few-public-methods
    """Test suite representation.

    The resulting test suite might look something like this::

        # noqa
        {
            "suite_name": "EnvironmentProvider",
            "suites": [
                {
                    "artifact": "0fa5e21d-9386-4b19-b7f6-7c855d273ba0",
                    "context": "c677c863-1802-4817-95f3-9cc272b03013",
                    "executor": {
                        "provider_id": "myexecutorprovider",
                        "identifier": "cd89c5aa-a2aa-495f-99fb-ec57e057ac9d",
                        "request": {
                            "data": {
                                "tests": "http://environment-provider/sub_suite?id=43b94f6f-4af7-4078-a1ca-70fb80dffd3f
                            },
                            "headers": {
                                "Accept": "application/json"
                            },
                            "method": "POST",
                            "url": "https://build_url"
                        }
                    },
                    "iut": {
                        "provider_id": "myiutprovider",
                        "commands": [
                            {
                                "command": [
                                    "pip install something",
                                    "run_something"
                                ],
                                "threaded": true
                            }
                        ],
                        "environment": {
                            "MYENV": "a value"
                        },
                        "identity": "pkg:pypi/etos/environment_provider@1.0.0",
                        "name": "environment_provider",
                        "namespace": "etos",
                        "qualifiers": {},
                        "subpath": null,
                        "type": "pypi",
                        "version": "1.0.0"
                    },
                    "log_area": {
                        "provider_id": "mylogareaprovider",
                        "livelogs": "https://logarea.com/etos/log/c677c863-1802-4817-95f3-9cc272b03013",
                        "logs": {},
                        "upload": {
                            "method": "PUT",
                            "url": "https://logarea.com/etos/log/c677c863-1802-4817-95f3-9cc272b03013/{folder}/{name}"
                        }
                    },
                    "name": "EnvironmentProvider_SubSuite_0",
                    "priority": 1,
                    "recipes": [
                        {
                            "constraints": [
                                {
                                    "key": "ENVIRONMENT",
                                    "value": {}
                                },
                                {
                                    "key": "PARAMETERS",
                                    "value": {}
                                },
                                {
                                    "key": "COMMAND",
                                    "value": "python -m pytest"
                                },
                                {
                                    "key": "TEST_RUNNER",
                                    "value": "pytest_testrunner:latest"
                                },
                                {
                                    "key": "EXECUTE",
                                    "value": [
                                        "pip install pytest pytest-cov",
                                        "pip install -r requirements.txt"
                                    ]
                                },
                                {
                                    "key": "CHECKOUT",
                                    "value": [
                                        "git clone environment_provider .",
                                    ]
                                }
                            ],
                            "id": "5aeb7054-15b2-4535-ac1e-ec4f15c8c2c8",
                            "testCase": {
                                "id": "EnvironmentProviderSuite",
                                "tracker": "http://environment-provider/",
                                "url": "http://environment-provider/"
                            }
                        }
                    ],
                    "test_runner": "pytest_testrunner:latest"

                }
            ]
        }
    """

    def __init__(
        self, test_suite_name: str, suite_runner_id: str, environment_provider_config: Config
    ) -> None:
        """Initialize test suite representation.

        :param test_suite_name: Name of the test suite.
        :param suite_runner_id: The test suite started that this suite correlates to.
        :param environment_provider_config: Environment provider config.
        """
        self._suite = {"suite_name": test_suite_name, "sub_suites": []}
        self.test_suite_name = test_suite_name
        self.suite_runner_id = suite_runner_id
        self.environment_provider_config = environment_provider_config

    def add(
        self, request: EnvironmentRequest, test_runner: str, iut: Iut, suite: dict, priority: int
    ) -> dict:
        """Add a new sub suite to suite.

        :param test_runner: The test runner to use for sub suite.
        :param iut: IUT to execute the sub suite.
        :param suite: The sub suite.
        :param priority: Execution priority of the sub suite.
        :return: The sub suite definition to be sent to the ESR.
        """
        sub_suite = {
            "name": f"{self.test_suite_name}_SubSuite_{len(self._suite['sub_suites'])}",
            "suite_id": request.spec.identifier,
            "sub_suite_id": suite.get("sub_suite_id"),
            "test_suite_started_id": self.suite_runner_id,
            "priority": priority,
            "recipes": suite.get("recipes", []),
            "test_runner": test_runner,
            "iut": iut.as_dict,
            "artifact": request.spec.artifact,
            "context": self.environment_provider_config.context,
            "executor": suite.get("executor").as_dict,
            "log_area": suite.get("log_area").as_dict,
        }
        self._suite["sub_suites"].append(sub_suite)
        return sub_suite
