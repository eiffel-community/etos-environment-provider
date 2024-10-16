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
"""A fake server implementation for testing remote requests."""
import json
import logging
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import requests

# pylint:disable=invalid-name


class Handler(BaseHTTPRequestHandler):
    """HTTP handler for the fake HTTP server."""

    response_json = None
    response_code = None
    parent = None
    logger = logging.getLogger(__name__)

    def do(self):
        """Handle fake requests to server."""
        json_string = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            json_string = json.loads(data_string)
        except:  # pylint: disable=bare-except
            pass
        response = self.response_json
        status = self.response_code
        if isinstance(self.response_json, list):
            response = self.response_json.pop(0)
        if isinstance(self.response_code, list):
            status = self.response_code.pop(0)
        if json_string is not None:
            self.parent.store_request(json_string)
        else:
            self.parent.store_request(self.request)
        self.send_response(requests.codes[status])
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        response_content = json.dumps(response)
        self.wfile.write(response_content.encode("utf-8"))

    def do_GET(self):
        """Handle GET requests."""
        self.do()

    def do_POST(self):
        """Handle POST requests."""
        self.do()


class FakeServer:
    """A fake server implementation for use in tests."""

    mock_server = None
    thread = None
    port = None

    def __init__(self, status_name, response_json, handler=Handler):
        """Initialize server with status name and response json.

        :param status_name: Name of status as defined by :obj:`requests.codes`.
        :type status_name: str or list
        :param response_json: A dictionary of JSON response that the fake server shal respond with.
        :type response_json: dict or list
        :param handler: Request handler to use for the fake server.
        :type handler: cls
        """
        self.requests = []
        self.handler = handler
        self.status_name = status_name
        self.response_json = response_json

    @staticmethod
    def __free_port():
        """Figure out a free port for localhost."""
        sock = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
        sock.bind(("localhost", 0))
        _, port = sock.getsockname()
        sock.close()
        return port

    @property
    def host(self):
        """Host property for this fake server."""
        return f"http://localhost:{self.port}"

    @property
    def nbr_of_requests(self):
        """Total number of requests made to server."""
        return len(self.requests)

    def store_request(self, request):
        """Store the request that was made.

        :param request: New request that was received.
        :type request: dict
        """
        self.requests.append(request)

    def __enter__(self):
        """Figure out free port and start up a fake server in a thread."""
        self.port = self.__free_port()
        self.mock_server = HTTPServer(("localhost", self.port), self.handler)
        self.thread = Thread(target=self.mock_server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.mock_server.RequestHandlerClass.parent = self
        self.mock_server.RequestHandlerClass.response_code = self.status_name
        self.mock_server.RequestHandlerClass.response_json = self.response_json
        return self

    def __exit__(self, *_):
        """Shut down fake server."""
        self.mock_server.shutdown()
        self.thread.join(timeout=10)
