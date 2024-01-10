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
"""Common functionality for all backend types."""
from typing import Optional

from falcon import Request
from falcon.errors import MediaNotFoundError


def get_suite_id(request: Request) -> Optional[str]:
    """Get a suite ID from the request.

    :param request: The falcon request object.
    :return: A Suite ID.
    """
    try:
        media = request.get_media()
        return media.get("suite_id")
    except MediaNotFoundError:
        return request.get_param("suite_id")


def get_suite_runner_ids(request: Request) -> Optional[str]:
    """Get suite runner IDs from the request.

    :param request: The falcon request object.
    :return: Suite runner IDs.
    """
    try:
        media = request.get_media()
        param = media.get("suite_runner_ids")
    except MediaNotFoundError:
        param = request.get_param("suite_runner_ids")
    if param is None:
        return param
    return param.split(",")
