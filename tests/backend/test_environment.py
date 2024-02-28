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
"""Tests for the environment backend system."""
import json
import logging
import unittest
from typing import OrderedDict

from etos_lib import ETOS
from etos_lib.lib.config import Config
from jsontas.jsontas import JsonTas
from mock import patch

from environment_provider_api.backend.common import get_suite_id
from environment_provider_api.backend.environment import (
    check_environment_status,
    get_environment_id,
    get_release_id,
    release_full_environment,
    request_environment,
)
from tests.library.fake_celery import FakeCelery, Task
from tests.library.fake_database import FakeDatabase
from tests.library.fake_request import FakeRequest


class TestEnvironmentBackend(unittest.TestCase):
    """Test the environment backend."""

    logger = logging.getLogger(__name__)

    def tearDown(self):
        """Reset all globally stored data for the next test."""
        Config().reset()

    def test_get_from_request(self):
        """Test that it is possible to get all parameters from request.

        Approval criteria:
            - It shall be possible to get parameters from request.

        Data driven repetitions:
            - Repeat for the following parameters: ["id", "release", "suite_id"]

        Test steps:
            1. For each parameter:
                1.1: Call the function to get the parameter.
                1.2: Verify that the parameter is correct.
        """
        requests = (
            ("id", get_environment_id),
            ("release", get_release_id),
            ("suite_id", get_suite_id),
        )
        self.logger.info("STEP: For each parameter:")
        for parameter, func in requests:
            test_value = f"testing_{parameter}"
            request = FakeRequest()
            request.fake_params[parameter] = test_value
            self.logger.info("STEP: Call the function to get the parameter %r", parameter)
            response_value = func(request)
            self.logger.info("STEP: Verify that the parameter is correct.")
            self.assertEqual(response_value, test_value)

    def test_release_full_environment(self):
        """Test that it is possible to release an environment.

        Approval criteria:
            - It shall be possible to release an environment.

        Note:
            - This is not perfectly testable today due to how the providers are used
              when checking in provider items.

        Test steps:
            1. Attempt to release an environment.
            2. Verify that it was possible to release that environment.
        """
        database = FakeDatabase()
        Config().set("database", database)
        test_iut_provider = OrderedDict(
            {
                "iut": {
                    "id": "iut_provider_test",
                    "list": {"available": [], "possible": []},
                }
            }
        )
        test_execution_space_provider = OrderedDict(
            {
                "execution_space": {
                    "id": "execution_space_provider_test",
                    "list": {"available": [{"identifier": "123"}], "possible": []},
                }
            }
        )
        test_log_area_provider = OrderedDict(
            {
                "log": {
                    "id": "log_area_provider_test",
                    "list": {"available": [], "possible": []},
                }
            }
        )
        database.put(
            f"/environment/provider/iut/{test_iut_provider['iut']['id']}",
            json.dumps(test_iut_provider),
        )
        provider_id = test_execution_space_provider["execution_space"]["id"]
        database.put(
            f"/environment/provider/execution-space/{provider_id}",
            json.dumps(test_execution_space_provider),
        )
        database.put(
            f"/environment/provider/log-area/{test_log_area_provider['log']['id']}",
            json.dumps(test_log_area_provider),
        )
        iut = {"id": "test_iut", "provider_id": test_iut_provider["iut"]["id"]}
        executor = {
            "id": "test_executor",
            "provider_id": test_execution_space_provider["execution_space"]["id"],
        }
        log_area = {
            "id": "test_log_area",
            "provider_id": test_log_area_provider["log"]["id"],
        }
        test_suite_id = "ce63f53e-1797-42bb-ae72-861a0b6b7ef6"
        jsontas = JsonTas()
        etos = ETOS("", "", "")
        database.put(
            f"/testrun/{test_suite_id}/suite/fakeid/subsuite/fakeid/suite",
            json.dumps(
                {
                    "iut": iut,
                    "executor": executor,
                    "log_area": log_area,
                }
            ),
        )

        self.logger.info("STEP: Attempt to release an environment.")
        success, _ = release_full_environment(etos, jsontas, test_suite_id)

        self.logger.info("STEP: Verify that it was possible to release that environment.")
        self.assertTrue(success)
        self.assertListEqual(database.get_prefix("/testrun"), [])

    def test_release_full_environment_failure(self):
        """Test that a failure is returned when there is a problem with releasing.

        Approval criteria:
            - The environment provider shall return failure if one provider failed.

        Note:
            - This is not perfectly testable today due to how the providers are used
              when checking in provider items.

        Test steps:
            1. Release an environment where one provider will fail to check in.
            2. Verify that the release return failure.
        """
        database = FakeDatabase()
        Config().set("database", database)
        test_iut_provider = {
            "iut": {
                "id": "iut_provider_test",
                "list": {"available": [], "possible": []},
            }
        }
        test_execution_space_provider = {
            "execution_space": {
                "id": "execution_space_provider_test",
                "list": {"available": [{"identifier": "123"}], "possible": []},
                "checkin": False,
            }
        }
        test_log_area_provider = {
            "log": {
                "id": "log_area_provider_test",
                "list": {"available": [], "possible": []},
            }
        }
        database.put(
            f"/environment/provider/iut/{test_iut_provider['iut']['id']}",
            json.dumps(test_iut_provider),
        )
        provider_id = test_execution_space_provider["execution_space"]["id"]
        database.put(
            f"/environment/provider/execution-space/{provider_id}",
            json.dumps(test_execution_space_provider),
        )
        database.put(
            f"/environment/provider/log-area/{test_log_area_provider['log']['id']}",
            json.dumps(test_log_area_provider),
        )

        iut = {"id": "test_iut", "provider_id": test_iut_provider["iut"]["id"]}
        executor = {
            "id": "test_executor",
            "provider_id": test_execution_space_provider["execution_space"]["id"],
        }
        log_area = {
            "id": "test_log_area",
            "provider_id": test_log_area_provider["log"]["id"],
        }
        test_suite_id = "ce63f53e-1797-42bb-ae72-861a0b6b7ef6"
        jsontas = JsonTas()
        etos = ETOS("", "", "")
        database.put(
            f"/testrun/{test_suite_id}/suite/fakeid/subsuite/fakeid/suite",
            json.dumps(
                {
                    "iut": iut,
                    "executor": executor,
                    "log_area": log_area,
                }
            ),
        )

        self.logger.info("STEP: Release an environment where one provider will fail to check in.")
        success, _ = release_full_environment(etos, jsontas, test_suite_id)

        self.logger.info("STEP: Verify that the release return failure.")
        self.assertFalse(success)
        self.assertListEqual(database.get_prefix("/testrun"), [])

    def test_check_environment_status(self):
        """Test that it is possible to get the status of an environment.

        Approval criteria:
            - The environment provider shall return the status of an environment.

        Test steps:
            1. Get status of an environment.
            2. Verify that the correct status is returned.
        """
        environment_id = "49b59fc9-4eab-4747-bd53-c638d95a87ea"
        result = {"this": "is", "a": "test"}
        status = "PENDING"
        worker = FakeCelery(environment_id, status, result)
        self.logger.info("STEP: Get status of an environment.")
        environment_status = check_environment_status(worker, environment_id)

        self.logger.info("STEP: Verify that the correct status is returned.")
        self.assertDictEqual(environment_status, {"status": status, "result": result})
        self.assertIn(environment_id, worker.received)

    @patch("environment_provider_api.backend.environment.get_environment")
    def test_request_environment(self, get_environment_mock):
        """Test that it is possible to start the environment provider.

        Approval criteria:
            - It shall be possible to request an environment from the environment provider.

        Test steps:
            1. Request an environment from the environment provider.
            2. Verify that the environment provider starts the celery task.
        """
        task_id = "f3286e6e-946c-4510-a935-abd7c7bdbe17"
        get_environment_mock.delay.return_value = Task(task_id)
        suite_id = "ca950c50-03d3-4a3c-8507-b4229dd3f8ea"
        suite_runner_id = ["dba8267b-d393-4e37-89ee-7657ea286564"]

        self.logger.info("STEP: Request an environment from the environment provider.")
        response = request_environment(suite_id, suite_runner_id)

        self.logger.info("STEP: Verify that the environment provider starts the celery task.")
        self.assertEqual(response, task_id)
        get_environment_mock.delay.assert_called_once_with(suite_id, suite_runner_id)
