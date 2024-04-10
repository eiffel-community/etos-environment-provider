#!/usr/bin/env python
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
# -*- coding: utf-8 -*-
import logging
import os
from opentelemetry.propagate import extract

LOGGER = logging.getLogger(__name__)

def get_current_context():
    # Get the context from the environment variable
    carrier = {}
    LOGGER.info("Current OpenTelemetry context env: %s", os.environ.get("OTEL_CONTEXT"))
    for kv in os.environ.get("OTEL_CONTEXT", "").split(","):
        if kv:
            k, v = kv.split("=", 1)
            carrier[k] = v
    ctx = extract(carrier)
    LOGGER.info("Current OpenTelemetry context %s", ctx)
    return ctx
