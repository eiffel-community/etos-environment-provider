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
"""Tests for the sub suite backend system."""
import logging
import unittest
import json

import falcon

from environment_provider.backend.subsuite import suite_id, sub_suite
from tests.library.fake_request import FakeRequest
from tests.library.fake_database import FakeDatabase


class TestSubSuiteBackend(unittest.TestCase):
    """Test the sub suite backend."""

    logger = logging.getLogger(__name__)

    def test_suite_id(self):
        """Test that the subsuite backend can return suite IDs.

        Approval criteria:
            - The subsuite backend shall be able to get the suite ID from request parameters.

        Test steps:
            1. Get Suite ID from request via the suite id function.
            2. Verify that the suite id function return the correct ID.
        """
        request = FakeRequest()
        test_id = "thisismytestid"
        request.fake_params["id"] = test_id
        self.logger.info("STEP: Get Suite ID from request via the suite id function.")
        response_id = suite_id(request)
        self.logger.info(
            "STEP: Verify that the suite id function return the correct ID."
        )
        self.assertEqual(test_id, response_id)

    def test_suite_id_missing(self):
        """Test that the subsuite backend raises bad request if id is missing.

        Approval criteria:
            - The subsuite backend shall raise falcon.HTTPBadRequest if ID is missing.

        Test steps:
            1. Get Suite ID from request via the suite id function.
            2. Verify that the suite id function raises falcon.HTTPBadRequest.
        """
        request = FakeRequest()
        request.fake_params["id"] = None
        self.logger.info("STEP: Get Suite ID from request via the suite id function.")
        self.logger.info(
            "STEP: Verify that the suite id function raises falcon.HTTPBadRequest."
        )
        with self.assertRaises(falcon.HTTPBadRequest):
            suite_id(request)

    def test_sub_suite(self):
        """Test that the subsuite backend can return the sub suite registered in database.

        Approval criteria:
            - The subsuite backend shall be able to return sub suites registered in the database.

        Test steps:
            1. Add a sub suite to the database.
            2. Get sub suite from the subsuite backend.
            3. Verify that the sub suite is the one stored in the database.
        """
        database = FakeDatabase()
        self.logger.info("STEP: Add a sub suite to the database.")
        test_suite = {"testing": "subsuites"}
        database.write("mysuite", json.dumps(test_suite))
        self.logger.info("STEP: Get the sub suite from the subsuite backend.")
        response_suite = sub_suite(database, "mysuite")
        self.logger.info(
            "STEP: Verify that the sub suite is the one stored in the database."
        )
        self.assertDictEqual(test_suite, response_suite)

    def test_sub_suite_does_not_exist(self):
        """Test that the subsuite backend return None when there is no sub suite in database.

        Approval criteria:
            - The subsuite backend shall return None when there is no sub suite in database.

        Test steps:
            1. Get sub suite from the subsuite backend.
            2. Verify that the sub suite returned is None.
        """
        self.logger.info("STEP: Get the sub suite from the subsuite backend.")
        suite = sub_suite(FakeDatabase(), 1)
        self.logger.info("STEP: Verify that the sub suite returned is None.")
        self.assertIsNone(suite)
