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
"""Tests for common functionality."""
import logging
import unittest

from tests.library.fake_request import FakeRequest

from environment_provider_api.backend.common import get_suite_id


class TestCommonFunctionality(unittest.TestCase):
    """Test the common backend functionality."""

    logger = logging.getLogger(__name__)

    def test_suite_id(self):
        """Test that the configure backend can return suite id.

        Approval criteria:
            - The configure backend shall be able to get the suite id from request.

        Test steps:
            1. Get suite id from request via the configure backend.
            2. Verify that the backend returns the correct suite id.
        """
        request = FakeRequest()
        test_suite_id = "b58415d4-2f39-4ab0-8763-7277e18f9606"
        request.fake_params["suite_id"] = test_suite_id
        self.logger.info("STEP: Get suite id from request via the configure backend.")
        response_suite_id = get_suite_id(request)

        self.logger.info("STEP: Verify that the backend returns the correct suite id.")
        self.assertEqual(test_suite_id, response_suite_id)

    def test_suite_id_media_is_none(self):
        """Test that the configure backend returns the result of get_param if media is not set.

        Approval criteria:
            - The configure backend shall return the value of get_param if media is None.

        Test steps:
            1. Get suite id from request via the configure backend without media.
            2. Verify that the backend returns the suite id.
        """
        request = FakeRequest()
        request.force_media_none = True
        test_suite_id = "b58415d4-2f39-4ab0-8763-7277e18f9606"
        request.fake_params["suite_id"] = test_suite_id
        self.logger.info("STEP: Get suite id from request via the configure backend without media.")
        response_suite_id = get_suite_id(request)

        self.logger.info("STEP: Verify that the backend returns the suite id.")
        self.assertEqual(test_suite_id, response_suite_id)

    def test_suite_id_none(self):
        """Test that the configure backend returns None if suite id is not set.

        Approval criteria:
            - The configure backend shall return None if suite id is not in request.

        Test steps:
            1. Get suite id from request via the configure backend.
            2. Verify that the backend returns None.
        """
        self.logger.info("STEP: Get suite id from request via the configure backend.")
        response = get_suite_id(FakeRequest())

        self.logger.info("STEP: Verify that the backend returns None.")
        self.assertIsNone(response)
