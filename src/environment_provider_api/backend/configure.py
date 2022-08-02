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
"""Backend for the configuration requests."""
import json


def get_iut_provider_id(request):
    """Get an IUT provider ID from the request.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: An IUT provider ID.
    :rtype: str
    """
    return request.media.get("iut_provider")


def get_execution_space_provider_id(request):
    """Get an execution space provider ID from the request.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: An IUT provider ID.
    :rtype: str
    """
    return request.media.get("execution_space_provider")


def get_log_area_provider_id(request):
    """Get an log area provider ID from the request.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: An IUT provider ID.
    :rtype: str
    """
    return request.media.get("log_area_provider")


def get_dataset(request):
    """Get a dataset from the request.

    :param request: The falcon request object.
    :type request: :obj:`falcon.request`
    :return: An IUT provider ID.
    :rtype: dict
    """
    dataset = request.media.get("dataset")
    if dataset is not None:
        if not isinstance(dataset, (dict, list)):
            dataset = json.loads(dataset)
    return dataset


# pylint:disable=too-many-arguments
def configure(
    provider_registry,
    iut_provider_id,
    execution_space_provider_id,
    log_area_provider_id,
    dataset,
    suite_id,
):
    """Configure the environment provider.

    :param provider_registry: The provider registry to store configuration in.
    :type provider_registry: :obj:`environment_provider.lib.registry.ProviderRegistry`
    :param iut_provider_id: The ID of the IUT provider to configure with.
    :type iut_provider_id: str
    :param execution_space_provider_id: The ID of the execution space provider to configure with.
    :type execution_space_provider_id: str
    :param log_area_provider_id: The ID of the log area provider to configure with.
    :type log_area_provider_id: str
    :param dataset: The dataset to configure with.
    :type dataset: dict
    :param suite_id: The suite to configure all providers to.
    :type suite_id: str
    :return: Whether or not the configuration was successful.
    :rtype: bool, str
    """
    if not all(
        [
            provider_registry,
            iut_provider_id,
            execution_space_provider_id,
            log_area_provider_id,
            isinstance(dataset, (dict, list)),
            suite_id,
        ]
    ):
        return False, "Missing parameters to configure request"
    iut_provider = provider_registry.get_iut_provider_by_id(iut_provider_id)
    execution_space_provider = provider_registry.get_execution_space_provider_by_id(
        execution_space_provider_id
    )
    log_area_provider = provider_registry.get_log_area_provider_by_id(
        log_area_provider_id
    )
    if not all(
        [
            iut_provider,
            execution_space_provider,
            log_area_provider,
        ]
    ):
        return (
            False,
            f"Could not find providers {iut_provider_id!r}, {execution_space_provider_id!r} "
            f" or {log_area_provider_id!r} registered in database",
        )
    provider_registry.configure_environment_provider_for_suite(
        suite_id,
        iut_provider,
        log_area_provider,
        execution_space_provider,
        dataset,
    )
    return True, ""


def get_configuration(provider_registry, suite_id):
    """Get a stored configuration by suite ID.

    :param provider_registry: The provider registry to get configuration from.
    :type provider_registry: :obj:`environment_provider.lib.registry.ProviderRegistry`
    :param suite_id: The ID of the suite to get configuration for.
    :type suite_id: str
    :return: The configuration stored for suite ID.
    :rtype: dict
    """
    iut_provider = provider_registry.iut_provider(suite_id)
    execution_space_provider = provider_registry.execution_space_provider(suite_id)
    log_area_provider = provider_registry.log_area_provider(suite_id)
    dataset = provider_registry.dataset(suite_id)
    return {
        "iut_provider": iut_provider.ruleset if iut_provider else None,
        "execution_space_provider": execution_space_provider.ruleset
        if execution_space_provider
        else None,
        "log_area_provider": log_area_provider.ruleset if log_area_provider else None,
        "dataset": dataset,
    }
