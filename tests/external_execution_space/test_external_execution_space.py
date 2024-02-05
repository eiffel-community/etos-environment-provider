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
"""Integration tests for the external execution space."""
import logging
import os
import unittest

from etos_lib import ETOS
from jsontas.jsontas import JsonTas
from packageurl import PackageURL
from requests.exceptions import RetryError

from execution_space_provider.exceptions import (
    ExecutionSpaceCheckinFailed,
    ExecutionSpaceCheckoutFailed,
    ExecutionSpaceNotAvailable,
)
from execution_space_provider.execution_space import ExecutionSpace
from execution_space_provider.utilities.external_provider import ExternalProvider
from tests.library.fake_server import FakeServer


class TestExternalExecutionSpace(unittest.TestCase):
    """Test the external execution space provider."""

    logger = logging.getLogger(__name__)

    def tearDown(self):
        """Re-set the default HTTP timeout."""
        os.environ["ETOS_DEFAULT_HTTP_TIMEOUT"] = "3600"

    def test_provider_start(self):
        """Test that it is possible to start an external execution space provider.

        Approval criteria:
            - It shall be possible to send start to an external execution space provider.

        Test steps::
            1. Initialize an external provider.
            2. Send a start request.
            3. Verify that the ID from the start request is returned.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        expected_start_id = "123"

        with FakeServer("ok", {"id": expected_start_id}) as server:
            ruleset = {"id": "test_provider_start", "start": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a start request.")
            start_id = provider.start(1, 2)
            self.logger.info("STEP: Verify that the ID from the start request is returned.")
            self.assertEqual(start_id, expected_start_id)

    def test_provider_start_http_exception(self):
        """Test that the start method tries again if there's an HTTP error.

        Approval criteria:
            - The start method shall try again on HTTP errors.

        Test steps::
            1. Initialize an external provider.
            2. Send a start request that fails.
            3. Verify that the start method tries again on HTTP errors.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        expected_start_id = "123"

        with FakeServer(["service_unavailable", "ok"], [{}, {"id": expected_start_id}]) as server:
            ruleset = {
                "id": "test_provider_start_http_exception",
                "start": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a start request that fails.")
            start_id = provider.start(1, 2)
            self.logger.info("STEP: Verify that the start method tries again on HTTP errors.")
            self.assertGreaterEqual(server.nbr_of_requests, 2)
            self.assertEqual(start_id, expected_start_id)

    def test_provider_start_timeout(self):
        """Test that the start method raises a RetryError.

        Approval criteria:
            - The start method shall raise RetryError if the timeout is reached.

        Test steps::
            1. Initialize an external provider.
            2. Send a start request which will never finish.
            3. Verify that the start method raises RetryError.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        os.environ["ETOS_DEFAULT_HTTP_TIMEOUT"] = "1"

        with FakeServer("service_unavailable", {}) as server:
            ruleset = {
                "id": "test_provider_start_timeout",
                "start": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a start request which will never finish.")

            with self.assertRaises(RetryError):
                self.logger.info("STEP: Verify that the start method raises RetryError.")
                provider.start(1, 2)

    def test_provider_stop(self):
        """Test that it is possible to checkin an external execution space provider.

        Approval criteria:
            - It shall be possible to send stop to an external execution space provider.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request for a single execution space.
            3. Verify that the stop endpoint is called.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        execution_space = ExecutionSpace(test_execution_space=1)

        with FakeServer("no_content", {}) as server:
            ruleset = {"id": "test_provider_stop", "stop": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request for a single execution space.")
            provider.checkin(execution_space)
            self.logger.info("STEP: Verify that the stop endpoint is called.")
            self.assertEqual(server.nbr_of_requests, 1)
            self.assertEqual(server.requests, [[execution_space.as_dict]])

    def test_provider_stop_many(self):
        """Test that it is possible to checkin an external execution space provider with many
           execution spaces.

        Approval criteria:
            - It shall be possible to send stop to an external execution space provider
              with multiple execution spaces.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request for multiple execution spaces.
            3. Verify that the stop endpoint is called.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        execution_spaces = [
            ExecutionSpace(test_execution_space=1),
            ExecutionSpace(test_execution_space=2),
        ]
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
                "execution_spaces": execution_spaces,
            }
        )
        dict_execution_spaces = [execution_space.as_dict for execution_space in execution_spaces]

        with FakeServer("no_content", {}) as server:
            ruleset = {"id": "test_provider_stop_many", "stop": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request for multiple execution spaces.")
            provider.checkin_all()
            self.logger.info("STEP: Verify that the stop endpoint is called.")
            self.assertEqual(server.nbr_of_requests, 1)
            self.assertEqual(server.requests, [dict_execution_spaces])

    def test_provider_stop_failed(self):
        """Test that the checkin method raises an ExecutionSpaceCheckinFailed exception.

        Approval criteria:
            - The checkin method shall fail with an ExecutionSpaceCheckinFailed exception.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request that fails.
            3. Verify that the checkin method raises ExecutionSpaceCheckinFailed exception.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        execution_space = ExecutionSpace(test_execution_space=1)

        with FakeServer("bad_request", {"error": "no"}) as server:
            ruleset = {"id": "test_provider_stop_failed", "stop": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request that fails.")
            with self.assertRaises(ExecutionSpaceCheckinFailed):
                self.logger.info(
                    "STEP: Verify that the checkin method raises ExecutionSpaceCheckinFailed "
                    "exception."
                )
                provider.checkin(execution_space)

    def test_provider_stop_timeout(self):
        """Test that the checkin method raises a TimeoutError when timed out.

        Approval criteria:
            - The checkin method shall raise TimeoutError when timed out.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request for execution spaces that times out.
            3. Verify that the checkin method raises a TimeoutError.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        execution_space = ExecutionSpace(test_execution_space=1)
        with FakeServer("bad_request", {}) as server:
            ruleset = {
                "id": "test_provider_stop_timeout",
                "stop": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request that fails.")
            with self.assertRaises(TimeoutError):
                self.logger.info("STEP: Verify that the checkin method raises a TimeoutError.")
                provider.checkin(execution_space)

    def test_provider_status(self):
        """Test that the wait method waits for status DONE and exits with response.

        Approvial criteria:
            - The wait method shall call the status endpoint and return on DONE.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request for a started execution space provider.
            3. Verify that the wait method returns response on DONE.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        test_id = "123"
        with FakeServer("ok", {"status": "DONE", "test_id": test_id}) as server:
            ruleset = {"id": "test_provider_status", "status": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a status request for a started execution space provider.")
            response = provider.wait("1")
            self.logger.info("STEP: Verify that the wait method return response on DONE.")
            self.assertEqual(response.get("test_id"), test_id)

    def test_provider_status_pending(self):
        """Test that the wait method waits on status PENDING.

        Approvial criteria:
            - The wait method shall call the status endpoint, waiting on PENDING.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request for a started execution space provider.
            3. Verify that the wait method waits on PENDING.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 10)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        responses = [{"status": "PENDING"}, {"status": "PENDING"}, {"status": "DONE"}]
        with FakeServer("ok", responses.copy()) as server:
            ruleset = {
                "id": "test_provider_status_pending",
                "status": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a status request for a started execution space provider.")
            provider.wait("1")
            self.logger.info("STEP: Verify that the wait method waits on PENDING.")
            self.assertEqual(server.nbr_of_requests, len(responses))

    def test_provider_status_failed(self):
        """Test that the wait method raises ExecutionSpaceCheckoutFailed on FAILED status.

        Approvial criteria:
            - The wait method shall raise ExecutionSpaceCheckoutFailed on a FAILED status.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request for a started execution space provider.
            3. Verify that the wait method raises ExecutionSpaceCheckoutFailed.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        description = "something failed!"
        with FakeServer("ok", {"status": "FAILED", "description": description}) as server:
            ruleset = {
                "id": "test_provider_status_failed",
                "status": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a status request for a started execution space provider.")
            with self.assertRaises(ExecutionSpaceCheckoutFailed):
                self.logger.info(
                    "STEP: Verify that the wait method raises ExecutionSpaceCheckoutFailed."
                )
                provider.wait("1")

    def test_provider_status_http_exceptions(self):
        """Test that the wait method handles HTTP errors.

        Approvial criteria:
            - The wait method shall raise ExecutionSpaceNotAvailable on 404 errors.
            - The wait method shall raise RuntimeError on 400 errors.

        Test steps::
            1. For status [400, 404]:
                1.1 Initialize an external provider.
                1.2 Send a status request for a started execution space provider.
                1.3 Verify that the wait method raises the correct exception.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        self.logger.info("STEP: For status [400, 404]:")
        for status, exception in (
            ("bad_request", RuntimeError),
            ("not_found", ExecutionSpaceNotAvailable),
        ):
            with FakeServer(status, {"error": "failure"}) as server:
                ruleset = {
                    "id": "test_provider_status_http_exceptions",
                    "status": {"host": server.host},
                }
                self.logger.info("STEP: Initialize an external provider.")
                provider = ExternalProvider(etos, jsontas, ruleset)
                provider.http.adapter.max_retries.status = 1
                self.logger.info(
                    "STEP: Send a status request for a started execution space provider."
                )
                with self.assertRaises(exception):
                    self.logger.info(
                        "STEP: Verify that the wait method raises the correct exception."
                    )
                    provider.wait("1")

    def test_provider_status_timeout(self):
        """Test that the wait method raises TimeoutError when timed out.

        Approvial criteria:
            - The wait method shall raise TimeoutError when timed out.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request that times out.
            3. Verify that the wait method raises TimeoutError.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 1)
        jsontas = JsonTas()
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        with FakeServer("internal_server_error", {}) as server:
            ruleset = {
                "id": "test_provider_status_timeout",
                "status": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a status request that times out.")
            with self.assertRaises(TimeoutError):
                self.logger.info("STEP: Verify that the wait method raises TimeoutError.")
                provider.wait("1")

    def test_request_and_wait(self):
        """Test that the external execution space provider can checkout execution spaces.

        Approval criteria:
            - The external execution space provider shall request an external provider and
              checkout execution spaces.

        Test steps::
            1. Initialize an external provider.
            2. Send a checkout request via the external execution space provider.
            3. Verify that the provider returns a list of checked out execution spaces.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_EXECUTION_SPACE_TIMEOUT", 10)
        jsontas = JsonTas()
        identity = PackageURL.from_string("pkg:testing/etos")
        jsontas.dataset.merge(
            {
                "identity": identity,
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
            }
        )
        start_id = "1"
        test_id = "executionspace123"
        provider_id = "test_request_and_wait"
        # First request is 'start'.
        # Second request is 'status'.
        # Third request is 'stop' which should not be requested in this test.
        with FakeServer(
            ["ok", "ok", "no_content"],
            [
                {"id": start_id},
                {"execution_spaces": [{"test_id": test_id}], "status": "DONE"},
                {},
            ],
        ) as server:
            ruleset = {
                "id": provider_id,
                "status": {"host": server.host},
                "start": {"host": server.host},
                "stop": {"host": server.host},
            }
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info(
                "STEP: Send a checkout request via the external execution space provider."
            )
            execution_spaces = provider.request_and_wait_for_execution_spaces()
            self.logger.info(
                "STEP: Verify that the provider returns a list of checked out execution spaces."
            )
            dict_execution_spaces = [
                execution_space.as_dict for execution_space in execution_spaces
            ]
            test_execution_spaces = [
                ExecutionSpace(provider_id=provider_id, test_id=test_id).as_dict
            ]
            self.assertEqual(dict_execution_spaces, test_execution_spaces)
