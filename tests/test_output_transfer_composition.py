"""Verify Output transfer composition owns every native-transfer resource lifetime."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskRequest,
)
from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.domain.generation import OutputPreferences
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_transfer_composition import (
    compose_output_transfer_lifecycle,
)

TResult = TypeVar("TResult")


class _Preferences:
    """Expose default Output preferences without touching filesystem persistence."""

    def load(self) -> OutputPreferences:
        """Return canonical-PNG transfer defaults."""

        return OutputPreferences()

    def save(self, preferences: OutputPreferences) -> None:
        """Accept unused fixture persistence requests."""

        del preferences


class _NoopSubmitter:
    """Reject materialization because this test exercises lifetime only."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Reject accidental task submission outside the lifetime assertion."""

        del request, cancellation
        raise AssertionError("Lifetime characterization must not submit drag work.")


def test_transfer_lifecycle_closes_provider_dispatcher_and_staged_artifacts(
    tmp_path: Path,
) -> None:
    """Shell cleanup must reclaim the provider route and every staged transfer file."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    closed_submitters: list[str] = []
    try:
        assert document.admit_image(image_id, _image())
        lifecycle = compose_output_transfer_lifecycle(
            document=document,
            is_image_authorized=lambda candidate: candidate == image_id,
            preference_service=OutputPreferenceService(
                _Preferences(), default_output_root=tmp_path
            ),
            drag_submitter=_NoopSubmitter(),
            close_drag_submitter=lambda: closed_submitters.append("drag"),
            clipboard_submitter=_NoopSubmitter(),
            close_clipboard_submitter=lambda: closed_submitters.append("clipboard"),
            publish_clipboard_mime_data=lambda _mime_data: None,
            report_clipboard_failure=lambda _message: None,
            staging_directory=tmp_path / "transfers",
        )
        artifact = lifecycle.artifact_store.materialize(
            _image(),
            canonical_path=None,
            transfer_format=OutputPreferences().transfer.preferred_format,
            jpeg_settings=OutputPreferences().jpeg,
        )
        assert artifact is not None

        lifecycle.close()
        lifecycle.close()

        assert closed_submitters == ["clipboard", "drag"]
        assert artifact.path.exists() is False
    finally:
        document.close()
        app.processEvents()


def _image() -> QImage:
    """Create deterministic transfer pixels."""

    image = QImage(12, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    return image


def _app() -> QApplication:
    """Return a Qt application for CuteCanvas document ownership."""

    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])
