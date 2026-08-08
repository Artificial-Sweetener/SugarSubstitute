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

"""Resolve live node-preview subjects from the authoritative Input document."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtCore import QRectF, QSize
from cutecanvas import (
    CanvasDocument,
    CanvasDocumentRuntime,
    CanvasRenderVariant,
    CanvasViewportSource,
)

from .input_document_view_lifetime import InputDocumentViewLifetime


@dataclass(frozen=True, slots=True)
class InputPreviewBinding:
    """Carry one live document source to a responsive preview widget."""

    identity: tuple[UUID, UUID]
    document: CanvasDocument
    runtime: CanvasDocumentRuntime
    source: CanvasViewportSource
    render_variant: CanvasRenderVariant
    features: tuple[str, ...]
    source_size: QSize
    view_lifetime: InputDocumentViewLifetime


class InputDocumentPreviewBindings:
    """Map application image and mask identities to public CuteCanvas subjects."""

    def __init__(
        self,
        *,
        document: CanvasDocument,
        runtime: CanvasDocumentRuntime,
        composition_for_image: Callable[[UUID], UUID | None],
        mask_layer_for_image: Callable[[UUID, UUID], UUID | None],
        view_lifetime: InputDocumentViewLifetime,
    ) -> None:
        """Capture identity lookups without owning document membership."""
        self._document = document
        self._runtime = runtime
        self._composition_for_image = composition_for_image
        self._mask_layer_for_image = mask_layer_for_image
        self._view_lifetime = view_lifetime

    def image(self, image_id: UUID) -> InputPreviewBinding | None:
        """Return the embedded image layer for one materialized Input image."""
        composition_id = self._composition_for_image(image_id)
        if composition_id is None:
            return None
        composition = self._document.snapshot().compositions.get(composition_id)
        if composition is None:
            return None
        layer = next(
            (
                candidate
                for candidate in composition.layers
                if candidate.role == "content"
            ),
            None,
        )
        if layer is None:
            return None
        reference = self._document.content_reference(
            composition_id,
            layer_id=layer.layer_id,
        )
        return InputPreviewBinding(
            identity=(composition_id, layer.layer_id),
            document=self._document,
            runtime=self._runtime,
            source=CanvasViewportSource.content(reference),
            render_variant=CanvasRenderVariant.COMPOSITE,
            features=(),
            source_size=_composition_size(composition.scene_bounds),
            view_lifetime=self._view_lifetime,
        )

    def mask(self, image_id: UUID, mask_id: UUID) -> InputPreviewBinding | None:
        """Return neutral coverage for one mask belonging to an Input image."""
        composition_id = self._composition_for_image(image_id)
        layer_id = self._mask_layer_for_image(image_id, mask_id)
        if composition_id is None or layer_id is None:
            return None
        composition = self._document.snapshot().compositions.get(composition_id)
        if composition is None:
            return None
        reference = self._document.content_reference(
            composition_id,
            layer_id=layer_id,
        )
        return InputPreviewBinding(
            identity=(composition_id, layer_id),
            document=self._document,
            runtime=self._runtime,
            source=CanvasViewportSource.content(reference),
            render_variant=CanvasRenderVariant.MASK_COVERAGE,
            features=("mask",),
            source_size=_composition_size(composition.scene_bounds),
            view_lifetime=self._view_lifetime,
        )


def _composition_size(bounds: QRectF | None) -> QSize:
    """Return a positive preview size from one composition canvas rectangle."""
    if bounds is None or bounds.isEmpty():
        return QSize(1, 1)
    return QSize(max(1, round(bounds.width())), max(1, round(bounds.height())))


__all__ = ["InputDocumentPreviewBindings", "InputPreviewBinding"]
