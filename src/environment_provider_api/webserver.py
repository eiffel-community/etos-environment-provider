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
"""ETOS Environment Provider webserver module."""
import json
import logging
import os
from pathlib import Path
from typing import Iterator

import falcon
from celery import Celery
from etos_lib.etos import ETOS
from etos_lib.logging.logger import FORMAT_CONFIG
from jsontas.jsontas import JsonTas

from environment_provider.lib.celery import APP
from environment_provider.lib.database import ETCDPath
from environment_provider.lib.registry import ProviderRegistry

from .backend.common import get_suite_id, get_suite_runner_ids
from .backend.configure import (
    configure,
    get_configuration,
    get_dataset,
    get_execution_space_provider_id,
    get_iut_provider_id,
    get_log_area_provider_id,
)
from .backend.environment import (
    check_environment_status,
    get_environment_id,
    get_release_id,
    get_single_release_id,
    release_environment,
    release_full_environment,
    request_environment,
)
from .backend.register import (
    get_execution_space_provider,
    get_iut_provider,
    get_log_area_provider,
    register,
)
from .middleware import JSONTranslator, RequireJSON


class Webserver:
    """Environment provider base endpoint."""

    logger = logging.getLogger(__name__)

    def __init__(self, celery_worker: Celery) -> None:
        """Init with a db class.

        :param celery_worker: The celery app to use.
        """
        self.celery_worker = celery_worker

    def release_by_environment_id(self, response: falcon.Response, environment_id: str) -> None:
        """Release a single environment.

        This is a backwards compatibility layer for the ESR so that it can still continue working
        with just sending in the environment ID.

        :param response: Response object to edit and return.
        :param environment_id: Environment to release.
        """
        environment = ETCDPath(f"/environment/{environment_id}")
        testrun_id = environment.join("testrun-id").read()
        suite_id = environment.join("suite-id").read()
        if testrun_id is None or suite_id is None:
            self.logger.warning("Environment for %r already checked in", environment_id)
            return
        try:
            self.release_single(response, environment_id, testrun_id.decode(), suite_id.decode())
        finally:
            environment.delete_all()

    def release_single(
        self, response: falcon.Response, environment_id: str, testrun_id: str, suite_id: str
    ) -> None:
        """Release a single environment using suite and test run IDs.

        :param response: Response object to edit and return.
        :param environment_id: Environment to release.
        :param testrun_id: ID of the testrun where the environment to release resides.
        :param suite_id: Test suite started ID where the environment to release resides.
        """
        etos = ETOS(
            "ETOS Environment Provider",
            os.getenv("HOSTNAME"),
            "Environment Provider",
        )
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, testrun_id)
        suite = ETCDPath(
            f"/testrun/{testrun_id}/suite/{suite_id}/subsuite/{environment_id}/suite"
        ).read()
        if suite is None:
            self.logger.warning(
                f"/testrun/{testrun_id}/suite/{suite_id}/subsuite/{environment_id}/suite"
            )
        try:
            failure = release_environment(etos, jsontas, registry, json.loads(suite))
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to decode test suite JSON: %r", suite)
            failure = exc

        if failure:
            response.media = {
                "error": "Failed to release environment",
                "details": "".join(
                    traceback.format_exception(failure, value=failure, tb=failure.__traceback__)
                ),
                "status": "FAILURE",
            }
            return

        response.status = falcon.HTTP_200
        response.media = {"status": "SUCCESS"}

    def release_full(self, response: falcon.Response, testrun_id: str) -> None:
        """Release a full test environment using test run ID.

        :param response: Response object to edit and return.
        :param testrun_id: Testrun to release.
        """
        etos = ETOS(
            "ETOS Environment Provider",
            os.getenv("HOSTNAME"),
            "Environment Provider",
        )
        jsontas = JsonTas()

        task_id = ETCDPath(f"/testrun/{testrun_id}/environment-provider/task-id").read().decode()
        task_result = None
        if task_id is not None:
            task_result = self.celery_worker.AsyncResult(task_id)
            task_result.forget()

        success, message = release_full_environment(etos, jsontas, testrun_id)
        if not success:
            self.logger.error(message)
            response.media = {
                "error": "Failed to release environment",
                "details": message,
                "status": task_result.status if task_result else "PENDING",
            }
            return

        response.status = falcon.HTTP_200
        response.media = {"status": task_result.status if task_result else "PENDING"}

    def release_by_task_id(self, response: falcon.Response, task_id: str) -> None:
        """Release a full environment.

        This is a backwards compatibility layer for the ESR to continue to release using the task
        ID that the environment provider returns when requesting an environment.

        :param response: Response object to edit and return.
        :param task_id: Task to release.
        """
        suite_id = ETCDPath(f"/environment/{task_id}/suite-id").read()
        if suite_id is None:
            self.logger.warning("Environment for %r already checked in", task_id)
            return
        self.release_full(response, suite_id.decode())
        ETCDPath(f"/environment/{task_id}/suite-id").delete()

    def on_get(self, request: falcon.Request, response: falcon.Response) -> None:
        """GET endpoint for environment provider API.

        Get environment task or release environment.

        :param request: Falcon request object.
        :param response: Falcon response object.
        """
        task_id = get_environment_id(request)
        release = get_release_id(request)
        single_release = get_single_release_id(request)
        if not any([task_id, release, single_release]):
            raise falcon.HTTPBadRequest(
                title="Missing parameters",
                description="'id', 'release' or 'single_release' are required parameters.",
            )
        if single_release:
            self.release_by_environment_id(response, single_release)
        elif release:
            self.release_by_task_id(response, release)
        else:
            result = check_environment_status(self.celery_worker, task_id)
            response.status = falcon.HTTP_200
            response.media = result

    @staticmethod
    def on_post(request: falcon.Request, response: falcon.Response) -> None:
        """POST endpoint for environment provider API.

        Create a new environment and return it.

        :param request: Falcon request object.
        :param response: Falcon response object.
        """
        suite_id = get_suite_id(request)
        suite_runner_ids = get_suite_runner_ids(request)
        if not all([suite_runner_ids, suite_id]):
            raise falcon.HTTPBadRequest(
                title="Missing parameters",
                description="the 'suite_id' and 'suite_runner_ids' parameters are required.",
            )

        task_id = request_environment(suite_id, suite_runner_ids)

        # TODO: This shall be removed when API version v1 is used by the ESR and API.
        ETCDPath(f"/environment/{task_id}/suite-id").write(suite_id)
        ETCDPath(f"/testrun/{suite_id}/environment-provider/task-id").write(task_id)

        response.status = falcon.HTTP_200
        response.media = {"result": "success", "data": {"id": task_id}}


