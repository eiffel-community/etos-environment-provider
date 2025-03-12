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

try:
    VERSION = version("environment_provider")
except PackageNotFoundError:
    VERSION = "Unknown"

DEV = os.getenv("DEV", "false").lower() == "true"

# JSONTas would print all passwords as they are encrypted,
# which is not safe, so we disable propagation on the loggers.
# Propagation needs to be set to 0 instead of disabling the
# logger or setting the loglevel higher because of how the
# etos library sets up logging.
logging.getLogger("Dataset").propagate = 0
logging.getLogger("JSONTas").propagate = 0
