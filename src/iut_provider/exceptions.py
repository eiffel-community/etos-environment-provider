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
"""IUT provider exceptions."""


class NoIutFound(Exception):
    """IUT not found."""


class IutNotAvailable(Exception):
    """IUT does not exist."""


class IutCheckoutFailed(Exception):
    """Checkout failed."""


class IutCheckinFailed(Exception):
    """Checkin failed."""


class NotEnoughIutsAvailable(Exception):
    """Too many IUTs requested."""
