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
"""Tests for the webserver and its endpoints."""
import logging
import json
import unittest

import falcon

from environment_provider.webserver import SubSuite
from tests.library.fake_request import FakeRequest, FakeResponse
from tests.library.fake_database import FakeDatabase


class TestSubSuite(unittest.TestCase):
    """Tests for the sub suite endpoint."""

    logger = logging.getLogger(__name__)

    def test_get(self):
        """Test that it is possible to get a sub suite from the sub suite endpoint.

        Approval criteria:
            - The sub suite endpoint shall return a sub suite if one exists.

        Test steps:
            1. Add a sub suite to the database.
            2. Send a fake request to the sub suite endpoint.
            3. Verify that the sub suite endpoint responds with a sub suite.
        """
        self.logger.info("STEP: Add a sub suite to the database.")
        database = FakeDatabase()
        suite_id = "thetestiestofsuites"
        sub_suite = {"test": "suite"}
        database.write(suite_id, json.dumps(sub_suite))

        self.logger.info("STEP: Send a fake request to the sub suite endpoint.")
        request = FakeRequest()
        request.fake_params["id"] = suite_id
        response = FakeResponse()
        SubSuite(database).on_get(request, response)

        self.logger.info(
            "STEP: Verify that the sub suite endpoint responds with a sub suite."
        )
        self.assertDictEqual(response.fake_responses.get("media"), sub_suite)

    def test_get_no_id(self):
        """Test that the sub suite endpoint fails when sub suite was not found.

        Approval criteria:
            - The sub suite endpoint shall raise a HTTPNotFound exception when no suite is found.

        Test steps:
            1. Send a fake request to the sub suite endpoint.
            2. Verify that the sub suite endpoint responds with HTTPNotFound.
        """
        self.logger.info("STEP: Send a fake request to the sub suite endpoint.")
        request = FakeRequest()
        request.fake_params["id"] = "thisonedoesnotexist"
        response = FakeResponse()
        self.logger.info(
            "STEP: Verify that the sub suite endpoint responds with HTTPNotFound."
        )
        with self.assertRaises(falcon.HTTPNotFound):
            SubSuite(FakeDatabase).on_get(request, response)
