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
"""ETOS testrun model."""
from typing import Optional, List, Any
from pydantic import BaseModel
from .common import Metadata, Image

__all__ = ["TestRun", "TestRunSpec"]


class Environment(BaseModel):
    """Environment describes the environment in which a test shall run.

    This is different from the `Execution.environment` field which is
    used to describe the environment variables to set for the testrunner.
    """


class TestCase(BaseModel):
    """TestCase holds meta information about a testcase to run."""

    id: str
    tracker: str
    url: str
    version: Optional[str] = "master"


class Execution(BaseModel):
    """Execution describes how to execute a single test case."""

    checkout: List[str]
    command: str
    testRunner: str
    environment: dict[str, Any] = {}
    execute: List[str] = []
    parameters: dict[str, str] = {}


class Test(BaseModel):
    """Test describes the environment and execution of a test case."""

    id: str
    environment: Environment
    execution: Execution
    testCase: TestCase


class Suite(BaseModel):
    """Suite is a single test suite to execute in an ETOS testrun."""

    name: str
    priority: Optional[int] = 1
    tests: List[Test]

    @classmethod
    def tests_from_recipes(cls, recipes: list[dict]) -> list[Test]:
        """Load tests from Eiffel TERCC recipes.

        Tests from recipes will read the recipes field of an Eiffel TERCC
        and create a list of Test.

        :param recipes: The recipes defined in an Eiffel TERCC.
        :return: A list of Test models.
        """
        tests: list[Test] = []
        for recipe in recipes:
            execution = {}
            for constraint in recipe.get("constraints", []):
                if constraint.get("key") == "ENVIRONMENT":
                    execution["environment"] = constraint.get("value", {})
                elif constraint.get("key") == "PARAMETERS":
                    execution["parameters"] = constraint.get("value", {})
                elif constraint.get("key") == "COMMAND":
                    execution["command"] = constraint.get("value", "")
                elif constraint.get("key") == "EXECUTE":
                    execution["execute"] = constraint.get("value", [])
                elif constraint.get("key") == "CHECKOUT":
                    execution["checkout"] = constraint.get("value", [])
                elif constraint.get("key") == "TEST_RUNNER":
                    execution["testRunner"] = constraint.get("value", "")
            tests.append(
                Test(
                    id=recipe.get("id", ""),
                    environment=Environment(),
                    testCase=TestCase(**recipe.get("testCase", {})),
                    execution=Execution(**execution),
                )
            )
        return tests


class Providers(BaseModel):
    """Providers describes the providers to use for a testrun."""

    executionSpace: Optional[str] = "default"
    logArea: Optional[str] = "default"
    iut: Optional[str] = "default"


class TestRunSpec(BaseModel):
    """TestRunSpec is the specification of a TestRun Kubernetes resource."""

    cluster: str
    artifact: str
    suiteRunner: Image
    environmentProvider: Image
    id: str
    identity: str
    providers: Providers
    suites: List[Suite]


class TestRun(BaseModel):
    """TestRun Kubernetes resource."""

    apiVersion: Optional[str] = "etos.eiffel-community.github.io/v1alpha1"
    kind: Optional[str] = "TestRun"
    metadata: Metadata
    spec: TestRunSpec
