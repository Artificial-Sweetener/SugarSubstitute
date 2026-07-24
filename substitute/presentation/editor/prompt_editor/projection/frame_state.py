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

"""Publish projection frame lineage and resolve layout width."""

from __future__ import annotations

from typing import TypeAlias

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorState,
    PromptViewportKey,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)

from .applicator import PromptProjectionApplicator
from .freshness_controller import (
    MINIMUM_VALID_PROJECTION_LAYOUT_WIDTH,
    PromptProjectionFreshnessController,
)
from .layout_engine import PromptProjectionLayout
from .model import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionTransientState,
)
from .paint_state import PromptProjectionPaintState
from .session import PromptProjectionSession
from .snapshot import PromptProjectionLayoutSnapshot

PromptProjectionEditorState: TypeAlias = PromptEditorState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
    PromptProjectionLayoutSnapshot,
    PromptProjectionPaintState,
]


def build_initial_prompt_projection_state(
    *,
    source: PromptSourceSnapshot,
    applicator: PromptProjectionApplicator,
    document_semantics: PromptDocumentSemantics | None,
    display_mode: PromptProjectionDisplayMode,
    session: PromptProjectionSession,
    scene_error_keys: frozenset[str],
) -> PromptProjectionEditorState:
    """Build the empty semantic and projection lineage for a new surface."""

    document_view = PromptDocumentView(
        source_text="",
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(0),
        has_trailing_comma=False,
    )
    render_plan = PromptSyntaxRenderPlan(
        syntax_spans=(),
        renderer_views=(),
        document_semantics_identity=(
            document_semantics.identity
            if document_semantics is not None
            else "ordinary-prompt-v1"
        ),
    )
    projection_document = applicator.build_projection(
        document_view,
        render_plan,
        display_mode=display_mode,
        session=session,
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=scene_error_keys,
        transient_state=PromptProjectionTransientState(),
    )
    return PromptProjectionEditorState(
        source=source,
        semantic_document=document_view,
        render_plan=render_plan,
        projection_document=projection_document,
    )


class PromptProjectionFrameStatePublisher:
    """Publish layout, viewport, and paint lineage from prepared frame values."""

    def __init__(self, state: PromptProjectionEditorState) -> None:
        """Store the authoritative revisioned editor state."""

        self._state = state

    def publish_layout(
        self,
        layout: PromptProjectionLayout,
    ) -> PromptLayoutIdentity | None:
        """Publish active frame geometry and return its exact identity."""

        projection = self._state.publish_frame_projection(layout.projection_document)
        current = self._state.layout
        if (
            current is not None
            and current.geometry is layout.snapshot
            and current.identity.projection is projection.identity
        ):
            return current.identity
        return self._state.publish_layout(
            layout.snapshot,
            projection=projection.identity,
            width_key=layout.width_key,
        ).identity

    def current_layout_identity(
        self,
        layout: PromptProjectionLayout,
    ) -> PromptLayoutIdentity | None:
        """Return current active-layout identity without publishing state."""

        snapshot = self._state.layout
        if (
            snapshot is None
            or snapshot.geometry is not layout.snapshot
            or snapshot.identity.projection is not self._state.frame_projection.identity
            or layout.projection_document is not self._state.frame_projection.document
        ):
            return None
        return snapshot.identity

    def publish_viewport(
        self,
        *,
        width: int,
        height: int,
        horizontal_scroll: int,
        vertical_scroll: int,
        device_pixel_ratio: float,
    ) -> None:
        """Publish prepared viewport geometry outside the paint path."""

        resolved_width = max(0, width)
        resolved_height = max(0, height)
        resolved_device_pixel_ratio = max(1.0, device_pixel_ratio)
        current = self._state.viewport
        if current is not None and current.key.matches(
            width=resolved_width,
            height=resolved_height,
            horizontal_scroll=horizontal_scroll,
            vertical_scroll=vertical_scroll,
            device_pixel_ratio=resolved_device_pixel_ratio,
        ):
            return
        self._state.publish_viewport(
            PromptViewportKey(
                width=resolved_width,
                height=resolved_height,
                horizontal_scroll=horizontal_scroll,
                vertical_scroll=vertical_scroll,
                device_pixel_ratio=resolved_device_pixel_ratio,
            )
        )

    def publish_widget_viewport(
        self,
        viewport: QWidget,
        *,
        horizontal_scroll: int,
        vertical_scroll: int,
    ) -> None:
        """Publish viewport state directly from prepared Qt geometry."""

        self.publish_viewport(
            width=viewport.width(),
            height=viewport.height(),
            horizontal_scroll=horizontal_scroll,
            vertical_scroll=vertical_scroll,
            device_pixel_ratio=float(viewport.devicePixelRatioF()),
        )

    def publish_prepared_paint(self, layout: PromptProjectionLayout) -> None:
        """Publish paint state when canonical layout and viewport are ready."""

        layout_snapshot = self._state.layout
        viewport_snapshot = self._state.viewport
        if (
            layout_snapshot is None
            or viewport_snapshot is None
            or layout_snapshot.geometry is not layout.snapshot
            or layout_snapshot.identity.projection
            is not self._state.frame_projection.identity
            or layout.projection_document is not self._state.frame_projection.document
        ):
            return
        self._state.publish_paint(
            layout.paint_state,
            layout=layout_snapshot.identity,
            viewport=viewport_snapshot.identity,
        )


class PromptProjectionLayoutWidthResolver:
    """Resolve stable projection width from viewport and parent geometry."""

    def __init__(
        self,
        *,
        host: QWidget,
        viewport: QWidget,
        freshness: PromptProjectionFreshnessController,
    ) -> None:
        """Store the Qt geometry sources and passive freshness policy."""

        self._host = host
        self._viewport = viewport
        self._freshness = freshness

    def resolve(self) -> float:
        """Return a non-pathological width for projection layout."""

        return self._freshness.layout_width_for_projection_rebuild(
            viewport_width=self._viewport.width(),
            parent_width=self._first_valid_parent_width(),
        )

    def _first_valid_parent_width(self) -> int | None:
        """Return the first usable parent width without retaining parent state."""

        parent = self._host.parentWidget()
        while parent is not None:
            width = parent.width()
            if width >= MINIMUM_VALID_PROJECTION_LAYOUT_WIDTH:
                return width
            parent = parent.parentWidget()
        return None


__all__ = [
    "PromptProjectionEditorState",
    "PromptProjectionFrameStatePublisher",
    "PromptProjectionLayoutWidthResolver",
    "build_initial_prompt_projection_state",
]
