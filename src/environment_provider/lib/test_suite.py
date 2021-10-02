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
"""Test suite module."""
import json
from etos_lib.lib.database import Database

# pylint:disable=line-too-long


class TestSuite:
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

    def __init__(self, test_suite_name, test_runners, environment_provider_config):
        """Initialize test suite representation.

        :param test_suite_name: Name of the test suite.
        :type test_suite_name: str
        :param test_runners: Dictionary of test runners and tests.
        :type test_runners: dict
        :param environment_provider_config: Environment provider config.
        :type environment_provider_config: :obj:`environment_provider.lib.config.Config`
        """
        self._suite = {}
        self.test_suite_name = test_suite_name
        self.test_runners = test_runners
        self.environment_provider_config = environment_provider_config
        self.database = Database()

    def add(self, name, value):
        """Add a new item to suite.

        :param name: Name of item to add.
        :type name: str
        :param value: Value of item.
        :type value: any
        """
        setattr(self, name, value)
        self._suite[name] = value

    def generate(self):
        """Generate an ETOS test suite definition."""
        counter = 0
        suites = []
        for test_runner, data in self.test_runners.items():
            for iut, suite in data.get("iuts", {}).items():
                sub_suite = {
                    "name": f"{self.test_suite_name}_SubSuite_{counter}",
                    "priority": data.get("priority"),
                    "recipes": suite.get("recipes", []),
                    "test_runner": test_runner,
                    "iut": iut.as_dict,
                    "artifact": self.environment_provider_config.artifact_id,
                    "context": self.environment_provider_config.context,
                    "executor": suite.get("executor").as_dict,
                    "log_area": suite.get("log_area").as_dict,
                }
                self.database.write(
                    sub_suite["executor"]["instructions"]["identifier"],
                    json.dumps(sub_suite),
                )
                suites.append(sub_suite)
                counter += 1
        self._suite = {"suite_name": self.test_suite_name, "suites": suites}

    def to_json(self):
        """Return test suite as a JSON dictionary."""
        return self._suite
