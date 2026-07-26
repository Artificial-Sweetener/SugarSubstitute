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

"""Own floating reorder drag-proxy state, placement, and widget publication."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import PromptReorderChipView

from ..geometry.widget_mapping import map_rect_to_host
from ..projection.observability import reorder_drag_started_at
from ..reorder_drag_proxy_state import (
    PromptReorderDragProxyRenderInputs,
    PromptReorderDragProxyRenderStateBuilder,
)
from .reorder_drag_proxy import PromptReorderDragProxyWidget
from .reorder_event_ports import PromptReorderTimingLogger
from .reorder_gesture_controller import (
    PromptReorderDragProxyPlacementContext,
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureStateView,
)
from .reorder_interaction_visual import prompt_reorder_chip_interaction_state
from .reorder_visual_style import PromptReorderVisualStyle


@dataclass(slots=True)
class PromptReorderDragProxyVisualOwner:
    """Coordinate cached proxy rendering, host placement, and widget lifecycle."""

    editor_viewport: QWidget
    host: QWidget
    proxy: PromptReorderDragProxyWidget
    render_state_builder: PromptReorderDragProxyRenderStateBuilder
    placement: PromptReorderDragProxyPlacementController
    log_timing: PromptReorderTimingLogger
    _prepared_segment_index: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Attach and initialize the floating widget under its visual host."""

        self.proxy.setParent(self.host)
        self.proxy.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.proxy.setFont(self.editor_viewport.font())
        self.proxy.hide()

    @property
    def widget(self) -> QWidget:
        """Return the concrete proxy through the public overlay host boundary."""

        return self.proxy

    @property
    def size(self) -> QSize:
        """Return the current proxy size for held-shadow capture."""

        return self.proxy.size()

    @property
    def size_hint(self) -> QSize:
        """Return the prepared proxy size hint for held-shadow fallback."""

        return self.proxy.sizeHint()

    @property
    def render_font(self) -> QFont:
        """Return the font identity used to key prepared proxy rendering."""

        return self.proxy.font()

    @property
    def render_palette(self) -> QPalette:
        """Return the palette identity used to key prepared proxy rendering."""

        return self.proxy.palette()

    def counters(self) -> dict[str, int]:
        """Return deterministic render-state lifecycle counters."""

        return self.render_state_builder.counters()

    def reset_counters(self) -> None:
        """Reset deterministic render-state counters."""

        self.render_state_builder.reset_counters()

    def reset_drag_session(self) -> None:
        """Clear render state tied to the previous drag session."""

        self._prepared_segment_index = None
        self.render_state_builder.reset_drag_session()

    def invalidate(self, *, reason: str) -> None:
        """Invalidate render state for one explicit visual dependency change."""

        self.render_state_builder.invalidate(reason=reason)

    def refresh_font(self) -> None:
        """Publish the editor viewport font and invalidate dependent render state."""

        self.proxy.setFont(self.editor_viewport.font())
        self.invalidate(reason="theme_or_font_change")

    def ensure_render_state(
        self,
        inputs: PromptReorderDragProxyRenderInputs,
        *,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Publish rebuilt proxy render state and report whether it changed."""

        started_at = reorder_drag_started_at()
        sync = self.render_state_builder.ensure_render_state(inputs)
        if not sync.rebuilt:
            return False
        self.proxy.set_render_state(sync.render_state)
        self.log_timing(
            "drag_proxy.sync_segment",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=inputs.segment_index,
            segment_text_length=len(inputs.segment_text),
            proxy_width=self.proxy.width(),
            proxy_height=self.proxy.height(),
        )
        return True

    def ensure_segment_render_state(
        self,
        *,
        segment: PromptReorderChipView,
        source_revision: int | None,
        visual_style: PromptReorderVisualStyle,
        interaction: PromptReorderGestureStateView,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Publish proxy state derived from one semantic segment and gesture state."""

        chip_state = prompt_reorder_chip_interaction_state(
            segment.index,
            visual_style=visual_style,
            dragged_segment_index=segment.index,
            hovered_segment_index=interaction.hovered_segment_index,
            active_segment_index=interaction.active_segment_index,
            pressed_segment_index=interaction.pressed_segment_index,
        )
        return self.ensure_render_state(
            PromptReorderDragProxyRenderInputs(
                segment_index=segment.index,
                segment_text=segment.serialized_text,
                source_revision=source_revision,
                fill_color=chip_state.style.fill_color,
                border_color=chip_state.style.border_color,
                font=self.render_font,
                palette=self.render_palette,
            ),
            gesture_id=gesture_id,
            event_id=event_id,
        )

    def prepare_segment_render_state(
        self,
        *,
        segment: PromptReorderChipView,
        source_revision: int | None,
        visual_style: PromptReorderVisualStyle,
        interaction: PromptReorderGestureStateView,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Prepare one pressed segment before pointer threshold crossing."""

        self.reset_drag_session()
        rebuilt = self.ensure_segment_render_state(
            segment=segment,
            source_revision=source_revision,
            visual_style=visual_style,
            interaction=interaction,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        self._prepared_segment_index = segment.index
        return rebuilt

    def begin_segment_render_state(
        self,
        *,
        segment: PromptReorderChipView,
        source_revision: int | None,
        visual_style: PromptReorderVisualStyle,
        interaction: PromptReorderGestureStateView,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Adopt prepared render state or reset stale press preparation."""

        if self._prepared_segment_index != segment.index:
            self.reset_drag_session()
        self._prepared_segment_index = None
        return self.ensure_segment_render_state(
            segment=segment,
            source_revision=source_revision,
            visual_style=visual_style,
            interaction=interaction,
            gesture_id=gesture_id,
            event_id=event_id,
        )

    def move(
        self,
        global_position: QPoint,
        *,
        gesture_id: int | None,
        event_id: int | None,
        log_timing: bool = True,
    ) -> float:
        """Move the proxy near the pointer and return elapsed milliseconds."""

        started_at = reorder_drag_started_at()
        proxy_size = self.proxy.size()
        if proxy_size.isEmpty():
            proxy_size = self.proxy.sizeHint()
        placement_context = PromptReorderDragProxyPlacementContext(
            pointer_global_position=global_position,
            pointer_host_position=self.host.mapFromGlobal(global_position),
            proxy_size=proxy_size,
            editor_rect_in_host=map_rect_to_host(
                self.editor_viewport,
                self.editor_viewport.rect(),
                self.host,
            ),
            host_rect=self.host.rect(),
        )
        proxy_rect = self.placement.proxy_rect_for_pointer(placement_context)
        self.proxy.setGeometry(proxy_rect)
        self.proxy.raise_()
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if not log_timing:
            return elapsed_ms
        return self.log_timing(
            "drag_proxy.move",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            proxy_width=proxy_rect.width(),
            proxy_height=proxy_rect.height(),
            proxy_left=proxy_rect.left(),
            proxy_top=proxy_rect.top(),
        )

    def sync_position_if_needed(
        self,
        global_position: QPoint | None,
        *,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Move for current pointer state and report whether geometry changed."""

        if global_position is None:
            return False
        previous_geometry = QRect(self.proxy.geometry())
        self.move(
            global_position,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return previous_geometry != self.proxy.geometry()

    def show(self) -> None:
        """Show the prepared proxy without changing render state."""

        self.proxy.show()

    def raise_proxy(self) -> None:
        """Keep the floating proxy above overlay chrome."""

        self.proxy.raise_()

    def hide(self) -> None:
        """Hide the proxy without destroying reusable widget resources."""

        self.proxy.hide()

    def close(self) -> None:
        """Hide and schedule deletion of the owned proxy widget."""

        self.proxy.hide()
        self.proxy.deleteLater()


__all__ = [
    "PromptReorderDragProxyVisualOwner",
]
