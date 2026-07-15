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

"""Prepare projection-backed render state for the reorder drag proxy overlay."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QFont, QPalette

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxProfile,
    PromptSyntaxService,
)

from .overlays.chip_visuals import PromptChipVisualBuilder
from .overlays.reorder_drag_proxy import PromptReorderDragProxyRenderState
from .projection.builder import PromptProjectionBuilder
from .projection.layout_engine import PromptProjectionLayout
from .projection.model import PromptProjectionDisplayMode, PromptProjectionDocument
from .projection.observability import (
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .projection.session import PromptProjectionSession
from .projection.tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)


@dataclass(frozen=True, slots=True)
class PromptReorderDragProxyTextPaintPayload:
    """Carry prepared projection text state for the floating reorder proxy."""

    projection_document: PromptProjectionDocument
    layout: PromptProjectionLayout

    @property
    def source_text(self) -> str:
        """Return the serialized source text represented by this payload."""

        return self.projection_document.source_text


@dataclass(frozen=True, slots=True)
class PromptReorderDragProxyRenderInputs:
    """Identify the inputs that affect the floating proxy render state."""

    segment_index: int
    segment_text: str
    fill_color: QColor
    border_color: QColor
    font: QFont
    palette: QPalette
    source_revision: int | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderDragProxyRenderStateSync:
    """Report whether the requested proxy state was rebuilt or reused."""

    render_state: PromptReorderDragProxyRenderState
    rebuilt: bool


@dataclass(frozen=True, slots=True)
class _PromptReorderDragProxyRenderKey:
    """Store the render-affecting identity for one cached proxy state."""

    segment_index: int
    segment_text: str
    source_revision: int | None
    fill_rgba: int
    border_rgba: int
    font_key: str
    palette_key: int
    syntax_profile_key: tuple[str, ...]


class PromptReorderDragProxyRenderStateBuilder:
    """Own drag-proxy render-state construction and explicit invalidation."""

    def __init__(
        self,
        *,
        document_service: PromptDocumentService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> None:
        """Initialize projection services used to prepare floating proxy state."""

        self._document_service = document_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._projection_builder = PromptProjectionBuilder()
        self._projection_session = PromptProjectionSession()
        self._visual_builder = PromptChipVisualBuilder()
        self._cached_key: _PromptReorderDragProxyRenderKey | None = None
        self._cached_render_state: PromptReorderDragProxyRenderState | None = None
        self._invalidated = True
        self._render_state_rebuild_count = 0
        self._render_state_reuse_count = 0
        self._render_state_invalidation_count = 0

    def reset_counters(self) -> None:
        """Reset per-gesture drag proxy render-state counters."""

        self._render_state_rebuild_count = 0
        self._render_state_reuse_count = 0
        self._render_state_invalidation_count = 0

    def reset_drag_session(self) -> None:
        """Start a fresh drag gesture that must build its first proxy state."""

        self.reset_counters()
        self._cached_key = None
        self._cached_render_state = None
        self._invalidated = True

    def invalidate(self, *, reason: str) -> None:
        """Require the next visible proxy use to rebuild render state."""

        _ = reason
        self._invalidated = True
        self._render_state_invalidation_count += 1

    def counters(self) -> dict[str, int]:
        """Return test-facing drag proxy render-state counters."""

        return {
            "drag_proxy_render_state_rebuild_count": (self._render_state_rebuild_count),
            "drag_proxy_render_state_reuse_count": self._render_state_reuse_count,
            "drag_proxy_render_state_invalidation_count": (
                self._render_state_invalidation_count
            ),
        }

    def ensure_render_state(
        self,
        inputs: PromptReorderDragProxyRenderInputs,
    ) -> PromptReorderDragProxyRenderStateSync:
        """Return cached proxy state unless render inputs were invalidated."""

        key = self._render_key(inputs)
        if (
            not self._invalidated
            and self._cached_key == key
            and self._cached_render_state is not None
        ):
            self._render_state_reuse_count += 1
            return PromptReorderDragProxyRenderStateSync(
                render_state=self._cached_render_state,
                rebuilt=False,
            )

        render_state = self.build_render_state(
            segment_index=inputs.segment_index,
            segment_text=inputs.segment_text,
            fill_color=inputs.fill_color,
            border_color=inputs.border_color,
            font=inputs.font,
            palette=inputs.palette,
        )
        self._cached_key = key
        self._cached_render_state = render_state
        self._invalidated = False
        return PromptReorderDragProxyRenderStateSync(
            render_state=render_state,
            rebuilt=True,
        )

    def build_render_state(
        self,
        *,
        segment_index: int,
        segment_text: str,
        fill_color: QColor,
        border_color: QColor,
        font: QFont,
        palette: QPalette,
    ) -> PromptReorderDragProxyRenderState:
        """Return prepared chrome and projection text state for one segment."""

        self._render_state_rebuild_count += 1
        total_started_at = reorder_drag_started_at()
        phase_started_at = reorder_drag_started_at()
        preview_document_view = self._document_service.build_document_view(segment_text)
        document_elapsed_ms = log_reorder_drag_timing(
            "drag_proxy_render_state.document_view",
            started_at=phase_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
            segment_count=len(preview_document_view.segments),
        )
        phase_started_at = reorder_drag_started_at()
        preview_render_plan = self._syntax_service.build_render_plan(
            preview_document_view,
            self._syntax_profile,
        )
        render_plan_elapsed_ms = log_reorder_drag_timing(
            "drag_proxy_render_state.render_plan",
            started_at=phase_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
            syntax_span_count=len(preview_render_plan.syntax_spans),
            renderer_view_count=len(preview_render_plan.renderer_views),
        )
        phase_started_at = reorder_drag_started_at()
        projection_document = self._projection_builder.build_projection(
            preview_document_view,
            preview_render_plan,
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            session=self._projection_session,
        )
        projection_elapsed_ms = log_reorder_drag_timing(
            "drag_proxy_render_state.projection",
            started_at=phase_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
        )
        phase_started_at = reorder_drag_started_at()
        layout = self._build_layout(font=font, palette=palette)
        layout.set_projection(
            projection_document,
            prompt_document_view=preview_document_view,
        )
        layout.set_text_width(10_000.0)
        content_size = layout.content_size()
        layout_elapsed_ms = log_reorder_drag_timing(
            "drag_proxy_render_state.layout",
            started_at=phase_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
            content_width=f"{content_size.width():.2f}",
            content_height=f"{content_size.height():.2f}",
        )
        phase_started_at = reorder_drag_started_at()
        fragments = layout.source_range_fragments(
            start=0,
            end=len(segment_text),
            viewport_rect=QRectF(
                0.0,
                0.0,
                max(1.0, content_size.width()),
                max(1.0, content_size.height()),
            ),
            scroll_offset=0.0,
        )
        fragments_elapsed_ms = log_reorder_drag_timing(
            "drag_proxy_render_state.fragments",
            started_at=phase_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
            fragment_count=len(fragments),
        )
        phase_started_at = reorder_drag_started_at()
        visual = (
            self._visual_builder.build_proxy_visual(fragments=fragments)
            if fragments
            else None
        )
        visual_elapsed_ms = log_reorder_drag_timing(
            "drag_proxy_render_state.visual",
            started_at=phase_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
            fragment_count=len(fragments),
            bubble_count=0 if visual is None else len(visual.bubble_rects),
            split_proxy_bubble=False
            if visual is None
            else len(visual.bubble_rects) > 1,
        )
        preferred_size = (
            QSize(
                max(1, int(round(content_size.width()))),
                max(1, int(round(content_size.height()))),
            )
            if visual is None or visual.preferred_size is None
            else visual.preferred_size
        )
        log_reorder_drag_timing(
            "drag_proxy_render_state.total",
            started_at=total_started_at,
            segment_index=segment_index,
            text_length=len(segment_text),
            width=preferred_size.width(),
            height=preferred_size.height(),
            fragment_count=len(fragments),
            bubble_count=0 if visual is None else len(visual.bubble_rects),
            document_elapsed_ms=f"{document_elapsed_ms:.3f}",
            render_plan_elapsed_ms=f"{render_plan_elapsed_ms:.3f}",
            projection_elapsed_ms=f"{projection_elapsed_ms:.3f}",
            layout_elapsed_ms=f"{layout_elapsed_ms:.3f}",
            fragments_elapsed_ms=f"{fragments_elapsed_ms:.3f}",
            visual_elapsed_ms=f"{visual_elapsed_ms:.3f}",
        )
        return PromptReorderDragProxyRenderState(
            segment_index=segment_index,
            preferred_size=preferred_size,
            chrome_payload=visual,
            text_paint_payload=PromptReorderDragProxyTextPaintPayload(
                projection_document=projection_document,
                layout=layout,
            ),
            fill_color=QColor(fill_color),
            border_color=QColor(border_color),
        )

    @staticmethod
    def _build_layout(*, font: QFont, palette: QPalette) -> PromptProjectionLayout:
        """Return a projection layout configured for floating proxy rendering."""

        layout = PromptProjectionLayout(
            PromptProjectionInlineObjectRendererRegistry(
                (
                    PromptEmphasisPrefixRenderer(),
                    PromptEmphasisSuffixRenderer(),
                    PromptLoraInlineObjectRenderer(suppress_banners=True),
                    PromptWildcardInlineObjectRenderer(),
                )
            )
        )
        layout.set_base_font(font)
        layout.set_palette(palette)
        return layout

    def _render_key(
        self,
        inputs: PromptReorderDragProxyRenderInputs,
    ) -> _PromptReorderDragProxyRenderKey:
        """Return a stable identity for all proxy render-affecting inputs."""

        return _PromptReorderDragProxyRenderKey(
            segment_index=inputs.segment_index,
            segment_text=inputs.segment_text,
            source_revision=inputs.source_revision,
            fill_rgba=inputs.fill_color.rgba(),
            border_rgba=inputs.border_color.rgba(),
            font_key=inputs.font.toString(),
            palette_key=inputs.palette.cacheKey(),
            syntax_profile_key=self._syntax_profile.enabled_syntaxes,
        )


__all__ = [
    "PromptReorderDragProxyRenderInputs",
    "PromptReorderDragProxyRenderStateBuilder",
    "PromptReorderDragProxyRenderStateSync",
    "PromptReorderDragProxyTextPaintPayload",
]
