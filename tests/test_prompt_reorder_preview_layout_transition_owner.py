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

"""Cover gesture-driven reorder preview-layout publication."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_viewport_geometry import (
    PromptReorderViewportGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _Geometry:
    """Publish replaceable state and capture layout updates."""

    def __init__(self, *, available: bool) -> None:
        """Initialize optional document availability."""

        self.state = PromptReorderInteractionGeometryState(
            document_view=(cast(PromptDocumentView, object()) if available else None)
        )
        self.updates: list[dict[str, object]] = []

    def update_preview_layout(self, **facts: object) -> None:
        """Capture one complete update request."""

        self.updates.append(facts)


class _Viewport:
    """Count bounded viewport queries."""

    def __init__(self) -> None:
        """Initialize query counting."""

        self.call_count = 0
        self.key = object()

    def position_geometry_key(self) -> object:
        """Return one stable identity."""

        self.call_count += 1
        return self.key


class _DragProxy:
    """Count stacking updates."""

    def __init__(self) -> None:
        """Initialize raise counting."""

        self.raise_count = 0

    def raise_proxy(self) -> None:
        """Record one stacking update."""

        self.raise_count += 1


def test_preview_layout_transition_stops_before_viewport_without_document() -> None:
    """Missing document state must suppress every follow-up operation."""

    owner, geometry, viewport, proxy = _owner(available=False)

    assert owner.update() is False
    assert geometry.updates == []
    assert viewport.call_count == 0
    assert proxy.raise_count == 0


def test_preview_layout_transition_publishes_once_and_restacks_proxy() -> None:
    """Available state must issue one coherent geometry update."""

    owner, geometry, viewport, proxy = _owner(available=True)

    assert owner.update() is True
    assert len(geometry.updates) == 1
    assert geometry.updates[0]["viewport_identity"] is viewport.key
    assert viewport.call_count == 1
    assert proxy.raise_count == 1


def _owner(
    *,
    available: bool,
) -> tuple[
    PromptReorderPreviewLayoutTransitionOwner,
    _Geometry,
    _Viewport,
    _DragProxy,
]:
    """Return one owner and observable collaborators."""

    geometry = _Geometry(available=available)
    viewport = _Viewport()
    proxy = _DragProxy()
    owner = PromptReorderPreviewLayoutTransitionOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=PromptReorderGestureController(),
        viewport=cast(PromptReorderViewportGeometryOwner, viewport),
        drag_proxy=cast(PromptReorderDragProxyVisualOwner, proxy),
        metrics=PromptReorderInteractionMetricsOwner(),
    )
    return owner, geometry, viewport, proxy
