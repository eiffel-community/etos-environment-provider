# Copyright 2020-2021 Axis Communications AB.
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
import os
import json
import logging
from collections import OrderedDict
import jsonschema
from etos_lib.lib.database import Database
from environment_provider import BASE
from environment_provider.execution_space.execution_space_provider import (
    ExecutionSpaceProvider,
)
from environment_provider.iut.iut_provider import IutProvider
from environment_provider.logs.log_area_provider import LogAreaProvider


class ProviderRegistry:
    """Environment provider registry."""

    logger = logging.getLogger("Registry")

    def __init__(self, etos, jsontas):
        """Initialize with ETOS library, JsonTas and ETOS database.

        :param etos: ETOS library instance.
        :type etos: :obj:`etos_lib.etos.Etos`
        :param jsontas: JSONTas instance used to evaluate JSONTas structures.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        """
        self.etos = etos
        self.jsontas = jsontas
        self.etos.config.set("PROVIDERS", [])
        self.database = Database()

    def is_configured(self, suite_id):
        """Check that there is a configuration for the given suite ID.

        :param suite_id: Suite ID to check for configuration.
        :type suite_id: str
        :return: Whether or not a configuration exists for the suite ID.
        :rtype: bool
        """
        configuration = self.database.reader.hgetall(
            "EnvironmentProvider:{}".format(suite_id)
        )
        return bool(configuration)

    def wait_for_configuration(self, suite_id):
        """Wait for ProviderRegistry to become configured.

        :param suite_id: Suite ID to check for configuration.
        :type suite_id: str
        :return: Whether or not a configuration exists for the suite ID.
        :rtype: bool
        """
        generator = self.etos.utils.wait(self.is_configured, suite_id=suite_id)
        result = None
        for result in generator:
            if result:
                break
        return result

    def validate(self, provider, schema):
        """Validate a provider JSON against schema.

        :param provider: Provider JSON to validate.
        :type provider: dict
        :param schema: JSON schema to validate against.
        :type schema: str
        :return: Provider JSON that was validated.
        :rtype: dict
        """
        self.logger.debug(
            "Validating provider %r against %r", provider, os.path.join(BASE, schema)
        )
        with open(os.path.join(BASE, schema)) as schema_file:
            schema = json.load(schema_file)
        jsonschema.validate(instance=provider, schema=schema)
        return provider

    def get_log_area_provider_by_id(self, provider_id):
        """Get log area provider by name from the ETOS Database.

        Must have been registered with the /register endpoint.

        :param provider_id: ID of log area provider.
        :type provider_id: str
        :return: Provider JSON or None.
        :rtype: dict or None
        """
        self.logger.info("Getting log area provider %r", provider_id)
        provider = self.database.reader.hget(
            "EnvironmentProvider:LogAreaProviders", provider_id
        )
        self.logger.debug(provider)
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def get_iut_provider_by_id(self, provider_id):
        """Get IUT provider by name from the ETOS Database.

        Must have been registered with the /register endpoint.

        :param provider_id: ID of IUT provider.
        :type provider_id: str
        :return: Provider JSON or None.
        :rtype: dict or None
        """
        self.logger.info("Getting iut provider %r", provider_id)
        provider = self.database.reader.hget(
            "EnvironmentProvider:IUTProviders", provider_id
        )
        self.logger.debug(provider)
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def get_execution_space_provider_by_id(self, provider_id):
        """Get execution space provider by name from the ETOS Database.

        Must have been registered with the /register endpoint.

        :param provider_id: ID of execution space provider.
        :type provider_id: str
        :return: Provider JSON or None.
        :rtype: dict or None
        """
        self.logger.info("Getting execution space provider %r", provider_id)
        provider = self.database.reader.hget(
            "EnvironmentProvider:ExecutionSpaceProviders", provider_id
        )
        self.logger.debug(provider)
        if provider:
            return json.loads(provider, object_pairs_hook=OrderedDict)
        return None

    def register_log_area_provider(self, ruleset):
        """Register a new log area provider.

        :param ruleset: Log area JSON definition to register.
        :type ruleset: dict
        """
        schema = "logs/log_area_definition.json"
        data = self.validate(ruleset, schema)
        self.logger.info("Registering %r", data)
        self.database.writer.hdel(
            "EnvironmentProvider:LogAreaProviders", data["log"]["id"]
        )
        self.database.writer.hset(
            "EnvironmentProvider:LogAreaProviders", data["log"]["id"], json.dumps(data)
        )

    def register_iut_provider(self, ruleset):
        """Register a new IUT provider.

        :param ruleset: IUT provider JSON definition to register.
        :type ruleset: dict
        """
        schema = "iut/iut_definition.json"
        data = self.validate(ruleset, schema)
        self.logger.info("Registering %r", data)
        self.database.writer.hdel("EnvironmentProvider:IUTProviders", data["iut"]["id"])
        self.database.writer.hset(
            "EnvironmentProvider:IUTProviders", data["iut"]["id"], json.dumps(data)
        )

    def register_execution_space_provider(self, ruleset):
        """Register a new execution space provider.

        :param ruleset: Execution space provider JSON definition to register.
        :type ruleset: dict
        """
        schema = "execution_space/execution_space_definition.json"
        data = self.validate(ruleset, schema)
        self.logger.info("Registering %r", data)
        self.database.writer.hdel(
            "EnvironmentProvider:ExecutionSpaceProvider", data["execution_space"]["id"]
        )
        self.database.writer.hset(
            "EnvironmentProvider:ExecutionSpaceProviders",
            data["execution_space"]["id"],
            json.dumps(data),
        )

    def execution_space_provider(self, suite_id):
        """Get the execution space provider configured to suite ID.

        :param suite_id: Suite ID to get execution space provider for.
        :type suite_id: str
        :return: Execution space provider object.
        :rtype: :obj:`environment_provider.execution_space.ExecutionSpaceProvider`
        """
        provider_json = self.database.reader.hget(
            "EnvironmentProvider:{}".format(suite_id), "ExecutionSpaceProvider"
        )
        self.logger.info(provider_json)
        if provider_json:
            provider = ExecutionSpaceProvider(
                self.etos,
                self.jsontas,
                json.loads(provider_json, object_pairs_hook=OrderedDict).get(
                    "execution_space"
                ),
            )
            self.etos.config.get("PROVIDERS").append(provider)
            return provider
        return None

    def iut_provider(self, suite_id):
        """Get the IUT provider configured to suite ID.

        :param suite_id: Suite ID to get IUT provider for.
        :type suite_id: str
        :return: IUT provider object.
        :rtype: :obj:`environment_provider.iut.iut_provider.IutProvider`
        """
        provider_json = self.database.reader.hget(
            "EnvironmentProvider:{}".format(suite_id), "IUTProvider"
        )
        self.logger.info(provider_json)
        if provider_json:
            provider = IutProvider(
                self.etos,
                self.jsontas,
                json.loads(provider_json, object_pairs_hook=OrderedDict).get("iut"),
            )
            self.etos.config.get("PROVIDERS").append(provider)
            return provider
        return None

    def log_area_provider(self, suite_id):
        """Get the log area provider configured to suite ID.

        :param suite_id: Suite ID to get log area provider for.
        :type suite_id: str
        :return: Log area provider object.
        :rtype: :obj:`environment_provider.logs.log_area_provider.LogAreaProvider`
        """
        provider_json = self.database.reader.hget(
            "EnvironmentProvider:{}".format(suite_id), "LogAreaProvider"
        )
        self.logger.info(provider_json)
        if provider_json:
            provider = LogAreaProvider(
                self.etos,
                self.jsontas,
                json.loads(provider_json, object_pairs_hook=OrderedDict).get("log"),
            )
            self.etos.config.get("PROVIDERS").append(provider)
            return provider
        return None

    def dataset(self, suite_id):
        """Get the dataset configured to suite ID.

        :param suite_id: Suite ID to get dataset for.
        :type suite_id: str
        :return: Dataset JSON data.
        :rtype: dict
        """
        dataset = self.database.reader.hget(
            "EnvironmentProvider:{}".format(suite_id), "Dataset"
        )
        if dataset:
            return json.loads(dataset)
        return None

    # pylint:disable=too-many-arguments
    def configure_environment_provider_for_suite(
        self,
        suite_id,
        iut_provider,
        log_area_provider,
        execution_space_provider,
        dataset,
    ):
        """Configure environment provider for a suite ID with providers and dataset.

        :param suite_id: Suite ID to configure providers for.
        :type suite_id: dict
        :param iut_provider: IUT provider definition to configure for suite ID.
        :type iut_provider: dict
        :param log_area_provider: Log area provider definition to configure for suite ID.
        :type log_area_provider: dict
        :param execution_space_provider: Execution space provider definition to configure
                                         for suite ID.
        :type execution_space_provider: dict
        :param dataset: Dataset to configure for suite ID.
        :type dataset: dict
        """
        self.logger.info("Configuring environment provider.")
        self.logger.info("Dataset: %r", dataset)
        self.logger.info("IUT provider: %r", iut_provider.get("iut", {}).get("id"))
        self.logger.info(
            "Execution space provider: %r",
            execution_space_provider.get("execution_space", {}).get("id"),
        )
        self.logger.info(
            "Log area provider: %r", log_area_provider.get("log", {}).get("id")
        )
        self.logger.info("Expire: 3600")
        self.database.writer.hset(
            "EnvironmentProvider:{}".format(suite_id), "Dataset", json.dumps(dataset)
        )
        self.database.writer.hset(
            "EnvironmentProvider:{}".format(suite_id),
            "IUTProvider",
            json.dumps(iut_provider),
        )
        self.database.writer.hset(
            "EnvironmentProvider:{}".format(suite_id),
            "ExecutionSpaceProvider",
            json.dumps(execution_space_provider),
        )
        self.database.writer.hset(
            "EnvironmentProvider:{}".format(suite_id),
            "LogAreaProvider",
            json.dumps(log_area_provider),
        )
        self.database.writer.expire("EnvironmentProvider:{}".format(suite_id), 3600)