class Configure:
    """Configure endpoint for environment provider. Configure an environment for checkout.

    This endpoint should be called before attempting to checkout an environment so that
    the environment provider is configured to handle it.
    """

    logger = logging.getLogger(__name__)

    def on_post(self, request: falcon.Request, response: falcon.Response) -> None:
        """Verify that all parameters are available and configure the provider registry.

        :param request: Falcon request object.
        :param response: Falcon response object.
        """
        etos = ETOS("ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider")
        jsontas = JsonTas()
        suite_id = get_suite_id(request)
        if suite_id is None:
            self.logger.error("Missing suite_id in request")
            raise falcon.HTTPBadRequest(
                title="Bad request", description="missing suite_id in request"
            )
        registry = ProviderRegistry(etos, jsontas, suite_id)
        FORMAT_CONFIG.identifier = suite_id

        success, message = configure(
            registry,
            get_iut_provider_id(request),
            get_execution_space_provider_id(request),
            get_log_area_provider_id(request),
            get_dataset(request),
        )
        if not success:
            self.logger.error(message)
            raise falcon.HTTPBadRequest(title="Bad request", description=message)
        response.status = falcon.HTTP_200

    def on_get(self, request: falcon.Request, response: falcon.Response) -> None:
        """Get an already configured environment based on suite ID.

        Use only to verify that the environment has been configured properly.

        :param request: Falcon request object.
        :param response: Falcon response object.
        """
        etos = ETOS("ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider")
        jsontas = JsonTas()
        suite_id = get_suite_id(request)
        if suite_id is None:
            raise falcon.HTTPBadRequest(
                title="Missing parameters", description="'suite_id' is a required parameter."
            )

        registry = ProviderRegistry(etos, jsontas, suite_id)

        FORMAT_CONFIG.identifier = suite_id
        response.status = falcon.HTTP_200
        response.media = get_configuration(registry)


class Register:  # pylint:disable=too-few-public-methods
    """Register one or several new providers to the environment provider."""

    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        """Load providers."""
        self.load_providers_from_disk()

    def providers(self, directory: Path) -> Iterator[dict]:
        """Read provider json files from a directory.

        :param directory: Directory to read provider json files from.
        :return: An iterator of the json files.
        """
        try:
            filenames = os.listdir(directory)
        except FileNotFoundError:
            return
        for provider_filename in filenames:
            if not directory.joinpath(provider_filename).is_file():
                self.logger.warn("Not a file: %r", provider_filename)
                continue
            with directory.joinpath(provider_filename).open() as provider_file:
                yield json.load(provider_file)

    def load_providers_from_disk(self) -> None:
        """Register provider files from file system, should environment variables be set."""
        etos = ETOS("ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider")
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, None)

        if os.getenv("EXECUTION_SPACE_PROVIDERS"):
            for provider in self.providers(Path(os.getenv("EXECUTION_SPACE_PROVIDERS"))):
                register(registry, execution_space_provider=provider)
        if os.getenv("LOG_AREA_PROVIDERS"):
            for provider in self.providers(Path(os.getenv("LOG_AREA_PROVIDERS"))):
                register(registry, log_area_provider=provider)
        if os.getenv("IUT_PROVIDERS"):
            for provider in self.providers(Path(os.getenv("IUT_PROVIDERS"))):
                register(registry, iut_provider=provider)

    def on_post(self, request: falcon.Request, response: falcon.Response) -> None:
        """Register a new provider.

        :param request: Falcon request object.
        :param response: Falcon response object.
        """
        etos = ETOS("ETOS Environment Provider", os.getenv("HOSTNAME"), "Environment Provider")
        jsontas = JsonTas()
        registry = ProviderRegistry(etos, jsontas, None)
        registered = register(
            registry,
            iut_provider=get_iut_provider(request),
            log_area_provider=get_log_area_provider(request),
            execution_space_provider=get_execution_space_provider(request),
        )
        if registered is False:
            raise falcon.HTTPBadRequest(
                title="Missing parameters",
                description="At least one of 'iut_provider', 'log_area_provider' "
                "& 'execution_space_provider' is a required parameter.",
            )
        response.status = falcon.HTTP_204


FALCON_APP = falcon.App(middleware=[RequireJSON(), JSONTranslator()])
WEBSERVER = Webserver(APP)
CONFIGURE = Configure()
REGISTER = Register()
FALCON_APP.add_route("/", WEBSERVER)
FALCON_APP.add_route("/configure", CONFIGURE)
FALCON_APP.add_route("/register", REGISTER)
