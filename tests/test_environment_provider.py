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
"""Tests for the environment provider."""
import functools
import json
import logging
import os
import unittest
from mock import patch

from etos_lib.lib.config import Config
from etos_lib.lib.debug import Debug

from environment_provider.environment_provider import EnvironmentProvider
from tests.library.fake_database import FakeDatabase
from tests.library.fake_server import FakeServer
from tests.library.graphql_handler import GraphQLHandler

from .tercc import TERCC, TERCC_PERMUTATION, TERCC_SUB_SUITES

IUT_PROVIDER = {
    "iut": {
        "id": "default",
        "list": {
            "possible": {
                "$expand": {
                    "value": {
                        "type": "$identity.type",
                        "namespace": "$identity.namespace",
                        "name": "$identity.name",
                        "version": "$identity.version",
                        "qualifiers": "$identity.qualifiers",
                        "subpath": "$identity.subpath",
                    },
                    "to": "$amount",
                }
            },
            "available": "$this.possible",
        },
    }
}


IUT_PROVIDER_SINGLE = {
    "iut": {
        "id": "only_one",
        "list": {
            "possible": [
                {
                    "type": "$identity.type",
                    "namespace": "$identity.namespace",
                    "name": "$identity.name",
                    "version": "$identity.version",
                    "qualifiers": "$identity.qualifiers",
                    "subpath": "$identity.subpath",
                }
            ],
            "available": "$this.possible",
        },
    }
}


EXECUTION_SPACE_PROVIDER = {
    "execution_space": {
        "id": "default",
        "list": {
            "possible": {
                "$expand": {
                    "value": {"instructions": "$execution_space_instructions"},
                    "to": "$amount",
                }
            },
            "available": "$this.possible",
        },
    }
}


LOG_AREA_PROVIDER = {
    "log": {
        "id": "default",
        "list": {
            "possible": {
                "$expand": {
                    "value": {"upload": {"url": "$dataset.host", "method": "GET"}},
                    "to": "$amount",
                }
            },
            "available": "$this.possible",
        },
    }
}


