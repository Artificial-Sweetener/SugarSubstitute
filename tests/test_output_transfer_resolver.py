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

"""Characterize authorization and revision safety for Output transfer resolution."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

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


class _Preferences:
    """Retain Output preferences in memory for resolver characterization."""

    def __init__(self) -> None:
        """Start with canonical-PNG transfer defaults."""

        self.preferences = OutputPreferences()

    def load(self) -> OutputPreferences:
        """Return stored preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Store normalized preferences."""

        self.preferences = preferences


def test_resolver_uses_captured_current_authorized_document_content(
    tmp_path: Path,
) -> None:
    """A captured composition should resolve to its matching staged PNG artifact."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    try:
        assert document.admit_image(image_id, _image("red"))
        reference = document.content_reference_for(image_id)
        assert reference is not None
        resolver = _resolver(document, tmp_path, authorized={image_id})

        resolved = resolver.resolve(reference)

        assert resolved is not None
        assert resolved.image_id == image_id
        assert resolved.artifact.mime_type == "image/png"
        assert resolved.artifact.staged is True
    finally:
        document.close()
        app.processEvents()


def test_resolver_rejects_foreign_or_replaced_document_subjects(tmp_path: Path) -> None:
    """Retired and product-unauthorized content must never materialize a transfer."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()
    try:
        assert document.admit_image(image_id, _image("red"))
        reference = document.content_reference_for(image_id)
        assert reference is not None
        assert (
            _resolver(document, tmp_path, authorized=set()).resolve(reference) is None
        )

        assert document.admit_image(image_id, _image("blue"))
        assert (
            _resolver(document, tmp_path, authorized={image_id}).resolve(reference)
            is None
        )
    finally:
        document.close()
        app.processEvents()


def _resolver(
    document: OutputCanvasDocument,
    tmp_path: Path,
    *,
    authorized: set[UUID],
) -> OutputTransferResolver:
    """Build one resolver with explicit product authorization."""

    return OutputTransferResolver(
        document=document,
        preference_service=OutputPreferenceService(
            _Preferences(), default_output_root=tmp_path
        ),
        artifact_store=OutputTransferArtifactStore(tmp_path / "transfers"),
        is_image_authorized=authorized.__contains__,
    )


def _image(color: str) -> QImage:
    """Create one deterministic opaque Output image."""

    image = QImage(12, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


def _app() -> QApplication:
    """Return a Qt application for CuteCanvas document ownership."""

    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])
