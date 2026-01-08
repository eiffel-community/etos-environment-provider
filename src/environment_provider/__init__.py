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
"""ETOS environment provider module."""

import logging
import os
from importlib.metadata import PackageNotFoundError, version

from etos_lib.logging.logger import setup_logging
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    SERVICE_VERSION,
    OTELResourceDetector,
    ProcessResourceDetector,
    Resource,
    get_aggregated_resources,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

try:
    VERSION = version("environment_provider")
except PackageNotFoundError:
    VERSION = "Unknown"

DEV = os.getenv("DEV", "false").lower() == "true"
os.environ["ETOS_ENABLE_SENDING_LOGS"] = "false"
LOGGER = logging.getLogger(__name__)

IN_CONTROLLER_ENVIRONMENT = bool(os.getenv("REQUEST"))
if IN_CONTROLLER_ENVIRONMENT and os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    OTEL_RESOURCE = Resource.create(
        {
            SERVICE_NAME: "etos-environment-provider",
            SERVICE_VERSION: VERSION,
        },
    )

    OTEL_RESOURCE = get_aggregated_resources(
        [OTELResourceDetector(), ProcessResourceDetector()],
    ).merge(OTEL_RESOURCE)
    LOGGER.info(
        "Using OpenTelemetry collector: %s",
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    PROVIDER = TracerProvider(resource=OTEL_RESOURCE)
    EXPORTER = OTLPSpanExporter()
    PROCESSOR = BatchSpanProcessor(EXPORTER)
    PROVIDER.add_span_processor(PROCESSOR)
    trace.set_tracer_provider(PROVIDER)
    setup_logging("ETOS Environment Provider", VERSION, otel_resource=OTEL_RESOURCE)

# JSONTas would print all passwords as they are encrypted,
# which is not safe, so we disable propagation on the loggers.
# Propagation needs to be set to 0 instead of disabling the
# logger or setting the loglevel higher because of how the
# etos library sets up logging.
logging.getLogger("Dataset").propagate = 0
logging.getLogger("JSONTas").propagate = 0
