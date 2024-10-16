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
"""Integration tests for the environment provider splitter."""
import logging
import unittest

from etos_lib import ETOS
from etos_lib.kubernetes.schemas.environment_request import Splitter as SplitterSchema

from environment_provider.splitter.split import Splitter
from iut_provider.iut import Iut


class TestSplitter(unittest.TestCase):
    """Test the environment provider slitter."""

    logger = logging.getLogger(__name__)

    def test_assign_iuts(self) -> None:
        """Test that that a test runner never gets 0 number of IUTs assigned.

        Approval criteria:
            - A test runner shall never had 0 number of IUTs assigned.

        Test steps::
            1. Assign IUTs to the provided test runners.
            2. Verify that no test runner get 0 assigned IUTs.
        """
        iuts = [Iut(name="iut1"), Iut(name="iut2")]
        test_runners = {
            "runner1": {"iuts": {}, "unsplit_recipes": [1]},
            "runner2": {"iuts": {}, "unsplit_recipes": [2, 3, 4, 5]},
        }

        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("TOTAL_TEST_COUNT", 5)
        etos.config.set("NUMBER_OF_IUTS", len(iuts))

        self.logger.info("STEP: Assign IUTs to the provided test runners.")
        _ = Splitter(etos, SplitterSchema(tests=[])).assign_iuts(test_runners, iuts)

        self.logger.info("STEP: Verify that no test runner get 0 assigned IUTs.")
        for test_runner in test_runners.values():
            self.assertNotEqual(
                test_runner.get("number_of_iuts"),
                0,
                f"'number_of_iuts' is 0, test_runner got 0 assigned IUTs. {test_runner}]",
            )
