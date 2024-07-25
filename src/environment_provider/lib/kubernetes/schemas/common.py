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
"""Common schemas that are used between most kubernetes resources."""
from typing import Optional
from pydantic import BaseModel


class OwnerReference(BaseModel):
    """Owner reference describes the owner of a kubernetes resource."""

    apiVersion: str
    kind: str
    name: str
    uid: str
    controller: Optional[bool]
    blockOwnerDeletion: bool


class Metadata(BaseModel):
    """Metadata describes the metadata of a kubernetes resource."""

    name: Optional[str] = None
    generateName: Optional[str] = None
    namespace: str = "default"
    ownerReferences: list[OwnerReference] = []


class Image(BaseModel):
    image: str
    imagePullPolicy: str = "IfNotPresent"
