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
"""Fake database library helpers."""
from etos_lib.lib.database import Database

# pylint:disable=too-few-public-methods


class FakeWriter:
    """A fake writer object for the FakeDatabase."""

    def __init__(self, db_dict):
        """Init."""
        self._writer_dict = db_dict

    def set(self, key, value):
        """Write a value to database.

        :param key: Key to store value in.
        :type key: any
        :param value: Value to write.
        :type value: str
        """
        self._writer_dict[key] = value
        return self._writer_dict.get(key)

    def hset(self, key, _id, value):
        """Set hash into database."""
        self.set(key + _id, value)

    def hdel(self, _key, _value):
        """Delete hash from database."""

    def expire(self, _key, _value):
        """Set expiration on database keys."""


class FakeReader:
    """A fake reader object for the FakeDatabase."""

    def __init__(self, db_dict):
        """Init."""
        self._reader_dict = db_dict

    def get(self, key):
        """Get a single key from database.

        :param key: Key to read from.
        :type key: str
        :return: Value of key.
        :rtype: any
        """
        return self._reader_dict.get(key)

    def hget(self, key, _id):
        """Get hash from database."""
        return self._reader_dict.get(key + _id)


class FakeDatabase(Database):
    """A fake database that follows the ETOS library database.

    This fake database closely follows the ETOS library implementation.
    The only difference between them is the writer and reader objects that
    are created.
    """

    def __init__(self):
        """Initialize fake reader and writer."""
        self.db_dict = {}
        self.__writer = FakeWriter(self.db_dict)
        self.__reader = FakeReader(self.db_dict)
        super().__init__(self)

    def __call__(self):
        """Database instantiation faker."""
        return self

    @property
    def writer(self):
        """Return our fake writer."""
        return self.__writer

    @property
    def reader(self):
        """Return our fake reader."""
        return self.__reader
