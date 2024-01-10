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
"""JSONTas uuid generate data structure module."""
from uuid import uuid4

from jsontas.data_structures.datastructure import DataStructure

# pylint:disable=too-few-public-methods


class UuidGenerate(DataStructure):
    """Generate UUID4 data structure."""

    def execute(self) -> tuple[None, str]:
        """Execute datastructure.

        :return: Name of key (None, to tell JSONTas to not override key name and a UUID4 string.
        """
        return None, str(uuid4())
