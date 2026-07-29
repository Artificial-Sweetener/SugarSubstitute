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

"""Characterize captured-subject clipboard publication for Output transfer policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar
from pathlib import Path
from uuid import uuid4

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

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
from substitute.presentation.canvas.output.output_transfer_clipboard_controller import (
    OutputTransferClipboardController,
)
from substitute.presentation.canvas.output.output_transfer_resolver import (
    OutputTransferResolver,
)

TResult = TypeVar("TResult")


class _Preferences:
    """Expose canonical-PNG defaults without filesystem preference persistence."""

    def load(self) -> OutputPreferences:
        """Return the default transfer preferences."""

        return OutputPreferences()

    def save(self, preferences: OutputPreferences) -> None:
        """Accept unused fixture persistence requests."""

        del preferences


class _ImmediateHandle(Generic[TResult]):
    """Publish one synchronous task result through the task-handle protocol."""

    def __init__(self, outcome: TaskOutcome[TResult]) -> None:
        """Store the settled task outcome."""

        self._outcome = outcome

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
        """Accept cancellation because this fixture is already settled."""

        del reason


class _ImmediateSubmitter:
    """Execute clipboard work deterministically through the application boundary."""

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
        return _ImmediateHandle(outcome)


def test_clipboard_uses_the_captured_document_subject_without_route_activation(
    tmp_path: Path,
) -> None:
    """Copy should publish the captured tile's selected MIME data without UI selection."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    published: list[object] = []
    failures: list[str] = []
    try:
        assert document.admit_image(image_id, _image())
        reference = document.content_reference_for(image_id)
        assert reference is not None
        active_composition_id = document.session.active_composition_id
        controller = OutputTransferClipboardController(
            resolver=_resolver(document, tmp_path, {image_id}),
            submitter=_ImmediateSubmitter(),
            publish_mime_data=published.append,
            report_failure=failures.append,
        )

        controller.copy(reference)

        assert failures == []
        assert len(published) == 1
        mime_data = published[0]
        assert hasattr(mime_data, "data")
        assert bytes(mime_data.data("image/png").data()).startswith(b"\x89PNG")
        assert document.session.active_composition_id == active_composition_id
    finally:
        document.close()
        app.processEvents()


def test_clipboard_rejects_a_replaced_captured_subject(tmp_path: Path) -> None:
    """A stale context-menu subject must not publish a later image to clipboard."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    published: list[object] = []
    failures: list[str] = []
    try:
        assert document.admit_image(image_id, _image())
        reference = document.content_reference_for(image_id)
        assert reference is not None
        assert document.admit_image(image_id, _image("blue"))
        controller = OutputTransferClipboardController(
            resolver=_resolver(document, tmp_path, {image_id}),
            submitter=_ImmediateSubmitter(),
            publish_mime_data=published.append,
            report_failure=failures.append,
        )

        controller.copy(reference)

        assert published == []
        assert failures == ["Output image is no longer available."]
    finally:
        document.close()
        app.processEvents()


def _resolver(
    document: OutputCanvasDocument,
    tmp_path: Path,
    authorized: set[object],
) -> OutputTransferResolver:
    """Build a resolver restricted to the fixture's active document content."""

    return OutputTransferResolver(
        document=document,
        preference_service=OutputPreferenceService(
            _Preferences(), default_output_root=tmp_path
        ),
        artifact_store=OutputTransferArtifactStore(tmp_path / "transfers"),
        is_image_authorized=authorized.__contains__,
    )


def _image(color: str = "red") -> QImage:
    """Create deterministic document pixels."""

    image = QImage(12, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


def _app() -> QApplication:
    """Return a Qt application for CuteCanvas document ownership."""

    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])
