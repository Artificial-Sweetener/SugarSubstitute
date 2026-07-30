#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
"""Hostile proof for coherent multi-resource Input generation capture."""

from uuid import UUID, uuid4

from cutecanvas import (
    CanvasContentKind,
    CanvasContentReference,
    EmbeddedImageExportSnapshot,
    MaskExportSnapshot,
)
from PySide6.QtGui import QImage

from substitute.presentation.canvas.input.input_generation_capture import (
    InputDocumentGenerationCapture,
)


def test_capture_retries_when_edit_lands_between_image_and_mask_products() -> None:
    """A mid-capture edit must discard the mixed attempt and retry coherently."""
    image_id = uuid4()
    mask_id = uuid4()
    revision = {"value": 1}
    mask_captures = 0

    def reference(composition_id: UUID) -> CanvasContentReference:
        """Return the current composition revision."""
        return CanvasContentReference(
            document_id=uuid4(),
            kind=CanvasContentKind.COMPOSITION,
            composition_id=composition_id,
            instance_revision=revision["value"],
        )

    document_id = uuid4()

    def stable_reference(composition_id: UUID) -> CanvasContentReference:
        """Return revisions from one stable document identity."""
        value = reference(composition_id)
        return CanvasContentReference(
            document_id=document_id,
            kind=value.kind,
            composition_id=value.composition_id,
            instance_revision=value.instance_revision,
        )

    def capture_mask(
        requested_mask_id: UUID,
        composition_id: UUID,
    ) -> MaskExportSnapshot:
        """Inject one edit into the first attempted capture."""
        nonlocal mask_captures
        mask_captures += 1
        snapshot = MaskExportSnapshot(
            requested_mask_id,
            composition_id,
            revision["value"],
            _image(),
        )
        if mask_captures == 1:
            revision["value"] += 1
        return snapshot

    capture = InputDocumentGenerationCapture(
        composition_for_image=lambda requested: requested,
        composition_for_mask=lambda _requested: image_id,
        content_reference=stable_reference,
        capture_image=lambda composition_id: EmbeddedImageExportSnapshot(
            composition_id,
            uuid4(),
            revision["value"],
            _image(),
        ),
        capture_mask=capture_mask,
    )

    result = capture.capture(image_ids=(image_id,), mask_ids=(mask_id,))

    assert result is not None
    assert mask_captures == 2
    assert result.images[image_id].revision == 2
    assert result.masks[mask_id].revision == 2


def test_capture_fails_closed_under_continuous_hostile_mutation() -> None:
    """Three unstable attempts must yield no externally materializable bundle."""
    image_id = uuid4()
    mask_id = uuid4()
    document_id = uuid4()
    revision = {"value": 0}

    def reference(composition_id: UUID) -> CanvasContentReference:
        """Return the latest deliberately unstable revision."""
        return CanvasContentReference(
            document_id,
            CanvasContentKind.COMPOSITION,
            composition_id=composition_id,
            instance_revision=revision["value"],
        )

    def capture_mask(
        requested_mask_id: UUID,
        composition_id: UUID,
    ) -> MaskExportSnapshot:
        """Advance the composition during every attempted capture."""
        revision["value"] += 1
        return MaskExportSnapshot(
            requested_mask_id,
            composition_id,
            revision["value"],
            _image(),
        )

    capture = InputDocumentGenerationCapture(
        composition_for_image=lambda requested: requested,
        composition_for_mask=lambda _requested: image_id,
        content_reference=reference,
        capture_image=lambda composition_id: EmbeddedImageExportSnapshot(
            composition_id,
            uuid4(),
            revision["value"],
            _image(),
        ),
        capture_mask=capture_mask,
    )

    assert capture.capture(image_ids=(image_id,), mask_ids=(mask_id,)) is None


def _image() -> QImage:
    """Return one non-null detached product."""
    image = QImage(4, 4, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    return image
