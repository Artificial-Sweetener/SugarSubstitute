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

"""Restore exact prompt history geometry through the prepared-frame owner."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)

from ..layout.checkpoints import (
    PromptProjectionLayoutCheckpoint,
    restore_layout_checkpoint,
)
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .freshness_controller import PromptProjectionFreshnessBlockers


class PromptHistoryCheckpointStrategy:
    """Own checkpoint eligibility and immutable frame restoration."""

    def __init__(self, layout: PromptLayoutEditToFrameCoordinator) -> None:
        """Store the sole edit-to-frame publication owner."""

        self._layout = layout

    def try_restore(
        self,
        checkpoint: PromptProjectionLayoutCheckpoint | None,
        *,
        blockers: PromptProjectionFreshnessBlockers | None,
        expected_source_text: str,
    ) -> PromptProjectionDocument | None:
        """Restore matching projected geometry and return its document."""

        if (
            checkpoint is None
            or blockers is None
            or blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED
            or blockers.reorder_preview_active
            or blockers.autocomplete_preview_active
            or blockers.exact_weight_edit_active
            or blockers.expanded_source_range_active
            or checkpoint.projection_document.source_text != expected_source_text
        ):
            return None
        frame = self._layout.frame
        paint_input = frame.paint_input
        restored_output = restore_layout_checkpoint(
            checkpoint,
            configuration=frame.output.configuration,
            palette_key=int(paint_input.palette.cacheKey()),
            semantic_palette=paint_input.semantic_palette,
        )
        if restored_output is None:
            return None
        frame.restore(restored_output)
        return checkpoint.projection_document


__all__ = ["PromptHistoryCheckpointStrategy"]
