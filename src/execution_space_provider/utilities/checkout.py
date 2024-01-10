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
"""Execution space checkout module."""
import logging
from copy import deepcopy

from jsontas.jsontas import JsonTas

from ..exceptions import ExecutionSpaceCheckoutFailed
from ..execution_space import ExecutionSpace


class Checkout:  # pylint:disable=too-few-public-methods
    """Handle checking out execution spaces from an execution space provider."""

    logger = logging.getLogger("ExecutionSpaceProvider - Checkout")

    def __init__(self, jsontas: JsonTas, checkout_ruleset: dict) -> None:
        """Initialize execution space checkout handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkout_ruleset: JSONTas ruleset for checking out execution spaces.
        """
        self.checkout_ruleset = checkout_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def checkout(self, execution_spaces: list[ExecutionSpace]) -> list[ExecutionSpace]:
        """Checkout a number of execution spaces from an execution space provider.

        :raises: ExecutionSpaceCheckoutFailed: If checkout failed due to any reason.
                                               Reason is added to exception.

        :param execution_spaces: Execution spaces to checkout.
        :return: Checked out execution spaces.
        """
        # Definition does not have the 'checkout' key. Just return execution spaces provided.
        if not self.checkout_ruleset:
            self.logger.info("No defined checkout rule.")
            self.dataset.add("execution_spaces", execution_spaces)
            return execution_spaces

        fail_message = ""
        for execution_space in reversed(execution_spaces):
            self.logger.debug("Checking out execution space %r.", execution_space)
            self.dataset.add("execution_space", execution_space)
            response = self.jsontas.run(self.checkout_ruleset)
            if isinstance(response, dict):
                execution_space.update(**response)
            else:
                fail_message = response
                self.logger.error("Unable to checkout %r.", execution_space)
                execution_spaces.remove(execution_space)
        self.dataset.add("execution_spaces", deepcopy(execution_spaces))
        if not execution_spaces:
            raise ExecutionSpaceCheckoutFailed(
                f"All ExecutionSpaces failed checkout. {fail_message}"
            )
        return execution_spaces
