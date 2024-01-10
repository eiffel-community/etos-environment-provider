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
"""Backend services for the register endpoint."""
import json
from typing import Optional

from falcon import Request

from environment_provider.lib.registry import ProviderRegistry


def get_iut_provider(request: Request) -> Optional[dict]:
    """Get IUT provider JSON from request.

    :param request: The falcon request object.
    :return: An IUT provider from request.
    """
    return json_to_dict(request.get_media().get("iut_provider"))


def get_log_area_provider(request: Request) -> Optional[dict]:
    """Get log area provider JSON from request.

    :param request: The falcon request object.
    :return: A log area provider from request.
    """
    return json_to_dict(request.get_media().get("log_area_provider"))


def get_execution_space_provider(request: Request) -> Optional[dict]:
    """Get execution space provider JSON from request.

    :param request: The falcon request object.
    :return: An execution space provider from request.
    """
    return json_to_dict(request.get_media().get("execution_space_provider"))


def register(
    provider_registry: ProviderRegistry,
    iut_provider: Optional[dict] = None,
    log_area_provider: Optional[dict] = None,
    execution_space_provider: Optional[dict] = None,
) -> bool:
    """Register one or many providers.

    :param provider_registry: The provider registry to store providers in.
    :param iut_provider: An IUT provider to register.
    :param log_area_provider: A log area provider to register.
    :param execution_space_provider: An execution space provider to register.
    :return: The result of the registering.
    """
    if not any([iut_provider, log_area_provider, execution_space_provider]):
        # At least one provider must be supplied.
        return False
    if iut_provider is not None:
        provider_registry.register_iut_provider(iut_provider)
    if log_area_provider is not None:
        provider_registry.register_log_area_provider(log_area_provider)
    if execution_space_provider is not None:
        provider_registry.register_execution_space_provider(execution_space_provider)
    return True


def json_to_dict(json_str: str) -> Optional[dict]:
    """Convert a JSON string to a dictionary if not already a dictionary.

    :param json_str: JSON string to convert.
    :return: JSON string as a dictionary.
    """
    if json_str:
        if isinstance(json_str, dict):
            return json_str
        return json.loads(json_str)
    return json_str
