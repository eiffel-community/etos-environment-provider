# Copyright 2021 Axis Communications AB.
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
"""Tests for webserver. Specifically the register endpoint."""
import logging
import json
import unittest

import falcon

from environment_provider_api.webserver import Register
from tests.library.fake_database import FakeDatabase
from tests.library.fake_request import FakeRequest, FakeResponse


class TestRegister(unittest.TestCase):
    """Tests for the register endpoint."""

    logger = logging.getLogger(__name__)

    def test_register_all_providers(self):
        """Test that it is possible to register providers via the register endpoint

        Approval criteria:
            - It shall be possible to register providers using the endpoint.

        Test steps:
            1. Send a register request for new providers.
            2. Verify that the new providers were registered in the database.
        """
        fake_database = FakeDatabase()
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
        fake_request = FakeRequest()
        fake_request.fake_params = {
            "iut_provider": json.dumps(test_iut_provider),
            "execution_space_provider": json.dumps(test_execution_space_provider),
            "log_area_provider": json.dumps(test_log_area_provider),
        }
        fake_response = FakeResponse()
        self.logger.info("STEP: Send a register request for new providers.")
        Register(fake_database).on_post(fake_request, fake_response)

        self.logger.info(
            "STEP: Verify that the new providers were registered in the database."
        )
        self.assertEqual(fake_response.fake_responses.get("status"), falcon.HTTP_204)
        stored_execution_space_provider = json.loads(
            fake_database.reader.hget(
                "EnvironmentProvider:ExecutionSpaceProviders",
                "execution_space_provider_test",
            )
        )
        self.assertDictEqual(
            stored_execution_space_provider,
            test_execution_space_provider,
        )
        stored_log_area_provider = json.loads(
            fake_database.reader.hget(
                "EnvironmentProvider:LogAreaProviders", "log_area_provider_test"
            )
        )
        self.assertDictEqual(stored_log_area_provider, test_log_area_provider)
        stored_iut_provider = json.loads(
            fake_database.reader.hget(
                "EnvironmentProvider:IUTProviders", "iut_provider_test"
            )
        )
        self.assertDictEqual(stored_iut_provider, test_iut_provider)

    def test_register_no_providers(self):
        """Test that it is not possible to register no providers.

        Approval criteria:
            - It shall not be possible to register no providers.

        Test steps:
            1. Send a register request with no providers.
            2. Verify that a 400 Bad Request is returned.
        """
        fake_database = FakeDatabase()
        fake_request = FakeRequest()
        fake_response = FakeResponse()
        self.logger.info("STEP: Send a register request with no providers.")
        with self.assertRaises(falcon.HTTPBadRequest):
            self.logger.info("STEP: Verify that a 400 Bad Request is returned.")
            Register(fake_database).on_post(fake_request, fake_response)
