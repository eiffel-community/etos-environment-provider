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
"""Tests for webserver. Specifically the environment endpoint."""
import json
import logging
import unittest

import falcon
from etos_lib.lib.config import Config
from mock import patch

from environment_provider_api.webserver import Webserver
from tests.library.fake_celery import FakeCelery, Task
from tests.library.fake_database import FakeDatabase
from tests.library.fake_request import FakeRequest, FakeResponse


class TestEnvironment(unittest.TestCase):
    """Tests for the environment endpoint."""

    logger = logging.getLogger(__name__)

    def tearDown(self):
        """Reset all globally stored data for the next test."""
        Config().reset()

    def test_release_environment(self):  # pylint:disable=too-many-locals
        """Test that it is possible to release an environment.

        Approval criteria:
            - It shall be possible to release an environment.

        Test steps:
            1. Store an environment i celery task.
            2. Send a release request for that environment.
            3. Verify that the environment was released.
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
        task_id = "d9689ea5-837b-48c1-87b1-3de122b3f2fe"
        suite_id = "6d779f97-67e7-4dfa-8260-c053fc0d7a2c"
        database.put(f"/environment/{task_id}/suite-id", suite_id)
        database.put(f"/testrun/{suite_id}/environment-provider/task-id", task_id)
        request = FakeRequest()
        request.fake_params = {"release": task_id}
        response = FakeResponse()

        iut = {"id": "test_iut", "provider_id": test_iut_provider["iut"]["id"]}
        executor = {
            "id": "test_executor",
            "provider_id": test_execution_space_provider["execution_space"]["id"],
        }
        log_area = {
            "id": "test_log_area",
            "provider_id": test_log_area_provider["log"]["id"],
        }

        self.logger.info("STEP: Store an environment i celery task.")
        test_status = "SUCCESS"
        worker = FakeCelery(
            task_id,
            test_status,
            {
                "suites": [
                    {
                        "iut": iut,
                        "executor": executor,
                        "log_area": log_area,
                    }
                ]
            },
        )

        self.logger.info("STEP: Send a release request for that environment.")
        environment = Webserver(worker)
        environment.on_get(request, response)

        self.logger.info("STEP: Verify that the environment was released.")
        self.assertDictEqual(response.media, {"status": test_status})
        self.assertIsNone(worker.results.get(task_id))

    def test_get_environment_status(self):
        """Test that it is possible to get status from an environment.

        Approval criteria:
            - It shall be possible to get status from environment that is being checked out.

        Test steps:
            1. Store a PENDING environment request in a celery task.
            2. Send a status request for that environment.
            3. Verify that the status for the environment was returned.
        """
        task_id = "d9689ea5-837b-48c1-87b1-3de122b3f2fe"
        database = FakeDatabase()
        Config().set("database", database)
        request = FakeRequest()
        request.fake_params = {"id": task_id}
        response = FakeResponse()
        test_result = {"this": "is", "results": ":)"}
        test_status = "PENDING"

        self.logger.info("STEP: Store a PENDING environment request in a celery task.")
        celery_worker = FakeCelery(task_id, test_status, test_result)

        self.logger.info("STEP: Send a status request for that environment.")
        environment = Webserver(celery_worker)
        environment.on_get(request, response)

        self.logger.info("STEP: Verify that the status for the environment was returned.")
        self.assertEqual(response.status, falcon.HTTP_200)
        self.assertDictEqual(response.media, {"status": test_status, "result": test_result})

    @patch("environment_provider_api.backend.environment.get_environment")
    def test_get_environment(self, get_environment_mock):
        """Test that it is possible to get environments from the environment provider.

        Approval criteria:
            - It shall be possible to get an environment from the environment provider.

        Note:
            - This test is mocked due to not wanting to run celery tasks.

        Test steps:
            1. Send a request for an environment.
            2. Verify that the environment provider gets an environment.
        """
        task_id = "f3286e6e-946c-4510-a935-abd7c7bdbe17"
        database = FakeDatabase()
        Config().set("database", database)
        get_environment_mock.delay.return_value = Task(task_id)
        celery_worker = FakeCelery(task_id, "", {})
        suite_id = "ca950c50-03d3-4a3c-8507-b4229dd3f8ea"
        suite_runner_ids = (
            "835cd892-7eda-408a-9e4c-84aaa71d05be,50146754-8b4f-4253-b5a9-2ee56960612c"
        )
        request = FakeRequest()
        request.fake_params = {
            "suite_id": suite_id,
            "suite_runner_ids": suite_runner_ids,
        }
        response = FakeResponse()

        self.logger.info("STEP: Send a request for an environment.")
        environment = Webserver(celery_worker)
        environment.on_post(request, response)

        self.logger.info("STEP: Verify that the environment provider gets an environment.")
        self.assertEqual(response.media, {"result": "success", "data": {"id": task_id}})
        get_environment_mock.delay.assert_called_once_with(suite_id, suite_runner_ids.split(","))
