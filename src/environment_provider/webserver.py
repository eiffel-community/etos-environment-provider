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
import traceback
import logging
import json
import falcon

from etos_lib.etos import ETOS
from etos_lib.lib.database import Database
from etos_lib.logging.logger import FORMAT_CONFIG
from jsontas.jsontas import JsonTas
from environment_provider.middleware import RequireJSON, JSONTranslator
from environment_provider.lib.celery import APP
from environment_provider.lib.registry import ProviderRegistry
from environment_provider.iut.iut_provider import IutProvider
from environment_provider.iut.iut import Iut
from environment_provider.logs.log_area_provider import LogAreaProvider
from environment_provider.logs.log_area import LogArea
from environment_provider.execution_space.execution_space_provider import (
    ExecutionSpaceProvider,
)
from environment_provider.execution_space.execution_space import ExecutionSpace
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
    get_suite_id,
    get_log_area_provider_id,
)
from .environment_provider import get_environment


class Webserver:
    """Environment provider base endpoint."""

    request = None

    def __init__(self, database):
        """Init with a db class.

        :param database: database class.
        :type database: class
        """
        self.database = database

    @property
    def suite_id(self):
        """Suite ID from media parameters."""
        suite_id = self.request.media.get("suite_id")
        if suite_id is None:
            raise falcon.HTTPBadRequest(
                "Missing parameters", "'suite_id' is a required parameter."
            )
        return suite_id

    def release(self, response, task_id):  # pylint:disable=too-many-locals
        """Release an environment.

        :param response: Response object to edit and return.
        :type response: :obj:`falcon.response`
        :param task_id: Task to release.
        :type task_id: str
        """
        try:
            task_result = APP.AsyncResult(task_id)
            result = {
                "status": task_result.status,
            }
            response.status = falcon.HTTP_200
            if task_result.result:
                etos = ETOS(
                    "ETOS Environment Provider",
                    os.getenv("HOSTNAME"),
                    "Environment Provider",
                )
                jsontas = JsonTas()
                registry = ProviderRegistry(etos, jsontas, self.database())
                failure = None
                for suite in task_result.result.get("suites", []):
                    try:
                        iut = suite.get("iut")
                        ruleset = registry.get_iut_provider_by_id(
                            iut.get("provider_id")
                        )
                        provider = IutProvider(etos, jsontas, ruleset["iut"])
                        provider.checkin(Iut(**iut))
                    except Exception as exception:  # pylint:disable=broad-except
                        failure = exception

                    try:
                        executor = suite.get("executor")
                        ruleset = registry.get_execution_space_provider_by_id(
                            executor.get("provider_id")
                        )
                        provider = ExecutionSpaceProvider(
                            etos, jsontas, ruleset["execution_space"]
                        )
                        provider.checkin(ExecutionSpace(**executor))
                    except Exception as exception:  # pylint:disable=broad-except
                        failure = exception

                    try:
                        log_area = suite.get("log_area")
                        ruleset = registry.get_log_area_provider_by_id(
                            log_area.get("provider_id")
                        )
                        provider = LogAreaProvider(etos, jsontas, ruleset["log"])
                        provider.checkin(LogArea(**log_area))
                    except Exception as exception:  # pylint:disable=broad-except
                        failure = exception
                task_result.forget()
                if failure:
                    raise failure
                response.media = {**result}
            else:
                response.media = {
                    "warning": f"Nothing to release with task_id '{task_id}'",
                    **result,
                }
        except Exception as exception:  # pylint:disable=broad-except
            traceback.print_exc()
            response.media = {
                "error": str(exception),
                "details": traceback.format_exc(),
                **result,
            }

    def on_get(self, request, response):
        """GET endpoint for environment provider API.

        Get environment task or release environment.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        task_id = request.get_param("id")
        release = request.get_param("release")
        if task_id is None and release is None:
            raise falcon.HTTPBadRequest(
                "Missing parameters", "'id' or 'release' are required parameters."
            )
        if release:
            self.release(response, release)
            return
        task_result = APP.AsyncResult(task_id)
        result = {"status": task_result.status, "result": task_result.result}
        if result["result"] and result["result"].get("error") is not None:
            result["status"] = "FAILURE"
        response.status = falcon.HTTP_200
        response.media = result
        if task_result.result:
            task_result.get()

    def on_post(self, request, response):
        """POST endpoint for environment provider API.

        Create a new environment and return it.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        self.request = request
        task = get_environment.delay(self.suite_id)
        data = {"result": "success", "data": {"id": task.id}}
        response.status = falcon.HTTP_200
        response.media = data


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

    @staticmethod
    def on_get(request, response):
        """Get a generated sub suite from environment provider.

        :param request: Falcon request object.
        :type request: :obj:`falcon.request`
        :param response: Falcon response object.
        :type response: :obj:`falcon.response`
        """
        sub_suite_id = request.get_param("id")
        if sub_suite_id is None:
            raise falcon.HTTPBadRequest(
                "Missing parameter", "'id' is a required parameter."
            )
        database = Database()
        sub_suite = database.read(sub_suite_id)
        if sub_suite:
            response.status = falcon.HTTP_200
            response.media = json.loads(sub_suite)
        else:
            raise falcon.HTTPNotFound(
                title="Sub suite not found.",
                description=f"Could not find sub suite with ID {sub_suite_id}",
            )


FALCON_APP = falcon.API(middleware=[RequireJSON(), JSONTranslator()])
WEBSERVER = Webserver(Database)
CONFIGURE = Configure(Database)
REGISTER = Register(Database)
SUB_SUITE = SubSuite(Database)
FALCON_APP.add_route("/", WEBSERVER)
FALCON_APP.add_route("/configure", CONFIGURE)
FALCON_APP.add_route("/register", REGISTER)
FALCON_APP.add_route("/sub_suite", SUB_SUITE)
