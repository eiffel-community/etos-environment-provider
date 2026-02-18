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
"""OpenTelemetry-related code."""

import logging
import os

import opentelemetry
from opentelemetry.propagators.textmap import Getter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

LOGGER = logging.getLogger(__name__)


class EnvVarContextGetter(Getter):
    """OpenTelemetry context getter class for environment variables."""

    def get(self, carrier, key):
        """Get value using the given carrier variable and key."""
        value = os.getenv(carrier)
        if value is not None and value != "":
            pairs = value.split(",")
            for pair in pairs:
                k, v = pair.split("=", 1)
                if k == key:
                    return [v]
        return []

    def keys(self, carrier):
        """Get keys of the given carrier variable."""
        value = os.getenv(carrier)
        if value is not None:
            return [pair.split("=")[0] for pair in value.split(",") if "=" in pair]
        return []


def get_current_context() -> opentelemetry.context.context.Context:
    """Get current context propagated via environment variable OTEL_CONTEXT."""
    propagator = TraceContextTextMapPropagator()
    ctx = propagator.extract(carrier="OTEL_CONTEXT", getter=EnvVarContextGetter())
    return ctx
