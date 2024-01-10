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
"""Log area provider list module."""
import logging

from jsontas.jsontas import JsonTas

from ..exceptions import LogAreaNotAvailable, NoLogAreaFound
from ..log_area import LogArea


class List:  # pylint:disable=too-few-public-methods
    """Handle the listing of available log areas (or a static list of log areas)."""

    logger = logging.getLogger("LogAreaProvider - List")

    def __init__(self, log_area_id: str, jsontas: JsonTas, list_ruleset: dict) -> None:
        """Initialize log area list handler.

        :param log_area_id: ID of log area provider that is being used.
        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkin_ruleset: JSONTas ruleset for listing log areas.
        """
        self.list_ruleset = list_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset
        self.id = log_area_id  # pylint:disable=invalid-name

    def list(self, amount: int) -> list[LogArea]:
        """List available log areas.

        Possible log areas are the log areas that were found in the provider but are not yet
        available for use.
        Available log areas are log areas that are available for use.

        If there are no possible log areas, raise NoLogAreaFound exception,
        telling the log area provider that there is no need to continue.
        If there are no available log areas, raise LogAreaNotAvailable exception,
        telling the log area provider to wait for one to become available.

        :raises: NoLogAreaFound: If there are no log areas at all in the pool.
        :raises: LogAreaNotAvailable: If there are log areas, but not available yet.

        :param amount: Number of log areas to list.
        :return: Available log areas in the log area provider.
        """
        self.dataset.add("amount", amount)
        log_areas = self.jsontas.run(self.list_ruleset)
        possible_log_areas = log_areas.get("possible")

        self.logger.debug("Number of possible log areas available: %r", len(possible_log_areas))
        if not possible_log_areas:
            raise NoLogAreaFound()

        available_log_areas = log_areas.get("available")

        self.logger.debug("Number of actual log areas available: %r", len(available_log_areas))
        if not available_log_areas:
            raise LogAreaNotAvailable()
        return [
            LogArea(provider_id=self.id, **log_area) for log_area in available_log_areas[:amount]
        ]
