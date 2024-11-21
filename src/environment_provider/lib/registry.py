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
"""ETOS Environment Provider registry module."""
import json
import logging
from collections import OrderedDict
from typing import Optional

import jsonschema
from etos_lib.etos import ETOS
from jsontas.jsontas import JsonTas

from execution_space_provider import ExecutionSpaceProvider
from iut_provider import IutProvider
from log_area_provider import LogAreaProvider

from .database import ETCDPath


class ProviderRegistry:
    """Environment provider registry."""

    logger = logging.getLogger("Registry")

    def __init__(self, etos: ETOS, jsontas: JsonTas, suite_id: Optional[str]) -> None:
        """Initialize with ETOS library, JsonTas and ETOS database.

        :param etos: ETOS library instance.
        :param jsontas: JSONTas instance used to evaluate JSONTas structures.
        :param suite_id: The suite ID for an ETOS testrun. If not set, testrun operations will not
                         work.
        """
        self.etos = etos
        self.jsontas = jsontas
        self.testrun = ETCDPath(f"/testrun/{suite_id}")
        if suite_id is None:
            # Results in exceptions if trying to use testrun without suite ID set. Otherwise
            # there's a big risk of writing data on bogus keys in the database.
            self.testrun = None
        self.providers = ETCDPath("/environment/provider")
        self.etos.config.set("PROVIDERS", [])

    def is_configured(self) -> bool:
        """Check that there is a configuration for the given suite ID.

        :return: Whether or not a configuration exists for the suite ID.
        """
        configuration = self.testrun.join("provider").read_all()
        return bool(configuration)

    def wait_for_configuration(self) -> bool:
        """Wait for ProviderRegistry to become configured.

        :return: Whether or not a configuration exists for the suite ID.
        """
        generator = self.etos.utils.wait(self.is_configured)
        result = None
        for result in generator:
            if result:
                break
        return result

    def validate(self, provider: dict, schema: str) -> dict:
        """Validate a provider JSON against schema.

        :param provider: Provider JSON to validate.
        :param schema: JSON schema to validate against.
        :return: Provider JSON that was validated.
        """
        self.logger.debug("Validating provider %r against %r", provider, schema)
        with open(schema, encoding="UTF-8") as schema_file:
            schema = json.load(schema_file)
        jsonschema.validate(instance=provider, schema=schema)
        return provider

    def get_log_area_provider(self) -> Optional[dict]:
        """Get log area provider for a testrun from the ETOS Database.

        :return: Provider JSON or None.
        """
        if self.testrun is None:
            self.logger.error(
                "Could not retrieve log area provider from database, testrun is not set."
            )
            return None
        provider = self.testrun.join("provider/log-area").read()
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def get_iut_provider(self) -> Optional[dict]:
        """Get IUT provider for testrun from the ETOS Database.

        :return: Provider JSON or None.
        """
        if self.testrun is None:
            self.logger.error("Could not retrieve IUT provider from database, testrun is not set.")
            return None
        provider = self.testrun.join("provider/iut").read()
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def get_execution_space_provider(self) -> Optional[dict]:
        """Get execution space provider by name from the ETOS Database.

        :return: Provider JSON or None.
        """
        if self.testrun is None:
            self.logger.error(
                "Could not retrieve execution space provider from database, testrun is not set."
            )
            return None
        provider = self.testrun.join("provider/execution-space").read()
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def execution_space_provider(self) -> Optional[ExecutionSpaceProvider]:
        """Get the execution space provider configured to suite ID.

        :return: Execution space provider object.
        """
        provider_json = self.testrun.join("provider/execution-space").read()
        if provider_json:
            provider = ExecutionSpaceProvider(
                self.etos,
                self.jsontas,
                json.loads(provider_json, object_pairs_hook=OrderedDict).get("execution_space"),
            )
            self.etos.config.get("PROVIDERS").append(provider)
            return provider
        return None

    def iut_provider(self) -> Optional[IutProvider]:
        """Get the IUT provider configured to suite ID.

        :return: IUT provider object.
        """
        provider_json = self.testrun.join("provider/iut").read()
        if provider_json:
            provider = IutProvider(
                self.etos,
                self.jsontas,
                json.loads(provider_json, object_pairs_hook=OrderedDict).get("iut"),
            )
            self.etos.config.get("PROVIDERS").append(provider)
            return provider
        return None

    def log_area_provider(self) -> Optional[LogAreaProvider]:
        """Get the log area provider configured to suite ID.

        :return: Log area provider object.
        """
        provider_json = self.testrun.join("provider/log-area").read()
        if provider_json:
            provider = LogAreaProvider(
                self.etos,
                self.jsontas,
                json.loads(provider_json, object_pairs_hook=OrderedDict).get("log"),
            )
            self.etos.config.get("PROVIDERS").append(provider)
            return provider
        return None

    def dataset(self) -> Optional[dict]:
        """Get the dataset configured to suite ID.

        :return: Dataset JSON data.
        """
        dataset = self.testrun.join("provider/dataset").read()
        if dataset:
            return json.loads(dataset)
        return None
