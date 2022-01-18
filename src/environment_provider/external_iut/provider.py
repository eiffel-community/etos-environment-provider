# Copyright 2021 Axis Communications AB.
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
"""External IUT provider."""
from json.decoder import JSONDecodeError
import time
import logging
from copy import deepcopy

import requests
from packageurl import PackageURL

from environment_provider.iut.exceptions import (
    IutCheckinFailed,
    IutCheckoutFailed,
    IutNotAvailable,
)
from environment_provider.iut.iut import Iut


class Provider:
    """A generic IUT provider facility for getting IUTs from an external source.

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

    logger = logging.getLogger("External IUTProvider")

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
        self.dataset = jsontas.dataset
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.logger.info("Initialized external IUT provider %r", self.id)

    @property
    def identity(self):
        """IUT Identity.

        :return: IUT identity as PURL object.
        :rtype: :obj:`packageurl.PackageURL`
        """
        return self.dataset.get("identity")

    def checkin(self, iut):
        """Check in IUTs.

        :param iut: IUT to checkin.
        :type iut: :obj:`environment_provider.iut.iut.Iut` or list
        """
        end = self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")

        if not isinstance(iut, list):
            self.logger.debug("Check in IUT %r (timeout %ds)", iut, end)
            iut = [iut]
        else:
            self.logger.debug("Check in IUTs %r (timeout %ds)", iut, end)
        iuts = [iut.as_dict for iut in iut]

        host = self.ruleset.get("stop", {}).get("host")
        timeout = time.time() + end
        while time.time() < timeout:
            time.sleep(2)
            try:
                response = requests.post(host, json=iuts)
                if response.status_code == requests.codes["no_content"]:
                    return
                response = response.json()
                if response.get("error") is not None:
                    raise IutCheckinFailed(
                        f"Unable to check in {iuts} ({response.get('error')})"
                    )
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue
        raise TimeoutError(f"Unable to stop external provider {self.id!r}")

    def checkin_all(self):
        """Check in all IUTs.

        This method does the same as 'checkin'. It exists for API consistency.
        """
        self.logger.debug("Checking in all checked out IUTs")
        self.checkin(self.dataset.get("iuts", []))

    def start(self, minimum_amount, maximum_amount):
        """Send a start request to an external IUT provider.

        :param minimum_amount: The minimum amount of IUTs to request.
        :type minimum_amount: int
        :param maximum_amount: The maximum amount of IUTs to request.
        :type maximum_amount: int
        :return: The ID of the external IUT provider request.
        :rtype: str
        """
        self.logger.debug("Start external IUT provider")
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
        """Wait for external IUT provider to finish its request.

        :param provider_id: The ID of the external IUT provider request.
        :type provider_id: str
        :return: The response from the external IUT provider.
        :rtype: dict
        """
        self.logger.debug(
            "Waiting for external IUT provider (%ds timeout)",
            self.etos.config.get("WAIT_FOR_IUT_TIMEOUT"),
        )

        host = self.ruleset.get("status", {}).get("host")
        timeout = time.time() + self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")

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
                raise IutCheckoutFailed(response.get("description"))
            if response.get("status") == "DONE":
                break
        else:
            raise TimeoutError(
                f"Status request timed out after {self.etos.config.get('WAIT_FOR_IUT_TIMEOUT')}s"
            )
        return response

    def check_error(self, response):
        """Check response for errors and try to translate them to something usable.

        :param response: The response from the external IUT provider.
        :type response: dict
        """
        self.logger.debug("Checking response from external IUT provider")
        try:
            if response.json().get("error") is not None:
                self.logger.error(response.json().get("error"))
        except JSONDecodeError:
            self.logger.error("Could not parse response as JSON")

        if response.status_code == requests.codes["not_found"]:
            raise IutNotAvailable(
                f"External provider {self.id!r} did not respond properly"
            )
        if response.status_code == requests.codes["bad_request"]:
            raise RuntimeError(
                f"IUT provider for {self.id!r} is not properly configured"
            )

        # This should work, no other errors found.
        # If this does not work, propagate JSONDecodeError up the stack.
        self.logger.debug("Status for response %r", response.json().get("status"))

    def build_iuts(self, response):
        """Build IUT objects from external IUT provider response.

        :param response: The response from the external IUT provider.
        :type response: dict
        :return: A list of IUTs.
        :rtype: list
        """
        iuts = []
        for iut in response.get("iuts", []):
            if iut.get("identity") is None:
                iut["identity"] = self.identity
            else:
                iut["identity"] = PackageURL.from_string(iut.get("identity"))
            iuts.append(Iut(provider_id=self.id, **iut))
        return iuts

    def request_and_wait_for_iuts(self, minimum_amount=0, maximum_amount=100):
        """Wait for IUTs from an external IUT provider.

        :raises: IutNotAvailable: If there are no available IUTs.

        :param minimum_amount: Minimum amount of IUTs to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of IUTs to checkout.
        :type maximum_amount: int
        :return: List of checked out IUTs.
        :rtype: list
        """
        try:
            provider_id = self.start(minimum_amount, maximum_amount)
            response = self.wait(provider_id)
            iuts = self.build_iuts(response)
            if len(iuts) < minimum_amount:
                raise IutNotAvailable(self.identity.to_string())
            if len(iuts) > maximum_amount:
                self.logger.warning(
                    "Too many IUTs from external IUT provider %r. (Expected: %d, Got %d)",
                    self.id,
                    maximum_amount,
                    len(iuts),
                )
                extra = iuts[maximum_amount:]
                iuts = iuts[:maximum_amount]
                for iut in extra:
                    self.checkin(iut)
            self.dataset.add("iuts", deepcopy(iuts))
        except:  # pylint:disable=bare-except
            self.checkin_all()
            raise
        return iuts
