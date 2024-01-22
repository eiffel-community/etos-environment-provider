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
"""IUT provider utilizing JSONTas."""
import logging
import time

from etos_lib import ETOS
from jsontas.jsontas import JsonTas
from packageurl import PackageURL

from ..exceptions import IutCheckoutFailed, IutNotAvailable, NoIutFound, NotEnoughIutsAvailable
from ..iut import Iut
from .checkin import Checkin
from .checkout import Checkout
from .list import List
from .prepare import Prepare


class JSONTasProvider:
    """Item under test (IUT) provider using JSONTas."""

    logger = logging.getLogger("IUTProvider")

    def __init__(self, etos: ETOS, jsontas: JsonTas, ruleset: dict) -> None:
        """Initialize IUT provider.

        :param etos: ETOS library instance.
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :param ruleset: JSONTas ruleset for handling IUTs.
        """
        self.etos = etos
        self.etos.config.set("iuts", [])
        self.jsontas = jsontas
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.context = self.etos.config.get("environment_provider_context")
        self.logger.info("Initialized IUT provider %r", self.id)

    @property
    def identity(self) -> PackageURL:
        """IUT Identity.

        :return: IUT identity as PURL object.
        """
        return self.jsontas.dataset.get("identity")

    def checkout(self, available_iuts: list[Iut]) -> list[Iut]:
        """Checkout a number of IUTs from an IUT provider.

        :param available_iuts: IUTs to checkout.
        :return: Checked out IUTs.
        """
        checkout_iuts = Checkout(self.jsontas, self.ruleset.get("checkout"))
        return checkout_iuts.checkout(available_iuts)

    def list_iuts(self, amount: int) -> list[Iut]:
        """List IUTs in order to find out which are available or not.

        :param amount: Number of IUTs to list.
        :return: Available IUTs in the IUT provider.
        """
        list_iuts = List(self.id, self.jsontas, self.ruleset.get("list"))
        return list_iuts.list(self.identity, amount)

    def checkin_all(self) -> None:
        """Check in all checked out IUTs."""
        checkin_iuts = Checkin(self.jsontas, self.ruleset.get("checkin"))
        checkin_iuts.checkin_all()

    def checkin(self, iut: Iut) -> None:
        """Check in a single IUT, returning it to the IUT provider.

        :param iut: IUT to checkin.
        """
        checkin_iuts = Checkin(self.jsontas, self.ruleset.get("checkin"))
        checkin_iuts.checkin(iut)

    def prepare(self, iuts: list[Iut]) -> list[Iut]:
        """Prepare all IUTs in the IUT provider.

        :param iuts: IUTs to prepare.
        :return: Prepared IUTs
        """
        prepare_iuts = Prepare(self.jsontas, self.ruleset.get("prepare"))
        return prepare_iuts.prepare(iuts)

    def _fail_message(self, last_exception: Exception) -> str:
        """Generate a fail message for IUT provider.

        :param last_exception: Latest exception that was raised within the wait method.
        :return: A failure reason.
        """
        timeout = self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
        fail_reason = "Unknown"
        if isinstance(last_exception, NoIutFound):
            fail_reason = f"IUT not found using IUT provider '{self.id}'"
        elif isinstance(last_exception, IutNotAvailable):
            fail_reason = f"No IUT became available within {timeout}s."
        elif isinstance(last_exception, IutCheckoutFailed):
            fail_reason = str(last_exception)
        return f"Failed to checkout {self.identity.to_string()}. Reason: {fail_reason}"

    # pylint: disable=too-many-branches
    def _wait_for_and_checkout_iuts(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[Iut]:
        """Wait for and checkout IUTs from an IUT provider.

        :raises: IutNotAvailable: If there are no available IUTs after timeout.

        :param minimum_amount: Minimum amount of IUTs to checkout.
        :param maximum_amount: Maximum amount of IUTs to checkout.
        :return: List of checked out IUTs.
        """
        timeout = time.time() + self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
        last_exception = None
        prepared_iuts = []
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(5)
            try:
                available_iuts = self.list_iuts(maximum_amount)
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
                    raise IutNotAvailable(f"Preparation of {self.identity.to_string()} failed")
                break
            except NoIutFound as not_found:
                self.logger.critical(
                    "%r does not exist in the IUT provider!", self.identity.to_string()
                )
                prepared_iuts = []
                last_exception = not_found
                break
            except IutNotAvailable as not_available:
                self.logger.warning("IUT %r is not available yet.", self.identity)
                last_exception = not_available
                continue
            except IutCheckoutFailed as checkout_failed:
                self.logger.critical(
                    "Checkout of %r failed with reason %r!",
                    self.identity.to_string(),
                    checkout_failed,
                )
                self.checkin_all()
                prepared_iuts = []
                last_exception = checkout_failed
                break
        else:
            self.logger.error(
                "IUT %r did not become available in %rs",
                self.identity.to_string(),
                self.etos.config.get("WAIT_FOR_IUT_TIMEOUT"),
            )
            prepared_iuts = []
        if len(prepared_iuts) < minimum_amount:
            raise IutNotAvailable(self._fail_message(last_exception))
        return prepared_iuts

    def wait_for_and_checkout_iuts(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[Iut]:
        """Wait for and checkout IUTs from an IUT provider.

        See: `_wait_for_and_checkout_iuts`

        :raises: IutNotAvailable: If there are no available IUTs after timeout.

        :param minimum_amount: Minimum amount of IUTs to checkout.
        :param maximum_amount: Maximum amount of IUTs to checkout.
        :return: List of checked out IUTs.
        """
        error = None
        triggered = None
        try:
            triggered = self.etos.events.send_activity_triggered(
                f"Checkout IUTs from {self.id}",
                {"CONTEXT": self.context},
                executionType="AUTOMATED",
                categories=["EnvironmentProvider", "IUTProvider"],
                triggers=[
                    {
                        "type": "OTHER",
                        "description": f"Checking out IUTs",
                    }
                ],
            )
            self.etos.events.send_activity_started(triggered)
            return self._wait_for_and_checkout_iuts(minimum_amount, maximum_amount)
        except Exception as exception:
            error = exception
            raise
        finally:
            if error is None:
                outcome = {"conclusion": "SUCCESSFUL"}
            else:
                outcome = {"conclusion": "UNSUCCESSFUL", "description": str(error)}
            if triggered is not None:
                self.etos.events.send_activity_finished(triggered, outcome)
