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
import json
import os
from typing import Union, Optional

from etos_lib import ETOS
from etos_lib.kubernetes.schemas.testrun import TestRun as TestRunSchema, TestRunSpec, Providers
from etos_lib.kubernetes import Kubernetes, TestRun
from etos_lib.kubernetes.schemas.common import Metadata, Image
from packageurl import PackageURL

from .graphql import request_activity_triggered, request_artifact_published, request_artifact_created


class Config:  # pylint:disable=too-many-instance-attributes
    """Environment provider configuration."""

    logger = logging.getLogger("Config")
    __testrun = None
    __artifact_created = None
    __artifact_published = None
    __activity_triggered = None

    def __init__(self, etos: ETOS) -> None:
        """Initialize with ETOS library and automatically load the config.

        :param etos: ETOS library instance.
        """
        self.kubernetes = Kubernetes()
        self.etos = etos
        self.load_config()

    @property
    def etos_controller(self) -> bool:
        """Whether or not the environment provider is running as a part of the ETOS controller."""
        testrun = TestRun(self.kubernetes)
        testrun_name = os.getenv("TESTRUN")
        return testrun_name is not None and testrun.exists(testrun_name)

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
            response = request_activity_triggered(self.etos, self.testrun.spec.id)
            assert response is not None, "ActivityTriggered must exist for the environment provider"
            self.__activity_triggered = response["activityTriggered"]["edges"][0]["node"]
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