class TestEnvironmentProvider(unittest.TestCase):
    """Scenario tests for the environment provider."""

    logger = logging.getLogger(__name__)

    def setUp(self):
        """Set up environment variables for the ESR."""
        os.environ["ETOS_DISABLE_SENDING_EVENTS"] = "1"
        os.environ["ETOS_DEFAULT_WAIT_TIMEOUT"] = "10"
        os.environ["ETOS_EVENT_DATA_TIMEOUT"] = "10"

    def tearDown(self):
        """Reset all globally stored data for the next test."""
        Config().reset()
        # pylint:disable=protected-access
        Debug()._Debug__events_published.clear()
        Debug()._Debug__events_received.clear()

    @patch("environment_provider.environment_provider.Kubernetes")
    def test_get_environment_sub_suites(self, _):
        """Test environment provider with 2 different sub suites.

        Approval criteria:
            - The environment provider shall provide 2 environments for 2 sub suites.

        Test steps:
            1. Start up a fake server.
            2. Run the environment provider.
            3. Verify that two environments were sent.
        """
        tercc = TERCC_SUB_SUITES

        suite_id = tercc["meta"]["id"]
        suite_runner_ids = ["14ffc8d7-572a-4f2f-9382-923de2bcf50a"]

        database = FakeDatabase()
        Config().set("database", database)
        database.put(f"/testrun/{suite_id}/tercc", json.dumps(tercc))
        database.put(f"/testrun/{suite_id}/provider/iut", json.dumps(IUT_PROVIDER))
        database.put(f"/testrun/{suite_id}/provider/log-area", json.dumps(LOG_AREA_PROVIDER))
        database.put(
            f"/testrun/{suite_id}/provider/execution-space", json.dumps(EXECUTION_SPACE_PROVIDER)
        )

        handler = functools.partial(GraphQLHandler, tercc)

        self.logger.info("STEP: Start up a fake server.")
        with FakeServer(None, None, handler) as server:
            database.put(
                f"/testrun/{suite_id}/provider/dataset",
                json.dumps({"host": server.host}),
            )
            os.environ["ETOS_GRAPHQL_SERVER"] = server.host
            os.environ["ETOS_API"] = server.host
            os.environ["TERCC"] = json.dumps(tercc)

            self.logger.info("STEP: Run the environment provider.")
            environment_provider = EnvironmentProvider(suite_runner_ids)
            result = environment_provider.run()
            print(result)
        self.assertIsNone(result.get("error"))

        self.logger.info("STEP: Verify that two environments were sent.")
        environments = []
        for event in Debug().events_published:
            if event.meta.type == "EiffelEnvironmentDefinedEvent":
                environments.append(event)
        self.assertEqual(len(environments), 2)

    @patch("environment_provider.environment_provider.Kubernetes")
    def test_get_environment(self, _):
        """Test environment provider with single sub suites.

        Approval criteria:
            - The environment provider shall provide 1 environment for 1 sub suites.

        Test steps:
            1. Start up a fake server.
            2. Run the environment provider.
            3. Verify that one environments was sent.
        """
        tercc = TERCC

        suite_id = tercc["meta"]["id"]
        suite_runner_ids = ["14ffc8d7-572a-4f2f-9382-923de2bcf50a"]

        database = FakeDatabase()
        Config().set("database", database)
        database.put(f"/testrun/{suite_id}/tercc", json.dumps(tercc))
        database.put(f"/testrun/{suite_id}/provider/iut", json.dumps(IUT_PROVIDER))
        database.put(f"/testrun/{suite_id}/provider/log-area", json.dumps(LOG_AREA_PROVIDER))
        database.put(
            f"/testrun/{suite_id}/provider/execution-space", json.dumps(EXECUTION_SPACE_PROVIDER)
        )

        handler = functools.partial(GraphQLHandler, tercc)

        self.logger.info("STEP: Start up a fake server.")
        with FakeServer(None, None, handler) as server:
            database.put(
                f"/testrun/{suite_id}/provider/dataset",
                json.dumps({"host": server.host}),
            )
            os.environ["ETOS_GRAPHQL_SERVER"] = server.host
            os.environ["ETOS_API"] = server.host
            os.environ["TERCC"] = json.dumps(tercc)

            self.logger.info("STEP: Run the environment provider.")
            environment_provider = EnvironmentProvider(suite_runner_ids)
            result = environment_provider.run()
            print(result)
        self.assertIsNone(result.get("error"))

        self.logger.info("STEP: Verify that two environments were sent.")
        environments = []
        for event in Debug().events_published:
            if event.meta.type == "EiffelEnvironmentDefinedEvent":
                environments.append(event)
        self.assertEqual(len(environments), 1)

    @patch("environment_provider.environment_provider.Kubernetes")
    def test_get_environment_permutation(self, _):
        """Test environment provider with 2 different environments for 2 permutations.

        Approval criteria:
            - The environment provider shall provide 2 environments for 2 permutations.

        Test steps:
            1. Start up a fake server.
            2. Run the environment provider.
            3. Verify that two environments was sent.
        """
        tercc = TERCC_PERMUTATION

        suite_id = tercc["meta"]["id"]
        suite_runner_ids = [
            "14ffc8d7-572a-4f2f-9382-923de2bcf50a",
            "02bb2d7c-5c58-43a7-9b2c-9a5fbc4d3cd2",
        ]

        database = FakeDatabase()
        Config().set("database", database)
        database.put(f"/testrun/{suite_id}/tercc", json.dumps(tercc))
        database.put(f"/testrun/{suite_id}/provider/iut", json.dumps(IUT_PROVIDER))
        database.put(f"/testrun/{suite_id}/provider/log-area", json.dumps(LOG_AREA_PROVIDER))
        database.put(
            f"/testrun/{suite_id}/provider/execution-space", json.dumps(EXECUTION_SPACE_PROVIDER)
        )

        handler = functools.partial(GraphQLHandler, tercc)

        self.logger.info("STEP: Start up a fake server.")
        with FakeServer(None, None, handler) as server:
            database.put(
                f"/testrun/{suite_id}/provider/dataset",
                json.dumps({"host": server.host}),
            )
            os.environ["ETOS_GRAPHQL_SERVER"] = server.host
            os.environ["ETOS_API"] = server.host
            os.environ["TERCC"] = json.dumps(tercc)

            self.logger.info("STEP: Run the environment provider.")
            environment_provider = EnvironmentProvider(suite_runner_ids)
            result = environment_provider.run()
        self.assertIsNone(result.get("error"))

        self.logger.info("STEP: Verify that two environments were sent.")
        environments = []
        for event in Debug().events_published:
            if event.meta.type == "EiffelEnvironmentDefinedEvent":
                environments.append(event)
        self.assertEqual(len(environments), 2)

    @patch("environment_provider.environment_provider.Kubernetes")
    def test_get_environment_sub_suites_sequential(self, _):
        """Test environment provider with 2 different sub suites sequentially.

        Approval criteria:
            - The environment provider shall provide 2 environments for 2 sub suites.

        Test steps:
            1. Register an IUT provider providing only 1 IUT.
            2. Start up a fake server.
            3. Run the environment provider.
            4. Verify that two environments were sent.
        """
        tercc = TERCC_SUB_SUITES

        suite_id = tercc["meta"]["id"]
        suite_runner_ids = ["14ffc8d7-572a-4f2f-9382-923de2bcf50a"]

        database = FakeDatabase()
        Config().set("database", database)
        database.put(f"/testrun/{suite_id}/tercc", json.dumps(tercc))
        self.logger.info("STEP: Register an IUT provider providing only 1 IUT.")
        database.put(f"/testrun/{suite_id}/provider/iut", json.dumps(IUT_PROVIDER_SINGLE))
        database.put(f"/testrun/{suite_id}/provider/log-area", json.dumps(LOG_AREA_PROVIDER))
        database.put(
            f"/testrun/{suite_id}/provider/execution-space", json.dumps(EXECUTION_SPACE_PROVIDER)
        )

        handler = functools.partial(GraphQLHandler, tercc)

        self.logger.info("STEP: Start up a fake server.")
        with FakeServer(None, None, handler) as server:
            database.put(
                f"/testrun/{suite_id}/provider/dataset",
                json.dumps({"host": server.host}),
            )
            os.environ["ETOS_GRAPHQL_SERVER"] = server.host
            os.environ["ETOS_API"] = server.host
            os.environ["TERCC"] = json.dumps(tercc)

            self.logger.info("STEP: Run the environment provider.")
            environment_provider = EnvironmentProvider(suite_runner_ids)
            result = environment_provider.run()
            print(result)
        self.assertIsNone(result.get("error"))

        self.logger.info("STEP: Verify that two environments were sent.")
        environments = []
        for event in Debug().events_published:
            if event.meta.type == "EiffelEnvironmentDefinedEvent":
                environments.append(event)
        self.assertEqual(len(environments), 2)
