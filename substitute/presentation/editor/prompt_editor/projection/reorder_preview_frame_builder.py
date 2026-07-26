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

"""Build prepared reorder preview frames from immutable projection snapshots."""

from __future__ import annotations

from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

from .applicator import PromptProjectionApplicator
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .prepared_frame import PromptProjectionPreparedFrame
from .reorder_preview import PromptReorderProjectionSnapshot
from .reorder_preview_layout_builder import (
    PromptReorderPreviewLayoutBuilder,
    PromptReorderPreviewLayoutIdentity,
    PromptReorderReusablePreviewLayout,
)
from .reorder_preview_projection_metrics import (
    PromptReorderPreviewProjectionMetrics,
)


class PromptReorderPreviewFrameBuilder:
    """Own full and incremental frame construction and build accounting."""

    def __init__(
        self,
        *,
        projection_applicator: PromptProjectionApplicator,
        thumbnail_cache: PromptLoraThumbnailCache,
        metrics: PromptReorderPreviewProjectionMetrics,
    ) -> None:
        """Create the focused layout builder used for one surface lifecycle."""

        self._layout_builder = PromptReorderPreviewLayoutBuilder(
            projection_applicator=projection_applicator,
            thumbnail_cache=thumbnail_cache,
        )
        self._metrics = metrics

    def build(
        self,
        snapshot: PromptReorderProjectionSnapshot,
        *,
        identity: PromptReorderPreviewLayoutIdentity,
        layout_width: float,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
        reusable: PromptReorderReusablePreviewLayout | None,
        gesture_id: int | None,
        event_id: int | None,
        reason: str,
    ) -> tuple[PromptProjectionDocument, PromptProjectionPreparedFrame]:
        """Build one frame and record whether it reused a local layout window."""

        self._metrics.projection_snapshot_rebuild_count += 1
        result = self._layout_builder.build(
            snapshot,
            identity=identity,
            layout_width=layout_width,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            reusable=reusable,
        )
        if result.incremental:
            self._metrics.incremental_layout_count += 1
        else:
            self._metrics.full_layout_count += 1
        return result.document, result.frame

    def can_reuse_exactly(
        self,
        reusable: PromptReorderReusablePreviewLayout | None,
        *,
        identity: PromptReorderPreviewLayoutIdentity,
        render_plan_hash: str,
        snapshot: PromptReorderProjectionSnapshot,
    ) -> bool:
        """Return whether a published frame exactly serves another role."""

        return self._layout_builder.can_reuse_exactly(
            reusable,
            identity=identity,
            render_plan_hash=render_plan_hash,
            snapshot=snapshot,
        )


__all__ = ["PromptReorderPreviewFrameBuilder"]
