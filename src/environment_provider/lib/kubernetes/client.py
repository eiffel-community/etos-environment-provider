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
"""Kubernetes client for ETOS custom resources."""
import os
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
from kubernetes import config
from kubernetes.client import api_client
from kubernetes.dynamic import DynamicClient
from kubernetes.dynamic.resource import Resource as DynamicResource, ResourceInstance
from kubernetes.dynamic.exceptions import ResourceNotFoundError, ResourceNotUniqueError, NotFoundError

config.load_config()
NAMESPACE_FILE = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


class NoNamespace(Exception):
    """NoNamespace exception is raised when ETOS could not determine the current namespace"""


class Resource:
    """Resource is the base resource client for ETOS custom resources."""

    client: DynamicResource
    namespace: str = "default"
    strict: bool = False
    __cache = {}

    @contextmanager
    def _catch_errors_if_not_strict(self):
        """Catch errors if the strict flag is False, else raise."""
        try:
            yield
        # Internal exceptions
        except NoNamespace:
            if self.strict:
                raise
        # Dynamic client exceptions
        except (ResourceNotFoundError, ResourceNotUniqueError):
            if self.strict:
                raise
        # Built-in exceptions
        except AttributeError:
            # AttributeError happens if ResourceNotFoundError was raised when setting up
            # clients.
            if self.strict:
                raise

    def __full_resource_name(self, name: str):
        """Full resource name will return the group, version, namespace and kind."""
        return f"{self.client.group}/{self.client.api_version}/{self.client.kind} {self.namespace}/{name}"

    def get(self, name: str, cache=True) -> Optional[ResourceInstance]:
        """Get a resource from Kubernetes by name.

        if Cache is set to False, then make sure to get the resource from kubernetes,
        if Cache is True, then the cache will be used every time.
        There is no cache invalidation!
        """
        resource: Optional[ResourceInstance] = None
        if cache:
            resource = self.__cache.get(self.__full_resource_name(name))
        if resource is not None:
            return resource
        try:
            with self._catch_errors_if_not_strict():
                resource = self.client.get(name=name, namespace=self.namespace)  # type: ignore
                if resource:
                    self.__cache[self.__full_resource_name(name)] = resource
        except NotFoundError:
            resource = None
        return resource

    def exists(self, name: str) -> bool:
        """Test if a resource with name exists."""
        return self.get(name) is not None


class Kubernetes:
    """Kubernetes is a client for fetching ETOS custom resources from Kubernetes."""

    __providers = None
    __requests = None
    __testruns = None
    __environments = None
    __namespace = None
    logger = logging.getLogger(__name__)

    def __init__(self, version="v1alpha1"):
        """Initialize a dynamic client with version."""
        self.version = f"etos.eiffel-community.github.io/{version}"
        self.__client = DynamicClient(api_client.ApiClient())

    @property
    def namespace(self) -> str:
        """Namespace returns the current namespace of the machine this code is running on."""
        if self.__namespace is None:
            if not NAMESPACE_FILE.exists():
                self.logger.warning("Not running in Kubernetes? Namespace file not found: %s", NAMESPACE_FILE)
                etos_ns = os.getenv("ETOS_NAMESPACE")
                if etos_ns:
                    self.logger.warning("Defauling to environment variable 'ETOS_NAMESPACE': %s", etos_ns)
                else:
                    self.logger.warning("ETOS_NAMESPACE environment variable not set!")
                    raise NoNamespace("Failed to determine Kubernetes namespace!")
                self.__namespace = etos_ns
            else:
                self.__namespace = NAMESPACE_FILE.read_text()
        return self.__namespace

    @property
    def providers(self) -> DynamicResource:
        """Providers request returns a client for Provider resources."""
        if self.__providers is None:
            self.__providers = self.__client.resources.get(api_version=self.version, kind="Provider")
        return self.__providers

    @property
    def environment_requests(self) -> DynamicResource:
        """Environment requests returns a client for EnvironmentRequest resources."""
        if self.__requests is None:
            self.__requests = self.__client.resources.get(api_version=self.version, kind="EnvironmentRequest")
        return self.__requests

    @property
    def environments(self) -> DynamicResource:
        """Environments returns a client for Environment resources."""
        if self.__environments is None:
            self.__environments = self.__client.resources.get(api_version=self.version, kind="Environment")
        return self.__environments

    @property
    def testruns(self) -> DynamicResource:
        """Testruns returns a client for TestRun resources."""
        if self.__testruns is None:
            self.__testruns = self.__client.resources.get(api_version=self.version, kind="TestRun")
        return self.__testruns
