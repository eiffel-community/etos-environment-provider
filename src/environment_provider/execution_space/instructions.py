# Copyright 2020 Axis Communications AB.
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
from uuid import uuid4
from copy import deepcopy
from jsontas.data_structures.datastructure import DataStructure


class Instructions(DataStructure):  # pylint:disable=too-few-public-methods
    """Create execution space instructions."""

    def execute(self):
        """Execute datastructure.

        :return: Name of key and execution space spin-up instructions.
        :rtype: tuple
        """
        instructions = deepcopy(self.datasubset.get("instructions"))
        instructions["environment"].update(self.data.get("environment", {}))
        instructions["parameters"].update(self.data.get("parameters", {}))
        instructions["image"] = self.data.get("image", instructions["image"])
        instructions["identifier"] = str(uuid4())

        instructions["environment"]["SUB_SUITE_URL"] = "{}/sub_suite?id={}".format(
            instructions["environment"]["ETOS_ENVIRONMENT_PROVIDER"],
            instructions["identifier"],
        )
        return None, instructions
