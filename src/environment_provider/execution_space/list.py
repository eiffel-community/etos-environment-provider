# Copyright 2020 Axis Communications AB.
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
"""Execution space list module."""
import logging
from .execution_space import ExecutionSpace
from .exceptions import NoExecutionSpaceFound, ExecutionSpaceNotAvailable
from .instructions import Instructions


class List:  # pylint:disable=too-few-public-methods
    """Handle the listing of available execution spaces (or a static list of execution spaces)."""

    logger = logging.getLogger("ExecutionSpaceProvider - List")

    def __init__(self, execution_space_id, etos, jsontas, list_ruleset):
        """Initialize execution space list handler.

        :param execution_space_id: ID of execution space provider that is being used.
        :type execution_space_id: str
        :param etos: ETOS library instance.
        :type etos: :obj:`etos_lib.etos.ETOS`
        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        :param list_ruleset: JSONTas ruleset for listing execution spaces.
        :type list_ruleset: dict
        """
        self.list_ruleset = list_ruleset
        self.etos = etos
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset
        self.add_instructions()
        self.dataset.add("execution_space_instructions", Instructions)
        self.id = execution_space_id  # pylint:disable=invalid-name

    def add_instructions(self):
        """Add execution space spin-up instructions."""
        rabbitmq = self.etos.config.get("rabbitmq")
        self.dataset.add(
            "instructions",
            {
                "image": self.dataset.get("test_runner"),
                "environment": {
                    "RABBITMQ_HOST": rabbitmq.get("host"),
                    "RABBITMQ_USERNAME": rabbitmq.get("username"),
                    "RABBITMQ_PASSWORD": rabbitmq.get("password"),
                    "RABBITMQ_EXCHANGE": rabbitmq.get("exchange"),
                    "RABBITMQ_PORT": rabbitmq.get("port"),
                    "RABBITMQ_VHOST": rabbitmq.get("vhost"),
                    "RABBITMQ_SSL": rabbitmq.get("ssl"),
                    "SOURCE_HOST": self.etos.config.get("source").get("host"),
                    "ETOS_GRAPHQL_SERVER": self.etos.debug.graphql_server,
                    "ETOS_API": self.etos.debug.etos_api,
                    "ETOS_ENVIRONMENT_PROVIDER": self.etos.debug.environment_provider,
                },
                "parameters": {},
            },
        )

    def list(self, amount):
        """List available execution spaces.

        Possible execution spaces are the execution spaces that were found in the provider
        but are not yet available for use.
        Available execution spaces are execution spaces that are available for use.

        If there are no possible execution spaces, raise NoExecutionSpaceFound exception,
        telling the execution space provider that there is no need to continue.
        If there are no available, raise ExecutionSpaceNotAvailable exception,
        telling the execution space provider to wait for one to become available.

        :raises: NoExecutionSpaceFound: If there are no execution spaces at all in the pool.
        :raises: ExecutionSpaceNotAvailable: If there are execution spaces, but not available yet.

        :param amount: Number of execution spaces to list.
        :type amount: int
        :return: Available execution spaces in the execution space provider.
        :rtype: list
        """
        self.dataset.add("amount", amount)
        execution_spaces = self.jsontas.run(self.list_ruleset)
        possible_execution_spaces = execution_spaces.get("possible")

        self.logger.debug(
            "Number of possible execution spaces available: %r",
            len(possible_execution_spaces),
        )
        if not possible_execution_spaces:
            raise NoExecutionSpaceFound()

        available_execution_spaces = execution_spaces.get("available")

        self.logger.debug(
            "Number of actual execution spaces available: %r",
            len(available_execution_spaces),
        )
        if not available_execution_spaces:
            raise ExecutionSpaceNotAvailable()

        return [
            ExecutionSpace(provider_id=self.id, **execution_space)
            for execution_space in available_execution_spaces
        ]
