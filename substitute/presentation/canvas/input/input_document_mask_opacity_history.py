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

"""Commit live mask-opacity previews into CuteCanvas chronological history."""

from __future__ import annotations

from dataclasses import replace
import math
from uuid import UUID

from cutecanvas import CanvasDocument

from substitute.presentation.canvas.input.input_document_catalog import (
    InputDocumentCatalog,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_document_mask_opacity_history")


class InputDocumentMaskOpacityHistory:
    """Record every node-owned mask opacity gesture as one atomic scene edit."""

    def __init__(
        self,
        *,
        document: CanvasDocument,
        catalog: InputDocumentCatalog,
    ) -> None:
        """Bind the document history and application-to-layer identity catalog."""

        self._document = document
        self._catalog = catalog

    def commit(
        self,
        mask_ids: tuple[UUID, ...],
        *,
        before: float,
        after: float,
    ) -> bool:
        """Record an already-previewed uniform opacity change as one stack edit."""

        previous = self._normalize(before)
        current = self._normalize(after)
        if previous is None or current is None or previous == current or not mask_ids:
            return False
        composition_ids = {
            self._catalog.composition_for_mask(mask_id) for mask_id in mask_ids
        }
        if None in composition_ids or len(composition_ids) != 1:
            return False
        composition_id = next(iter(composition_ids))
        if composition_id is None:
            return False
        image_id = self._catalog.image_id_for_composition(composition_id)
        if image_id is None:
            return False
        layer_ids = {
            layer_id
            for mask_id in mask_ids
            if (layer_id := self._catalog.mask_layer_for_image(image_id, mask_id))
            is not None
        }
        if len(layer_ids) != len(mask_ids):
            return False

        compositions = self._document.resources.compositions
        applied_stack = compositions.layers.layers_for_composition(composition_id)
        target_layers = tuple(
            layer for layer in applied_stack if layer.layer_id in layer_ids
        )
        if len(target_layers) != len(layer_ids) or any(
            layer.opacity != current for layer in target_layers
        ):
            return False
        previous_stack = tuple(
            replace(layer, opacity=previous) if layer.layer_id in layer_ids else layer
            for layer in applied_stack
        )
        if not compositions.layers.replace_layers(composition_id, previous_stack):
            return False
        if compositions.layer_edits.replace_stack(
            composition_id,
            applied_stack,
            history_scope_id=composition_id,
        ):
            return True
        restored = compositions.layers.replace_layers(composition_id, applied_stack)
        if not restored:
            log_warning(
                _LOGGER,
                "Failed to restore mask opacity preview after history rejection",
                composition_id=str(composition_id),
                mask_count=len(mask_ids),
                before=previous,
                after=current,
            )
        return False

    @staticmethod
    def _normalize(value: float) -> float | None:
        """Return one finite normalized opacity or reject it."""

        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return None
        return (
            normalized
            if math.isfinite(normalized) and 0.0 <= normalized <= 1.0
            else None
        )


__all__ = ["InputDocumentMaskOpacityHistory"]
