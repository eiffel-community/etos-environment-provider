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
"""Log area provider module."""
from abc import abstractmethod
from .utilities.external_provider import ExternalProvider
from .utilities.jsontas_provider import JSONTasProvider


class LogAreaProvider:
    """Log area provider."""

    def __new__(cls, etos, jsontas, ruleset):
        """Check which type of provider and return an appropriate one."""
        if ruleset.get("type", "jsontas") == "external":
            return ExternalProvider(etos, jsontas, ruleset)
        else:
            return JSONTasProvider(etos, jsontas, ruleset)

    @abstractmethod
    def checkin(self, log_area):
        """Check in a single log area, returning it to the log area provider.

        :param log_area: Log area to checkin.
        :type log_area: :obj:`environment_provider.logs.log_area.LogArea`
        """

    @abstractmethod
    def checkin_all(self):
        """Check in all checked out log areas."""

    @abstractmethod
    def wait_for_and_checkout_log_areas(self, minimum_amount=0, maximum_amount=100):
        """Wait for and checkout log areas from an log area provider.

        :raises: LogAreaNotAvailable: If there are no available log areas after timeout.

        :param minimum_amount: Minimum amount of log areas to checkout.
        :type minimum_amount: int
        :param maximum_amount: Maximum amount of log areas to checkout.
        :type maximum_amount: int
        :return: List of checked out log areas.
        :rtype: list
        """
