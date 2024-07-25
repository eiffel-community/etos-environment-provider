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
from typing import Optional
from pydantic import BaseModel
from .common import Metadata
from .testrun import Test, Suite


class EnvironmentSpec(BaseModel):
    """EnvironmentSpec is the specification of a Environment Kubernetes resource."""

    name: str
    suite_id: str
    sub_suite_id: str
    test_suite_started_id: str
    artifact: str
    context: str
    priority: int = 1
    test_runner: str
    recipes: list[Test]
    iut: dict
    executor: dict
    log_area: dict

    @classmethod
    def from_subsuite(cls, sub_suite: dict) -> "EnvironmentSpec":
        sub_suite["recipes"] = Suite.tests_from_recipes(sub_suite.pop("recipes"))
        spec = EnvironmentSpec(**sub_suite)
        return spec


class Environment(BaseModel):
    """Environment Kubernetes resource."""

    apiVersion: Optional[str] = "etos.eiffel-community.github.io/v1alpha1"
    kind: Optional[str] = "Environment"
    metadata: Metadata
    spec: EnvironmentSpec
