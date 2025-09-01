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
"""Environment provider log area handler."""
import logging
import os
import traceback
from copy import deepcopy
from json.decoder import JSONDecodeError
from typing import IO, Optional, Union
from urllib3.util import Retry

from cryptography.fernet import Fernet
from etos_lib import ETOS
from etos_lib.lib.http import Http
from requests import Response
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments

MAX_RETRIES = (
    10  # With 1 as backoff_factor, the total wait time between retries will be 1023 seconds
)
HTTP_RETRY_PARAMETERS = Retry(
    total=None,
    read=MAX_RETRIES,
    connect=MAX_RETRIES,
    status=MAX_RETRIES,
    backoff_factor=1,
    other=0,
    status_forcelist=list(Retry.RETRY_AFTER_STATUS_CODES),
)


class LogArea:  # pylint:disable=too-few-public-methods
    """Library for uploading logs to log area."""

    logger = logging.getLogger(__name__)

    def __init__(self, etos: ETOS, sub_suite: dict) -> None:
        """Initialize with an ETOS instance.

        :param etos: Instance of ETOS library.
        :param sub_suite: The sub suite to upload.
        """
        self.etos = etos
        self.suite_name = sub_suite.get("name").replace(" ", "-")
        self.log_area = sub_suite.get("log_area")
        self.http = Http(retry=HTTP_RETRY_PARAMETERS)

    def upload(self, log: str, name: str, main_suite_id: str, sub_suite_id: str) -> str:
        """Upload log to a storage location.

        :param log: Path to the log to upload.
        :param name: Name of file to upload.
        :param main_suite_id: First part of folder to upload to.
        :param sub_suite_id: Second part of folder to upload to.
        :return: URI where log was uploaded to.
        """
        upload = deepcopy(self.log_area.get("upload"))
        data = {"name": name, "main_suite_id": main_suite_id, "sub_suite_id": sub_suite_id}

        # ETOS Library, for some reason, uses the key 'verb' instead of 'method'
        # for HTTP method.
        upload["verb"] = upload.pop("method")
        upload["url"] = upload["url"].format(**data)
        upload["timeout"] = upload.get("timeout", 30)
        if upload.get("auth"):
            upload["auth"] = self.__auth(**upload["auth"])

        with open(log, "rb") as log_file:
            try:
                response = self.__upload(log_file=log_file, **upload)
                self.logger.debug("%r", response)
                if not upload.get("as_json", True):
                    self.logger.debug("%r", response.text)
                self.logger.info("Uploaded log %r.", log)
                self.logger.info("Upload URI          %r", upload["url"])
                self.logger.info("Data:               %r", data)
            except Exception as error:
                self.logger.error("%r", traceback.format_exc())
                self.logger.error("Failed to upload log!")
                self.logger.error("Attempted upload of %r", log)
                raise error
        return upload["url"]

    def __upload(
        self,
        verb: str,
        url: str,
        log_file: IO,
        timeout: Optional[int] = None,
        as_json: bool = True,
        **requests_kwargs: dict,
    ) -> Union[Response, dict]:
        """Attempt to connect to url for x time.

        :param verb: Which HTTP verb to use. GET, PUT, POST
                     (DELETE omitted)
        :param url: URL to retry upload request
        :param log_file: Opened log file to upload.
        :param timeout: How long, in seconds, to retry request.
        :param as_json: Whether or not to return json instead of response.
        :param request_kwargs: Keyword arguments for the requests command.
        :return: HTTP response or json.
        """
        if timeout is None:
            timeout = self.etos.debug.default_http_timeout
        self.logger.debug("Retrying URL %s for %d seconds with a %s request.", url, timeout, verb)

        method = getattr(self.http, verb.lower())
        try:
            response = method(url, data=log_file, timeout=timeout, **requests_kwargs)
            response.raise_for_status()
            if as_json:
                return response.json()
            return response
        except (HTTPError, RequestsConnectionError, JSONDecodeError) as error:
            # pylint:disable=broad-exception-raised
            raise Exception("Failed to upload test suite to {url!r}") from error

    def __decrypt(self, password: Union[str, dict]) -> str:
        """Decrypt a password using an encryption key.

        :param password: Password to decrypt.
        :return: Decrypted password
        """
        key = os.getenv("ETOS_ENCRYPTION_KEY")
        if key is None:
            self.logger.debug("No encryption key available, won't decrypt password")
            return password
        password_value = password.get("$decrypt", {}).get("value")
        if password_value is None:
            self.logger.debug("No '$decrypt' JSONTas struct for password, won't decrypt password")
            return password
        return Fernet(key).decrypt(password_value).decode()

    def __auth(
        self, username: str, password: str, type: str = "basic"  # pylint:disable=redefined-builtin
    ) -> Union[HTTPBasicAuth, HTTPDigestAuth]:
        """Create an authentication for HTTP request.

        :param username: Username to authenticate.
        :param password: Password to authenticate with.
        :param type: Type of authentication. 'basic' or 'digest'.
        :return: Authentication method.
        """
        password = self.__decrypt(password)
        if type.lower() == "basic":
            return HTTPBasicAuth(username, password)
        return HTTPDigestAuth(username, password)
