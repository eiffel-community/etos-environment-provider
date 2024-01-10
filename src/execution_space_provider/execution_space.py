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
"""Execution space data module."""
from typing import Any


class ExecutionSpace:
    """Execution space data object."""

    _execution_space_dictionary = None

    def __init__(self, **execution_space: dict) -> None:
        """Take a dictionary as input and setattr on instance.

        :param execution_space: Dictionary to set attributes from.
        """
        self._execution_space_dictionary = execution_space
        for key, value in execution_space.items():
            setattr(self, key, value)

    def __setattr__(self, name: str, value: Any) -> None:
        """Set execution space parameters to dict and object.

        :param name: Name of parameter to set.
        :param value: Value of parameter.
        """
        if self._execution_space_dictionary is not None:
            self._execution_space_dictionary[name] = value
        super().__setattr__(name, value)

    def update(self, **dictionary: dict) -> None:
        """Update execution space dictionary with new data.

        :param dictionary: Dictionary to update attributes from.
        """
        self._execution_space_dictionary.update(**dictionary)
        for key, value in dictionary.items():
            setattr(self, key, value)

    @property
    def as_dict(self) -> dict:
        """Represent execution space as dictionary.

        :return: Execution space dictionary.
        """
        return self._execution_space_dictionary

    def __repr__(self) -> str:
        """Represent execution space as string.

        :return: Execution space dictionary as string.
        """
        return repr(self._execution_space_dictionary)
