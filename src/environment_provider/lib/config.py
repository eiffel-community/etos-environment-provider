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
"""ETOS Environment Provider configuration module."""
import logging
import time
import json
import os
from typing import Optional

from urllib3.exceptions import MaxRetryError
from etos_lib import ETOS
from etos_lib.lib.events import EiffelActivityTriggeredEvent
from etos_lib.kubernetes.schemas.testrun import Suite
from etos_lib.kubernetes.schemas.environment_request import (
    EnvironmentRequest as EnvironmentRequestSchema,
    EnvironmentRequestSpec,
    EnvironmentProviders,
    Splitter,
)
from etos_lib.kubernetes import Kubernetes, EnvironmentRequest
from etos_lib.kubernetes.schemas.common import Metadata
from jsontas.jsontas import JsonTas
from environment_provider.lib.registry import ProviderRegistry

from .graphql import request_activity_triggered, request_artifact_created


class Config:
    """Environment provider configuration."""

    logger = logging.getLogger("Config")
    __request = None
    __activity_triggered = None

    def __init__(self, etos: ETOS, kubernetes: Kubernetes, ids: Optional[list[str]] = None) -> None:
        """Initialize with ETOS library and automatically load the config.

        :param etos: ETOS library instance.
        :param kubernetes: Kubernetes client.
        :param ids: Suite runner IDs to correlate environment requests when not running in the
                    ETOS controller environment. Is set to None if executed by the ETOS controller.
        """
        self.kubernetes = kubernetes
        self.etos = etos
        self.ids = ids
        self.load_config()

    @property
    def etos_controller(self) -> bool:
        """Whether or not the environment provider is running as a part of the ETOS controller."""
        try:
            request = EnvironmentRequest(self.kubernetes)
            request_name = os.getenv("REQUEST")
            return request_name is not None and request.exists(request_name)
        except MaxRetryError:
            self.logger.warning(
                "Could not initialize EnvironmentRequest client, "
                "assuming that the environment provider is not running "
                "in Kubernetes or that the ETOS controller system is not "
                "deployed in this cluster."
            )
            return False

    def load_config(self) -> None:
        """Load config from environment variables."""
        self.etos.config.set("DEV", os.getenv("DEV", "false").lower() == "true")

        for key, value in os.environ.items():
            # The ENVIRONMENT_PROVIDER key is added to all configuration parameters
            # from the configuration files. This is to make the configuration
            # files more explicit and informative.
            # However this explicitness and information is detrimental to the
            # readability of the environment provider, so we choose to remove
            # them when loading them into the local configuration.
            if key.startswith("ENVIRONMENT_PROVIDER"):
                if isinstance(value, bytes):
                    value = value.decode("utf-8")
                if value.isdigit():
                    value = int(value)
                elif value.isdecimal():
                    value = float(value)
                self.etos.config.set(key.replace("ENVIRONMENT_PROVIDER_", ""), value)

    def __wait_for_activity(self) -> Optional[dict]:
        """Wait for activity triggered event."""
        self.logger.info(
            "Waiting for an activity triggered event - Timeout: %ds",
            self.etos.config.get("EVENT_DATA_TIMEOUT"),
        )
        timeout = time.time() + self.etos.config.get("EVENT_DATA_TIMEOUT")  # type: ignore
        while time.time() <= timeout:
            time.sleep(1)
            # The reason we select the first index in the list here is because of how the
            # current way of running the environment provider works. Whereas the new controller
            # based way of running will create a request per test suite, the current way
            # will start the environment provider once for all test suites. We will create
            # requests per test suite in this config, but they will hold mostly the same
            # information, such as the identifier being the same on all requests.
            testrun_id = self.requests[0].spec.identifier
            self.logger.info("Testrun ID is %s", testrun_id)
            response = request_activity_triggered(self.etos, testrun_id)
            self.logger.info("Response from GraphQL query: %s", response)
            if response is None:
                self.logger.info("No response from event repository yet, retrying")
                continue
            edges = response.get("activityTriggered", {}).get("edges", [])
            self.logger.info("Activity triggered edges found: %s", edges)
            if len(edges) == 0:
                self.logger.info("No activity triggered found yet, retrying")
                continue
            return edges[0]["node"]
        self.logger.info(
            "Activity triggered event not found after %ds",
            self.etos.config.get("EVENT_DATA_TIMEOUT"),
        )
        return None

    # TODO: The requests method shall not return a list in the future, this is just to
    # keep the changes backwards compatible.
    @property
    def requests(self) -> list[EnvironmentRequestSchema]:
        """Request returns the environment request, either from Eiffel TERCC or environment."""
        if self.__request is None:
            if self.etos_controller:
                request_client = EnvironmentRequest(self.kubernetes)
                request_name = os.getenv("REQUEST")
                assert request_name is not None, "Environment variable REQUEST must be set!"
                self.__request = [
                    EnvironmentRequestSchema.model_validate(
                        request_client.get(request_name).to_dict()  # type: ignore
                    )
                ]
            else:
                # Whenever the environment provider is run as a part of the suite runner,
                # this variable is set.
                tercc = json.loads(os.getenv("TERCC", "{}"))
                self.__request = self.__request_from_tercc(tercc)
        return self.__request

    @property
    def context(self) -> str:
        """Get activity triggered ID.

        :return: Activity Triggered ID
        """
        if self.etos_controller:
            activity_triggered: Optional[EiffelActivityTriggeredEvent] = self.etos.config.get(
                "environment_provider_context"
            )
            if activity_triggered is not None:
                self.__activity_triggered = activity_triggered.json
        if self.__activity_triggered is None:
            self.logger.info("No activity triggered yet, waiting for the event")
            self.__activity_triggered = self.__wait_for_activity()
            assert (
                self.__activity_triggered is not None
            ), "ActivityTriggered must exist for the environment provider"
        try:
            return self.__activity_triggered["meta"]["id"]
        except KeyError:
            return ""

    def __request_from_tercc(self, tercc: dict) -> list[EnvironmentRequestSchema]:
        """Create an environment request schema from a TERCC."""
        assert (
            self.ids is not None
        ), "Suite runner IDs must be provided when running outside of controller"
        requests = []
        artifact_id = tercc["links"][0]["target"]
        response = request_artifact_created(self.etos, artifact_id)
        assert response is not None, "ArtifactCreated must exist for the environment provider"
        artifact = response["artifactCreated"]["edges"][0]["node"]

        test_suites = self.__test_suite(tercc)

        registry = ProviderRegistry(self.etos, JsonTas(), tercc["meta"]["id"])

        datasets = registry.dataset()
        if isinstance(datasets, list):
            assert len(datasets) == len(test_suites), (
                "If multiple datasets are provided, the number of datasets must correspond "
                "with number of test suites"
            )
        else:
            datasets = [datasets] * len(test_suites)

        for suite in test_suites:
            requests.append(
                EnvironmentRequestSchema(
                    metadata=Metadata(),
                    spec=EnvironmentRequestSpec(
                        id=self.ids.pop(0),
                        name=suite.get("name"),
                        identifier=tercc["meta"]["id"],
                        artifact=artifact_id,
                        identity=artifact["data"]["identity"],
                        minimumAmount=1,
                        maximumAmount=10,  # TODO: Ignored in environment_provider.py
                        image="N/A",
                        imagePullPolicy="N/A",
                        splitter=Splitter(tests=Suite.tests_from_recipes(suite.get("recipes", []))),
                        dataset=datasets.pop(0),
                        providers=EnvironmentProviders(),
                    ),
                )
            )
        return requests

    def __test_suite(self, tercc: dict) -> list[dict]:
        """Download and return test batches.

        :return: Batches.
        """
        try:
            batch = tercc.get("data", {}).get("batches")
            batch_uri = tercc.get("data", {}).get("batchesUri")
            if batch is not None and batch_uri is not None:
                raise ValueError("Only one of 'batches' or 'batchesUri' shall be set")
            if batch is not None:
                return batch
            if batch_uri is not None:
                response = self.etos.http.get(
                    batch_uri,
                    timeout=self.etos.config.get("TEST_SUITE_TIMEOUT"),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                return response.json()
            return []
        except AttributeError:
            return []
