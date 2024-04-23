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
"""External Execution Space provider."""
import logging
import json
import os
import time
from copy import deepcopy
from json.decoder import JSONDecodeError

import opentelemetry
import requests
from etos_lib import ETOS
from etos_lib.lib.http import Http
from jsontas.jsontas import JsonTas
from packageurl import PackageURL
from requests.exceptions import HTTPError, ConnectionError as RequestsConnectionError
from urllib3.util import Retry

from environment_provider.lib.encrypt import encrypt

from ..exceptions import (
    ExecutionSpaceCheckinFailed,
    ExecutionSpaceCheckoutFailed,
    ExecutionSpaceNotAvailable,
)
from ..execution_space import ExecutionSpace


class ExternalProvider:
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

    def __init__(self, etos: ETOS, jsontas: JsonTas, ruleset: dict) -> None:
        """Initialize Execution Space provider.

        :param etos: ETOS library instance.
        :param jsontas: JSONTas instance used to evaluate the rulesets.
        :param ruleset: JSONTas ruleset for handling execution spaces.
        """
        self.etos = etos
        self.etos.config.set("execution_spaces", [])
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
        self.logger.info("Initialized external execution space provider %r", self.id)

    @property
    def identity(self) -> PackageURL:
        """IUT Identity.

        :return: IUT identity as PURL object.
        """
        return self.dataset.get("identity")

    def checkin(self, execution_space: ExecutionSpace) -> None:
        """Check in execution spaces.

        :param execution_space: Execution space to checkin.
        """
        end = self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")
        if end is None:
            end = os.getenv("ENVIRONMENT_PROVIDER_WAIT_FOR_EXECUTION_SPACE_TIMEOUT")
        if end is None:
            end = 3600
        end = int(end)

        if not isinstance(execution_space, list):
            self.logger.debug("Check in execution space %r (timeout %ds)", execution_space, end)
            execution_space = [execution_space]
        else:
            self.logger.debug("Check in execution spaces %r (timeout %ds)", execution_space, end)
        execution_spaces = [execution_space.as_dict for execution_space in execution_space]

        host = self.ruleset.get("stop", {}).get("host")
        headers = {"X-ETOS-ID": self.identifier}
        otel_span = opentelemetry.trace.get_current_span()
        otel_span.set_attribute("http.request.host", host)
        otel_span.set_attribute("http.request.body", json.dumps(execution_spaces, indent=4))
        for header, value in headers.items():
            otel_span.set_attribute(f"http.request.headers.{header.lower()}", value)
        timeout = time.time() + end
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(2)
            try:
                response = requests.post(host, json=execution_spaces, headers=headers)
                if response.status_code == requests.codes["no_content"]:
                    return
                response = response.json()
                if response.get("error") is not None:
                    raise ExecutionSpaceCheckinFailed(
                        f"Unable to check in {execution_spaces} " f"({response.get('error')})"
                    )
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
        """Check in all execution spaces.

        This method does the same as 'checkin'. It exists for API consistency.
        """
        self.logger.debug("Checking in all checked out execution spaces")
        self.checkin(self.dataset.get("execution_spaces", []))

    def start(self, minimum_amount: int, maximum_amount: int) -> str:
        """Send a start request to an external execution space provider.

        :param minimum_amount: The minimum amount of execution spaces to request.
        :param maximum_amount: The maximum amount of execution spaces to request.
        :return: The ID of the external execution space provider request.
        """
        self.logger.debug("Start external execution space provider")
        rabbitmq = self.etos.config.get("rabbitmq")
        rabbitmq_password = rabbitmq.get("password")
        if os.getenv("ETOS_ENCRYPTION_KEY") is not None:
            rabbitmq_password = encrypt(
                rabbitmq_password.encode(), os.getenv("ETOS_ENCRYPTION_KEY")
            )
        data = {
            "minimum_amount": minimum_amount,
            "maximum_amount": maximum_amount,
            "identity": self.identity.to_string(),
            "test_runner": self.dataset.get("test_runner"),
            "environment": {  # All environments must be string
                "RABBITMQ_HOST": rabbitmq.get("host"),
                "RABBITMQ_USERNAME": rabbitmq.get("username"),
                "RABBITMQ_PASSWORD": rabbitmq_password,
                "RABBITMQ_EXCHANGE": rabbitmq.get("exchange"),
                "RABBITMQ_PORT": str(rabbitmq.get("port")),
                "RABBITMQ_VHOST": rabbitmq.get("vhost"),
                "RABBITMQ_SSL": str(rabbitmq.get("ssl")).lower(),
                "SOURCE_HOST": self.etos.config.get("source").get("host"),
                "ETOS_GRAPHQL_SERVER": self.etos.debug.graphql_server,
                "ETOS_API": self.etos.debug.etos_api,
                "ETR_VERSION": os.getenv(
                    "ETR_VERSION",
                ),
            },
            "artifact_id": self.dataset.get("artifact_id"),
            "artifact_created": self.dataset.get("artifact_created"),
            "artifact_published": self.dataset.get("artifact_published"),
            "tercc": self.dataset.get("tercc"),
            "dataset": self.dataset.get("dataset"),
            "context": self.dataset.get("context"),
        }
        host = self.ruleset.get("start", {}).get("host")
        headers = {"X-ETOS-ID": self.identifier}
        otel_span = opentelemetry.trace.get_current_span()
        otel_span.set_attribute("http.request.host", host)
        otel_span.set_attribute("http.request.body", json.dumps(data, indent=4))
        for header, value in headers.items():
            otel_span.set_attribute(f"http.request.headers.{header.lower()}", value)
        try:
            response = self.http.post(
                host,
                json=data,
                headers=headers,
            )
            response.raise_for_status()
            return response.json().get("id")
        except (HTTPError, JSONDecodeError) as error:
            raise Exception(f"Could not start external provider {self.id!r}") from error

    def wait(self, provider_id: str) -> dict:
        """Wait for external execution space provider to finish its request.

        :param provider_id: The ID of the external execution space provider request.
        :return: The response from the external execution space provider.
        """
        self.logger.debug(
            "Waiting for external execution space provider (%ds timeout)",
            self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT"),
        )

        host = self.ruleset.get("status", {}).get("host")
        timeout = time.time() + self.etos.config.get("WAIT_FOR_EXECUTION_SPACE_TIMEOUT")

        response = None
        first_iteration = True
        while time.time() < timeout:
            if first_iteration:
                first_iteration = False
            else:
                time.sleep(2)
            headers = {"X-ETOS-ID": self.identifier}
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
                raise ExecutionSpaceCheckoutFailed(response.get("description"))
            if response.get("status") == "DONE":
                break
        else:
            raise TimeoutError(
                "Status request timed out after "
                f"{self.etos.config.get('WAIT_FOR_EXECUTION_SPACE_TIMEOUT')}s"
            )
        return response

    def check_error(self, response: dict) -> None:
        """Check response for errors and try to translate them to something usable.

        :param response: The response from the external execution space provider.
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

    def build_execution_spaces(self, response: dict) -> list[ExecutionSpace]:
        """Build execution space objects from external execution space provider response.

        :param response: The response from the external execution space provider.
        :return: A list of execution spaces.
        """
        return [
            ExecutionSpace(provider_id=self.id, **execution_space)
            for execution_space in response.get("execution_spaces", [])
        ]

    def request_and_wait_for_execution_spaces(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[ExecutionSpace]:
        """Wait for execution spaces from an external execution space provider.

        :raises: ExecutionSpaceNotAvailable: If there are no available execution spaces after
                                             timeout.

        :param minimum_amount: Minimum amount of execution spaces to checkout.
        :param maximum_amount: Maximum amount of execution spaces to checkout.
        :return: List of checked out execution spaces.
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

    def wait_for_and_checkout_execution_spaces(
        self, minimum_amount: int = 0, maximum_amount: int = 100
    ) -> list[ExecutionSpace]:
        """Wait for execution spaces from an external execution space provider.

        See: `request_and_wait_for_execution_spaces`

        :raises: ExecutionSpaceNotAvailable: If there are no available execution spaces after
                                             timeout.

        :param minimum_amount: Minimum amount of execution spaces to checkout.
        :param maximum_amount: Maximum amount of execution spaces to checkout.
        :return: List of checked out execution spaces.
        """
        error = None
        triggered = None
        try:
            triggered = self.etos.events.send_activity_triggered(
                f"Checkout execution spaces from {self.id}",
                {"CONTEXT": self.context},
                executionType="AUTOMATED",
                categories=[
                    "EnvironmentProvider",
                    "ExecutionSpaceProvider",
                    "External",
                ],
                triggers=[
                    {
                        "type": "OTHER",
                        "description": f"Checking out execution spaces",
                    }
                ],
            )
            self.etos.events.send_activity_started(triggered)
            return self.request_and_wait_for_execution_spaces(minimum_amount, maximum_amount)
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
