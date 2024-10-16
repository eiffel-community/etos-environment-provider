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
import json
import time
import sys
import traceback
import logging
import re
from typing import Optional, Union

from etos_lib import ETOS
from jsontas.jsontas import JsonTas
from opentelemetry import trace

from environment_provider.lib.database import ETCDPath
from environment_provider.lib.registry import ProviderRegistry
from environment_provider.lib.releaser import EnvironmentReleaser
from execution_space_provider import ExecutionSpaceProvider
from execution_space_provider.execution_space import ExecutionSpace
from iut_provider import IutProvider
from iut_provider.iut import Iut
from log_area_provider import LogAreaProvider
from log_area_provider.log_area import LogArea


TRACER = trace.get_tracer(__name__)
# REGEX for matching /testrun/tercc-id/suite/main-suite-id/subsuite/subsuite-id/suite.
SUBSUITE_REGEX = r"/testrun/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/suite/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/subsuite/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/suite"  # pylint:disable=line-too-long


def checkin_provider(
    item: dict, provider: Union[IutProvider, ExecutionSpaceProvider, LogAreaProvider]
) -> tuple[bool, Optional[Exception]]:
    """Check in a provider.

    :param item: Item to check in.
    :param provider: The provider to use for check in.
    :return: Whether or not the checkin was successful together with an exception
             if there was any.
    """
    failure = None
    try:
        provider.checkin(item)
    except Exception as exception:  # pylint:disable=broad-except
        failure = exception
    # If failure is None, return True.
    return not failure, failure


def release_environment(
    etos: ETOS, jsontas: JsonTas, provider_registry: ProviderRegistry, sub_suite: dict
) -> Optional[Exception]:
    """Release a single sub-suite environment.

    :param etos: ETOS library instance.
    :param jsontas: JSONTas instance.
    :param provider_registry: The provider registry to get environments from.
    :param sub_suite: The sub suite environment to release.
    :return: Whether or not the release was successful
    """
    etos.config.set("SUITE_ID", sub_suite.get("suite_id"))
    iut = sub_suite.get("iut")
    iut_ruleset = provider_registry.get_iut_provider().get("iut")
    executor = sub_suite.get("executor")
    executor_ruleset = provider_registry.get_execution_space_provider().get("execution_space")

    log_area = sub_suite.get("log_area")
    log_area_ruleset = provider_registry.get_log_area_provider().get("log")

    failure = None

    span_name = "stop_iuts"
    with TRACER.start_as_current_span(span_name, kind=trace.SpanKind.CLIENT) as span:
        success, exception = checkin_provider(Iut(**iut), IutProvider(etos, jsontas, iut_ruleset))
        if not success:
            span.record_exception(exception)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            failure = exception

    span_name = "stop_log_area"
    with TRACER.start_as_current_span(span_name, kind=trace.SpanKind.CLIENT) as span:
        success, exception = checkin_provider(
            LogArea(**log_area), LogAreaProvider(etos, jsontas, log_area_ruleset)
        )
        if not success:
            span.record_exception(exception)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            failure = exception

    span_name = "stop_execution_space"
    with TRACER.start_as_current_span(span_name, kind=trace.SpanKind.CLIENT):
        success, exception = checkin_provider(
            ExecutionSpace(**executor),
            ExecutionSpaceProvider(etos, jsontas, executor_ruleset),
        )
        if not success:
            span.record_exception(exception)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            failure = exception

    return failure


def release_full_environment(etos: ETOS, jsontas: JsonTas, suite_id: str) -> tuple[bool, str]:
    """Release an already requested environment.

    :param etos: ETOS library instance.
    :param jsontas: JSONTas instance.
    :return: Release status and a message if status is False.
    """
    failure = None
    registry = ProviderRegistry(etos, jsontas, suite_id)
    # TODO: Remove the sleeping when we can communicate the log urls to the
    # etos-client using internal messaging via SSE.
    #
    # We need to sleep here for a while to prevent us from deleting the
    # references to the last log files created. This is to ensure that
    # etos-client has enough time to find and download them.
    time.sleep(30)
    # Iterating over all keys "below" the suite key to find all sub suites.
    for value, metadata in registry.testrun.join("suite").read_all():
        key = metadata.get("key", b"").decode()
        if re.match(SUBSUITE_REGEX, key) is None:
            continue
        try:
            sub_suite = json.loads(value)
            failure = release_environment(etos, jsontas, registry, sub_suite)
        except json.JSONDecodeError as exception:
            failure = exception
        ETCDPath(key).delete()
    registry.testrun.delete_all()

    if failure:
        # Return the traceback from exception stored in failure.
        return False, "".join(
            traceback.format_exception(failure, value=failure, tb=failure.__traceback__)
        )
    return True, ""


def run(environment_id: str):
    """Run is an entrypoint for releasing environments."""
    logformat = "[%(asctime)s] %(levelname)s:%(message)s"
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )
    try:
        releaser = EnvironmentReleaser()
        releaser.run(environment_id)
        result = {"conclusion": "Successful", "description": "Successfully released an environment"}
        with open("/dev/termination-log", "w", encoding="utf-8") as termination_log:
            json.dump(result, termination_log)
    except:
        try:
            result = {"conclusion": "Failed", "description": traceback.format_exc()}
            with open("/dev/termination-log", "w", encoding="utf-8") as termination_log:
                json.dump(result, termination_log)
        except PermissionError:
            pass
        raise


if __name__ == "__main__":
    run(sys.argv[1])
