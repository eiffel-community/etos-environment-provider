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
"""Backend services for the sub suite endpoint."""
import json

import falcon


def get_sub_suite(database, sub_suite_id):
    """Sub suite gets a sub suite by suite_id from database.

    :param database: The database to get sub suites from.
    :type database: :obj:`etos_lib.lib.database.Database`
    :param sub_suite_id: The suite ID of the sub suite in database.
    :type sub_suite_id: str
    :return: Sub suite or None.
    :rtype: dict
    """
    suite = database.read(sub_suite_id)
    if suite is None:
        return suite
    return json.loads(suite)


def get_id(request):
    """ID returns the 'id' parameter from a request.

    :raises: falcon.HTTPBadRequest if ID is missing.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: A suite ID from the request.
    :rtype: str
    """
    _id = request.get_param("id")
    if _id is None:
        raise falcon.HTTPBadRequest(
            "Missing parameter", "'id' is a required parameter."
        )
    return _id
