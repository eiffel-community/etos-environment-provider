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
"""External log area provider."""
import os
from json.decoder import JSONDecodeError
import time
import logging
from copy import deepcopy

import requests

from ..exceptions import (
    LogAreaCheckinFailed,
    LogAreaCheckoutFailed,
    LogAreaNotAvailable,
)
from ..log_area import LogArea


class ExternalProvider:
    """A log area provider facility for getting log areas from an external source.

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

    logger = logging.getLogger("External LogAreaProvider")

    def __init__(self, etos, jsontas, ruleset):
        """Initialize log area provider.

        :param etos: ETOS library instance.
        :type etos: :obj:`etos_lib.etos.Etos`
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        :param ruleset: JSONTas ruleset for handling log areas.
        :type ruleset: dict
        """
        self.etos = etos
        self.etos.config.set("logs", [])
        self.dataset = jsontas.dataset
        self.ruleset = ruleset
        self.id = self.ruleset.get("id")  # pylint:disable=invalid-name
        self.context = self.etos.config.get("environment_provider_context")
        self.identifier = self.etos.config.get("SUITE_ID")
        self.logger.info("Initialized external log area provider %r", self.id)

    @property
    def identity(self):
        """IUT identity.

        :return: IUT identity as PURL object.
        :rtype: :obj:`packageurl.PackageURL`
        """
        return self.dataset.get("identity")

    def checkin(self, log_area):
        """Check in log areas.

        :param log_area: Log area to check in.
        :type log_area: :obj:`environment_provider.logs.log_area.LogArea` or list
        """
        end = self.etos.config.get("WAIT_FOR_LOG_AREA_TIMEOUT")
        if end is None:
            end = os.getenv("ENVIRONMENT_PROVIDER_WAIT_FOR_LOG_AREA_TIMEOUT")
        if end is None:
            end = 3600
        end = int(end)

        if not isinstance(log_area, list):
            self.logger.debug("Check in log area %r (timeout %ds)", log_area, end)
            log_area = [log_area]
        else:
            self.logger.debug("Check in log areas %r (timeout %ds)", log_area, end)
        log_areas = [log_area.as_dict for log_area in log_area]

        host = self.ruleset.get("stop", {}).get("host")
        timeout = time.time() + end
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(2)
            try:
                response = requests.post(
                    host, json=log_areas, headers={"X-ETOS-ID": self.identifier}
                )
                if response.status_code == requests.codes["no_content"]:
                    return
                response = response.json()
                if response.get("error") is not None:
                    raise LogAreaCheckinFailed(
                        f"Unable to check in {log_areas} ({response.get('error')})"
                    )
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue
        raise TimeoutError(f"Unable to stop external provider {self.id!r}")

    def checkin_all(self):
        """Check in all log areas.

        This method does the same as 'checkin'. It exists for API consistency.
        """
        self.logger.debug("Checking in all checked out log areas")
        self.checkin(self.dataset.get("logs", []))

    def start(self, minimum_amount, maximum_amount):
        """Send a start request to an external log area provider.

        :param minimum_amount: Minimum amount of log areas to request.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of log areas to request.
        :type maximum_amount: int
        :return: The ID of the external log area provider request.
        :rtype: str
        """
        self.logger.debug("Start external log area provider")
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
            headers={"X-ETOS-ID": self.identifier},
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
        """Wait for external log area provider to finish its request.

        :param provider_id: The ID of the external log area provider request.
        :type provider_id: str
        :return: The response from the external log area provider.
        :rtype: dict
        """
        self.logger.debug(
            "Waiting for external log area provider (%ds timeout)",
            self.etos.config.get("WAIT_FOR_LOG_AREA_TIMEOUT"),
        )

        host = self.ruleset.get("status", {}).get("host")
        timeout = time.time() + self.etos.config.get("WAIT_FOR_LOG_AREA_TIMEOUT")

        response = None
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
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
                raise LogAreaCheckoutFailed(response.get("description"))
            if response.get("status") == "DONE":
                break
        else:
            raise TimeoutError(
                "Status request timed out after "
                f"{self.etos.config.get('WAIT_FOR_LOG_AREA_TIMEOUT')}s"
            )
        return response

    def check_error(self, response):
        """Check response for errors and try to translate them to something usable.

        :param response: The response from the external log area provider.
        :type response: dict
        """
        self.logger.debug("Checking response from external log area provider")
        try:
            if response.json().get("error") is not None:
                self.logger.error(response.json().get("error"))
        except JSONDecodeError:
            self.logger.error("Could not parse response as JSON")

        if response.status_code == requests.codes["not_found"]:
            raise LogAreaNotAvailable(
                f"External provider {self.id!r} did not respond properly"
            )
        if response.status_code == requests.codes["bad_request"]:
            raise RuntimeError(
                f"Log area provider for {self.id!r} is not properly configured"
            )

        # This should work, no other errors found.
        # If this does not work, propagate JSONDecodeError up the stack.
        self.logger.debug("Status for response %r", response.json().get("status"))

    def build_log_areas(self, response):
        """Build log area objects from external log area provider response.

        :param response: The response from the external log area provider.
        :type response: dict
        :return: A list of log areas.
        :rtype: list
        """
        return [
            LogArea(provider_id=self.id, **log_area)
            for log_area in response.get("log_areas", [])
        ]

    def request_and_wait_for_log_areas(self, minimum_amount=0, maximum_amount=100):
        """Wait for log areas from an external log area provider.

        :raises: LogAreaNotAvailable: If there are not available log areas after timeout.

        :param minimum_amount: Minimum amount of log areas to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of log areas to checkout.
        :type maximum_amount: int
        :return: List of checked out log areas.
        :rtype: list
        """
        try:
            provider_id = self.start(minimum_amount, maximum_amount)
            response = self.wait(provider_id)
            log_areas = self.build_log_areas(response)
            if len(log_areas) < minimum_amount:
                raise LogAreaNotAvailable(self.id)
            if len(log_areas) > maximum_amount:
                self.logger.warning(
                    "Too many log areas from external log area provider "
                    "%r. (Expected: %d, Got %d)",
                    self.id,
                    maximum_amount,
                    len(log_areas),
                )
                extra = log_areas[maximum_amount:]
                log_areas = log_areas[:maximum_amount]
                for log_area in extra:
                    self.checkin(log_area)
            self.dataset.add("logs", deepcopy(log_areas))
        except:  # pylint:disable=bare-except
            self.checkin_all()
            raise
        return log_areas

    def wait_for_and_checkout_log_areas(self, minimum_amount=0, maximum_amount=100):
        """Wait for log areas from an external log area provider.

        See: `request_and_wait_for_log_areas`

        :raises: LogAreaNotAvailable: If there are not available log areas after timeout.

        :param minimum_amount: Minimum amount of log areas to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of log areas to checkout.
        :type maximum_amount: int
        :return: List of checked out log areas.
        :rtype: list
        """
        error = None
        triggered = None
        try:
            triggered = self.etos.events.send_activity_triggered(
                self.id,
                {"CONTEXT": self.context},
                executionType="AUTOMATED",
                categories=["EnvironmentProvider", "LogAreaProvider", "External"],
                triggers=[
                    {
                        "type": "OTHER",
                        "description": f"Checking out log areas",
                    }
                ],
            )
            self.etos.events.send_activity_started(triggered)
            return self.request_and_wait_for_log_areas(minimum_amount, maximum_amount)
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
