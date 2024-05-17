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
"""External log area provider."""
import logging
import json
import os
import time
from copy import deepcopy
from json.decoder import JSONDecodeError

import opentelemetry
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.semconv.trace import SpanAttributes
import requests
from etos_lib import ETOS
from etos_lib.lib.http import Http
from jsontas.jsontas import JsonTas
from packageurl import PackageURL
from requests.exceptions import HTTPError, ConnectionError as RequestsConnectionError
from urllib3.util import Retry

from ..exceptions import LogAreaCheckinFailed, LogAreaCheckoutFailed, LogAreaNotAvailable
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

    def __init__(self, etos: ETOS, jsontas: JsonTas, ruleset: dict) -> None:
        """Initialize log area provider.

        :param etos: ETOS library instance.
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :param ruleset: JSONTas ruleset for handling log areas.
        """
        self.etos = etos
        self.etos.config.set("logs", [])
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
        self.logger.info("Initialized external log area provider %r", self.id)

    @property
    def identity(self) -> PackageURL:
        """IUT identity.

        :return: IUT identity as PURL object.
        """
        return self.dataset.get("identity")

    @staticmethod
    def _record_exception(exc) -> None:
        """Record the given exception to the current OpenTelemetry span."""
        span = opentelemetry.trace.get_current_span()
        span.set_attribute("error.type", exc.__class__.__name__)
        span.record_exception(exc)
        span.set_status(opentelemetry.trace.Status(opentelemetry.trace.StatusCode.ERROR))

    def checkin(self, log_area: LogArea) -> None:
        """Check in log areas.

        :param log_area: Log area to check in.
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
        headers = {"X-ETOS-ID": self.identifier}
        TraceContextTextMapPropagator().inject(headers)
        span = opentelemetry.trace.get_current_span()
        span.set_attribute(SpanAttributes.URL_FULL, host)
        span.set_attribute("http.request.body", json.dumps(log_areas))
        for header, value in headers.items():
            span.set_attribute(f"http.request.headers.{header.lower()}", value)
        timeout = time.time() + end
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(2)
            try:
                response = requests.post(host, json=log_areas, headers=headers)
                if response.status_code == requests.codes["no_content"]:
                    return
                response = response.json()
                if response.get("error") is not None:
                    exc = LogAreaCheckinFailed(
                        f"Unable to check in {log_areas} ({response.get('error')})"
                    )
                    self._record_exception(exc)
                    raise exc
            except RequestsConnectionError as error:
                if "connection refused" in str(error).lower():
                    self.logger.error("Error connecting to %r: %r", host, error)
                    continue
                self._record_exception(error)
                raise
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue
        exc = TimeoutError(f"Unable to stop external provider {self.id!r}")
        self._record_exception(exc)
        raise exc

    def checkin_all(self) -> None:
        """Check in all log areas.

        This method does the same as 'checkin'. It exists for API consistency.
        """
        self.logger.debug("Checking in all checked out log areas")
        self.checkin(self.dataset.get("logs", []))

    def start(self, minimum_amount: int, maximum_amount: int) -> str:
        """Send a start request to an external log area provider.

        :param minimum_amount: Minimum amount of log areas to request.
        :param maximum_amount: Maximum amount of log areas to request.
        :return: The ID of the external log area provider request.
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
        host = self.ruleset.get("start", {}).get("host")
        headers = {"X-ETOS-ID": self.identifier}
        TraceContextTextMapPropagator().inject(headers)
        span = opentelemetry.trace.get_current_span()
        span.set_attribute(SpanAttributes.URL_FULL, host)
        span.set_attribute("http.request.body", json.dumps(data))
        for header, value in headers.items():
            span.set_attribute(f"http.request.headers.{header.lower()}", value)
        try:
            response = self.http.post(
                host,
                json=data,
                headers=headers,
            )
            response.raise_for_status()
            return response.json().get("id")
        except (HTTPError, JSONDecodeError) as error:
            self._record_exception(error)
            raise Exception(f"Could not start external provider {self.id!r}") from error

    def wait(self, provider_id: str) -> dict:
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
        headers = {"X-ETOS-ID": self.identifier}
        TraceContextTextMapPropagator().inject(headers)
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(2)
            try:
                response = requests.get(
                    host,
                    params={"id": provider_id},
                    headers=headers,
                )
                self.check_error(response)
                response = response.json()
            except ConnectionError:
                self.logger.error("Error connecting to %r", host)
                continue

            if response.get("status") == "FAILED":
                exc = LogAreaCheckoutFailed(response.get("description"))
                self._record_exception(exc)
                raise exc
            if response.get("status") == "DONE":
                break
        else:
            exc = TimeoutError(
                "Status request timed out after "
                f"{self.etos.config.get('WAIT_FOR_LOG_AREA_TIMEOUT')}s"
            )
            self._record_exception(exc)
            raise exc
        return response

    def check_error(self, response: dict) -> None:
        """Check response for errors and try to translate them to something usable.

        :param response: The response from the external log area provider.
        """
        self.logger.debug("Checking response from external log area provider")
        try:
            if response.json().get("error") is not None:
                self.logger.error(response.json().get("error"))
        except JSONDecodeError:
            self.logger.error("Could not parse response as JSON")

        if response.status_code == requests.codes["not_found"]:
            exc = LogAreaNotAvailable(f"External provider {self.id!r} did not respond properly")
            self._record_exception(exc)
            raise exc
        if response.status_code == requests.codes["bad_request"]:
            exc = RuntimeError(f"Log area provider for {self.id!r} is not properly configured")
            self._record_exception(exc)
            raise exc

        # This should work, no other errors found.
        # If this does not work, propagate JSONDecodeError up the stack.
        self.logger.debug("Status for response %r", response.json().get("status"))

    def build_log_areas(self, response: dict) -> list[LogArea]:
        """Build log area objects from external log area provider response.

        :param response: The response from the external log area provider.
        :return: A list of log areas.
        """
        return [
            LogArea(provider_id=self.id, **log_area) for log_area in response.get("log_areas", [])
        ]

    def request_and_wait_for_log_areas(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[LogArea]:
        """Wait for log areas from an external log area provider.

        :raises: LogAreaNotAvailable: If there are not available log areas after timeout.

        :param minimum_amount: Minimum amount of log areas to checkout.
        :param maximum_amount: Maximum amount of log areas to checkout.
        :return: List of checked out log areas.
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

    def wait_for_and_checkout_log_areas(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[LogArea]:
        """Wait for log areas from an external log area provider.

        See: `request_and_wait_for_log_areas`

        :raises: LogAreaNotAvailable: If there are not available log areas after timeout.

        :param minimum_amount: Minimum amount of log areas to checkout.
        :param maximum_amount: Maximum amount of log areas to checkout.
        :return: List of checked out log areas.
        """
        error = None
        triggered = None
        try:
            triggered = self.etos.events.send_activity_triggered(
                f"Checkout log areas from {self.id}",
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
            self._record_exception(exception)
            error = exception
            raise
        finally:
            if error is None:
                outcome = {"conclusion": "SUCCESSFUL"}
            else:
                outcome = {"conclusion": "UNSUCCESSFUL", "description": str(error)}
            if triggered is not None:
                self.etos.events.send_activity_finished(triggered, outcome)
