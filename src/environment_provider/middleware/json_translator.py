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
"""JSON translator module."""
import falcon

# pylint: disable=too-few-public-methods


class JSONTranslator:
    """Translate request media to JSON."""

    def process_request(self, req, _):
        """Process request."""
        if req.content_length in (None, 0):
            return

        body = req.media
        if not body:
            raise falcon.HTTPBadRequest(
                "Empty request body", "A valid JSON document is required."
            )
