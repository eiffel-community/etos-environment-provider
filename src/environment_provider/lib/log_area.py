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
import os
import logging
import traceback
import time
from copy import deepcopy
from json.decoder import JSONDecodeError

from cryptography.fernet import Fernet
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import HTTPError
from urllib3.exceptions import MaxRetryError, NewConnectionError


class LogArea:  # pylint:disable=too-few-public-methods
    """Library for uploading logs to log area."""

    logger = logging.getLogger(__name__)

    def __init__(self, etos, sub_suite):
        """Initialize with an ETOS instance.

        :param etos: Instance of ETOS library.
        :type etos: :obj:`etos_lib.etos.Etos`
        """
        self.etos = etos
        self.suite_name = sub_suite.get("name").replace(" ", "-")
        self.log_area = sub_suite.get("log_area")

    def upload(self, log, name, folder):
        """Upload log to a storage location.

        :param log: Path to the log to upload.
        :type log: str
        :param name: Name of file to upload.
        :type name: str
        :param folder: Folder to upload to.
        :type folder: str
        :return: URI where log was uploaded to.
        :rtype: str
        """
        upload = deepcopy(self.log_area.get("upload"))
        data = {"name": name, "folder": folder}

        # ETOS Library, for some reason, uses the key 'verb' instead of 'method'
        # for HTTP method.
        upload["verb"] = upload.pop("method")
        upload["url"] = upload["url"].format(**data)
        upload["timeout"] = upload.get("timeout", 30)
        if upload.get("auth"):
            upload["auth"] = self.__auth(**upload["auth"])

        with open(log, "rb") as log_file:
            for _ in range(3):
                request_generator = self.__retry_upload(log_file=log_file, **upload)
                try:
                    for response in request_generator:
                        self.logger.debug("%r", response)
                        if not upload.get("as_json", True):
                            self.logger.debug("%r", response.text)
                        self.logger.info("Uploaded log %r.", log)
                        self.logger.info("Upload URI          %r", upload["url"])
                        self.logger.info("Data:               %r", data)
                        break
                    break
                except:  # noqa pylint:disable=bare-except
                    self.logger.error("%r", traceback.format_exc())
                    self.logger.error("Failed to upload log!")
                    self.logger.error("Attempted upload of %r", log)
        return upload["url"]

    def __retry_upload(
        self, verb, url, log_file, timeout=None, as_json=True, **requests_kwargs
    ):  # pylint:disable=too-many-arguments
        """Attempt to connect to url for x time.

        :param verb: Which HTTP verb to use. GET, PUT, POST
                     (DELETE omitted)
        :type verb: str
        :param url: URL to retry upload request
        :type url: str
        :param log_file: Opened log file to upload.
        :type log_file: file
        :param timeout: How long, in seconds, to retry request.
        :type timeout: int or None
        :param as_json: Whether or not to return json instead of response.
        :type as_json: bool
        :param request_kwargs: Keyword arguments for the requests command.
        :type request_kwargs: dict
        :return: HTTP response or json.
        :rtype: Response or dict
        """
        if timeout is None:
            timeout = self.etos.debug.default_http_timeout
        end_time = time.time() + timeout
        self.logger.debug("Retrying URL %s for %d seconds with a %s request.", url, timeout, verb)
        iteration = 0
        while time.time() < end_time:
            iteration += 1
            self.logger.debug("Iteration: %d", iteration)
            try:
                # Seek back to the start of the file so that the uploaded file
                # is not 0 bytes in size.
                log_file.seek(0)
                yield self.etos.http.request(verb, url, as_json, data=log_file, **requests_kwargs)
                break
            except (
                ConnectionError,
                HTTPError,
                NewConnectionError,
                MaxRetryError,
                TimeoutError,
                JSONDecodeError,
            ):
                self.logger.warning("%r", traceback.format_exc())
                time.sleep(2)
        else:
            raise ConnectionError(f"Unable to {verb} {url} with params {requests_kwargs}")

    def __decrypt(self, password):
        """Decrypt a password using an encryption key.

        :param password: Password to decrypt.
        :type password: str or dict
        :return: Decrypted password
        :rtype: str
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

    def __auth(self, username, password, type="basic"):  # pylint:disable=redefined-builtin
        """Create an authentication for HTTP request.

        :param username: Username to authenticate.
        :type username: str
        :param password: Password to authenticate with.
        :type password: str
        :param type: Type of authentication. 'basic' or 'digest'.
        :type type: str
        :return: Authentication method.
        :rtype: :obj:`requests.auth`
        """
        password = self.__decrypt(password)
        if type.lower() == "basic":
            return HTTPBasicAuth(username, password)
        return HTTPDigestAuth(username, password)
