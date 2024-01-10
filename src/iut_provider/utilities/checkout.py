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
"""IUT provider checkout module."""
import logging
from copy import deepcopy

from jsontas.jsontas import JsonTas

from ..exceptions import IutCheckoutFailed
from ..iut import Iut


class Checkout:  # pylint:disable=too-few-public-methods
    """Handle checking out IUTs from an IUT provider."""

    logger = logging.getLogger("IUTProvider - Checkout")

    def __init__(self, jsontas: JsonTas, checkout_ruleset: dict) -> None:
        """Initialize IUT checkout handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param checkout_ruleset: JSONTas ruleset for checking out IUTs.
        """
        self.checkout_ruleset = checkout_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def checkout(self, iuts: list[Iut]) -> list[Iut]:
        """Checkout a number of IUTs from an IUT provider.

        :raises: IutCheckoutFailed: If checkout failed due to any reason.
                                    Reason is added to exception.

        :param iuts: IUTs to checkout.
        :return: Checked out IUTs.
        """
        # Definition does not have the 'checkout' key. Just return IUTs provided.
        if not self.checkout_ruleset:
            self.logger.info("No defined checkout rule.")
            self.dataset.add("iuts", iuts)
            return iuts

        fail_message = ""
        for iut in reversed(iuts):
            self.logger.debug("Checking out IUT %r.", iut)
            self.dataset.add("iut", iut)
            response = self.jsontas.run(self.checkout_ruleset)
            if isinstance(response, dict):
                iut.update(**response)
            else:
                fail_message = response
                self.logger.error("Unable to checkout %r Reason %r.", iut, fail_message)
                iuts.remove(iut)
        self.dataset.add("iuts", deepcopy(iuts))
        if not iuts:
            raise IutCheckoutFailed(f"All IUTs failed checkout. {fail_message}")
        return iuts
