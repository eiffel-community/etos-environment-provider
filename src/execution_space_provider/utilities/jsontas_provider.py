# Copyright 2022 Axis Communications AB.
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
"""Execution space provider utilizing JSONTas."""
import logging
import time
from .list import List
from .checkout import Checkout
from .checkin import Checkin
from ..exceptions import (
    NoExecutionSpaceFound,
    ExecutionSpaceNotAvailable,
    ExecutionSpaceCheckoutFailed,
    NotEnoughExecutionSpacesAvailable,
)


class JSONTasProvider:
    """Execution space provider using JSONTas."""

    logger = logging.getLogger("ExecutionSpaceProvider")

    def __init__(self, etos, jsontas, ruleset):
        """Initialize execution space provider.

        :param etos: ETOS library instance.
        :type etos: :obj:`etos_lib.etos.Etos`
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        :param ruleset: JSONTas ruleset for handling execution spaces.
        :type ruleset: dict
        """
        self.etos = etos
        self.jsontas = jsontas
        self.etos.config.set("execution_spaces", [])
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.context = self.etos.config.get("environment_provider_context")
        self.logger.info("Initialized execution space provider %r", self.id)

    def checkout(self, available_execution_spaces):
        """Checkout a number of execution spaces from an execution space provider.

        :param available_execution_spaces: Execution spaces to checkout.
        :type available_execution_spaces: list
        :return: Checked out execution spaces.
        :rtype: list
        """
        checkout_execution_spaces = Checkout(self.jsontas, self.ruleset.get("checkout"))
        return checkout_execution_spaces.checkout(available_execution_spaces)

    def list(self, amount):
        """List execution spaces in order to find out which are available.

        :param amount: Number of execution spaces to list.
        :type amount: int
        :return: Available execution spaces in the execution space provider.
        :rtype: list
        """
        list_execution_spaces = List(
            self.id, self.etos, self.jsontas, self.ruleset.get("list")
        )
        return list_execution_spaces.list(amount)

    def checkin_all(self):
        """Check in all checked out execution spaces."""
        checkin_execution_spaces = Checkin(self.jsontas, self.ruleset.get("checkin"))
        checkin_execution_spaces.checkin_all()

    def checkin(self, execution_space):
        """Check in a single execution space, returning it to the execution space provider.

        :param execution_space: Execution space to checkin.
        :type execution_space:
            :obj:`environment_provider.execution_space.execution_space.ExecutionSpace`
        """
        checkin_execution_spaces = Checkin(self.jsontas, self.ruleset.get("checkin"))
        checkin_execution_spaces.checkin(execution_space)

    def _wait_for_and_checkout_execution_spaces(
        self, minimum_amount=0, maximum_amount=100
    ):
        """Wait for and checkout execution spaces from an execution space provider.

        :raises: ExecutionSpaceNotAvailable: If there are no available execution spaces after
                                             timeout.

        :param minimum_amount: Minimum amount of execution spaces to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of execution spaces to checkout.
        :type maximum_amount: int
        :return: List of checked out execution spaces.
        :rtype: list
        """
        timeout = time.time() + self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(5)
            try:
                available_execution_spaces = self.list(maximum_amount)
                self.logger.info("Available execution spaces:")
                for execution_space in available_execution_spaces:
                    self.logger.info(execution_space)
                if len(available_execution_spaces) < minimum_amount:
                    self.logger.critical(
                        "Not enough available execution spaces in "
                        "execution space provider!"
                    )
                    raise NotEnoughExecutionSpacesAvailable(self.id)

                checked_out_execution_spaces = self.checkout(available_execution_spaces)
                self.logger.info("Checked out execution spaces:")
                for execution_space in checked_out_execution_spaces:
                    self.logger.info(execution_space)
                if len(checked_out_execution_spaces) < minimum_amount:
                    raise ExecutionSpaceNotAvailable(self.id)
                break
            except NoExecutionSpaceFound:
                self.logger.critical(
                    "Execution space does not exist in execution space provider!"
                )
                checked_out_execution_spaces = []
                break
            except ExecutionSpaceNotAvailable:
                self.logger.warning("Execution space not available yet.")
                continue
            except ExecutionSpaceCheckoutFailed as checkout_failed:
                self.logger.critical(
                    "Checkout of execution space failed with reason %r!",
                    checkout_failed,
                )
                self.checkin_all()
                checked_out_execution_spaces = []
                break
        else:
            self.logger.error(
                "Execution space did not become available in %rs",
                self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT"),
            )
            checked_out_execution_spaces = []
        if len(checked_out_execution_spaces) < minimum_amount:
            raise ExecutionSpaceNotAvailable(self.id)
        return checked_out_execution_spaces

    def wait_for_and_checkout_execution_spaces(
        self, minimum_amount=0, maximum_amount=100
    ):
        """Wait for and checkout execution spaces from an execution space provider.

        See: `_wait_for_and_checkout_execution_spaces`

        :raises: ExecutionSpaceNotAvailable: If there are no available execution spaces after
                                             timeout.

        :param minimum_amount: Minimum amount of execution spaces to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of execution spaces to checkout.
        :type maximum_amount: int
        :return: List of checked out execution spaces.
        :rtype: list
        """
        error = None
        triggered = None
        try:
            triggered = self.etos.events.send_activity_triggered(
                self.id,
                {"CONTEXT": self.context},
                executionType="AUTOMATED",
                categories=["EnvironmentProvider", "ExecutionSpaceProvider"],
                triggers=[
                    {
                        "type": "OTHER",
                        "description": f"Checking out execution spaces",
                    }
                ],
            )
            self.etos.events.send_activity_started(triggered)
            return self._wait_for_and_checkout_execution_spaces(
                minimum_amount, maximum_amount
            )
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
