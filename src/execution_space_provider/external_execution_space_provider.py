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
"""External Execution Space provider."""
from json.decoder import JSONDecodeError
import time
import logging
from copy import deepcopy

import requests

from .exceptions import (
    ExecutionSpaceCheckinFailed,
    ExecutionSpaceCheckoutFailed,
    ExecutionSpaceNotAvailable,
)
from .execution_space import ExecutionSpace


class ExternalExecutionSpaceProvider:
    """An Execution space provider facility for getting Execution spaces from an external source.

    The ruleset must provide this structure:

    {
        "status": {
            "host": "host to status endpoint"
        },
        "start": {
            "host": "host to start endpoint"
        },
        "stop": {
            "host": "host to stop endpoint"
        }
    }
    """

    logger = logging.getLogger("External ExecutionSpaceProvider")

    def __init__(self, etos, jsontas, ruleset):
        """Initialize Execution Space provider.

        :param etos: ETOS library instance.
        :type etos: :obj:`etos_lib.etos.Etos`
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        :param ruleset: JSONTas ruleset for handling execution spaces.
        :type ruleset: dict
        """
        self.etos = etos
        self.etos.config.set("execution_spaces", [])
        self.dataset = jsontas.dataset
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.logger.info("Initialized external execution space provider %r", self.id)

    @property
    def identity(self):
        """IUT Identity.

        :return: IUT identity as PURL object.
        :rtype: :obj:`packageurl.PackageURL`
        """
        return self.dataset.get("identity")

    def checkin(self, execution_space):
        """Check in execution spaces.

        :param execution_space: Execution space to checkin.
        :type execution_space:
            :obj:`environment_provider.execution_space.execution_space.ExecutionSpace` or list
        """
        end = self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")

        if not isinstance(execution_space, list):
            self.logger.debug(
                "Check in execution space %r (timeout %ds)", execution_space, end
            )
            execution_space = [execution_space]
        else:
            self.logger.debug(
                "Check in execution spaces %r (timeout %ds)", execution_space, end
            )
        execution_spaces = [
            execution_space.as_dict for execution_space in execution_space
        ]

        host = self.ruleset.get("stop", {}).get("host")
        timeout = time.time() + end
        while time.time() < timeout:
            time.sleep(2)
            try:
                response = requests.post(host, json=execution_spaces)
                if response.status_code == requests.codes["no_content"]:
                    return
                response = response.json()
                if response.get("error") is not None:
                    raise ExecutionSpaceCheckinFailed(
                        f"Unable to check in {execution_spaces} "
                        r"({response.get('error')})"
                    )
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue
        raise TimeoutError(f"Unable to stop external provider {self.id!r}")

    def checkin_all(self):
        """Check in all execution spaces.

        This method does the same as 'checkin'. It exists for API consistency.
        """
        self.logger.debug("Checking in all checked out execution spaces")
        self.checkin(self.dataset.get("execution_spaces", []))

    def start(self, minimum_amount, maximum_amount):
        """Send a start request to an external execution space provider.

        :param minimum_amount: The minimum amount of execution spaces to request.
        :type minimum_amount: int
        :param maximum_amount: The maximum amount of execution spaces to request.
        :type maximum_amount: int
        :return: The ID of the external execution space provider request.
        :rtype: str
        """
        self.logger.debug("Start external execution space provider")
        data = {
            "minimum_amount": minimum_amount,
            "maximum_amount": maximum_amount,
            "identity": self.identity.to_string(),
            "artifact_id": self.dataset.get("artifact_id"),
            "artifact_created": self.dataset.get("artifact_created"),
            "artifact_published": self.dataset.get("artifact_published"),
            "tercc": self.dataset.get("tercc"),
            "dataset": self.dataset.get("dataset"),
            "context": self.dataset.get("context"),
        }
        response_iterator = self.etos.http.retry(
            "POST",
            self.ruleset.get("start", {}).get("host"),
            json=data,
        )
        try:
            for response in response_iterator:
                return response.get("id")
        except ConnectionError as http_error:
            self.logger.error(
                "Could not start external provider due to a connection error"
            )
            raise TimeoutError(
                f"Unable to start external provider {self.id!r}"
            ) from http_error
        raise TimeoutError(f"Unable to start external provider {self.id!r}")

    def wait(self, provider_id):
        """Wait for external execution space provider to finish its request.

        :param provider_id: The ID of the external execution space provider request.
        :type provider_id: str
        :return: The response from the external execution space provider.
        :rtype: dict
        """
        self.logger.debug(
            "Waiting for external execution space provider (%ds timeout)",
            self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT"),
        )

        host = self.ruleset.get("status", {}).get("host")
        timeout = time.time() + self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")

        response = None
        while time.time() < timeout:
            time.sleep(2)
            try:
                response = requests.get(host, params={"id": provider_id})
                self.check_error(response)
                response = response.json()
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue

            if response.get("status") == "FAILED":
                raise ExecutionSpaceCheckoutFailed(response.get("description"))
            if response.get("status") == "DONE":
                break
        else:
            raise TimeoutError(
                "Status request timed out after "
                f"{self.etos.config.get('WAIT_FOR_EXECUTION_SPACE_TIMEOUT')}s"
            )
        return response

    def check_error(self, response):
        """Check response for errors and try to translate them to something usable.

        :param response: The response from the external execution space provider.
        :type response: dict
        """
        self.logger.debug("Checking response from external execution space provider")
        try:
            if response.json().get("error") is not None:
                self.logger.error(response.json().get("error"))
        except JSONDecodeError:
            self.logger.error("Could not parse response as JSON")

        if response.status_code == requests.codes["not_found"]:
            raise ExecutionSpaceNotAvailable(
                f"External provider {self.id!r} did not respond properly"
            )
        if response.status_code == requests.codes["bad_request"]:
            raise RuntimeError(
                f"Execution space provider for {self.id!r} is not properly configured"
            )

        # This should work, no other errors found.
        # If this does not work, propagate JSONDecodeError up the stack.
        self.logger.debug("Status for response %r", response.json().get("status"))

    def build_execution_spaces(self, response):
        """Build execution space objects from external execution space provider response.

        :param response: The response from the external execution space provider.
        :type response: dict
        :return: A list of execution spaces.
        :rtype: list
        """
        return [
            ExecutionSpace(provider_id=self.id, **execution_space)
            for execution_space in response.get("execution_spaces", [])
        ]

    def request_and_wait_for_execution_spaces(
        self, minimum_amount=0, maximum_amount=100
    ):
        """Wait for execution spaces from an external execution space provider.

        :raises: ExecutionSpaceNotAvailable: If there are no available execution spaces after
                                             timeout.

        :param minimum_amount: Minimum amount of execution spaces to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of execution spaces to checkout.
        :type maximum_amount: int
        :return: List of checked out execution spaces.
        :rtype: list
        """
        try:
            provider_id = self.start(minimum_amount, maximum_amount)
            response = self.wait(provider_id)
            execution_spaces = self.build_execution_spaces(response)
            if len(execution_spaces) < minimum_amount:
                raise ExecutionSpaceNotAvailable(self.id)
            if len(execution_spaces) > maximum_amount:
                self.logger.warning(
                    "Too many execution spaces from external execution space provider "
                    "%r. (Expected: %d, Got %d)",
                    self.id,
                    maximum_amount,
                    len(execution_spaces),
                )
                extra = execution_spaces[maximum_amount:]
                execution_spaces = execution_spaces[:maximum_amount]
                for execution_space in extra:
                    self.checkin(execution_space)
            self.dataset.add("execution_spaces", deepcopy(execution_spaces))
        except:  # pylint:disable=bare-except
            self.checkin_all()
            raise
        return execution_spaces
