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

"""Cover authoritative reorder drag-proxy visual coordination."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy import (
    PromptReorderDragProxyRenderState,
    PromptReorderDragProxyWidget,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
    PromptReorderVisualStyle,
)
from substitute.presentation.editor.prompt_editor.reorder_drag_proxy_state import (
    PromptReorderDragProxyRenderInputs,
    PromptReorderDragProxyRenderStateBuilder,
    PromptReorderDragProxyRenderStateSync,
)


class _RenderStateOwner:
    """Provide deterministic render-state publication for owner tests."""

    def __init__(self) -> None:
        """Initialize lifecycle observations."""

        self.rebuilt = True
        self.invalidations: list[str] = []
        self.reset_count = 0

    def reset_counters(self) -> None:
        """Reset the deterministic reset observation."""

        self.reset_count = 0

    def reset_drag_session(self) -> None:
        """Record one drag-session reset."""

        self.reset_count += 1

    def invalidate(self, *, reason: str) -> None:
        """Record one explicit invalidation reason."""

        self.invalidations.append(reason)

    def counters(self) -> dict[str, int]:
        """Return deterministic lifecycle counts."""

        return {"reset_count": self.reset_count}

    def ensure_render_state(
        self,
        inputs: PromptReorderDragProxyRenderInputs,
    ) -> PromptReorderDragProxyRenderStateSync:
        """Return a stable prepared proxy state."""

        state = PromptReorderDragProxyRenderState(
            segment_index=inputs.segment_index,
            preferred_size=QSize(52, 24),
            chrome_payload=None,
            fill_color=inputs.fill_color,
            border_color=inputs.border_color,
        )
        sync = PromptReorderDragProxyRenderStateSync(
            render_state=state,
            rebuilt=self.rebuilt,
        )
        self.rebuilt = False
        return sync


def test_drag_proxy_visual_owner_coordinates_render_placement_and_lifecycle() -> None:
    """One owner must publish render state, placement, and widget lifecycle."""

    app = QApplication.instance() or QApplication([])
    _ = app
    host = QWidget()
    host.setGeometry(0, 0, 320, 240)
    viewport = QWidget(host)
    viewport.setGeometry(20, 20, 280, 180)
    render_owner = _RenderStateOwner()
    timings: list[str] = []

    def log_timing(
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Record one timing event without wall-clock assertions."""

        _ = (started_at, context)
        timings.append(event)
        return 0.0

    owner = PromptReorderDragProxyVisualOwner(
        editor_viewport=viewport,
        host=host,
        proxy=PromptReorderDragProxyWidget(object_name="ownerTestProxy"),
        render_state_builder=cast(
            PromptReorderDragProxyRenderStateBuilder, render_owner
        ),
        placement=PromptReorderDragProxyPlacementController(),
        log_timing=log_timing,
    )
    inputs = PromptReorderDragProxyRenderInputs(
        segment_index=3,
        segment_text="alpha",
        fill_color=QColor(10, 20, 30),
        border_color=QColor(40, 50, 60),
        font=QFont(owner.render_font),
        palette=QPalette(owner.render_palette),
        source_revision=7,
    )

    assert owner.widget.parentWidget() is host
    assert owner.ensure_render_state(inputs, gesture_id=1, event_id=2) is True
    assert owner.ensure_render_state(inputs, gesture_id=1, event_id=3) is False
    owner.move(QPoint(140, 120), gesture_id=1, event_id=4)
    assert owner.size == QSize(52, 24)
    assert timings == ["drag_proxy.sync_segment", "drag_proxy.move"]

    owner.refresh_font()
    owner.reset_drag_session()
    assert render_owner.invalidations == ["theme_or_font_change"]
    assert owner.counters()["reset_count"] == 1

    segment = PromptReorderChipView(
        index=3,
        partition_index=0,
        text="alpha",
        serialized_text="alpha",
        display_text="alpha",
        display_source_start=0,
        display_source_end=5,
        selection_start=0,
        selection_end=5,
        separator_text_after="",
        has_separator_after=False,
    )
    other_segment = PromptReorderChipView(
        index=4,
        partition_index=0,
        text="beta",
        serialized_text="beta",
        display_text="beta",
        display_source_start=6,
        display_source_end=10,
        selection_start=6,
        selection_end=10,
        separator_text_after="",
        has_separator_after=False,
    )
    interaction = PromptReorderGestureController().state
    visual_style = PromptReorderVisualStyle.from_current_theme()
    owner.prepare_segment_render_state(
        segment=segment,
        source_revision=7,
        visual_style=visual_style,
        interaction=interaction,
        gesture_id=1,
        event_id=5,
    )
    assert owner.counters()["reset_count"] == 2
    owner.begin_segment_render_state(
        segment=segment,
        source_revision=7,
        visual_style=visual_style,
        interaction=interaction,
        gesture_id=1,
        event_id=6,
    )
    assert owner.counters()["reset_count"] == 2
    owner.begin_segment_render_state(
        segment=other_segment,
        source_revision=7,
        visual_style=visual_style,
        interaction=interaction,
        gesture_id=1,
        event_id=7,
    )
    assert owner.counters()["reset_count"] == 3

    owner.show()
    assert owner.widget.isHidden() is False
    owner.hide()
    assert owner.widget.isHidden() is True
    owner.close()
