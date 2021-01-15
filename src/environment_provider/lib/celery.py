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
"""Celery connection module."""
import os
from celery import Celery
from etos_lib.logging.logger import FORMAT_CONFIG


FORMAT_CONFIG.identifier = "TaskListener"
PORT = os.getenv("ETOS_DATABASE_PORT", "26379")
HOST = os.getenv("ETOS_DATABASE_HOST", "localhost")
PASSWORD = os.getenv("ETOS_DATABASE_PASSWORD", None)
if PASSWORD:
    CELERY_BROKER_URL = "sentinel://:{}@{}:{}".format(PASSWORD, HOST, PORT)
else:
    CELERY_BROKER_URL = "sentinel://{}:{}".format(HOST, PORT)

APP = Celery(
    "environment_provider", broker=CELERY_BROKER_URL, backend=CELERY_BROKER_URL
)
if PASSWORD:
    APP.conf.broker_transport_options = {
        "master_name": "mymaster",
        "sentinel_kwargs": {"password": PASSWORD},
    }
    APP.conf.result_backend_transport_options = {
        "master_name": "mymaster",
        "sentinel_kwargs": {"password": PASSWORD},
    }
else:
    APP.conf.broker_transport_options = {"master_name": "mymaster"}
    APP.conf.result_backend_transport_options = {"master_name": "mymaster"}
APP.conf.worker_hijack_root_logger = False
