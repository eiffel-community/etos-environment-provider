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
"""Execution space check in module."""
import logging

from jsontas.jsontas import JsonTas

from ..exceptions import ExecutionSpaceCheckinFailed
from ..execution_space import ExecutionSpace


class Checkin:
    """Handle checking in execution spaces to an execution space provider."""

    logger = logging.getLogger("ExecutionSpaceProvider - Checkin")

    def __init__(self, jsontas: JsonTas, checkin_ruleset: dict) -> None:
        """Initialize execution space checkin handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkin_ruleset: JSONTas ruleset for checking in execution spaces.
        """
        self.checkin_ruleset = checkin_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def checkin(self, execution_space: ExecutionSpace) -> None:
        """Check in a single execution space, returning it to the execution space provider.

        :raises: ExecutionSpaceCheckinFailed: If checkin failed due to any reason.
                                              Reason is added to exception.

        :param execution_space: Execution space to checkin.
        """
        # Definition does not have the 'checkin' key. Just return.
        if self.checkin_ruleset is None:
            self.logger.info("No defined checkin rule.")
            return

        self.logger.info("Checking in execution space %r", execution_space)
        self.dataset.add("execution_space", execution_space)
        verified = self.jsontas.run(self.checkin_ruleset)
        if not verified:
            raise ExecutionSpaceCheckinFailed(f"Unable to checkin {execution_space}")
        try:
            self.dataset.get("execution_spaces", []).remove(execution_space)
        except ValueError:
            pass

    def checkin_all(self) -> None:
        """Checkin all checked out execution spaces."""
        self.logger.info("Checking in all checked out execution spaces.")
        for execution_space in reversed(self.dataset.get("execution_spaces", [])):
            try:
                self.checkin(execution_space)
            except ExecutionSpaceCheckinFailed as exception:
                self.logger.error("%r", exception)
