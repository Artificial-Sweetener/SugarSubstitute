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

"""Provide deterministic owners shared by Output transfer contract tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar
from uuid import UUID

from PySide6.QtGui import QColor, QImage

from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
)
from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.domain.generation import OutputPreferences
from substitute.infrastructure.persistence.output_transfer_artifact_store import (
    OutputTransferArtifactStore,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_transfer_resolver import (
    OutputTransferResolver,
)

TResult = TypeVar("TResult")


class MemoryOutputPreferences:
    """Retain Output preferences without filesystem persistence."""

    def __init__(self) -> None:
        """Start with canonical-PNG transfer defaults."""

        self.preferences = OutputPreferences()

    def load(self) -> OutputPreferences:
        """Return the current preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Store normalized preferences."""

        self.preferences = preferences


class ImmediateTaskHandle(Generic[TResult]):
    """Publish one synchronous task result through the task-handle protocol."""

    def __init__(self, outcome: TaskOutcome[TResult]) -> None:
        """Store the settled task outcome."""

        self._outcome = outcome
        self.cancel_reasons: list[str] = []

    @property
    def identity(self) -> TaskIdentity:
        """Return the settled task identity."""

        return self._outcome.identity

    @property
    def is_finished(self) -> bool:
        """Return that the deterministic task has settled."""

        return True

    @property
    def outcome(self) -> TaskOutcome[TResult]:
        """Return the published outcome."""

        return self._outcome

    @property
    def state(self) -> str:
        """Return the protocol settlement state."""

        return self._outcome.status

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Synchronously deliver the completed result."""

        del reason
        callback(self._outcome)

    def cancel(self, *, reason: str) -> None:
        """Record a cancellation request for assertion."""

        self.cancel_reasons.append(reason)


class ImmediateTaskSubmitter:
    """Execute task work deterministically through the application boundary."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Return a completed success, failure, or cancellation outcome."""

        if cancellation.is_cancelled:
            outcome: TaskOutcome[TResult] = TaskOutcome(
                identity=request.identity,
                context=request.context,
                status="cancelled",
                cancellation_reason=cancellation.reason or "cancelled",
            )
        else:
            try:
                outcome = TaskOutcome(
                    identity=request.identity,
                    context=request.context,
                    status="succeeded",
                    result=request.work(cancellation),
                )
            except Exception as error:
                outcome = TaskOutcome(
                    identity=request.identity,
                    context=request.context,
                    status="failed",
                    error=error,
                )
        return ImmediateTaskHandle(outcome)


class RejectingTaskSubmitter:
    """Reject task submission in lifecycle-only tests."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Fail if a lifecycle assertion accidentally starts transfer work."""

        del request, cancellation
        raise AssertionError("Lifetime characterization must not submit transfer work.")


def build_transfer_resolver(
    document: OutputCanvasDocument,
    root: Path,
    authorized: set[UUID],
) -> OutputTransferResolver:
    """Build a resolver restricted to current authorized document content."""

    return OutputTransferResolver(
        document=document,
        preference_service=OutputPreferenceService(
            MemoryOutputPreferences(), default_output_root=root
        ),
        artifact_store=OutputTransferArtifactStore(root / "transfers"),
        is_image_authorized=authorized.__contains__,
    )


def transfer_image(color: str = "red") -> QImage:
    """Create deterministic transferable pixels."""

    image = QImage(12, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image
