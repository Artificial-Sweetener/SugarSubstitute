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

"""Own queued editor cube-reveal requests and navigation settlement."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, cast

from PySide6.QtCore import QObject, QTimer
from shiboken6 import isValid

from substitute.presentation.motion import (
    INPUT_SCROLL_DURATION_MS,
    SCROLL_DURATION_MS,
)
from substitute.shared.logging.logger import get_logger, log_debug

from .cube_reveal_geometry import CubeRevealGeometryHost, CubeRevealGeometryResolver
from .cube_reveal_scroll_driver import CubeRevealScrollDriver
from .visible_cube_synchronizer import VisibleCubeSynchronizer, VisibleCubeSyncHost

_LOGGER = get_logger(__name__)
DEFAULT_REVEAL_LAYOUT_ATTEMPT_LIMIT = 12


class SignalEmitterProtocol(Protocol):
    """Describe a Qt-like signal that emits one route key."""

    def emit(self, route_key: str) -> None:
        """Emit one visible cube route key."""


class ScrollBarProtocol(Protocol):
    """Describe scrollbar APIs used by reveal animation."""

    def value(self) -> int:
        """Return the current scrollbar value."""

    def setValue(self, value: int) -> None:  # noqa: N802
        """Set the current scrollbar value."""

    def maximum(self) -> int:
        """Return the maximum scrollbar value."""


class PointProtocol(Protocol):
    """Describe point-like objects returned by Qt geometry calls."""

    def y(self) -> int:
        """Return the vertical coordinate."""


class RectProtocol(Protocol):
    """Describe rectangle APIs used to center input widgets."""

    def center(self) -> object:
        """Return the rectangle center point."""


class ViewportProtocol(Protocol):
    """Describe viewport APIs consumed by reveal geometry."""

    def height(self) -> int:
        """Return viewport height."""


class RevealedWidgetProtocol(Protocol):
    """Describe widget geometry needed by cube reveal ownership."""

    def height(self) -> int:
        """Return widget height."""

    def mapTo(self, parent: object, point: object) -> PointProtocol:  # noqa: N802
        """Map one point into the supplied parent coordinate space."""


class InputWidgetProtocol(RevealedWidgetProtocol, Protocol):
    """Describe input widget geometry needed for search-result navigation."""

    def rect(self) -> RectProtocol:
        """Return the widget rectangle."""


class RevealScrollSurfaceProtocol(Protocol):
    """Describe scroll-surface APIs used by cube reveal ownership."""

    def widget(self) -> object | None:
        """Return the scroll content widget."""

    def viewport(self) -> ViewportProtocol:
        """Return the scroll viewport."""

    def verticalScrollBar(self) -> ScrollBarProtocol:  # noqa: N802
        """Return the vertical scrollbar."""

    def visible_content_top(self) -> int:
        """Return the visible content top coordinate."""

    def visible_content_bottom(self) -> int:
        """Return the visible content bottom coordinate."""

    def content_y_to_scroll_value(self, content_y: int) -> int:
        """Convert content-space y to a clamped scroll value."""


class EditorPanelCubeRevealHost(Protocol):
    """Describe panel state and signals required by cube reveal ownership."""

    scroll: RevealScrollSurfaceProtocol
    cube_sections: Mapping[str, object]
    _stack_order: Sequence[str] | None
    currentCubeVisibleChanged: SignalEmitterProtocol


class EditorPanelCubeRevealController:
    """Coordinate reveal request state across focused navigation collaborators."""

    def __init__(
        self,
        host: EditorPanelCubeRevealHost,
        *,
        layout_attempt_limit: int = DEFAULT_REVEAL_LAYOUT_ATTEMPT_LIMIT,
    ) -> None:
        """Store the host view and initialize reveal state."""

        self._host = host
        self.geometry = CubeRevealGeometryResolver(cast(CubeRevealGeometryHost, host))
        self.scroll_driver = CubeRevealScrollDriver(
            cast(QObject, host),
            lambda: self.on_scroll_updated(
                self._host.scroll.verticalScrollBar().value()
            ),
        )
        self.visible_sync = VisibleCubeSynchronizer(
            cast(VisibleCubeSyncHost, host),
            self.geometry,
        )
        self._layout_attempt_limit = layout_attempt_limit
        self._pending_reveal_route_key: str | None = None
        self._pending_reveal_attempts = 0
        self._pending_reveal_force_navigation = False
        self._pending_reveal_geometry_signature: tuple[int, ...] | None = None
        self._programmatic_navigation_route_key: str | None = None

    def is_user_scroll_interruption(self, watched: QObject, event_type: object) -> bool:
        """Return whether one viewport event should cancel automated reveal."""

        scroll = getattr(self._host, "scroll", None)
        if scroll is None:
            return False
        try:
            viewport = scroll.viewport()
        except RuntimeError:
            return False
        return watched is viewport and event_type in {"wheel", "mouse_press"}

    def cancel_active_cube_reveal_scroll(self) -> None:
        """Stop active or pending cube reveal motion after deliberate user input."""

        interrupted_route_key = self._pending_reveal_route_key
        if interrupted_route_key is not None:
            log_debug(
                _LOGGER,
                "Cancelled pending cube reveal after user scroll",
                cube_alias=interrupted_route_key,
            )
        self._clear_pending_reveal()
        self._programmatic_navigation_route_key = None
        self.scroll_driver.cancel_cube_navigation()

    def scroll_to_cube(
        self,
        route_key: str,
        animated: bool = False,
        duration: int | None = None,
        *,
        only_if_needed: bool = False,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Scroll the panel so the requested cube section becomes visible."""

        if route_key not in self._host.cube_sections:
            return
        if only_if_needed and self.geometry.is_mostly_visible(route_key):
            if on_finished is not None:
                on_finished()
            return

        scroll = self._host.scroll
        scroll_content = scroll.widget()
        if scroll_content is None:
            return
        target_value = self.geometry.scroll_target_value(route_key)
        if target_value is None:
            return
        scrollbar = scroll.verticalScrollBar()
        self._programmatic_navigation_route_key = route_key

        def finish_navigation() -> None:
            """Clear programmatic navigation state after scroll completion."""

            if self._programmatic_navigation_route_key == route_key:
                self._programmatic_navigation_route_key = None
            if on_finished is not None:
                on_finished()

        self.scroll_driver.move_cube_scrollbar(
            scrollbar,
            target_value,
            animated=animated,
            duration_ms=SCROLL_DURATION_MS if duration is None else duration,
            on_finished=finish_navigation,
        )

    def reveal_new_cube(self, route_key: str) -> None:
        """Reveal a newly loaded cube with optional scroll navigation."""

        self.reveal_loaded_cube(route_key)

    def reveal_loaded_cube(self, route_key: str) -> None:
        """Navigate to a newly loaded cube after layout metrics settle."""

        self.queue_cube_reveal(route_key, force_navigation=True)

    def reveal_cube_when_layout_ready(self, route_key: str) -> None:
        """Queue a cube reveal until section height and scroll metrics are stable."""

        self.queue_cube_reveal(route_key, force_navigation=False)

    def queue_cube_reveal(self, route_key: str, *, force_navigation: bool) -> None:
        """Queue one cube reveal until section height and scroll metrics are stable."""

        if route_key not in self._host.cube_sections:
            return
        self._pending_reveal_route_key = route_key
        self._pending_reveal_attempts = 0
        self._pending_reveal_force_navigation = force_navigation
        self._pending_reveal_geometry_signature = None
        self.schedule_pending_cube_reveal_metrics_refresh()

    def schedule_pending_cube_reveal_metrics_refresh(self) -> None:
        """Request scroll metrics before completing a pending cube reveal."""

        scroll = getattr(self._host, "scroll", None)
        schedule_refresh = getattr(scroll, "schedule_metrics_refresh", None)
        if callable(schedule_refresh):
            schedule_refresh()
            return
        QTimer.singleShot(0, self.complete_pending_cube_reveal)

    def complete_pending_cube_reveal(self) -> None:
        """Finish a pending cube reveal after layout and metrics have refreshed."""

        route_key = self._pending_reveal_route_key
        if route_key is None:
            return
        force_navigation = self._pending_reveal_force_navigation
        ready_for_reveal = self.cube_section_ready_for_reveal(
            route_key,
            allow_first_valid=force_navigation,
        )
        if not ready_for_reveal:
            self._pending_reveal_attempts += 1
            if self._pending_reveal_attempts <= self._layout_attempt_limit:
                QTimer.singleShot(0, self.schedule_pending_cube_reveal_metrics_refresh)
            else:
                log_debug(
                    _LOGGER,
                    "Skipped cube reveal because layout did not become ready",
                    cube_alias=route_key,
                )
                self._clear_pending_reveal()
            return

        self._clear_pending_reveal()
        is_mostly_visible = self.geometry.is_mostly_visible(route_key)
        if not force_navigation and is_mostly_visible:
            self.visible_sync.emit(route_key)
            return

        self.scroll_to_cube(
            route_key,
            animated=True,
            duration=SCROLL_DURATION_MS,
            only_if_needed=not force_navigation,
        )

    def cube_section_ready_for_reveal(
        self,
        route_key: str,
        *,
        allow_first_valid: bool = False,
    ) -> bool:
        """Return whether one cube section has stable enough geometry to reveal."""

        signature = self.geometry.readiness_signature(route_key)
        if signature is None:
            self._pending_reveal_geometry_signature = None
            return False

        target_value, maximum_value = signature[:2]
        if target_value > maximum_value:
            self._pending_reveal_geometry_signature = None
            return False

        previous_signature = self._pending_reveal_geometry_signature
        self._pending_reveal_geometry_signature = signature
        if allow_first_valid:
            return True
        return previous_signature == signature

    def scroll_to_input_widget(
        self,
        widget: object,
        animated: bool = True,
        duration: int | None = None,
    ) -> None:
        """Scroll the panel so one input widget is centered when possible."""

        input_widget = cast(InputWidgetProtocol | None, widget)
        if input_widget is None or not isValid(input_widget):
            return

        scroll = self._host.scroll
        content_widget = scroll.widget()
        if content_widget is None:
            return

        widget_pos = input_widget.mapTo(content_widget, input_widget.rect().center())
        viewport = scroll.viewport()
        viewport_height = viewport.height()

        target_value = max(0, widget_pos.y() - (viewport_height // 2))
        scrollbar = scroll.verticalScrollBar()
        self.scroll_driver.move_input_scrollbar(
            scrollbar,
            target_value,
            animated=animated,
            duration_ms=INPUT_SCROLL_DURATION_MS if duration is None else duration,
        )

    def on_scroll_updated(self, _value: int) -> None:
        """Sync the visible cube tab with the current editor scroll position."""

        if self.scroll_driver.suppresses_visible_sync:
            return
        self.visible_sync.synchronize(
            programmatic_route_key=self._programmatic_navigation_route_key
        )

    def emit_current_cube_visible(self, route_key: str) -> None:
        """Emit the visible-cube signal when the target signal is available."""

        self.visible_sync.emit(route_key)

    def _clear_pending_reveal(self) -> None:
        """Clear pending delayed-reveal state."""

        self._pending_reveal_route_key = None
        self._pending_reveal_attempts = 0
        self._pending_reveal_force_navigation = False
        self._pending_reveal_geometry_signature = None


__all__ = [
    "EditorPanelCubeRevealController",
    "EditorPanelCubeRevealHost",
]
