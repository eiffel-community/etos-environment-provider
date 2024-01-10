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
"""Execution space provider instructions module."""
import os
from copy import deepcopy
from uuid import uuid4

from jsontas.data_structures.datastructure import DataStructure


class Instructions(DataStructure):  # pylint:disable=too-few-public-methods
    """Create execution space instructions."""

    def execute(self) -> tuple[None, dict]:
        """Execute datastructure.

        :return: Name of key and execution space spin-up instructions.
        """
        instructions = deepcopy(self.datasubset.get("instructions"))
        instructions["environment"].update(self.data.get("environment", {}))
        instructions["parameters"].update(self.data.get("parameters", {}))
        instructions["image"] = self.data.get("image", instructions["image"])
        instructions["identifier"] = str(uuid4())
        instructions["environment"]["ENVIRONMENT_ID"] = str(uuid4())
        if instructions["environment"].get("ETR_VERSION") is None:
            instructions["environment"]["ETR_VERSION"] = os.getenv("ETR_VERSION")
        self.add_feature_flags(instructions)
        return None, instructions

    @staticmethod
    def add_feature_flags(instructions: dict) -> None:
        """Add feature flag environment variables to instructions.

        :param instructions: The instructions dictionary in which to add environments.
        """
