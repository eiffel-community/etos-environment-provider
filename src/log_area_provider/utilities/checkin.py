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
"""Log area provider check in module."""
import logging

from jsontas.jsontas import JsonTas

from ..exceptions import LogAreaCheckinFailed
from ..log_area import LogArea


class Checkin:
    """Handle checking in log areas to an log area provider."""

    logger = logging.getLogger("LogAreaProvider - Checkin")

    def __init__(self, jsontas: JsonTas, checkin_ruleset: dict) -> None:
        """Initialize log area checkin handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkin_ruleset: JSONTas ruleset for checking in log areas.
        """
        self.checkin_ruleset = checkin_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def checkin(self, log_area: LogArea) -> None:
        """Check in a single log area, returning it to the log area provider.

        :raises: LogAreaCheckinFailed: If checkin failed due to any reason.
                                       Reason is added to exception.

        :param log_area: log area to checkin.
        """
        # Definition does not have the 'checkin' key. Just return.
        if self.checkin_ruleset is None:
            self.logger.info("No defined checkin rule.")
            return

        self.logger.info("Checking in log area %r", log_area)
        self.dataset.add("log_area", log_area)
        verified = self.jsontas.run(self.checkin_ruleset)
        if not verified:
            raise LogAreaCheckinFailed(f"Unable to checkin {log_area}")
        try:
            self.dataset.get("log_areas", []).remove(log_area)
        except ValueError:
            pass

    def checkin_all(self) -> None:
        """Checkin all checked out log areas."""
        self.logger.info("Checking in all checked out log areas.")
        for log_area in reversed(self.dataset.get("log_areas", [])):
            try:
                self.checkin(log_area)
            except LogAreaCheckinFailed as exception:
                self.logger.error("%r", exception)
