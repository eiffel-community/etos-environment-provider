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
"""Fake celery library helpers."""


class FakeCeleryResult:
    """Fake AsyncResult for celery."""

    def __init__(self, status, result, task_id, fake_app):
        """Init with a celery status and a result dictionary."""
        self.status = status
        self.result = result
        self.task_id = task_id
        self.fake_app = fake_app

    def forget(self):
        """Forget a result."""
        self.fake_app.results.pop(self.task_id)

    def get(self):
        """Get a result."""
        self.fake_app.received.append(self.task_id)


class Task:  # pylint:disable=too-few-public-methods
    """Fake task."""

    def __init__(self, task_id):
        """Fake task."""
        # pylint:disable=invalid-name
        self.id = task_id


class FakeCelery:  # pylint:disable=too-few-public-methods
    """A fake celery application."""

    def __init__(self, task_id, status, result):
        """Init with a task_id status and a result dictionary.

        The results dictionary created after init can be appended
        after the fact if necessary.
        """
        self.received = []
        self.results = {task_id: FakeCeleryResult(status, result, task_id, self)}

    # pylint:disable=invalid-name
    def AsyncResult(self, task_id):
        """Get the results of a specific task ID."""
        return self.results.get(task_id)
