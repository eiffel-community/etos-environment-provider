# Copyright 2020-2021 Axis Communications AB.
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
"""IUT provider module."""
import logging
import time
from environment_provider.iut.list import List
from environment_provider.iut.checkout import Checkout
from environment_provider.iut.checkin import Checkin
from environment_provider.iut.prepare import Prepare
from .exceptions import (
    NoIutFound,
    IutNotAvailable,
    IutCheckoutFailed,
    NotEnoughIutsAvailable,
)


class IutProvider:
    """Item under test (IUT) provider."""

    logger = logging.getLogger("IUTProvider")

    def __init__(self, etos, jsontas, ruleset):
        """Initialize IUT provider.

        :param etos: ETOS library instance.
        :type etos: :obj:`etos_lib.etos.Etos`
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        :param ruleset: JSONTas ruleset for handling IUTs.
        :type ruleset: dict
        """
        self.etos = etos
        self.etos.config.set("iuts", [])
        self.jsontas = jsontas
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.logger.info("Initialized IUT provider %r", self.id)

    @property
    def identity(self):
        """IUT Identity.

        :return: IUT identity as PURL object.
        :rtype: :obj:`packageurl.PackageURL`
        """
        return self.jsontas.dataset.get("identity")

    def checkout(self, available_iuts):
        """Checkout a number of IUTs from an IUT provider.

        :param available_iuts: IUTs to checkout.
        :type available_iuts: list
        :return: Checked out IUTs.
        :rtype: list
        """
        checkout_iuts = Checkout(self.jsontas, self.ruleset.get("checkout"))
        return checkout_iuts.checkout(available_iuts)

    def list(self, amount):
        """List IUTs in order to find out which are available or not.

        :param amount: Number of IUTs to list.
        :type amount: int
        :return: Available IUTs in the IUT provider.
        :rtype: list
        """
        list_iuts = List(self.id, self.jsontas, self.ruleset.get("list"))
        return list_iuts.list(self.identity, amount)

    def checkin_all(self):
        """Check in all checked out IUTs."""
        checkin_iuts = Checkin(self.jsontas, self.ruleset.get("checkin"))
        checkin_iuts.checkin_all()

    def checkin(self, iut):
        """Check in a single IUT, returning it to the IUT provider.

        :param iut: IUT to checkin.
        :type iut: :obj:`environment_provider.iut.iut.Iut`
        """
        checkin_iuts = Checkin(self.jsontas, self.ruleset.get("checkin"))
        checkin_iuts.checkin(iut)

    def prepare(self, iuts):
        """Prepare all IUTs in the IUT provider.

        :param iuts: IUTs to prepare.
        :type iuts: list
        :return: Prepared IUTs
        :rtype: list
        """
        prepare_iuts = Prepare(self.jsontas, self.ruleset.get("prepare"))
        return prepare_iuts.prepare(iuts)

    # pylint: disable=too-many-branches
    def wait_for_and_checkout_iuts(self, minimum_amount=0, maximum_amount=100):
        """Wait for and checkout IUTs from an IUT provider.

        :raises: IutNotAvailable: If there are no available IUTs after timeout.

        :param minimum_amount: Minimum amount of IUTs to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of IUTs to checkout.
        :type maximum_amount: int
        :return: List of checked out IUTs.
        :rtype: list
        """
        timeout = time.time() + self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
        fail_reason = ""
        prepared_iuts = []
        while time.time() < timeout:
            time.sleep(5)
            try:
                available_iuts = self.list(maximum_amount)
                self.logger.info("Available IUTs:")
                for iut in available_iuts:
                    self.logger.info(iut)
                if len(available_iuts) < minimum_amount:
                    self.logger.critical(
                        "Not enough available IUTs %r in the IUT provider!",
                        self.identity.to_string(),
                    )
                    raise NotEnoughIutsAvailable(self.identity.to_string())

                checked_out_iuts = self.checkout(available_iuts)
                self.logger.info("Checked out IUTs:")
                for iut in checked_out_iuts:
                    self.logger.info(iut)
                if len(checked_out_iuts) < minimum_amount:
                    raise IutNotAvailable(self.identity.to_string())

                prepared_iuts, unprepared_iuts = self.prepare(checked_out_iuts)

                for iut in unprepared_iuts:
                    self.checkin(iut)
                self.logger.info("Prepared IUTs:")
                for iut in prepared_iuts:
                    self.logger.info(iut)
                if len(prepared_iuts) < minimum_amount:
                    raise IutNotAvailable(
                        f"Preparation of {self.identity.to_string()} failed"
                    )
                break
            except NoIutFound:
                self.logger.critical(
                    "%r does not exist in the IUT provider!", self.identity.to_string()
                )
                prepared_iuts = []
                break
            except IutNotAvailable:
                self.logger.warning("IUT %r is not available yet.", self.identity)
                continue
            except IutCheckoutFailed as checkout_failed:
                fail_reason = str(checkout_failed)
                self.logger.critical(
                    "Checkout of %r failed with reason %r!",
                    self.identity.to_string(),
                    checkout_failed,
                )
                self.checkin_all()
                prepared_iuts = []
                break
        else:
            self.logger.error(
                "IUT %r did not become available in %rs",
                self.identity.to_string(),
                self.etos.config.get("WAIT_FOR_IUT_TIMEOUT"),
            )
            prepared_iuts = []
        if len(prepared_iuts) < minimum_amount:
            message = (
                f"Failed to checkout {self.identity.to_string()}. Reason: {fail_reason}"
            )
            raise IutNotAvailable(message)
        return prepared_iuts
