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
"""IUT provider list module."""
import logging

from jsontas.jsontas import JsonTas
from packageurl import PackageURL

from ..exceptions import IutNotAvailable, NoIutFound
from ..iut import Iut


class List:  # pylint:disable=too-few-public-methods
    """Handle the listing of available items under test (IUTs) (or a static list of IUTs)."""

    logger = logging.getLogger("IUTProvider - List")

    def __init__(self, iut_id: str, jsontas: JsonTas, list_ruleset: dict) -> None:
        """Initialize IUT list handler.

        :param iut_id: ID of IUT provider that is being used.
        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param list_ruleset: JSONTas ruleset for listing IUTs.
        """
        self.list_ruleset = list_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset
        self.id = iut_id  # pylint:disable=invalid-name

    def list(self, identity: PackageURL, amount: int) -> list[Iut]:
        """List available IUTs.

        Possible IUTs are the IUTs that were found in the provider but are not yet available
        for use.
        Available IUTs are IUTs that are available for use.

        If there are no possible IUTs, raise NoIutFound exception, telling the IUT provider
        that there is no need to continue.
        If there are no available IUTs, raise IutNotAvailable exception, telling the IUT provider
        to wait for one to become available.

        :raises: NoIutFound: If there are no IUTs at all in the pool.
        :raises: IutNotAvailable: If there are IUTs, but not available yet.

        :param identity: Identity of IUT.
        :param amount: Number of IUTs to list.
        :return: Available IUTs in the IUT provider.
        """
        self.dataset.add("amount", amount)
        iuts = self.jsontas.run(self.list_ruleset)
        possible_iuts = iuts.get("possible")

        self.logger.debug("Number of possible IUTs available: %r", len(possible_iuts))
        if not possible_iuts:
            raise NoIutFound()

        available_iuts = iuts.get("available")

        self.logger.debug("Number of actual IUTs available: %r", len(available_iuts))
        if not available_iuts:
            raise IutNotAvailable()
        return [
            Iut(provider_id=self.id, identity=identity, **iut) for iut in available_iuts[:amount]
        ]
