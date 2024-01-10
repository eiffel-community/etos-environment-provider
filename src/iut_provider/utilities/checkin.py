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
"""IUT provider check in module."""
import logging

from jsontas.jsontas import JsonTas

from ..exceptions import IutCheckinFailed
from ..iut import Iut


class Checkin:
    """Handle checking in IUTs to an IUT provider."""

    logger = logging.getLogger("IUTProvider - Checkin")

    def __init__(self, jsontas: JsonTas, checkin_ruleset: dict) -> None:
        """Initialize IUT checkin handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkin_ruleset: JSONTas ruleset for checking in IUTs.
        """
        self.checkin_ruleset = checkin_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def checkin(self, iut: Iut) -> None:
        """Check in a single IUT, returning it to the IUT provider.

        :raises: IutCheckinFailed: If checkin failed due to any reason.
                                   Reason is added to exception.

        :param iut: IUT to checkin.
        """
        # Definition does not have the 'checkin' key. Just return.
        if self.checkin_ruleset is None:
            self.logger.info("No defined checkin rule.")
            return

        self.logger.info("Checking in IUT %r", iut)
        self.dataset.add("iut", iut)
        verified = self.jsontas.run(self.checkin_ruleset)
        if not verified:
            raise IutCheckinFailed(f"Unable to checkin {iut}")

        try:
            self.dataset.get("iuts", []).remove(iut)
        except ValueError:
            pass

    def checkin_all(self) -> None:
        """Checkin all checked out IUTs."""
        self.logger.info("Checking in all checked out IUTs.")
        for iut in reversed(self.dataset.get("iuts", [])):
            try:
                self.checkin(iut)
            except IutCheckinFailed as exception:
                self.logger.error("%r", exception)
