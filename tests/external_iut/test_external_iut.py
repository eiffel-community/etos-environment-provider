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
"""Integration tests for the external IUT."""
import logging
import os
import unittest

from etos_lib import ETOS
from jsontas.jsontas import JsonTas
from packageurl import PackageURL
from requests.exceptions import RetryError

from iut_provider.exceptions import IutCheckinFailed, IutCheckoutFailed, IutNotAvailable
from iut_provider.iut import Iut
from iut_provider.utilities.external_provider import ExternalProvider
from tests.library.fake_server import FakeServer


class TestExternalIUT(unittest.TestCase):
    """Test the external IUT provider."""

    logger = logging.getLogger(__name__)

    def tearDown(self):
        """Re-set the default HTTP timeout."""
        os.environ["ETOS_DEFAULT_HTTP_TIMEOUT"] = "3600"

    def test_provider_start(self):
        """Test that it is possible to start an external IUT provider.

        Approval criteria:
            - It shall be possible to send start to an external IUT provider.

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
        """Test that it is possible to checkin an external IUT provider.

        Approval criteria:
            - It shall be possible to send stop to an external IUT provider.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request for a single IUT.
            3. Verify that the stop endpoint is called.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
        iut = Iut(test_iut=1)

        with FakeServer("no_content", {}) as server:
            ruleset = {"id": "test_provider_stop", "stop": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request for a single IUT.")
            provider.checkin(iut)
            self.logger.info("STEP: Verify that the stop endpoint is called.")
            self.assertEqual(server.nbr_of_requests, 1)
            self.assertEqual(server.requests, [[iut.as_dict]])

    def test_provider_stop_many(self):
        """Test that it is possible to checkin an external IUT provider with many IUTs.

        Approval criteria:
            - It shall be possible to send stop to an external IUT provider with multiple IUTs.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request for multiple IUTs.
            3. Verify that the stop endpoint is called.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
        jsontas = JsonTas()
        iuts = [Iut(test_iut=1), Iut(test_iut=2)]
        jsontas.dataset.merge(
            {
                "identity": PackageURL.from_string("pkg:testing/etos"),
                "artifact_id": "artifactid",
                "artifact_created": "artifactcreated",
                "artifact_published": "artifactpublished",
                "tercc": "tercc",
                "dataset": {},
                "context": "context",
                "iuts": iuts,
            }
        )
        dict_iuts = [iut.as_dict for iut in iuts]

        with FakeServer("no_content", {}) as server:
            ruleset = {"id": "test_provider_stop_many", "stop": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request for multiple IUTs.")
            provider.checkin_all()
            self.logger.info("STEP: Verify that the stop endpoint is called.")
            self.assertEqual(server.nbr_of_requests, 1)
            self.assertEqual(server.requests, [dict_iuts])

    def test_provider_stop_failed(self):
        """Test that the checkin method raises an IutCheckinFailed exception.

        Approval criteria:
            - The checkin method shall fail with an IutCheckinFailed exception.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request that fails.
            3. Verify that the checkin method raises IutCheckinFailed exception.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
        iut = Iut(test_iut=1)

        with FakeServer("bad_request", {"error": "no"}) as server:
            ruleset = {"id": "test_provider_stop_failed", "stop": {"host": server.host}}
            self.logger.info("STEP: Initialize an external provider.")
            provider = ExternalProvider(etos, jsontas, ruleset)
            provider.http.adapter.max_retries.status = 1
            self.logger.info("STEP: Send a stop request that fails.")
            with self.assertRaises(IutCheckinFailed):
                self.logger.info(
                    "STEP: Verify that the checkin method raises IutCheckinFailed exception."
                )
                provider.checkin(iut)

    def test_provider_stop_timeout(self):
        """Test that the checkin method raises a TimeoutError when timed out.

        Approval criteria:
            - The checkin method shall raise TimeoutError when timed out.

        Test steps::
            1. Initialize an external provider.
            2. Send a stop request for IUTs that times out.
            3. Verify that the checkin method raises a TimeoutError.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
        iut = Iut(test_iut=1)
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
                provider.checkin(iut)

    def test_provider_status(self):
        """Test that the wait method waits for status DONE and exits with response.

        Approvial criteria:
            - The wait method shall call the status endpoint and return on DONE.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request for a started IUT provider.
            3. Verify that the wait method returns response on DONE.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
            self.logger.info("STEP: Send a status request for a started IUT provider.")
            response = provider.wait("1")
            self.logger.info("STEP: Verify that the wait method return response on DONE.")
            self.assertEqual(response.get("test_id"), test_id)

    def test_provider_status_pending(self):
        """Test that the wait method waits on status PENDING.

        Approvial criteria:
            - The wait method shall call the status endpoint, waiting on PENDING.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request for a started IUT provider.
            3. Verify that the wait method waits on PENDING.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 10)
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
            self.logger.info("STEP: Send a status request for a started IUT provider.")
            provider.wait("1")
            self.logger.info("STEP: Verify that the wait method waits on PENDING.")
            self.assertEqual(server.nbr_of_requests, len(responses))

    def test_provider_status_failed(self):
        """Test that the wait method raises IutCheckoutFailed on FAILED status.

        Approvial criteria:
            - The wait method shall raise IutCheckoutFailed on a FAILED status.

        Test steps::
            1. Initialize an external provider.
            2. Send a status request for a started IUT provider.
            3. Verify that the wait method raises IutCheckoutFailed.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
            self.logger.info("STEP: Send a status request for a started IUT provider.")
            with self.assertRaises(IutCheckoutFailed):
                self.logger.info("STEP: Verify that the wait method raises IutCheckoutFailed.")
                provider.wait("1")

    def test_provider_status_http_exceptions(self):
        """Test that the wait method handles HTTP errors.

        Approvial criteria:
            - The wait method shall raise IutNotAvailable on 404 errors.
            - The wait method shall raise RuntimeError on 400 errors.

        Test steps::
            1. For status [400, 404]:
                1.1 Initialize an external provider.
                1.2 Send a status request for a started IUT provider.
                1.3 Verify that the wait method raises the correct exception.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
            ("not_found", IutNotAvailable),
        ):
            with FakeServer(status, {"error": "failure"}) as server:
                ruleset = {
                    "id": "test_provider_status_http_exceptions",
                    "status": {"host": server.host},
                }
                self.logger.info("STEP: Initialize an external provider.")
                provider = ExternalProvider(etos, jsontas, ruleset)
                provider.http.adapter.max_retries.status = 1
                self.logger.info("STEP: Send a status request for a started IUT provider.")
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
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 1)
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
        """Test that the external IUT provider can checkout IUTs.

        Approvial criteria:
            - The external IUT provider shall request an external provider and checkout IUTs.

        Test steps::
            1. Initialize an external provider.
            2. Send a checkout request via the external IUT provider.
            3. Verify that the provider returns a list of checked out IUTs.
        """
        etos = ETOS("testing_etos", "testing_etos", "testing_etos")
        etos.config.set("WAIT_FOR_IUT_TIMEOUT", 10)
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
        test_id = "iut123"
        provider_id = "test_request_and_wait"
        # First request is 'start'.
        # Second request is 'status'.
        # Third request is 'stop' which should not be requested in this test.
        with FakeServer(
            ["ok", "ok", "no_content"],
            [{"id": start_id}, {"iuts": [{"test_id": test_id}], "status": "DONE"}, {}],
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
            self.logger.info("STEP: Send a checkout request via the external IUT provider.")
            iuts = provider.request_and_wait_for_iuts()
            self.logger.info("STEP: Verify that the provider returns a list of checked out IUTs.")
            dict_iuts = [iut.as_dict for iut in iuts]
            test_iuts = [Iut(provider_id=provider_id, test_id=test_id, identity=identity).as_dict]
            self.assertEqual(dict_iuts, test_iuts)
