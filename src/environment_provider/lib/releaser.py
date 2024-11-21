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
"""Releaser of environments."""
import logging
from jsontas.jsontas import JsonTas
from opentelemetry import trace
from pydantic import ValidationError
from etos_lib.kubernetes.schemas import Environment as EnvironmentSchema
from etos_lib.kubernetes.schemas import Provider as ProviderSchema
from etos_lib.kubernetes import Kubernetes, Environment, Provider
from etos_lib import ETOS
from execution_space_provider import ExecutionSpaceProvider
from execution_space_provider.exceptions import ExecutionSpaceCheckinFailed
from execution_space_provider.execution_space import ExecutionSpace
from iut_provider import IutProvider
from iut_provider.exceptions import IutCheckinFailed
from iut_provider.iut import Iut as IutSpec
from log_area_provider import LogAreaProvider
from log_area_provider.exceptions import LogAreaCheckinFailed
from log_area_provider.log_area import LogArea as LogAreaSpec

TRACER = trace.get_tracer(__name__)


class ReleaseError(Exception):
    """Error when releasing environment."""


class Releaser:
    """Releaser is a tool for releasing environments that have been checked out by ETOS."""

    logger = logging.getLogger(__name__)

    def __init__(self, etos: ETOS, environment: EnvironmentSchema):
        """Set up releaser."""
        self.environment = environment
        self.etos = etos
        self.jsontas = JsonTas()
        self.kubernetes = Kubernetes()
        self.provider_client = Provider(self.kubernetes)

    def provider(self, provider_id: str) -> dict:
        """Get a provider by ID from Kubernetes or a database."""
        provider = self.provider_client.get(provider_id)
        assert provider is not None, f"Could not find a provider with ID {provider_id!r}"
        provider_model = ProviderSchema.model_validate(provider.to_dict())
        if provider_model.spec.jsontas:
            return provider_model.to_jsontas()
        return provider_model.to_external()

    def run(self) -> None:
        """Run a release task for ETOS."""
        raise NotImplementedError()


class Iut(Releaser):
    """Iut releases IUTs checked out by ETOS."""

    logger = logging.getLogger(__name__)

    def get_provider(self) -> IutProvider:
        """Get provider returns an IUT provider using the provider model."""
        ruleset = self.environment.spec.iut
        assert ruleset is not None, f"There is no IUT field in environment {self.environment!r}"
        self.logger.info("Releasing IUT with ruleset: %r", ruleset)
        provider_id = ruleset.get("provider_id", "")
        self.logger.info("Provider to use for release: %r", provider_id)
        provider_model = self.provider(provider_id)
        self.logger.info("Model to use for release: %r", provider_model)
        return IutProvider(self.etos, self.jsontas, provider_model)  # type: ignore

    def release(self):
        """Release an IUT."""
        ruleset = self.environment.spec.iut
        provider_id = ruleset.get("provider_id", "")
        try:
            provider = self.get_provider()
        except AssertionError:
            self.logger.exception("Missing IUT provider")
            raise
        except ValidationError:
            self.logger.exception(
                "The schema of IUT provider with id %r could not be validated",
                provider_id,
            )
            return

        self.logger.info("Initializing release of IUT %r", ruleset)
        try:
            provider.checkin(IutSpec(**ruleset))
            self.logger.info("Successfully released IUT")
        except IutCheckinFailed:
            self.logger.error("Failed to release IUT %r with provider %r", ruleset, provider_id)
            raise

    def run(self):
        """Run releases IUTs that ETOS has checked out for an environment."""
        with TRACER.start_as_current_span(name="stop_iuts", kind=trace.SpanKind.CLIENT) as span:
            try:
                self.release()
            except Exception as exception:
                span.record_exception(exception)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise


