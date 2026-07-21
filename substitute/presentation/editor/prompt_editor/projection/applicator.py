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

"""Apply prepared prompt projection state to projection-owned layout objects."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)

from .builder import PromptProjectionBuilder
from .layout_engine import PromptProjectionLayout
from .model import (
    PromptProjectionCaretState,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionTransientState,
)
from .paint_state import (
    PromptProjectionPaintState,
    PromptProjectionPaintStateBuilder,
)
from .session import PromptProjectionSession


@dataclass(frozen=True, slots=True)
class PromptProjectionPaintStateApplyResult:
    """Carry geometry-neutral paint state applied over canonical geometry."""

    projection_document: PromptProjectionDocument
    paint_state: PromptProjectionPaintState
    active_span_range: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class PromptProjectionRebuildResult:
    """Carry rebuilt projection state and caret states resolved through it."""

    projection_document: PromptProjectionDocument
    active_span_range: tuple[int, int] | None
    cursor_state: PromptProjectionCaretState
    anchor_state: PromptProjectionCaretState


@dataclass(frozen=True, slots=True)
class PromptProjectionLayoutSyncResult:
    """Carry layout metrics after projection-owned layout state is synchronized."""

    layout_width: float
    active_layout: PromptProjectionLayout
    content_height: float
    content_width: float


class PromptProjectionApplicator:
    """Own projection document building and layout apply decisions."""

    def __init__(self, builder: PromptProjectionBuilder) -> None:
        """Store the projection builder used by apply paths."""

        self._builder = builder
        self._paint_state_builder = PromptProjectionPaintStateBuilder()

    def source_edit_requires_canonical_rebuild(
        self,
        previous_source_text: str,
        next_source_text: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether a source-local edit changes canonical scene topology."""

        return self._builder.source_edit_requires_canonical_rebuild(
            previous_source_text,
            next_source_text,
            start=start,
            end=end,
        )

    def apply_prompt_state_without_geometry_rebuild(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        source_changed: bool,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
        transient_state: PromptProjectionTransientState | None = None,
        current_document: PromptProjectionDocument,
        layout: PromptProjectionLayout,
    ) -> PromptProjectionPaintStateApplyResult | None:
        """Apply semantic paint state when projection geometry is identical."""

        if (
            source_changed
            or display_mode is PromptProjectionDisplayMode.RAW
            or current_document.source_text != document_view.source_text
            or session.autocomplete_preview is not None
            or session.exact_weight_edit is not None
            or session.expanded_source_range is not None
            or session.transient_neutral_emphasis is not None
            or (
                transient_state is not None
                and transient_state.autocomplete_preview is not None
            )
        ):
            return None
        _ = (document_view, render_plan)
        paint_state = self._paint_state_builder.build(
            current_document,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )
        if not layout.can_apply_paint_state(paint_state):
            return None
        layout.set_projection_paint_state(paint_state)
        return PromptProjectionPaintStateApplyResult(
            projection_document=current_document,
            paint_state=paint_state,
            active_span_range=active_span_range,
        )

    def apply_reusable_projection_paint_state(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
        transient_state: PromptProjectionTransientState | None = None,
        layout: PromptProjectionLayout,
    ) -> PromptProjectionPaintStateApplyResult | None:
        """Apply projection paint state when layout reports reusable geometry."""

        if (
            display_mode is PromptProjectionDisplayMode.RAW
            or session.autocomplete_preview is not None
            or session.exact_weight_edit is not None
            or session.expanded_source_range is not None
            or session.transient_neutral_emphasis is not None
            or (
                transient_state is not None
                and transient_state.autocomplete_preview is not None
            )
        ):
            return None
        _ = (document_view, render_plan)
        projection_document = layout.projection_document
        if projection_document.source_text != document_view.source_text:
            return None
        paint_state = self._paint_state_builder.build(
            projection_document,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )
        if not layout.can_apply_paint_state(paint_state):
            return None
        layout.set_projection_paint_state(paint_state)
        return PromptProjectionPaintStateApplyResult(
            projection_document=projection_document,
            paint_state=paint_state,
            active_span_range=active_span_range,
        )

    def rebuild_projection(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
        transient_state: PromptProjectionTransientState | None = None,
        layout: PromptProjectionLayout,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette,
        previous_cursor_state: PromptProjectionCaretState,
        previous_anchor_state: PromptProjectionCaretState,
    ) -> PromptProjectionRebuildResult:
        """Build a projection document, publish it to layout, and resolve carets."""

        projection_document = self.build_projection(
            document_view,
            render_plan,
            display_mode=display_mode,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
            transient_state=transient_state,
        )
        layout.set_base_font(font)
        layout.set_palette(palette)
        layout.set_semantic_palette(semantic_palette)
        layout.set_projection(
            projection_document,
            prompt_document_view=document_view,
        )
        return PromptProjectionRebuildResult(
            projection_document=projection_document,
            active_span_range=active_span_range,
            cursor_state=projection_document.caret_map.resolve_state(
                previous_cursor_state
            ),
            anchor_state=projection_document.caret_map.resolve_state(
                previous_anchor_state
            ),
        )

    def sync_layout_state(
        self,
        *,
        layout: PromptProjectionLayout,
        reorder_preview_layout: PromptProjectionLayout | None,
        reorder_base_drag_layout: PromptProjectionLayout | None,
        layout_width: float,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette,
        content_left_inset: float,
    ) -> PromptProjectionLayoutSyncResult:
        """Synchronize projection-owned layout style and width inputs."""

        layout.set_base_font(font)
        layout.set_palette(palette)
        layout.set_semantic_palette(semantic_palette)
        layout.set_text_width(layout_width)
        layout.set_content_left_inset(content_left_inset)
        if reorder_preview_layout is not None:
            self._sync_auxiliary_layout(
                reorder_preview_layout,
                layout_width=layout_width,
                font=font,
                palette=palette,
                semantic_palette=semantic_palette,
            )
        if reorder_base_drag_layout is not None:
            self._sync_auxiliary_layout(
                reorder_base_drag_layout,
                layout_width=layout_width,
                font=font,
                palette=palette,
                semantic_palette=semantic_palette,
            )
        active_layout = (
            reorder_preview_layout if reorder_preview_layout is not None else layout
        )
        content_size = active_layout.content_size()
        return PromptProjectionLayoutSyncResult(
            layout_width=layout_width,
            active_layout=active_layout,
            content_height=content_size.height(),
            content_width=content_size.width(),
        )

    def build_projection(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
        transient_state: PromptProjectionTransientState | None = None,
    ) -> PromptProjectionDocument:
        """Build a projection document from prepared prompt snapshots."""

        return self._builder.build_projection(
            document_view,
            render_plan,
            display_mode=display_mode,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
            transient_state=transient_state,
        )

    def _sync_auxiliary_layout(
        self,
        layout: PromptProjectionLayout,
        *,
        layout_width: float,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette,
    ) -> None:
        """Synchronize style and width inputs for one preview layout."""

        layout.set_base_font(font)
        layout.set_palette(palette)
        layout.set_semantic_palette(semantic_palette)
        layout.set_text_width(layout_width)


def projection_geometry_signature_matches(
    projection_document: PromptProjectionDocument,
    *,
    current_document: PromptProjectionDocument,
) -> bool:
    """Return whether a projection document preserves current layout geometry."""

    return (
        projection_document.source_text == current_document.source_text
        and projection_document.projection_text == current_document.projection_text
        and projection_document.runs == current_document.runs
        and projection_document.tokens == current_document.tokens
        and projection_document.mapping.source_length
        == current_document.mapping.source_length
        and projection_document.mapping.projection_length
        == current_document.mapping.projection_length
    )


__all__ = [
    "PromptProjectionApplicator",
    "PromptProjectionLayoutSyncResult",
    "PromptProjectionPaintStateApplyResult",
    "PromptProjectionRebuildResult",
    "projection_geometry_signature_matches",
]
