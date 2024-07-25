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
"""ETOS provider model."""
import json
from json.decoder import JSONDecodeError
from typing import Optional, Union
from typing_extensions import Annotated
from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator
from .common import Metadata

def json_load_str_if_possible(data: str) -> Union[dict, str]:
    """Attempt to load a str as JSON or just return the str."""
    try:
        return json.loads(data)
    except JSONDecodeError:
        return data

JSON = Annotated[str, AfterValidator(json_load_str_if_possible)]


class JSONTasList(BaseModel):
    """JSONTasList describes the list part of a JSONTas provider."""

    possible: JSON
    available: JSON


class BaseProvider(BaseModel):
    """BaseProvider describes the base parts of JSONTas providers."""

    id: str
    checkin: Optional[JSON] = None
    checkout: Optional[JSON] = None
    list: JSONTasList


class Stage(BaseModel):
    """Stage is the IUT prepare stage for an IUT provider."""

    steps: str


class JSONTasIutPrepareStages(BaseModel):
    """JSONTasIUTPrepareStages describes the prepare stages for an IUT provider."""

    environmentProvider: Optional[Stage] = None
    suiteRunner: Optional[Stage] = None
    testRunner: Optional[Stage] = None


class JSONTasIutPrepare(BaseModel):
    """JSONTasIUTPrepare describes the prepare for an IUT provider."""

    stages: JSONTasIutPrepareStages


class JSONTasIut(BaseProvider):
    """JSONTasIUT describes the JSONTas specification of an IUT provider."""

    prepare: Optional[JSONTasIutPrepare] = None


class JSONTasExecutionSpace(BaseProvider):
    """JSONTasExecutionSpace describes the JSONTas specification of an execution space provider."""


class JSONTasLogArea(BaseProvider):
    """JSONTasLogArea describes the JSONTas specification of a log area provider."""


class JSONTas(BaseModel):
    """JSONTas describes the JSONTas specification of a provider."""

    iut: Optional[JSONTasIut] = None
    executionSpace: Optional[JSONTasExecutionSpace] = None
    logArea: Optional[JSONTasLogArea] = None


class Healthcheck(BaseModel):
    """Healthcheck describes the healthcheck rules of a provider."""

    endpoint: str
    intervalSeconds: int


class ProviderSpec(BaseModel):
    """ProviderSpec is the specification of a Provider Kubernetes resource."""

    type: str
    host: str
    healthCheck: Healthcheck
    jsontas: Optional[JSONTas] = None


class Provider(BaseModel):
    """Provider Kubernetes resource."""

    apiVersion: Optional[str] = "etos.eiffel-community.github.io/v1alpha1"
    kind: Optional[str] = "Provider"
    spec: ProviderSpec
    metadata: Metadata

    def to_jsontas(self) -> dict:
        """To JSONTas will convert a provider to a JSONTas ruleset.

        This method is for the transition period between the current ETOS and
        the kubernetes controller based ETOS.
        """
        ruleset = {}
        if self.spec.jsontas is not None:
            if self.spec.type == "iut":
                assert self.spec.jsontas.iut is not None, \
                        "IUT must be a part of a Provider with type 'iut'."
                ruleset = self.spec.jsontas.iut.model_dump()
            elif self.spec.type == "execution-space":
                assert self.spec.jsontas.executionSpace is not None, \
                        "Execution space must be a part of a Provider with type 'execution-space'."
                ruleset = self.spec.jsontas.executionSpace.model_dump()
            elif self.spec.type == "log-area":
                assert self.spec.jsontas.logArea is not None, \
                        "Log area must be a part of a Provider with type 'log-area'."
                ruleset = self.spec.jsontas.logArea.model_dump()
        ruleset["id"] = self.metadata.name
        return ruleset

    def to_external(self) -> dict:
        """To external will convert a provider to an external provider ruleset.

        This method is for the transition period between the current ETOS and
        the kubernetes controller based ETOS.
        """
        return {
            "id": self.metadata.name,
            "type": "external",
            "status": {
                "host": f"{self.spec.host}/status"
            },
            "start": {
                "host": f"{self.spec.host}/start"
            },
            "stop": {
                "host": f"{self.spec.host}/stop"
            },
        }
