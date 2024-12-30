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

    def __init__(self, etos: ETOS, jsontas: JsonTas):
        """Initialize with ETOS library, JsonTas and ETOS database.

        :param etos: ETOS library instance.
        :param jsontas: JSONTas instance used to evaluate JSONTas structures.
        """
        self.etos = etos
        self.jsontas = jsontas
        self.etos.config.set("PROVIDERS", [])
        self.request = None
        self.suite_id = None

    def with_suite_id(self, suite_id) -> "ProviderRegistry":
        """Initialize the provider registry with a suite id.

        :param suite_id: The suite ID for an ETOS testrun. If not set, testrun operations will not work.
        """
        self.logger.info(f"Initializing with suite id: {suite_id}")
        if not suite_id:
            raise ValueError("Suite id not set!")
        self.suite_id = suite_id
        return self

    def with_environment_request(self, request: "EnvironmentRequest") -> "ProviderRegistry":
        """Initialize the provider registry with an environment request.

        :param request: environment request.
        """
        self.logger.info(f"Initializing with env request: {request}")
        if not request:
            raise ValueError("Environment request not set!")
        self.request = request
        self.suite_id = self.request.spec.identifier
        return self

    def is_configured(self) -> bool:
        """Check that there is a configuration for the given suite ID.

        :return: Whether or not a configuration exists for the suite ID.
        """
        if self.suite_id:
            key = f"/testrun/{self.suite_id}/provider"
            self.logger.info(f"Reading etcd key: {key}") # TODO: remove
            return bool(ETCDPath(key).read_all())
        else:
            base_key = f"/environment/provider"
            # check that at least one provider of each type is registered:
            for _key in ("execution-space", "iut", "log-area"):
                key = f"{base_key}/{_key}/default" # TODO: fix
                self.logger.info(f"Reading etcd key: {key}") # TODO: remove
                if not bool(ETCDPath(key).read_all()):
                    self.logger.info(f"Reading etcd key {key} returned False") # TODO: remove
                    return False
        return True

    def _get_provider(self, provider_type):
        if provider_type not in ("log-area", "execution-space", "iut"):
            raise ValueError(f"Unknown provider type: {provider_type}")
        if self.request.spec.identifier is not None:
            key = f"/testrun/{self.request.spec.identifier}/provider/{provider_type}"
            return ETCDPath(key).read()

        providers = self.request.spec.providers
        prefix = f"/environment/provider/{provider_type}"
        key = ""
        if provider_type == "execution-space":
            key =  f"{prefix}/{providers.executionSpace.id}"
        elif provider_type == "iut":
            key = f"{prefix}/{providers.iut.id}"
        elif provider_type == "log-area":
            key = f"{prefix}/{providers.logArea.id}"

        # TODO: fix matching of provider ids from environment request to the registered providers
        key = f"{prefix}/default"
        provider = ETCDPath(key).read()
        return provider

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
        provider = self._get_provider("log-area")
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def get_iut_provider(self) -> Optional[dict]:
        """Get IUT provider for testrun from the ETOS Database.

        :return: Provider JSON or None.
        """
        provider = self._get_provider("iut")
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def get_execution_space_provider(self) -> Optional[dict]:
        """Get execution space provider by name from the ETOS Database.

        :return: Provider JSON or None.
        """
        provider = self._get_provider("execution-space")
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def execution_space_provider(self) -> Optional[ExecutionSpaceProvider]:
        """Get the execution space provider configured to suite ID.

        :return: Execution space provider object.
        """
        provider_json = self._get_provider("execution-space")
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
        provider_json = self._get_provider("iut")
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
        provider_json = self._get_provider("log-area")
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
        if self.request.spec.identifier:
            dataset = ETCDPath(f"/testrun/{self.request.spec.identifier}/provider/dataset").read()
        else:
            dataset = self.jsontas.dataset  # TODO: fix
        if dataset:
            return json.loads(dataset)
        return None
