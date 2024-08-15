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
from typing import Union, Optional

from etos_lib import ETOS
from etos_lib.kubernetes.schemas.testrun import TestRun as TestRunSchema, TestRunSpec, Providers, Suite
from etos_lib.kubernetes.schemas.environment_request import (
    EnvironmentRequest as EnvironmentRequestSchema,
    EnvironmentRequestSpec,
    EnvironmentProviders,
    Splitter,
)
from etos_lib.kubernetes import Kubernetes, TestRun, EnvironmentRequest
from etos_lib.kubernetes.schemas.common import Metadata, Image
from environment_provider.lib.registry import ProviderRegistry
from packageurl import PackageURL
from jsontas.jsontas import JsonTas

from .graphql import request_activity_triggered, request_artifact_published, request_artifact_created


class Config:  # pylint:disable=too-many-instance-attributes
    """Environment provider configuration."""

    logger = logging.getLogger("Config")
    __testrun = None
    __request = None
    __artifact_created = None
    __artifact_published = None
    __activity_triggered = None

    def __init__(self, etos: ETOS, ids: Optional[list[str]]=None) -> None:
        """Initialize with ETOS library and automatically load the config.

        :param etos: ETOS library instance.
        """
        self.kubernetes = Kubernetes()
        self.etos = etos
        self.ids = ids
        self.load_config()

    @property
    def etos_controller(self) -> bool:
        """Whether or not the environment provider is running as a part of the ETOS controller."""
        request = EnvironmentRequest(self.kubernetes)
        request_name = os.getenv("REQUEST")
        return request_name is not None and request.exists(request_name)

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
        timeout = time.time() + (self.etos.config.get("EVENT_DATA_TIMEOUT") or 30)  # TODO: This default is nogood
        while time.time() <= timeout:
            time.sleep(1)
            # This selects an index from the requests list. This is because of how the
            # current way of running the environment provider works. Whereas the new controller
            # based way of running will create a request per test suite, the current way
            # will start the environment provider once for all test suites. We will create
            # requests per test suite in this config, but they will hold mostly the same
            # information, such as the identifier being the same on all requests.
            testrun_id = self.requests[0].spec.identifier
            response = request_activity_triggered(self.etos, testrun_id)
            if response is None:
                continue
            edges = response.get("activityTriggered", {}).get("edges", [])
            if len(edges) == 0:
                continue
            return edges[0]["node"]

    @property
    def requests(self) -> list[EnvironmentRequestSchema]:  # TODO: This shall not return a list
        """Request returns the environment request, either from Eiffel TERCC or environment."""
        if self.__request is None:
            if self.etos_controller:
                request_client = EnvironmentRequest(self.kubernetes, strict=True)
                request_name = os.getenv("REQUEST")
                assert request_name is not None, "Environment variable REQUEST must be set!"
                self.__request = [EnvironmentRequestSchema.model_validate(
                    request_client.get(request_name).to_dict()  # type: ignore
                )]
            else:
                # Whenever the environment provider is run as a part of the suite runner, this variable is set.
                tercc = json.loads(os.getenv("TERCC", "{}"))
                self.__request = self.__request_from_tercc(tercc)
        return self.__request

    @property
    def testrun(self) -> TestRunSchema:
        """Testrun returns the current testrun, either from Eiffel TERCC or ETOS TestRun."""
        if self.__testrun is None:
            if self.etos_controller:
                testrun_client = TestRun(self.kubernetes, strict=True)
                testrun_name = os.getenv("TESTRUN")
                assert testrun_name is not None, "Environment variable TESTRUN must be set!"
                self.__testrun = TestRunSchema.model_validate(testrun_client.get(testrun_name).to_dict())  # type: ignore
            else:
                # Whenever the environment provider is run as a part of the suite runner, this variable is set.
                tercc = json.loads(os.getenv("TERCC", "{}"))
                self.__testrun = self.__testrun_from_tercc(tercc)
        return self.__testrun

    @property
    def context(self) -> str:
        """Get activity triggered ID.

        :return: Activity Triggered ID
        """
        if self.__activity_triggered is None:
            self.__activity_triggered = self.__wait_for_activity()
            assert self.__activity_triggered is not None, "ActivityTriggered must exist for the environment provider"
        try:
            return self.__activity_triggered["meta"]["id"]
        except KeyError:
            return ""

    @property
    def artifact_id(self) -> str:
        """Get artifact ID.

        :return: Artifact ID
        """
        try:
            return self.testrun.spec.artifact
        except KeyError:
            return ""

    @property
    def artifact_created(self) -> dict:
        """Artifact created event that is the IUT of this execution."""
        if self.__artifact_created is None:
            response = request_artifact_created(self.etos, self.artifact_id)
            assert response is not None, "ArtifactCreated must exist for the environment provider"
            self.__artifact_created = response["artifactCreated"]["edges"][0]["node"]
        return self.__artifact_created

    @property
    def artifact_published(self) -> Optional[dict]:
        """Artifact published event where we shall find the IUT software, if it exists."""
        if self.__artifact_published is None:
            response = request_artifact_published(self.etos, self.artifact_id)
            if response is not None:
                self.__artifact_published = response["artifactPublished"]["edges"][0]["node"]
        return self.__artifact_published

    @property
    def identity(self) -> Union[PackageURL, str]:
        """Get artifact identity.

        :return: Artifact identity.
        """
        try:
            return PackageURL.from_string(self.testrun.spec.identity)
        except KeyError:
            return ""

    @property
    def tercc(self) -> dict:
        """This is a fake TERCC event with all fields that existed before.

        While we are working towards the ETOS controller style of running tests,
        we keep this as to be backwards compatible. If the ETOS controller
        becomes the way we run tests, we shall remove this property and fix up
        the environment provider.
        """
        return {
            "meta": {
                "id": self.testrun.spec.id
            },
            "data": {
                "batchesUri": self.testrun.spec.suiteSource
            }
        }

    def __request_from_tercc(self, tercc: dict) -> list[EnvironmentRequestSchema]:
        assert self.ids is not None, "Suite runner IDs must be provided when running outside of controller"
        requests = []
        response = request_artifact_created(self.etos, tercc["links"][0]["target"])
        assert response is not None, "ArtifactCreated must exist for the environment provider"
        self.__artifact_created = response
        artifact = response["artifactCreated"]["edges"][0]["node"]

        test_suites = self.__test_suite(tercc)

        registry = ProviderRegistry(self.etos, JsonTas(), tercc["meta"]["id"])

        datasets = registry.dataset()
        if isinstance(datasets, list):
            assert len(datasets) == len(
                test_suites
            ), "If multiple datasets are provided it must correspond with number of test suites"
        else:
            datasets = [datasets] * len(test_suites)

        for suite in test_suites:
            requests.append(EnvironmentRequestSchema(
                metadata=Metadata(),
                spec=EnvironmentRequestSpec(
                    id=self.ids.pop(0),
                    name=suite.get("name"),
                    identifier=tercc["meta"]["id"],
                    artifact=artifact["meta"]["id"],
                    identity=artifact["data"]["identity"],
                    minimumAmount=1,
                    maximumAmount=10,
                    image="N/A",
                    imagePullPolicy="N/A",
                    splitter=Splitter(
                        tests=Suite.tests_from_recipes(suite.get("recipes", []))
                    ),
                    dataset=datasets.pop(0),
                    providers=EnvironmentProviders()
                )
            ))
        return requests

    def __testrun_from_tercc(self, tercc: dict) -> TestRunSchema:
        """Testrun from tercc will create a fake TestRun schema from TERCC.

        Some fields in this testrun schema are set to Unknown. This is fine for
        now, but might want to look into populating a few of them, such as
        'dataset' & 'providers', depending on how long we want to roll with
        both implementations of ETOS.
        """
        testrun = TestRunSchema(
            metadata=Metadata(),
            spec=TestRunSpec(
                cluster="Unknown",
                artifact=tercc["links"][0]["target"],
                suiteRunner=Image(image="Unknown"),
                logListener=Image(image="Unknown"),
                environmentProvider=Image(image="Unknown"),
                providers=Providers(
                    executionSpace="Unknown",
                    iut="Unknown",
                    logArea="Unknown",
                ),
                id=tercc["meta"]["id"],
                identity="Unknown",
                suiteSource=tercc.get("data", {}).get("batchesUri", "n/a"),
                suites=TestRunSpec.from_tercc(self.__test_suite(tercc), {}),
            )
        )
        response = request_artifact_created(self.etos, testrun.spec.artifact)
        assert response is not None, "ArtifactCreated must exist for the environment provider"
        self.__artifact_created = response
        node = response["artifactCreated"]["edges"][0]["node"]
        testrun.spec.identity = node["data"]["identity"]
        return testrun

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
            elif batch_uri is not None:
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


if __name__ == "__main__":
    ETOS_LIB = ETOS("", "", "")
    REGISTRY = ProviderRegistry(ETOS_LIB, JsonTas(), "12345")
    CONFIG = Config(ETOS_LIB,REGISTRY)
    print(CONFIG.etos_controller)
    print(CONFIG.request)
