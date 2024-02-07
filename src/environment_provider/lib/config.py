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
import os
import time
from typing import Iterator, Union

from etos_lib import ETOS
from packageurl import PackageURL

from .graphql import request_activity_triggered, request_artifact_published, request_tercc


class Config:  # pylint:disable=too-many-instance-attributes
    """Environment provider configuration."""

    logger = logging.getLogger("Config")
    __test_suite = None
    generated = False
    artifact_created = None
    artifact_published = None
    activity_triggered = None
    tercc = None

    def __init__(self, etos: ETOS, tercc_id: str) -> None:
        """Initialize with ETOS library and automatically load the config.

        :param etos: ETOS library instance.
        :param tercc_id: ID of test execution recipe.
        """
        self.etos = etos
        self.load_config()
        self.tercc_id = tercc_id
        self.__generate()

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

    def __search_for_node_typename(
        self, response: dict, *nodes: list[str], key: str = "node"
    ) -> Iterator[tuple[str, dict]]:
        """Search for a graphql node by __typename.

        :param response: Response to search through.
        :param nodes: Nodes to search for.
        :param key: Name of the node key.
        :return: Iterator
        """
        for _, node in self.etos.utils.search(response, key):
            if isinstance(node, dict) and node.get("__typename") in nodes:
                yield node.get("__typename"), node

    def __get_node(self, response: dict, node: str, key: str) -> tuple[str, dict]:
        """Get a single node from graphql response.

        :param response: Response to search through.
        :param node: Node to search for.
        :param key: Name of the node key.
        :return: Tuple of node name(str) and node data(dict)
        """
        try:
            node_name, node = next(self.__search_for_node_typename(response, node, key=key))
            node = node.copy()
            try:
                node.pop("reverse")
            except KeyError:
                pass
            return node_name, node
        except StopIteration:
            return "", {}

    def _validate_event_data(self) -> bool:
        """Validate that the event data required for environment provider is set.

        :return: Whether event data is set or not.
        """
        try:
            assert self.tercc is not None
            assert self.artifact_created is not None
            assert self.activity_triggered is not None
            return True
        except AssertionError:
            return False

    def __generate(self) -> None:
        """Generate the event data required for the environment provider."""
        if self.generated is False:
            self.logger.info("Generate event data from event storage.")
            timeout = time.time() + self.etos.config.get("EVENT_DATA_TIMEOUT")
            while not self._validate_event_data():
                self.logger.info("Waiting for event data.")
                if time.time() > timeout:
                    self.logger.error("Timeout reached. Exiting.")
                    return None

                try:
                    response = request_tercc(self.etos, self.tercc_id)
                    node = response["testExecutionRecipeCollectionCreated"]["edges"][0]["node"]
                    node = node.copy()
                    node.pop("links")
                    self.tercc = node
                    _, self.artifact_created = self.__get_node(response, "ArtifactCreated", "links")

                    response = request_activity_triggered(self.etos, self.tercc_id)
                    self.activity_triggered = response["activityTriggered"]["edges"][0]["node"]

                    response = request_artifact_published(self.etos, self.artifact_id)
                    # ArtifactPublished is not required and can be None.
                    if response:
                        self.artifact_published = response["artifactPublished"]["edges"][0]["node"]
                except:  # noqa, pylint:disable=bare-except
                    pass
                time.sleep(1)
            self.generated = True
        return None

    @property
    def context(self) -> str:
        """Get activity triggered ID.

        :return: Activity Triggered ID
        """
        try:
            return self.activity_triggered["meta"]["id"]
        except KeyError:
            return ""

    @property
    def artifact_id(self) -> str:
        """Get artifact ID.

        :return: Artifact ID
        """
        try:
            return self.artifact_created["meta"]["id"]
        except KeyError:
            return ""

    @property
    def identity(self) -> Union[PackageURL, str]:
        """Get artifact identity.

        :return: Artifact identity.
        """
        try:
            return PackageURL.from_string(self.artifact_created["data"]["identity"])
        except KeyError:
            return ""

    @property
    def test_suite(self) -> list[dict]:
        """Download and return test batches.

        :return: Batches.
        """
        if self.__test_suite is None:
            try:
                batch = self.tercc.get("data", {}).get("batches")
                batch_uri = self.tercc.get("data", {}).get("batchesUri")
                if batch is not None and batch_uri is not None:
                    raise ValueError("Only one of 'batches' or 'batchesUri' shall be set")
                if batch is not None:
                    self.__test_suite = batch
                elif batch_uri is not None:
                    response = self.etos.http.get(
                        batch_uri,
                        timeout=self.etos.config.get("TEST_SUITE_TIMEOUT"),
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()
                    self.__test_suite = response.json()
            except AttributeError:
                pass
        return self.__test_suite if self.__test_suite else []
