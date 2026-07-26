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

"""Build reorder preview projection layouts through bounded incremental reuse."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)

from ..layout.canonical_engine import PromptCanonicalLayoutEngine
from ..layout.configuration import PromptLayoutConfigurationFactory
from ..layout.contracts import (
    PromptLayoutEdit,
    PromptLayoutRequest,
    PromptLayoutStatus,
)
from .applicator import PromptProjectionApplicator
from .source_text_edit import single_source_text_edit
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_preview import PromptReorderProjectionSnapshot
from .session import PromptProjectionSession
from .prepared_frame import PromptProjectionPreparedFrame
from .tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)

_SLOW_REORDER_PROJECTION_LAYOUT_MS = 8.0


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewLayoutIdentity:
    """Identify inputs that must stay stable for incremental layout reuse."""

    source_revision: int
    viewport_width: int
    layout_width_x100: int
    font_key: str
    palette_cache_key: int
    semantic_palette_hash: str


@dataclass(frozen=True, slots=True)
class PromptReorderReusablePreviewLayout:
    """Carry the active projection layout eligible for local target reflow."""

    identity: PromptReorderPreviewLayoutIdentity
    render_plan_hash: str
    document: PromptProjectionDocument
    frame: PromptProjectionPreparedFrame


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewLayoutBuildResult:
    """Carry one built projection plus the layout path used to obtain it."""

    document: PromptProjectionDocument
    frame: PromptProjectionPreparedFrame
    incremental: bool


class PromptReorderPreviewLayoutBuilder:
    """Own full and minimal-window layout construction for reorder previews."""

    def __init__(
        self,
        *,
        projection_applicator: PromptProjectionApplicator,
        thumbnail_cache: PromptLoraThumbnailCache,
    ) -> None:
        """Store projection collaborators shared across one preview lifecycle."""

        self._projection_applicator = projection_applicator
        self._thumbnail_cache = thumbnail_cache
        self._session = PromptProjectionSession()
        self._inline_object_renderers = PromptProjectionInlineObjectRendererRegistry(
            (
                PromptEmphasisPrefixRenderer(),
                PromptEmphasisSuffixRenderer(),
                PromptLoraInlineObjectRenderer(
                    self._thumbnail_cache,
                    suppress_banners=True,
                ),
                PromptWildcardInlineObjectRenderer(),
            )
        )
        self._configuration_factory = PromptLayoutConfigurationFactory(
            self._inline_object_renderers
        )
        self._canonical_engine = PromptCanonicalLayoutEngine(
            self._inline_object_renderers
        )

    def can_reflow_incrementally(
        self,
        reusable: PromptReorderReusablePreviewLayout | None,
        *,
        identity: PromptReorderPreviewLayoutIdentity,
        snapshot: PromptReorderProjectionSnapshot,
    ) -> bool:
        """Return whether one changed preview can reuse the active line snapshot."""

        return bool(
            reusable is not None
            and reusable.identity == identity
            and reusable.document.source_text != snapshot.document_view.source_text
        )

    def can_reuse_exactly(
        self,
        reusable: PromptReorderReusablePreviewLayout | None,
        *,
        identity: PromptReorderPreviewLayoutIdentity,
        render_plan_hash: str,
        snapshot: PromptReorderProjectionSnapshot,
    ) -> bool:
        """Return whether two snapshot inputs share one immutable layout."""

        return bool(
            reusable is not None
            and reusable.identity == identity
            and reusable.render_plan_hash == render_plan_hash
            and reusable.document.source_text == snapshot.document_view.source_text
        )

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
    ) -> PromptReorderPreviewLayoutBuildResult:
        """Build a preview layout, reflowing only the changed target window when safe."""

        total_started_at = reorder_drag_started_at()
        phase_started_at = reorder_drag_started_at()
        projection_document = self._projection_applicator.build_projection(
            snapshot.document_view,
            snapshot.render_plan,
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            session=self._session,
            active_span_range=None,
            decoration_accent_ranges=(),
            scene_error_keys=frozenset(),
        )
        build_projection_elapsed_ms = log_reorder_drag_timing(
            "surface.build_reorder_projection_snapshot.build_projection",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            text_length=len(snapshot.document_view.source_text),
            segment_count=len(snapshot.document_view.segments),
            syntax_span_count=len(snapshot.render_plan.syntax_spans),
            run_count=len(projection_document.runs),
            token_count=len(projection_document.tokens),
            layout_width=f"{layout_width:.2f}",
        )
        phase_started_at = reorder_drag_started_at()
        incremental = self.can_reflow_incrementally(
            reusable,
            identity=identity,
            snapshot=snapshot,
        )
        if incremental:
            assert reusable is not None
            edit = single_source_text_edit(
                reusable.document.source_text,
                projection_document.source_text,
            )
            assert edit is not None
            previous_output = replace(
                reusable.frame.output,
                configuration=replace(
                    reusable.frame.output.configuration,
                    inline_object_renderers=self._inline_object_renderers,
                ),
            )
            projection_frame = reusable.frame.fork(previous_output)
            outcome = self._canonical_engine.reflow(
                PromptLayoutRequest(
                    previous=previous_output,
                    projection_document=projection_document,
                    prompt_document_view=snapshot.document_view,
                    configuration=previous_output.configuration,
                    edit=PromptLayoutEdit(
                        start=edit.start,
                        end=edit.end,
                        replacement_text=edit.replacement_text,
                        first_dirty_projection_position=0,
                    ),
                )
            )
            if (
                outcome.status is not PromptLayoutStatus.APPLIED
                or outcome.output is None
                or outcome.damage is None
            ):
                raise AssertionError(
                    f"canonical reorder reflow rejected: {outcome.reason.value}"
                )
            layout_damage = projection_frame.publish(
                outcome,
                reset_paint_state=True,
            )
            reflowed_line_count = layout_damage.reflowed_line_count
        else:
            configuration = self._configuration_factory.create(
                base_font=font,
                text_width=layout_width,
            )
            outcome = self._canonical_engine.build(
                PromptLayoutRequest(
                    previous=None,
                    projection_document=projection_document,
                    prompt_document_view=snapshot.document_view,
                    configuration=configuration,
                )
            )
            if (
                outcome.status is not PromptLayoutStatus.APPLIED
                or outcome.output is None
            ):
                raise AssertionError(
                    f"canonical reorder layout rejected: {outcome.reason.value}"
                )
            projection_frame = PromptProjectionPreparedFrame(
                outcome.output,
                palette=palette,
                semantic_palette=semantic_palette,
            )
            reflowed_line_count = projection_frame.output.snapshot.line_count()
        layout_snapshot = projection_frame.output.snapshot
        layout_elapsed_ms = log_reorder_drag_timing(
            "surface.build_reorder_projection_snapshot.layout",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            incremental=incremental,
            reflowed_line_count=reflowed_line_count,
            text_length=len(snapshot.document_view.source_text),
            segment_count=len(snapshot.document_view.segments),
            run_count=len(projection_document.runs),
            token_count=len(projection_document.tokens),
            visual_line_count=layout_snapshot.line_count(),
            text_fragment_count=layout_snapshot.text_fragment_count(),
            inline_object_count=layout_snapshot.inline_object_fragment_count(),
            chip_count=len(snapshot.chip_rendered_ranges_by_index),
            layout_width=f"{layout_width:.2f}",
            content_width=f"{layout_snapshot.content_size.width():.2f}",
            content_height=f"{layout_snapshot.content_size.height():.2f}",
        )
        self._log_slow_layout(
            snapshot,
            frame=projection_frame,
            layout_width=layout_width,
            elapsed_ms=layout_elapsed_ms,
            incremental=incremental,
            reflowed_line_count=reflowed_line_count,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
        )
        log_reorder_drag_timing(
            "surface.build_reorder_projection_snapshot.total",
            started_at=total_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            incremental=incremental,
            reflowed_line_count=reflowed_line_count,
            text_length=len(snapshot.document_view.source_text),
            segment_count=len(snapshot.document_view.segments),
            rendered_range_count=len(snapshot.chip_rendered_ranges_by_index),
            gap_range_count=len(snapshot.gap_ranges_by_index),
            layout_width=f"{layout_width:.2f}",
            build_projection_elapsed_ms=f"{build_projection_elapsed_ms:.3f}",
            layout_elapsed_ms=f"{layout_elapsed_ms:.3f}",
        )
        return PromptReorderPreviewLayoutBuildResult(
            document=projection_document,
            frame=projection_frame,
            incremental=incremental,
        )

    @staticmethod
    def _log_slow_layout(
        snapshot: PromptReorderProjectionSnapshot,
        *,
        frame: PromptProjectionPreparedFrame,
        layout_width: float,
        elapsed_ms: float,
        incremental: bool,
        reflowed_line_count: int,
        gesture_id: int | None,
        event_id: int | None,
        reason: str,
    ) -> None:
        """Record actionable context when one preview layout misses its budget."""

        if elapsed_ms < _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            return
        layout_snapshot = frame.output.snapshot
        context = {
            "gesture_id": gesture_id,
            "event_id": event_id,
            "reason": reason,
            "elapsed_ms": f"{elapsed_ms:.3f}",
            "threshold_ms": f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
            "incremental": incremental,
            "reflowed_line_count": reflowed_line_count,
            "text_length": len(snapshot.document_view.source_text),
            "segment_count": len(snapshot.document_view.segments),
            "visual_line_count": layout_snapshot.line_count(),
            "text_fragment_count": layout_snapshot.text_fragment_count(),
            "inline_object_count": layout_snapshot.inline_object_fragment_count(),
            "chip_count": len(snapshot.chip_rendered_ranges_by_index),
            "layout_width": f"{layout_width:.2f}",
        }
        log_reorder_drag_event("slow.projection_layout", **context)
        log_reorder_drag_event("budget.projection_layout_exceeded", **context)


__all__ = [
    "PromptReorderPreviewLayoutBuildResult",
    "PromptReorderPreviewLayoutBuilder",
    "PromptReorderPreviewLayoutIdentity",
    "PromptReorderReusablePreviewLayout",
]
