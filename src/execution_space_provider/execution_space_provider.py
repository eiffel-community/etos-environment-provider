# Copyright 2020-2022 Axis Communications AB.
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
"""Execution space provider module."""
from abc import abstractmethod
from typing import Union

from etos_lib import ETOS
from jsontas.jsontas import JsonTas

from .execution_space import ExecutionSpace
from .utilities.external_provider import ExternalProvider
from .utilities.jsontas_provider import JSONTasProvider


class ExecutionSpaceProvider:
    """Execution space provider."""

    id = "Undefined"

    def __new__(
        cls, etos: ETOS, jsontas: JsonTas, ruleset: dict
    ) -> Union[ExternalProvider, JSONTasProvider]:
        """Check which type of provider and return an appropriate one."""
        if ruleset.get("type", "jsontas") == "external":
            return ExternalProvider(etos, jsontas, ruleset)
        else:
            return JSONTasProvider(etos, jsontas, ruleset)

    @abstractmethod
    def checkin(self, execution_space: ExecutionSpace) -> None:
        """Check in a single execution space, returning it to the execution space provider.

        :param execution_space: Execution space to checkin.
        """

    @abstractmethod
    def checkin_all(self) -> None:
        """Check in all checked out execution spaces."""

    @abstractmethod
    def wait_for_and_checkout_execution_spaces(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[ExecutionSpace]:
        """Wait for and checkout execution spaces from an execution space provider.

        :raises: ExecutionSpaceNotAvailable: If there are no available execution spaces after
                                             timeout.

        :param minimum_amount: Minimum amount of execution spaces to checkout.
        :param maximum_amount: Maximum amount of execution spaces to checkout.
        :return: List of checked out execution spaces.
        """
