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
"""IUT provider prepare module."""
import logging
from collections import OrderedDict
from copy import deepcopy
from multiprocessing.pool import ThreadPool
from threading import Lock

from etos_lib.logging.logger import FORMAT_CONFIG
from jsontas.jsontas import JsonTas

from ..iut import Iut


class Prepare:  # pylint:disable=too-few-public-methods
    """Prepare and add preparation configuration for ETR to use to item under test (IUT)."""

    logger = logging.getLogger("IUTProvider - Prepare")
    lock = Lock()

    def __init__(self, jsontas: JsonTas, prepare_ruleset: dict) -> None:
        """Initialize IUT preparation handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :param prepare_ruleset: JSONTas ruleset for preparing IUTs.
        """
        self.prepare_ruleset = prepare_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset
        self.suite_id = self.dataset.get("config", {}).get("SUITE_ID")

    def execute_preparation_steps(self, iut: Iut, preparation_steps: dict) -> tuple[bool, Iut]:
        """Execute the preparation steps for the environment provider on an IUT.

        :param iut: IUT to prepare for execution.
        :param preparation_steps: Steps to execute to prepare an IUT.
        """
        FORMAT_CONFIG.identifier = self.suite_id
        try:
            with self.lock:
                dataset = self.dataset.copy()
            jsontas = JsonTas(dataset=dataset)
            steps = {}
            dataset.add("iut", iut)
            dataset.add("steps", steps)
            for step, definition in preparation_steps.items():
                definition = OrderedDict(**definition)
                self.logger.info("Executing step %r", step)
                step_result = jsontas.run(json_data=definition)
                self.logger.info("%r", step_result)
                setattr(iut, step, step_result)
                if not step_result:
                    self.logger.error("Failed to execute step %r", step)
                    return False, iut
                steps[step] = step_result
        except Exception as exception:  # pylint:disable=broad-except
            self.logger.error("Failure when preparing IUT %r", iut)
            self.logger.error("%r", exception)
            return False, iut
        return True, iut

    def prepare(self, iuts: list[Iut]) -> tuple[list[Iut], list[Iut]]:
        """Prepare IUTs.

        :param iuts: IUTs to prepare.
        :return: List of prepared IUTs and a list of IUTs that failed preparation.
        """
        iuts = deepcopy(iuts)
        failed_iuts = []
        if not self.prepare_ruleset:
            self.logger.info("No defined preparation rule.")
            return iuts, []
        thread_pool = ThreadPool()

        stages = self.prepare_ruleset.get("stages", {})
        steps = stages.get("environment_provider", {}).get("steps", {})
        results = []
        for iut in reversed(iuts):
            self.logger.info("Preparing IUT %r", iut)
            results.append(
                thread_pool.apply_async(
                    self.execute_preparation_steps,
                    args=(iut, deepcopy(steps)),
                )
            )
        for result in results:
            success, iut = result.get()
            if not success:
                self.logger.error("Unable to prepare %r.", iut)
                iuts.remove(iut)
                failed_iuts.append(iut)
            else:
                iut.update(**deepcopy(stages))
        self.dataset.add("iuts", deepcopy(iuts))
        return iuts, failed_iuts
