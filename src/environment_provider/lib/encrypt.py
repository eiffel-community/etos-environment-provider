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
"""JSONTas encrypt string data structure module."""
import os

from cryptography.fernet import Fernet
from jsontas.data_structures.datastructure import DataStructure

# pylint:disable=too-few-public-methods


def encrypt(value: bytes, key: str) -> str:
    """Encrypt a string.

    :param value: Data to encrypt.
    :param key: Encryption key to encrypt data with.
    :return: Encrypted data.
    """
    return Fernet(key).encrypt(value).decode()


class Encrypt(DataStructure):
    """Encrypt a string value."""

    def execute(self) -> tuple[str, dict]:
        """Execute datastructure.

        :return: Name of key and encrypted value
        """
        key = os.getenv("ETOS_ENCRYPTION_KEY")
        assert key is not None, "ETOS_ENCRYPTION_KEY environment variable must be set"
        return "$decrypt", {"value": encrypt(self.data.get("value").encode(), key)}
