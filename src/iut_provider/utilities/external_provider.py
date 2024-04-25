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
"""IUT provider for external providers."""
import logging
import os
import time
from copy import deepcopy
from json.decoder import JSONDecodeError

import requests
from etos_lib import ETOS
from etos_lib.lib.http import Http
from jsontas.jsontas import JsonTas
from packageurl import PackageURL
from requests.exceptions import HTTPError, ConnectionError as RequestsConnectionError
from urllib3.util import Retry

from ..exceptions import IutCheckinFailed, IutCheckoutFailed, IutNotAvailable
from ..iut import Iut


class ExternalProvider:
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

    def __init__(self, etos: ETOS, jsontas: JsonTas, ruleset: dict) -> None:
        """Initialize IUT provider.

        :param etos: ETOS library instance.
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :param ruleset: JSONTas ruleset for handling IUTs.
        """
        self.etos = etos
        self.etos.config.set("iuts", [])
        self.dataset = jsontas.dataset
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.context = self.etos.config.get("environment_provider_context")
        self.identifier = self.etos.config.get("SUITE_ID")
        self.http = Http(
            retry=Retry(
                total=None,
                read=0,
                connect=10,  # With 1 as backoff_factor, will retry for 1023s
                status=10,  # With 1 as backoff_factor, will retry for 1023s
                backoff_factor=1,
                other=0,
                allowed_methods=["POST", "GET"],
                status_forcelist=Retry.RETRY_AFTER_STATUS_CODES,  # 413, 429, 503
            )
        )
        self.logger.info("Initialized external IUT provider %r", self.id)

    @property
    def identity(self) -> PackageURL:
        """IUT Identity.

        :return: IUT identity as PURL object.
        """
        return self.dataset.get("identity")

    def checkin(self, iut: Iut) -> None:
        """Check in IUTs.

        :param iut: IUT to checkin.
        """
        end = self.etos.config.get("WAIT_FOR_IUT_TIMEOUT")
        if end is None:
            end = os.getenv("ENVIRONMENT_PROVIDER_WAIT_FOR_IUT_TIMEOUT")
        if end is None:
            end = 3600
        end = int(end)

        if not isinstance(iut, list):
            self.logger.debug("Check in IUT %r (timeout %ds)", iut, end)
            iut = [iut]
        else:
            self.logger.debug("Check in IUTs %r (timeout %ds)", iut, end)
        iuts = [iut.as_dict for iut in iut]

        host = self.ruleset.get("stop", {}).get("host")
        timeout = time.time() + end
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(2)
            try:
                response = requests.post(host, json=iuts, headers={"X-ETOS-ID": self.identifier})
                if response.status_code == requests.codes["no_content"]:
                    return
                response = response.json()
                if response.get("error") is not None:
                    raise IutCheckinFailed(f"Unable to check in {iuts} ({response.get('error')})")
            except RequestsConnectionError as error:
                if "connection refused" in str(error).lower():
                    self.logger.error("Error connecting to %r: %r", host, error)
                    continue
                raise
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue
        raise TimeoutError(f"Unable to stop external provider {self.id!r}")

    def checkin_all(self) -> None:
        """Check in all IUTs.

        This method does the same as 'checkin'. It exists for API consistency.
        """
        self.logger.debug("Checking in all checked out IUTs")
        self.checkin(self.dataset.get("iuts", []))

    def start(self, minimum_amount: int, maximum_amount: int) -> str:
        """Send a start request to an external IUT provider.

        :param minimum_amount: The minimum amount of IUTs to request.
        :param maximum_amount: The maximum amount of IUTs to request.
        :return: The ID of the external IUT provider request.
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
        try:
            response = self.http.post(
                self.ruleset.get("start", {}).get("host"),
                json=data,
                headers={"X-ETOS-ID": self.identifier},
            )
            response.raise_for_status()
            return response.json().get("id")
        except (HTTPError, JSONDecodeError) as error:
            raise Exception(f"Could not start external provider {self.id!r}") from error

    def wait(self, provider_id: str) -> dict:
        """Wait for external IUT provider to finish its request.

        :param provider_id: The ID of the external IUT provider request.
        :return: The response from the external IUT provider.
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
                response = requests.get(
                    host,
                    params={"id": provider_id},
                    headers={"X-ETOS-ID": self.identifier},
                )
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

    def check_error(self, response: dict) -> None:
        """Check response for errors and try to translate them to something usable.

        :param response: The response from the external IUT provider.
        """
        self.logger.debug("Checking response from external IUT provider")
        try:
            if response.json().get("error") is not None:
                self.logger.error(response.json().get("error"))
        except JSONDecodeError:
            self.logger.error("Could not parse response as JSON")

        if response.status_code == requests.codes["not_found"]:
            raise IutNotAvailable(f"External provider {self.id!r} did not respond properly")
        if response.status_code == requests.codes["bad_request"]:
            raise RuntimeError(f"IUT provider for {self.id!r} is not properly configured")

        # This should work, no other errors found.
        # If this does not work, propagate JSONDecodeError up the stack.
        self.logger.debug("Status for response %r", response.json().get("status"))

    def build_iuts(self, response: dict) -> list[Iut]:
        """Build IUT objects from external IUT provider response.

        :param response: The response from the external IUT provider.
        :return: A list of IUTs.
        """
        iuts = []
        for iut in response.get("iuts", []):
            if iut.get("identity") is None:
                iut["identity"] = self.identity
            else:
                iut["identity"] = PackageURL.from_string(iut.get("identity"))
            iuts.append(Iut(provider_id=self.id, **iut))
        return iuts

    def request_and_wait_for_iuts(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[Iut]:
        """Wait for IUTs from an external IUT provider.

        :raises: IutNotAvailable: If there are no available IUTs.

        :param minimum_amount: Minimum amount of IUTs to checkout.
        :param maximum_amount: Maximum amount of IUTs to checkout.
        :return: List of checked out IUTs.
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

    def wait_for_and_checkout_iuts(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[Iut]:
        """Wait for IUTs from an external IUT provider.

        See: `request_and_wait_for_iuts`

        :raises: IutNotAvailable: If there are no available IUTs.

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
                categories=["EnvironmentProvider", "IUTProvider", "External"],
                triggers=[
                    {
                        "type": "OTHER",
                        "description": f"Checking out IUTs",
                    }
                ],
            )
            self.etos.events.send_activity_started(triggered)
            return self.request_and_wait_for_iuts(minimum_amount, maximum_amount)
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
