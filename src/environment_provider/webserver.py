# Copyright 2020-2021 Axis Communications AB.
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
"""ETOS Environment Provider webserver module."""
import os
import logging
import falcon

from etos_lib.etos import ETOS
from etos_lib.lib.database import Database
from etos_lib.logging.logger import FORMAT_CONFIG
from jsontas.jsontas import JsonTas
from environment_provider.middleware import RequireJSON, JSONTranslator
from environment_provider.lib.celery import APP
from environment_provider.lib.registry import ProviderRegistry

from environment_provider.backend.environment import (
    check_environment_status,
    get_environment_id,
    get_release_id,
    release_environment,
    request_environment,
)
from environment_provider.backend.register import (
    get_iut_provider,
    get_execution_space_provider,
    get_log_area_provider,
    register,
)
from environment_provider.backend.configure import (
    configure,
    get_configuration,
    get_dataset,
    get_execution_space_provider_id,
    get_iut_provider_id,
    get_log_area_provider_id,
)
from environment_provider.backend.subsuite import get_sub_suite, get_id
from environment_provider.backend.common import get_suite_id, get_suite_runner_ids


class Webserver:
    """Environment provider base endpoint."""

    def __init__(self, database, celery_worker):
        """Init with a db class.

        :param database: database class.
        :type database: class
        :param celery_worker: The celery app to use.
        :type celery_worker: :obj:`celery.Celery`
        """
        self.database = database
        self.celery_worker = celery_worker

    def release(self, response, task_id):  # pylint:disable=too-many-locals
        """Release an environment.

        :param response: Response object to edit and return.
        :type response: :obj:`falcon.response`
        :param task_id: Task to release.
        :type task_id: str
        """
        etos = ETOS(
            "ETOS Environment Provider",
            os.getenv("HOSTNAME"),
            "Environment Provider",
        )
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, self.database())
        task_result = self.celery_worker.AsyncResult(task_id)
        success, message = release_environment(
            etos, jsontas, registry, task_result, task_id
        )
        if not success:
            response.media = {
                "error": "Failed to release environment",
                "details": message,
                "status": task_result.status if task_result else "PENDING",
            }
            return
        response.status = falcon.HTTP_200
        response.media = {"status": task_result.status if task_result else "PENDING"}

    def on_get(self, request, response):
        """GET endpoint for environment provider API.

        Get environment task or release environment.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        task_id = get_environment_id(request)
        release = get_release_id(request)
        if task_id is None and release is None:
            raise falcon.HTTPBadRequest(
                "Missing parameters", "'id' or 'release' are required parameters."
            )
        if release:
            self.release(response, release)
            return
        result = check_environment_status(self.celery_worker, task_id)
        response.status = falcon.HTTP_200
        response.media = result

    @staticmethod
    def on_post(request, response):
        """POST endpoint for environment provider API.

        Create a new environment and return it.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        task_id = request_environment(
            get_suite_id(request), get_suite_runner_ids(request)
        )
        response.status = falcon.HTTP_200
        response.media = {"result": "success", "data": {"id": task_id}}


class Configure:
    """Configure endpoint for environment provider. Configure an environment for checkout.

    This endpoint should be called before attempting to checkout an environment so that
    the environment provider is configured to handle it.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, database):
        """Init with a db class.

        :param database: database class.
        :type database: class
        """
        self.database = database

    def on_post(self, request, response):
        """Verify that all parameters are available and configure the provider registry.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        etos = ETOS(
            "ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider"
        )
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, self.database())
        suite_id = get_suite_id(request)
        FORMAT_CONFIG.identifier = suite_id

        success, message = configure(
            registry,
            get_iut_provider_id(request),
            get_execution_space_provider_id(request),
            get_log_area_provider_id(request),
            get_dataset(request),
            get_suite_id(request),
        )
        if not success:
            self.logger.error(message)
            raise falcon.HTTPBadRequest("Bad request", message)
        response.status = falcon.HTTP_200

    def on_get(self, request, response):
        """Get an already configured environment based on suite ID.

        Use only to verify that the environment has been configured properly.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        etos = ETOS(
            "ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider"
        )
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, self.database())

        suite_id = get_suite_id(request)
        if suite_id is None:
            raise falcon.HTTPBadRequest(
                "Missing parameters", "'suite_id' is a required parameter."
            )
        FORMAT_CONFIG.identifier = suite_id
        response.status = falcon.HTTP_200
        response.media = get_configuration(registry, suite_id)


class Register:  # pylint:disable=too-few-public-methods
    """Register one or several new providers to the environment provider."""

    def __init__(self, database):
        """Init with a db class.

        :param database: database class.
        :type database: class
        """
        self.database = database

    def on_post(self, request, response):
        """Register a new provider.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        etos = ETOS(
            "ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider"
        )
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, self.database())
        registered = register(
            registry,
            iut_provider=get_iut_provider(request),
            log_area_provider=get_log_area_provider(request),
            execution_space_provider=get_execution_space_provider(request),
        )
        if registered is False:
            raise falcon.HTTPBadRequest(
                "Missing parameters",
                "At least one of 'iut_provider', 'log_area_provider' "
                "& 'execution_space_provider' is a required parameter.",
            )
        response.status = falcon.HTTP_204


class SubSuite:  # pylint:disable=too-few-public-methods
    """Get generated sub suites from environment provider."""

    def __init__(self, database):
        """Init with a db class.

        :param database: database class.
        :type database: class
        """
        self.database = database

    def on_get(self, request, response):
        """Get a generated sub suite from environment provider.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        suite = get_sub_suite(self.database(), get_id(request))
        if suite is None:
            raise falcon.HTTPNotFound(
                title="Sub suite not found.",
                description=f"Could not find sub suite with ID {get_suite_id(request)}",
            )
        response.status = falcon.HTTP_200
        response.media = suite


FALCON_APP = falcon.API(middleware=[RequireJSON(), JSONTranslator()])
WEBSERVER = Webserver(Database, APP)
CONFIGURE = Configure(Database)
REGISTER = Register(Database)
SUB_SUITE = SubSuite(Database)
FALCON_APP.add_route("/", WEBSERVER)
FALCON_APP.add_route("/configure", CONFIGURE)
FALCON_APP.add_route("/register", REGISTER)
FALCON_APP.add_route("/sub_suite", SUB_SUITE)
