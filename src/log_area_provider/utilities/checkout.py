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
"""Log area provider checkout module."""
import logging
from copy import deepcopy

from jsontas.jsontas import JsonTas

from ..exceptions import LogAreaCheckoutFailed
from ..log_area import LogArea


class Checkout:  # pylint:disable=too-few-public-methods
    """Handle checking out log areas from an log area provider."""

    logger = logging.getLogger("LogAreaProvider - Checkout")

    def __init__(self, jsontas: JsonTas, checkout_ruleset: dict) -> None:
        """Initialize log area checkout handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkin_ruleset: JSONTas ruleset for checking out log areas.
        """
        self.checkout_ruleset = checkout_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def checkout(self, log_areas: list[LogArea]) -> list[LogArea]:
        """Checkout a number of log areas from an log area provider.

        :raises: LogAreaCheckoutFailed: If checkout failed due to any reason.
                                        Reason is added to exception.

        :param log_areas: Log areas to checkout.
        :return: Checked out log areas.
        """
        # Definition does not have the 'checkout' key. Just return log areas provided.
        if not self.checkout_ruleset:
            self.logger.info("No defined checkout rule.")
            self.dataset.add("log_areas", log_areas)
            return log_areas

        fail_message = ""
        for log_area in reversed(log_areas):
            self.logger.debug("Checking out log area %r.", log_area)
            self.dataset.add("log_area", log_area)
            response = self.jsontas.run(self.checkout_ruleset)
            if isinstance(response, dict):
                log_area.update(**response)
            else:
                fail_message = response
                self.logger.error("Unable to checkout %r.", log_area)
                log_areas.remove(log_area)
        self.dataset.add("log_areas", deepcopy(log_areas))
        if not log_areas:
            raise LogAreaCheckoutFailed(f"All LogAreas failed checkout. {fail_message}")
        return log_areas
