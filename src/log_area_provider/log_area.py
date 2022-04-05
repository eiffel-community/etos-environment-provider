# Copyright 2020-2022 Axis Communications AB.
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
"""Log area provider data module."""


class LogArea:
    """Log area data object."""

    _log_area_dictionary = None

    def __init__(self, **log_area):
        """Take a dictionary as input and setattr on instance.

        :param log_area: Dictionary to set attributes from.
        :type log_area: dict
        """
        self._log_area_dictionary = log_area
        for key, value in log_area.items():
            setattr(self, key, value)

    def __setattr__(self, name, value):
        """Set log area parameters to dict and object.

        :param name: Name of parameter to set.
        :type name: str
        :param value: Value of parameter.
        :type value: any
        """
        if self._log_area_dictionary is not None:
            self._log_area_dictionary[name] = value
        super().__setattr__(name, value)

    def update(self, **dictionary):
        """Update log area dictionary with new data.

        :param dictionary: Dictionary to update attributes from.
        :type dictionary: dict
        """
        self._log_area_dictionary.update(**dictionary)
        for key, value in dictionary.items():
            setattr(self, key, value)

    @property
    def as_dict(self):
        """Represent log area as dictionary.

        :return: Log area dictionary.
        :rtype: dict
        """
        return self._log_area_dictionary

    def __repr__(self):
        """Represent log area as string.

        :return: Log area dictionary as string.
        :rtype: str
        """
        return repr(self._log_area_dictionary)
