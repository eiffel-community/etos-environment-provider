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
"""Tests for webserver. Specifically the configure endpoint."""
import json
import logging
import unittest
from uuid import uuid4

import falcon
from etos_lib.lib.config import Config

from environment_provider_api.webserver import Configure
from tests.library.fake_database import FakeDatabase
from tests.library.fake_request import FakeRequest, FakeResponse


class TestConfigure(unittest.TestCase):
    """Tests for the configure endpoint."""

    logger = logging.getLogger(__name__)

    def tearDown(self):
        """Reset all globally stored data for the next test."""
        Config().reset()

    def test_get_configuration(self):
        """Test that it is possible to get a stored configuration.

        Approval criteria:
            - It shall be possible to get a stored configuration.

        Test steps:
            1. Store a configuration in the database.
            2. Send a GET request to the configure endpoint.
            3. Verify that the configuration is the same as in the database.
        """
        database = FakeDatabase()
        Config().set("database", database)
        test_suite_id = "5ef5a01c-8ff9-448d-9ac5-21836a2fa6ff"
        test_dataset = {"dataset": "test"}
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
        self.logger.info("STEP: Store a configuration in the database.")
        database.put(f"/testrun/{test_suite_id}/provider/dataset", json.dumps(test_dataset))
        database.put(f"/testrun/{test_suite_id}/provider/iut", json.dumps(test_iut_provider))
        database.put(
            f"/testrun/{test_suite_id}/provider/log-area", json.dumps(test_log_area_provider)
        )
        database.put(
            f"/testrun/{test_suite_id}/provider/execution-space",
            json.dumps(test_execution_space_provider),
        )

        response = FakeResponse()
        request = FakeRequest()
        request.fake_params["suite_id"] = test_suite_id
        self.logger.info("STEP: Send a GET request to the configure endpoint.")
        Configure().on_get(request, response)

        self.logger.info("STEP: Verify that the configuration is the same as in the database.")
        self.assertEqual(response.status, falcon.HTTP_200)
        self.assertDictEqual(response.media.get("iut_provider", {}), test_iut_provider["iut"])
        self.assertDictEqual(
            response.media.get("log_area_provider", {}), test_log_area_provider["log"]
        )
        self.assertDictEqual(
            response.media.get("execution_space_provider", {}),
            test_execution_space_provider["execution_space"],
        )
        self.assertDictEqual(response.media.get("dataset", {}), test_dataset)

    def test_get_configuration_no_suite_id(self):
        """Test that it is not possible to get a configuration without suite id.

        Approval criteria:
            - The configure endpoint shall return BadRequest when missing suite id.

        Test steps:
            1. Send a GET request to the configure endpoint without suite id.
            2. Verify that a BadRequest is returned.
        """
        database = FakeDatabase()
        Config().set("database", database)
        response = FakeResponse()
        request = FakeRequest()
        self.logger.info("STEP: Send a GET request to the configure endpoint without suite id.")
        with self.assertRaises(falcon.HTTPBadRequest):
            self.logger.info("STEP: Verify that a BadRequest is returned.")
            Configure().on_get(request, response)

    def test_configure(self):
        """Test that it is possible to configure the environment provider for a suite.

        Approval criteria:
            - It shall be possible to configure the environment provider.
            - The configure endpoint shall return with the configured IUT, execution space &
              log area provider.

        Test steps:
            1. Store some providers in the database.
            2. Send a configure request to use those providers.
            3. Verify that the configuration matches the providers in database.
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
        test_suite_id = "2a4cb06d-4ebf-4aaa-a53b-1293194827d8"
        self.logger.info("STEP: Store some providers in the database.")
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

        response = FakeResponse()
        request = FakeRequest()
        request.fake_params = {
            "iut_provider": test_iut_provider["iut"]["id"],
            "execution_space_provider": test_execution_space_provider["execution_space"]["id"],
            "log_area_provider": test_log_area_provider["log"]["id"],
            "dataset": {},
            "suite_id": test_suite_id,
        }
        self.logger.info("STEP: Send a configure request to use those providers.")
        Configure().on_post(request, response)

        self.logger.info("STEP: Verify that the configuration matches the providers in database.")
        self.assertEqual(response.status, falcon.HTTP_200)
        stored_iut_provider = json.loads(database.get(f"/testrun/{test_suite_id}/provider/iut")[0])
        self.assertDictEqual(stored_iut_provider, test_iut_provider)
        stored_execution_space_provider = json.loads(
            database.get(f"/testrun/{test_suite_id}/provider/execution-space")[0]
        )
        self.assertDictEqual(stored_execution_space_provider, test_execution_space_provider)
        stored_log_area_provider = json.loads(
            database.get(f"/testrun/{test_suite_id}/provider/log-area")[0]
        )
        self.assertDictEqual(stored_log_area_provider, test_log_area_provider)
        stored_dataset = json.loads(database.get(f"/testrun/{test_suite_id}/provider/dataset")[0])
        self.assertDictEqual(stored_dataset, {})

    def test_configure_missing_parameters(self):
        """Test that it is not possible to configure the environment provider without providers.

        Approval criteria:
            - It shall not be possible to configure the environment provider when
              missing parameters.

        Test steps:
            1. Store some providers in the database.
            2. For each parameter:
                2.1. Send a configure request missing that parameter.
                2.2. Verify that it was not possible to configure.
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
        self.logger.info("STEP: Store some providers in the database.")
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

        response = FakeResponse()
        request = FakeRequest()
        test_params = {
            "iut_provider": test_iut_provider["iut"]["id"],
            "execution_space_provider": test_execution_space_provider["execution_space"]["id"],
            "log_area_provider": test_log_area_provider["log"]["id"],
            "dataset": {},
        }
        self.logger.info("STEP: For each parameter:")
        for parameter in (
            "iut_provider",
            "log_area_provider",
            "execution_space_provider",
            "dataset",
            "suite_id",
        ):
            self.logger.info("Missing parameter: %s", parameter)
            # Make sure we get a new suite id for each test.
            # that way we don't have to clear the database every time.
            test_suite_id = str(uuid4())
            test_params["suite_id"] = test_suite_id

            request.fake_params = test_params.copy()
            request.fake_params.pop(parameter)

            self.logger.info("STEP: Send a configure request missing that parameter.")
            with self.assertRaises(falcon.HTTPBadRequest):
                Configure().on_post(request, response)

            self.logger.info("STEP: Verify that it was not possible to configure.")
            self.assertListEqual(database.get(f"/testrun/{test_suite_id}/provider/iut"), [])
            self.assertListEqual(
                database.get(f"/testrun/{test_suite_id}/provider/execution-space"), []
            )
            self.assertListEqual(database.get(f"/testrun/{test_suite_id}/provider/log-area"), [])
            self.assertListEqual(database.get(f"/testrun/{test_suite_id}/provider/dataset"), [])
