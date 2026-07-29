"""Verify native Output transfer data stays internally representation-consistent."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtGui import QColor, QImage
from cutecanvas import CanvasContentKind, CanvasContentReference

from substitute.infrastructure.persistence.output_transfer_artifact_store import (
    OutputTransferArtifact,
)
from substitute.presentation.canvas.output.output_transfer_payloads import (
    drag_payload_for_transfer,
    mime_data_for_transfer,
)
from substitute.presentation.canvas.output.output_transfer_resolver import (
    ResolvedOutputTransfer,
)


def test_drag_and_clipboard_represent_the_same_selected_jpeg(tmp_path: Path) -> None:
    """File URL, bytes, preview, and clipboard image must agree on JPEG selection."""

    artifact = OutputTransferArtifact(
        path=tmp_path / "selected.jpg",
        mime_type="image/jpeg",
        data=b"jpeg-bytes",
        image=_image(),
        staged=True,
    )
    resolved = ResolvedOutputTransfer(uuid4(), _reference(), artifact)

    drag = drag_payload_for_transfer(resolved)
    clipboard = mime_data_for_transfer(resolved)

    assert drag.items[0].mime_type == "image/jpeg"
    assert drag.items[0].data == b"jpeg-bytes"
    assert drag.urls[0].toLocalFile().endswith("selected.jpg")
    assert drag.preview is not None and drag.preview.pixelColor(0, 0) == QColor("red")
    assert bytes(clipboard.data("image/jpeg").data()) == b"jpeg-bytes"
    assert clipboard.urls()[0].toLocalFile().endswith("selected.jpg")


def _reference() -> CanvasContentReference:
    """Return a structurally valid immutable composition reference."""

    return CanvasContentReference(
        document_id=uuid4(),
        kind=CanvasContentKind.COMPOSITION,
        composition_id=uuid4(),
    )


def _image() -> QImage:
    """Return deterministic decoded transfer pixels."""

    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    return image