class Executor(Releaser):
    """Executor releases execution spaces checked out by ETOS."""

    logger = logging.getLogger(__name__)

    def get_provider(self) -> ExecutionSpaceProvider:
        """Get provider returns an execution space provider using the provider model."""
        ruleset = self.environment.spec.executor
        assert (
            ruleset is not None
        ), f"There is no executor field in environment {self.environment!r}"
        self.logger.info("Releasing executor with ruleset: %r", ruleset)
        provider_id = ruleset.get("provider_id", "")
        self.logger.info("Provider to use for release: %r", provider_id)
        provider_model = self.provider(provider_id)
        return ExecutionSpaceProvider(self.etos, self.jsontas, provider_model)  # type: ignore

    def release(self):
        """Release an executor."""
        ruleset = self.environment.spec.executor
        provider_id = ruleset.get("provider_id", "")
        try:
            provider = self.get_provider()
        except AssertionError:
            self.logger.exception("Missing executor provider")
            raise
        except ValidationError:
            self.logger.exception(
                "The schema of execution space provider with id %r could not be validated",
                provider_id,
            )
            return

        self.logger.info("Initializing release of executor %r", ruleset)
        try:
            provider.checkin(ExecutionSpace(**ruleset))
            self.logger.info("Successfully released executor")
        except ExecutionSpaceCheckinFailed:
            self.logger.error(
                "Failed to release executor %r with provider %r", ruleset, provider_id
            )
            raise

    def run(self):
        """Run releases executors that ETOS has checked out for an environment."""
        with TRACER.start_as_current_span(
            name="stop_execution_space", kind=trace.SpanKind.CLIENT
        ) as span:
            try:
                self.release()
            except Exception as exception:
                span.record_exception(exception)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise


class LogArea(Releaser):
    """Logarea releases log areas checked out by ETOS."""

    logger = logging.getLogger(__name__)

    def get_provider(self) -> LogAreaProvider:
        """Get provider returns an log area provider using the provider model."""
        ruleset = self.environment.spec.log_area
        assert (
            ruleset is not None
        ), f"There is no log area field in environment {self.environment!r}"
        self.logger.info("Releasing log area with ruleset: %r", ruleset)
        provider_id = ruleset.get("provider_id", "")
        self.logger.info("Provider to use for release: %r", provider_id)
        provider_model = self.provider(provider_id)
        return LogAreaProvider(self.etos, self.jsontas, provider_model)  # type: ignore

    def release(self):
        """Release an executor."""
        ruleset = self.environment.spec.log_area
        provider_id = ruleset.get("provider_id", "")
        try:
            provider = self.get_provider()
        except AssertionError:
            self.logger.exception("Missing log area provider")
            raise
        except ValidationError:
            self.logger.exception(
                "The schema of log area provider with id %r could not be validated",
                provider_id,
            )
            return

        self.logger.info("Initializing release of log area %r", ruleset)
        try:
            provider.checkin(LogAreaSpec(**ruleset))
            self.logger.info("Successfully released log area")
        except LogAreaCheckinFailed:
            self.logger.error(
                "Failed to release log area %r with provider %r", ruleset, provider_id
            )
            raise

    def run(self):
        """Run releases log areas that ETOS has checked out for an environment."""
        with TRACER.start_as_current_span(name="stop_log_area", kind=trace.SpanKind.CLIENT) as span:
            try:
                self.release()
            except Exception as exception:
                span.record_exception(exception)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                self.logger.exception("Release failed")
                raise


class EnvironmentReleaser:
    """Release environments checked out by ETOS."""

    logger = logging.getLogger(__name__)

    def environment(self, environment_id: str) -> EnvironmentSchema:
        """Environment gets an environment from kubernetes with environment_id as name."""
        client = Environment(Kubernetes())
        environment = client.get(environment_id).to_dict()  # type: ignore
        return EnvironmentSchema.model_validate(environment)

    def run(self, environment_id: str):
        """Run the releaser. It will check which type of environment and release it."""
        self.logger.info("Running the environment releaser")
        etos = ETOS("", "", "")

        self.logger.info("Releasing environment based of an environment ID: %r", environment_id)
        try:
            environment = self.environment(environment_id)
        except AttributeError:
            self.logger.exception(
                "Could not find Environment with id %r in Kubernetes. "
                "Trying to release something that's already released?",
                environment_id,
            )
            return
        except ValidationError:
            self.logger.exception(
                "The schema of Environment with id %r could not be validated",
                environment_id,
            )
            return
        etos.config.set("SUITE_ID", environment.spec.suite_id)
        tasks = [Iut(etos, environment), LogArea(etos, environment), Executor(etos, environment)]

        exceptions = []
        for task in tasks:
            self.logger.info("Running release task on %r", type(task).__name__)
            try:
                task.run()
            except Exception as exception:  # pylint:disable=broad-exception-caught
                self.logger.error("Task %r failed", type(task).__name__)
                exceptions.append(exception)
        if exceptions:
            raise ReleaseError("Some or all release tasks failed")
