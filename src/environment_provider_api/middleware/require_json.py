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
"""Require JSON module."""
import falcon

# pylint: disable=too-few-public-methods


class RequireJSON:
    """Require Accept: application/json headers for this API."""

    def process_request(self, req: falcon.Request, _) -> None:
        """Process request."""
        if not req.client_accepts_json:
            raise falcon.HTTPNotAcceptable(
                "This API only supports responses encoded as JSON.",
                href="http://docs.examples.com/api/json",
            )

        if req.method in ("POST", "PUT"):
            if req.content_type is None or "application/json" not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    "This API only supports requests encoded as JSON.",
                    href="http://docs.examples.com/api/json",
                )
