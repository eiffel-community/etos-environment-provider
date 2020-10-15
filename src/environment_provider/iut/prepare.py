# Copyright 2020 Axis Communications AB.
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
from threading import Lock
from multiprocessing.pool import ThreadPool
from collections import OrderedDict
from copy import deepcopy
from jsontas.jsontas import JsonTas


class Prepare:  # pylint:disable=too-few-public-methods
    """Prepare and add preparation configuration for ETR to use to item under test (IUT)."""

    logger = logging.getLogger("IUTProvider - Prepare")
    lock = Lock()

    def __init__(self, jsontas, prepare_ruleset):
        """Initialize IUT preparation handler.

        :param jsontas: JSONTas instance used to evaluate the ruleset.
        :type jsontas: :obj:`jsontas.jsontas.JsonTas`
        :param prepare_ruleset: JSONTas ruleset for preparing IUTs.
        :type prepare_ruleset: dict
        """
        self.prepare_ruleset = prepare_ruleset
        self.jsontas = jsontas
        self.dataset = self.jsontas.dataset

    def execute_preparation_steps(self, iut, preparation_steps):
        """Execute the preparation steps for the environment provider on an IUT.

        :param iut: IUT to prepare for execution.
        :type iut: :obj:`environment_provider.lib.iut.Iut`
        :param preparation_steps: Steps to execute to prepare an IUT.
        :type preparation_steps: dict
        """
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
            if not step_result:
                self.logger.error("Failed to execute step %r", step)
                return False, iut
            steps[step] = step_result
        return True, iut

    def prepare(self, iuts):
        """Prepare IUTs.

        :param iuts: IUTs to prepare.
        :type iuts: list
        :return: Prepared IUTs.
        :rtype: list
        """
        if not self.prepare_ruleset:
            self.logger.info("No defined preparation rule.")
            return iuts
        thread_pool = ThreadPool()

        stages = self.prepare_ruleset.get("stages", {})
        steps = stages.get("environment_provider", {}).get("steps", {})
        results = []
        for iut in reversed(iuts):
            self.logger.info("Preparing IUT %r", iut)
            results.append(
                thread_pool.apply_async(
                    self.execute_preparation_steps, args=(iut, deepcopy(steps))
                )
            )
        for result in results:
            success, iut = result.get()
            if not success:
                self.logger.error("Unable to prepare %r.", iut)
                iuts.remove(iut)
            else:
                iut.update(**deepcopy(stages))
        self.dataset.add("iuts", deepcopy(iuts))
        return iuts
