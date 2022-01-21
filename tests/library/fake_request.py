# Copyright 2021 Axis Communications AB.
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
"""A fake request and response structure that can be used in tests."""


class FakeRequest:  # pylint:disable=too-few-public-methods
    """Fake request structure."""

    force_media_none = False

    def __init__(self):
        """Init some fake parameters."""
        self.fake_params = {}

    def get_param(self, name):
        """Get a parameter from the fake params dictionary.

        This is a fake version of the :obj:`falcon.Request` object.

        :param name: Name of parameter to get.
        :type name: str
        :return: The value in fake params.
        :rtype: any
        """
        return self.fake_params.get(name)

    @property
    def media(self):
        """Media is used for POST requests."""
        if self.force_media_none:
            return None
        return self.fake_params


class FakeResponse:  # pylint:disable=too-few-public-methods
    """Fake response structure."""

    fake_responses = None
    media = {}
    status = 0

    def __init__(self):
        """Init a fake response storage dict."""
        self.fake_responses = {}

    def __setattr__(self, key, value):
        """Set attributes to the fake responses dictionary."""
        if self.fake_responses is not None:
            self.fake_responses[key] = value
        super().__setattr__(key, value)
