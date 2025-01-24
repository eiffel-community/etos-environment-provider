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
"""TERCCs to use for testing."""


TERCC_SUB_SUITES = {
    "data": {
        "selectionStrategy": {"id": "6e922b03-1323-42ca-9cf8-34427ea13f2b"},
        "batches": [
            {
                "name": "Suite",
                "priority": 1,
                "recipes": [
                    {
                        "id": "ce8a900d-7921-4c0f-aac4-cc08801e074f",
                        "testCase": {
                            "id": "test_regular_scenario",
                            "tracker": "",
                            "uri": "",
                        },
                        "constraints": [
                            {"key": "ENVIRONMENT", "value": {}},
                            {"key": "PARAMETERS", "value": {}},
                            {"key": "COMMAND", "value": "exit 0"},
                            {"key": "EXECUTE", "value": []},
                            {
                                "key": "CHECKOUT",
                                "value": ["git clone https://github.com/eiffel-community/etos.git"],
                            },
                            {
                                "key": "TEST_RUNNER",
                                "value": "ghcr.io/eiffel-community/etos-python-test-runner:3.9.0",
                            },
                        ],
                    },
                    {
                        "id": "4efdd599-d7a1-4d4b-ae8c-d781cd1fd658",
                        "testCase": {
                            "id": "test_regular_scenario",
                            "tracker": "",
                            "uri": "",
                        },
                        "constraints": [
                            {"key": "ENVIRONMENT", "value": {}},
                            {"key": "PARAMETERS", "value": {}},
                            {"key": "COMMAND", "value": "exit 0"},
                            {"key": "EXECUTE", "value": []},
                            {
                                "key": "CHECKOUT",
                                "value": ["git clone https://github.com/eiffel-community/etos.git"],
                            },
                            {
                                "key": "TEST_RUNNER",
                                "value": "ghcr.io/eiffel-community/etos-python-test-runner:3.7.0",
                            },
                        ],
                    },
                ],
            },
        ],
    },
    "meta": {
        "type": "EiffelTestExecutionRecipeCollectionCreatedEvent",
        "id": "af344dcc-8cb5-4d79-976b-939a1d90424b",
        "time": 1664260578384,
        "version": "4.1.1",
    },
    "links": [{"type": "CAUSE", "target": "b44e0d4a-bc88-4c2a-b808-d336448c959e"}],
}


TERCC = {
    "data": {
        "selectionStrategy": {"id": "6e922b03-1323-42ca-9cf8-34427ea13f2b"},
        "batches": [
            {
                "name": "Suite",
                "priority": 1,
                "recipes": [
                    {
                        "id": "ce8a900d-7921-4c0f-aac4-cc08801e074f",
                        "testCase": {
                            "id": "test_regular_scenario",
                            "tracker": "",
                            "uri": "",
                        },
                        "constraints": [
                            {"key": "ENVIRONMENT", "value": {}},
                            {"key": "PARAMETERS", "value": {}},
                            {"key": "COMMAND", "value": "exit 0"},
                            {"key": "EXECUTE", "value": []},
                            {
                                "key": "CHECKOUT",
                                "value": ["git clone https://github.com/eiffel-community/etos.git"],
                            },
                            {
                                "key": "TEST_RUNNER",
                                "value": "ghcr.io/eiffel-community/etos-python-test-runner:3.9.0",
                            },
                        ],
                    },
                ],
            },
        ],
    },
    "meta": {
        "type": "EiffelTestExecutionRecipeCollectionCreatedEvent",
        "id": "3f684de0-be14-491b-bfc1-f5e3b01c3352",
        "time": 1664260578384,
        "version": "4.1.1",
    },
    "links": [{"type": "CAUSE", "target": "588d3421-e769-4b6a-adf7-332b2d4c046b"}],
}


TERCC_PERMUTATION = {
    "data": {
        "selectionStrategy": {"id": "6e922b03-1323-42ca-9cf8-34427ea13f2b"},
        "batches": [
            {
                "name": "SuitePermutation1",
                "priority": 1,
                "recipes": [
                    {
                        "id": "ce8a900d-7921-4c0f-aac4-cc08801e074f",
                        "testCase": {
                            "id": "test_regular_scenario",
                            "tracker": "",
                            "uri": "",
                        },
                        "constraints": [
                            {"key": "ENVIRONMENT", "value": {}},
                            {"key": "PARAMETERS", "value": {}},
                            {"key": "COMMAND", "value": "exit 0"},
                            {"key": "EXECUTE", "value": []},
                            {
                                "key": "CHECKOUT",
                                "value": ["git clone https://github.com/eiffel-community/etos.git"],
                            },
                            {
                                "key": "TEST_RUNNER",
                                "value": "ghcr.io/eiffel-community/etos-python-test-runner:3.9.0",
                            },
                        ],
                    },
                ],
            },
            {
                "name": "SuitePermutation2",
                "priority": 1,
                "recipes": [
                    {
                        "id": "ce8a900d-7921-4c0f-aac4-cc08801e074f",
                        "testCase": {
                            "id": "test_regular_scenario",
                            "tracker": "",
                            "uri": "",
                        },
                        "constraints": [
                            {"key": "ENVIRONMENT", "value": {}},
                            {"key": "PARAMETERS", "value": {}},
                            {"key": "COMMAND", "value": "exit 0"},
                            {"key": "EXECUTE", "value": []},
                            {
                                "key": "CHECKOUT",
                                "value": ["git clone https://github.com/eiffel-community/etos.git"],
                            },
                            {
                                "key": "TEST_RUNNER",
                                "value": "ghcr.io/eiffel-community/etos-python-test-runner:3.9.0",
                            },
                        ],
                    },
                ],
            },
        ],
    },
    "meta": {
        "type": "EiffelTestExecutionRecipeCollectionCreatedEvent",
        "id": "3f684de0-be14-491b-bfc1-f5e3b01c3352",
        "time": 1664260578384,
        "version": "4.1.1",
    },
    "links": [{"type": "CAUSE", "target": "588d3421-e769-4b6a-adf7-332b2d4c046b"}],
}
