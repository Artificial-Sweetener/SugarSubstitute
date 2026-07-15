#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Compose onboarding execution submitters from the application runtime."""

from __future__ import annotations

from typing import Protocol, TypeVar

from PySide6.QtCore import QObject

from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskRequest,
    TaskSubmitter,
)
from substitute.infrastructure.execution.thread_pool_lane import CompletionDispatcher
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingProvisioningExecutionRoute,
    OnboardingProvisioningSubmitterFactory,
)
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher

TResult = TypeVar("TResult")

_ONBOARDING_PROVISIONING_LANE = "onboarding_provisioning"


class RuntimeOnboardingSubmitter(TaskSubmitter, Protocol):
    """Describe a closeable runtime submitter for onboarding provisioning."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one onboarding provisioning task."""

    def close(self) -> None:
        """Release the runtime dispatcher route."""


class OnboardingExecutionRuntime(Protocol):
    """Describe the runtime factory needed by onboarding composition."""

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: CompletionDispatcher,
    ) -> RuntimeOnboardingSubmitter:
        """Create one owner-scoped runtime submitter."""


def create_onboarding_provisioning_submitter_factory(
    execution_runtime: OnboardingExecutionRuntime,
) -> OnboardingProvisioningSubmitterFactory:
    """Return a factory that creates controller-owned provisioning submitters."""

    def create_submitter(owner: QObject) -> OnboardingProvisioningExecutionRoute:
        """Create task and progress routes bound to an onboarding controller."""

        dispatcher = QtOwnerThreadDispatcher(owner)
        runtime_submitter = execution_runtime.submitter(
            _ONBOARDING_PROVISIONING_LANE,
            owner_id="onboarding_controller",
            dispatcher=dispatcher,
        )
        return OnboardingProvisioningExecutionRoute(
            submitter=runtime_submitter,
            close_submitter=runtime_submitter.close,
            progress_publisher=dispatcher,
        )

    return create_submitter


__all__ = [
    "OnboardingExecutionRuntime",
    "RuntimeOnboardingSubmitter",
    "create_onboarding_provisioning_submitter_factory",
]
