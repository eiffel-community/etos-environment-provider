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
"""Handler for graphql queries."""
import json
from http.server import BaseHTTPRequestHandler

from graphql import parse

# pylint:disable=invalid-name


class GraphQLHandler(BaseHTTPRequestHandler):
    """GraphQL handler for the fake HTTP server."""

    def __init__(self, tercc, *args, **kwargs):
        """Initialize a BaseHTTPRequestHandler. This must be initialized with functools.partial.

        Example:
            handler = functools.partial(Handler, self.tercc)
            with FakeServer(handler) as server:
                print(server.host)

        :param tercc: Test execution recipe collection for a test scenario.
        :type tercc: dict
        """
        self.tercc = tercc
        super().__init__(*args, **kwargs)

    def get_gql_query(self, request_data):
        """Parse request data in order to get a GraphQL query string.

        :param request_data: Data to parse query string from.
        :type request_data: byte
        :return: The GraphQL query name.
        :rtype: str
        """
        data_dict = json.loads(request_data)
        parsed = parse(data_dict["query"]).to_dict()
        for definition in parsed.get("definitions", []):
            for selection in definition.get("selection_set", {}).get("selections", []):
                query_name = selection.get("name", {}).get("value")
                return query_name
        raise TypeError("Not a valid GraphQL query")

    def test_execution_recipe_collection_created(self):
        """Create a fake tercc event.

        :return: A graphql response with a tercc event.
        :rtype dict
        """
        return {
            "data": {
                "testExecutionRecipeCollectionCreated": {
                    "edges": [
                        {
                            "node": {
                                "data": self.tercc["data"],
                                "meta": {"id": self.tercc["meta"]["id"]},
                                "links": [
                                    {
                                        "links": {
                                            "__typename": "ArtifactCreated",
                                            "data": {"identity": "pkg:test/environment-provider"},
                                            "meta": {"id": self.tercc["links"][0]["target"]},
                                        }
                                    }
                                ],
                            }
                        }
                    ]
                }
            }
        }

    def activity_triggered(self):
        """Create a fake activity triggered event.

        :return: A graphql response with an activity triggered event.
        :rtype dict
        """
        return {
            "data": {
                "activityTriggered": {
                    "edges": [{"node": {"meta": {"id": "2ec8b7db-1cdd-417a-9cf8-9cec370b117f"}}}]
                }
            }
        }

    def artifact_published(self):
        """Create a fake artifact published event.

        :return: A graphql response with an artifact published event.
        :rtype dict
        """
        return {"data": {"artifactPublished": {"edges": [{"node": {"data": {"locations": []}}}]}}}

    def artifact_created(self):
        """Create a fake artifact created event.

        :return: A graphql response with an artifact created event.
        :rtype dict:
        """
        artifact_id = self.tercc["links"][0]["target"]
        return {
            "data": {
                "artifactCreated": {
                    "edges": [
                        {
                            "node": {
                                "data": {"identity": "pkg:test/environment-provider"},
                                "meta": {"id": artifact_id},
                            }
                        }
                    ]
                }
            }
        }

    def test_suite_started(self):
        """Create a fake test suite started to simulate ESR.

        :return: A graphql response with a test suite started event.
        :rtype dict
        """
        return {
            "data": {
                "testSuiteStarted": {
                    "edges": [{"node": {"meta": {"id": "3d1cab0e-dacb-4991-afac-7581eea4a3df"}}}]
                }
            }
        }

    def do_POST(self):
        """Handle graphql post requests for the environment provider tests."""
        request_data = self.rfile.read(int(self.headers["Content-Length"]))
        query_name = self.get_gql_query(request_data)

        if query_name == "activityTriggered":
            response = self.activity_triggered()
        elif query_name == "artifactCreated":
            response = self.artifact_created()
        elif query_name == "artifactPublished":
            response = self.artifact_published()
        elif query_name == "testSuiteStarted":
            response = self.test_suite_started()
        else:
            response = None

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        response_content = json.dumps(response)
        self.wfile.write(response_content.encode("utf-8"))

    def do_GET(self):
        """Handle GET requests."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        response_content = json.dumps({})
        self.wfile.write(response_content.encode("utf-8"))
