# Copyright 2021-2022 Axis Communications AB.
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
"""Backend for the environment requests."""
import traceback

from log_area_provider import LogAreaProvider
from log_area_provider.log_area import LogArea

from iut_provider import IutProvider
from iut_provider.iut import Iut

from execution_space_provider import ExecutionSpaceProvider
from execution_space_provider.execution_space import ExecutionSpace

from environment_provider.environment_provider import get_environment


def get_environment_id(request):
    """Get the environment ID from request.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: The ID of the environment.
    :rtype: str
    """
    return request.get_param("id")


def get_release_id(request):
    """Get the environment ID to release, from request.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: The ID of the environment to release.
    :rtype: str
    """
    return request.get_param("release")


def checkin_provider(item, provider):
    """Check in a provider.

    :param item: Item to check in.
    :type item: dict
    :param provider: The provider to use for check in.
    :type provider: cls
    :return: Whether or not the checkin was successful together with an exception
             if there was any.
    :rtype: tuple
    """
    failure = None
    try:
        provider.checkin(item)
    except Exception as exception:  # pylint:disable=broad-except
        failure = exception
    # If failure is None, return True.
    return not failure, failure


def release_environment(
    etos, jsontas, provider_registry, task_result, release_id
):  # pylint:disable=too-many-locals
    """Release an already requested environment.

    :param etos: ETOS library instance.
    :type etos: :obj:`etos_lib.ETOS`
    :param jsontas: JSONTas instance.
    :type jsontas: :obj:`jsontas.jsontas.JsonTas`
    :param provider_registry: The provider registry to get environments from.
    :type provider_registry: :obj:`environment_provider.lib.registry.ProviderRegistry`
    :param celery_worker: The worker holding the task results.
    :type celery_worker: :obj:`celery.Celery`
    :param release_id: The environment ID to release.
    :type release_id: str
    :return: Whether or not the release was successful together with
             a message should the release not be successful.
    :rtype tuple
    """
    if task_result is None or not task_result.result:
        return False, f"Nothing to release with task_id {release_id}"
    failure = None
    for suite in task_result.result.get("suites", {}):
        for sub_suite in suite.get("sub_suites", []):
            etos.config.set("SUITE_ID", sub_suite.get("suite_id"))
            iut = sub_suite.get("iut")
            iut_ruleset = provider_registry.get_iut_provider_by_id(
                iut.get("provider_id")
            ).get("iut")
            executor = sub_suite.get("executor")
            executor_ruleset = provider_registry.get_execution_space_provider_by_id(
                executor.get("provider_id")
            ).get("execution_space")
            log_area = sub_suite.get("log_area")
            log_area_ruleset = provider_registry.get_log_area_provider_by_id(
                log_area.get("provider_id")
            ).get("log")

            success, exception = checkin_provider(
                Iut(**iut), IutProvider(etos, jsontas, iut_ruleset)
            )
            if not success:
                failure = exception

            success, exception = checkin_provider(
                LogArea(**log_area), LogAreaProvider(etos, jsontas, log_area_ruleset)
            )
            if not success:
                failure = exception
            success, exception = checkin_provider(
                ExecutionSpace(**executor),
                ExecutionSpaceProvider(etos, jsontas, executor_ruleset),
            )
            if not success:
                failure = exception
    task_result.forget()
    if failure:
        # Return the traceback from exception stored in failure.
        return False, "".join(
            traceback.format_exception(failure, value=failure, tb=failure.__traceback__)
        )
    return True, ""


def check_environment_status(celery_worker, environment_id):
    """Check the status of the environment that is being requested.

    :param celery_worker: The worker holding the task results.
    :type celery_worker: :obj:`celery.Celery`
    :param environment_id: The environment ID to check status on.
    :type environment_id: str
    :return: A dictionary of status and and result.
    :rtype: dict
    """
    task_result = celery_worker.AsyncResult(environment_id)
    result = task_result.result
    status = task_result.status
    if result and result.get("error") is not None:
        status = "FAILURE"
    if result:
        task_result.get()
    return {"status": status, "result": result}


def request_environment(suite_id):
    """Request an environment for a test suite ID.

    :param suite_id: Suite ID to request an environment for.
    :type suite_id: str
    :return: The environment ID for the request.
    :rtype: str
    """
    return get_environment.delay(suite_id).id
