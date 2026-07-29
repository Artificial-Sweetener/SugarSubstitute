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

"""Characterize captured-subject execution for native Output drag materialization."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar
from uuid import uuid4

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from cutecanvas import DragSubject

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
from substitute.presentation.canvas.output.output_transfer_drag_provider import (
    OutputTransferDragProvider,
)
from substitute.presentation.canvas.output.output_transfer_resolver import (
    OutputTransferResolver,
)

TResult = TypeVar("TResult")


class _Preferences:
    """Retain default Output preferences for execution characterization."""

    def load(self) -> OutputPreferences:
        """Return the canonical-PNG default preferences."""

        return OutputPreferences()

    def save(self, preferences: OutputPreferences) -> None:
        """Accept persistence calls unused by this test fixture."""

        del preferences


class _ImmediateHandle(Generic[TResult]):
    """Publish a precomputed task outcome when a listener is attached."""

    def __init__(self, outcome: TaskOutcome[TResult]) -> None:
        """Store one completed outcome."""

        self._outcome = outcome
        self.cancel_reasons: list[str] = []

    @property
    def identity(self) -> TaskIdentity:
        """Return the completed task identity."""

        return self._outcome.identity

    @property
    def is_finished(self) -> bool:
        """Return that this deterministic handle is already complete."""

        return True

    @property
    def outcome(self) -> TaskOutcome[TResult]:
        """Return the completed task outcome."""

        return self._outcome

    @property
    def state(self) -> str:
        """Return the settled state used by the task protocol."""

        return self._outcome.status

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Synchronously publish the captured outcome."""

        del reason
        callback(self._outcome)

    def cancel(self, *, reason: str) -> None:
        """Record a cancellation request for assertion."""

        self.cancel_reasons.append(reason)


class _ImmediateSubmitter:
    """Execute task work deterministically through the TaskSubmitter contract."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Run the task and return a settled, callback-capable handle."""

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
        return _ImmediateHandle(outcome)


def test_drag_provider_materializes_the_captured_document_subject(
    tmp_path: Path,
) -> None:
    """Native drag payload must represent the pressed document content, not active state."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    try:
        assert document.admit_image(image_id, _image())
        reference = document.content_reference_for(image_id)
        assert reference is not None
        provider = OutputTransferDragProvider(
            resolver=_resolver(document, tmp_path, {image_id}),
            submitter=_ImmediateSubmitter(),
        )
        published: list[tuple[object | None, BaseException | None]] = []

        cancellation = provider.materialize(
            DragSubject(reference),
            lambda payload, error: published.append((payload, error)),
        )

        assert cancellation is not None
        assert len(published) == 1
        payload, error = published[0]
        assert error is None
        assert payload is not None
        assert hasattr(payload, "items")
        assert hasattr(payload, "urls")
        assert payload.items[0].mime_type == "image/png"
        assert payload.urls[0].toLocalFile().endswith(".png")
    finally:
        document.close()
        app.processEvents()


def test_drag_provider_rejects_retired_captured_subject(tmp_path: Path) -> None:
    """Replacing content before materialization must not start a stale native drag."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    try:
        assert document.admit_image(image_id, _image())
        reference = document.content_reference_for(image_id)
        assert reference is not None
        assert document.admit_image(image_id, _image("blue"))
        provider = OutputTransferDragProvider(
            resolver=_resolver(document, tmp_path, {image_id}),
            submitter=_ImmediateSubmitter(),
        )
        published: list[tuple[object | None, BaseException | None]] = []

        provider.materialize(
            DragSubject(reference),
            lambda payload, error: published.append((payload, error)),
        )

        assert len(published) == 1
        payload, error = published[0]
        assert payload is None
        assert isinstance(error, RuntimeError)
        assert str(error) == "Output image is no longer available."
    finally:
        document.close()
        app.processEvents()


def _resolver(
    document: OutputCanvasDocument,
    tmp_path: Path,
    authorized: set[object],
) -> OutputTransferResolver:
    """Build one explicit resolver for a currently authorized fixture image."""

    return OutputTransferResolver(
        document=document,
        preference_service=OutputPreferenceService(
            _Preferences(), default_output_root=tmp_path
        ),
        artifact_store=OutputTransferArtifactStore(tmp_path / "transfers"),
        is_image_authorized=authorized.__contains__,
    )


def _image(color: str = "red") -> QImage:
    """Create one deterministic transferable image."""

    image = QImage(12, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


def _app() -> QApplication:
    """Return a Qt application for CuteCanvas document ownership."""

    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])
