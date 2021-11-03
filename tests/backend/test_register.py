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
"""Tests for the register backend system."""
import logging
import unittest
import json

from etos_lib import ETOS
from jsontas.jsontas import JsonTas

from environment_provider.lib.registry import ProviderRegistry
from environment_provider.backend.register import (
    register,
    get_iut_provider,
    get_execution_space_provider,
    get_log_area_provider,
    json_to_dict,
)

from tests.library.fake_request import FakeRequest
from tests.library.fake_database import FakeDatabase


class TestRegisterBackend(unittest.TestCase):
    """Test the register backend."""

    logger = logging.getLogger(__name__)

    def test_iut_provider(self):
        """Test that the register backend can return IUT provider.

        Approval criteria:
            - The register backend shall be able to get the IUT provider from request parameters.

        Test steps:
            1. Get IUT provider from request via the register backend.
            2. Verify that the backend returns the correct iut provider.
        """
        request = FakeRequest()
        test_iut_provider = {"iut": {"id": "providertest"}}
        request.fake_params["iut_provider"] = test_iut_provider
        self.logger.info(
            "STEP: Get IUT provider from request via the register backend."
        )
        response_iut_provider = get_iut_provider(request)

        self.logger.info(
            "STEP: Verify that the backend returns the correct iut provider."
        )
        self.assertDictEqual(test_iut_provider, response_iut_provider)

    def test_iut_provider_none(self):
        """Test that the register backend returns None if IUT provider is not set.

        Approval criteria:
            - The register backend shall return None if IUT provider is not in request.

        Test steps:
            1. Get IUT provider from request via the register backend.
            2. Verify that the backend returns None.
        """
        request = FakeRequest()
        self.logger.info(
            "STEP: Get IUT provider from request via the register backend."
        )
        response_iut_provider = get_iut_provider(request)

        self.logger.info("STEP: Verify that the backend returns None.")
        self.assertIsNone(response_iut_provider)

    def test_execution_space_provider(self):
        """Test that the register backend can return execution space provider.

        Approval criteria:
            - The register backend shall be able to get the execution space provider from
              request parameters.

        Test steps:
            1. Get execution space provider from request via the register backend.
            2. Verify that the backend returns the correct execution space provider.
        """
        request = FakeRequest()
        test_execution_space_provider = {"execution_space": {"id": "providertest"}}
        request.fake_params["execution_space_provider"] = test_execution_space_provider
        self.logger.info(
            "STEP: Get execution space provider from request via the register backend."
        )
        response_execution_space_provider = get_execution_space_provider(request)

        self.logger.info(
            "STEP: Verify that the backend returns the correct execution space provider."
        )
        self.assertDictEqual(
            test_execution_space_provider, response_execution_space_provider
        )

    def test_execution_space_provider_none(self):
        """Test that the register backend returns None if execution space provider is not set.

        Approval criteria:
            - The register backend shall return None if execution space provider is not in request.

        Test steps:
            1. Get execution space provider from request via the register backend.
            2. Verify that the backend returns None.
        """
        request = FakeRequest()
        self.logger.info(
            "STEP: Get execution space provider from request via the register backend."
        )
        response_execution_space_provider = get_execution_space_provider(request)

        self.logger.info("STEP: Verify that the backend returns None.")
        self.assertIsNone(response_execution_space_provider)

    def test_log_area_provider(self):
        """Test that the register backend can return log area provider.

        Approval criteria:
            - The register backend shall be able to get the log area provider from
              request parameters.

        Test steps:
            1. Get log area provider from request via the register backend.
            2. Verify that the backend returns the correct log area provider.
        """
        request = FakeRequest()
        test_log_area_provider = {"log": {"id": "providertest"}}
        request.fake_params["log_area_provider"] = test_log_area_provider
        self.logger.info(
            "STEP: Get log area provider from request via the register backend."
        )
        response_log_area_provider = get_log_area_provider(request)

        self.logger.info(
            "STEP: Verify that the backend returns the correct log area provider."
        )
        self.assertDictEqual(test_log_area_provider, response_log_area_provider)

    def test_log_area_provider_none(self):
        """Test that the register backend returns None if log area provider is not set.

        Approval criteria:
            - The register backend shall return None if log area provider is not in request.

        Test steps:
            1. Get log area provider from request via the register backend.
            2. Verify that the backend returns None.
        """
        request = FakeRequest()
        self.logger.info(
            "STEP: Get log area provider from request via the register backend."
        )
        response_log_area_provider = get_log_area_provider(request)

        self.logger.info("STEP: Verify that the backend returns None.")
        self.assertIsNone(response_log_area_provider)

    def test_json_to_dict(self):
        """Test that the json to dict function returns a dictionary.

        Approval criteria:
            - The json_to_dict function shall convert strings to dictionary.

        Test steps:
            1. Verify that the json_to_dict converts JSON strings to dictionary.
        """
        json_string = '{"data": "testing"}'
        self.logger.info(
            "STEP: Verify that the json_to_dict converts JSON strings to dictionary."
        )
        json_dict = json_to_dict(json_string)
        self.assertDictEqual(json_dict, json.loads(json_string))

    def test_json_to_dict_already_dict(self):
        """Test that the json to dict function does not do anything if input is already a dict.

        Approval criteria:
            - The json_to_dict function shall return dictionary as it is.

        Test steps:
            1. Verify that the json_to_dict returns the same dictionary when provided with one.
        """
        json_dict = {"data": "testing"}
        self.logger.info(
            "STEP: Verify that the json_to_dict returns the same dictionary when provided with one."
        )
        json_dict_response = json_to_dict(json_dict)
        self.assertDictEqual(json_dict, json_dict_response)

    def test_register_iut_provider(self):
        """Test that the register backend can register iut providers.

        Approval criteria:
            - The register backend shall be able to register an IUT provider.

        Test steps:
            1. Register an IUT provider with the register backend.
            2. Verify that the IUT provider was stored in the database.
        """
        fake_database = FakeDatabase()
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        provider = {
            "iut": {
                "id": "iut_provider_test",
                "list": {"possible": [], "available": []},
            }
        }
        provider_registry = ProviderRegistry(etos, jsontas, fake_database)
        self.logger.info("STEP: Register an IUT provider with the register backend.")
        response = register(provider_registry, iut_provider=provider)

        self.logger.info(
            "STEP: Verify that the IUT provider was stored in the database."
        )
        stored_provider = json.loads(
            fake_database.reader.hget(
                "EnvironmentProvider:IUTProviders", "iut_provider_test"
            )
        )
        self.assertDictEqual(stored_provider, provider)
        self.assertTrue(response)

    def test_register_log_area_provider(self):
        """Test that the register backend can register log area providers.

        Approval criteria:
            - The register backend shall be able to register a log area provider.

        Test steps:
            1. Register a log area provider with the register backend.
            2. Verify that the log area provider was stored in the database.
        """
        fake_database = FakeDatabase()
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        provider = {
            "log": {
                "id": "log_area_provider_test",
                "list": {"available": [], "possible": []},
            }
        }
        provider_registry = ProviderRegistry(etos, jsontas, fake_database)
        self.logger.info(
            "STEP: Register a log area provider with the register backend."
        )
        response = register(provider_registry, log_area_provider=provider)

        self.logger.info(
            "STEP: Verify that the log area provider was stored in the database."
        )
        stored_provider = json.loads(
            fake_database.reader.hget(
                "EnvironmentProvider:LogAreaProviders", "log_area_provider_test"
            )
        )
        self.assertDictEqual(stored_provider, provider)
        self.assertTrue(response)

    def test_register_execution_space_provider(self):
        """Test that the register backend can register execution space providers.

        Approval criteria:
            - The register backend shall be able to register an execution space provider.

        Test steps:
            1. Register an execution space provider with the register backend.
            2. Verify that the execution space provider was stored in the database.
        """
        fake_database = FakeDatabase()
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        provider = {
            "execution_space": {
                "id": "execution_space_provider_test",
                "list": {"available": [{"identifier": "123"}], "possible": []},
            }
        }
        provider_registry = ProviderRegistry(etos, jsontas, fake_database)
        self.logger.info(
            "STEP: Register an execution space provider with the register backend."
        )
        response = register(provider_registry, execution_space_provider=provider)

        self.logger.info(
            "STEP: Verify that the execution space provider was stored in the database."
        )
        stored_provider = json.loads(
            fake_database.reader.hget(
                "EnvironmentProvider:ExecutionSpaceProviders",
                "execution_space_provider_test",
            )
        )
        self.assertDictEqual(stored_provider, provider)
        self.assertTrue(response)

    def test_register_all_providers(self):
        """Test that the register backend can register all providers.

        Approval criteria:
            - The register backend shall be able to register an all providers.

        Test steps:
            1. Register one of each provider with the register backend.
            2. Verify that the providers were stored in the database.
        """
        fake_database = FakeDatabase()
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
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
        provider_registry = ProviderRegistry(etos, jsontas, fake_database)
        self.logger.info(
            "STEP: Register one of each provider with the register backend."
        )
        response = register(
            provider_registry,
            iut_provider=test_iut_provider,
            log_area_provider=test_log_area_provider,
            execution_space_provider=test_execution_space_provider,
        )

        self.logger.info("STEP: Verify that the providers were stored in the database.")
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
        self.assertTrue(response)

    def test_register_provider_none(self):
        """Test that the register backend return false if no provider is supplied.

        Approval criteria:
            - The register backend shall return False if no provider is supplied.

        Test steps:
            1. Register no provider with the register backend.
            2. Verify that the register backend return False.
        """
        fake_database = FakeDatabase()
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        provider_registry = ProviderRegistry(etos, jsontas, fake_database)

        self.logger.info("STEP: Register no provider with the register backend.")
        response = register(provider_registry)

        self.logger.info("STEP: Verify that the register backend return False.")
        self.assertFalse(response)
