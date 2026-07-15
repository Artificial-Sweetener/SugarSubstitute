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

"""Own editor-panel cube reveal, scroll animation, and visible-cube sync."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, cast

from PySide6.QtCore import QObject, QPoint, QPropertyAnimation, QTimer
from PySide6.QtGui import QAction
from shiboken6 import isValid

from substitute.application.display_labels import beautify_label
from substitute.presentation.motion import (
    INPUT_SCROLL_DURATION_MS,
    SCROLL_DURATION_MS,
    TRANSFORM_EASING_CURVE,
    restart_property_animation,
    stop_animation,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger(__name__)
DEFAULT_REVEAL_LAYOUT_ATTEMPT_LIMIT = 12


class SignalEmitterProtocol(Protocol):
    """Describe a Qt-like signal that emits one route key."""

    def emit(self, route_key: str) -> None:
        """Emit one visible cube route key."""


class VisibilityButtonProtocol(Protocol):
    """Describe reveal-menu button state APIs."""

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Set whether the reveal menu button is enabled."""

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Set whether the reveal menu button is visible."""


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
    _cube_states: dict[str, object] | None
    _cube_visibility_btns: dict[str, VisibilityButtonProtocol]
    _cube_visibility_menus: dict[str, object]
    _stack_order: Sequence[str] | None
    node_behavior_service: object
    currentCubeVisibleChanged: SignalEmitterProtocol

    def sender(self) -> object | None:
        """Return the Qt signal sender for reveal-menu action routing."""

    def current_behavior_snapshot(self) -> object | None:
        """Return the latest prepared node-behavior snapshot."""

    def refresh_node_behavior_state(self, *, reason: str) -> None:
        """Refresh node behavior after reveal-policy mutation."""


class EditorPanelCubeRevealController:
    """Coordinate cube reveal requests, scroll animation, and tab sync."""

    def __init__(
        self,
        host: EditorPanelCubeRevealHost,
        *,
        layout_attempt_limit: int = DEFAULT_REVEAL_LAYOUT_ATTEMPT_LIMIT,
    ) -> None:
        """Store the host view and initialize reveal state."""

        self._host = host
        self._layout_attempt_limit = layout_attempt_limit
        self._suppress_tab_sync = False
        self._scroll_anim: QPropertyAnimation | None = None
        self._input_scroll_anim: QPropertyAnimation | None = None
        self._pending_reveal_route_key: str | None = None
        self._pending_reveal_attempts = 0
        self._pending_reveal_force_navigation = False
        self._pending_reveal_geometry_signature: tuple[int, ...] | None = None
        self._programmatic_navigation_route_key: str | None = None

    def rebuild_all_cube_visibility_menus(self) -> None:
        """Rebuild all per-cube reveal menus from the latest behavior snapshot."""

        host = self._host
        aliases = list(getattr(host, "_stack_order", []) or [])
        for alias in aliases:
            if alias in host._cube_visibility_menus:
                self.rebuild_cube_visibility_menu(alias)

    def on_cube_visibility_menu_triggered(self, action: object) -> None:
        """Resolve reveal-menu sender alias and apply the toggle to runtime state."""

        data_reader = getattr(action, "data", None)
        data = data_reader() if callable(data_reader) else {}
        alias = data.get("alias") if isinstance(data, Mapping) else None
        if not alias:
            sender = self._host.sender()
            for current_alias, menu in self._host._cube_visibility_menus.items():
                if menu is sender:
                    alias = current_alias
                    break
        if alias:
            self.on_cube_visibility_menu_toggled(str(alias), action)

    def rebuild_cube_visibility_menu(self, alias: str) -> None:
        """Rebuild one reveal menu from the latest snapshot reveal entries."""

        host = self._host
        menu = host._cube_visibility_menus.get(alias)
        if menu is None:
            return
        clear = getattr(menu, "clear", None)
        if callable(clear):
            clear()
        current_behavior_snapshot = getattr(host, "current_behavior_snapshot", None)
        snapshot = (
            current_behavior_snapshot()
            if callable(current_behavior_snapshot)
            else getattr(host, "_last_behavior_snapshot", None)
        )
        entries = snapshot.reveal_entries_by_alias.get(alias, []) if snapshot else []
        button = host._cube_visibility_btns.get(alias)
        if not entries:
            if button is not None:
                button.setEnabled(False)
                button.setVisible(False)
            return
        if button is not None:
            button.setEnabled(True)
            button.setVisible(True)
        for entry in entries:
            action_parent = menu if isinstance(menu, QObject) else None
            action = QAction(beautify_label(entry.label), action_parent)
            action.setCheckable(True)
            action.setChecked(bool(entry.checked))
            action.setData({"alias": alias, "node_name": entry.node_name})
            action.toggled.connect(
                lambda checked, *, current_alias=alias, node_name=entry.node_name: (
                    self.on_cube_visibility_menu_action_toggled(
                        current_alias,
                        node_name,
                        bool(checked),
                    )
                )
            )
            add_action = getattr(menu, "addAction", None)
            if callable(add_action):
                add_action(action)

    def on_cube_visibility_menu_toggled(self, alias: str, action: object) -> None:
        """Persist one reveal-menu toggle through the application command surface."""

        data_reader = getattr(action, "data", None)
        data = data_reader() if callable(data_reader) else {}
        node_name = data.get("node_name") if isinstance(data, Mapping) else None
        if not node_name:
            return
        is_checked = getattr(action, "isChecked", None)
        self.on_cube_visibility_menu_action_toggled(
            alias,
            str(node_name),
            bool(is_checked()) if callable(is_checked) else False,
        )

    def on_cube_visibility_menu_action_toggled(
        self,
        alias: str,
        node_name: str,
        checked: bool,
    ) -> None:
        """Persist one reveal-menu checked state through the application command surface."""

        host = self._host
        cube_state = (
            host._cube_states.get(alias)
            if isinstance(host._cube_states, dict)
            else None
        )
        if cube_state is None:
            return
        set_node_visibility_override = getattr(
            host.node_behavior_service,
            "set_node_visibility_override",
            None,
        )
        if not callable(set_node_visibility_override):
            return
        set_node_visibility_override(
            cube_state,
            node_name,
            True if checked else None,
        )
        host.refresh_node_behavior_state(reason="node_activation_changed")
        self.rebuild_cube_visibility_menu(alias)

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
        animation = self._scroll_anim
        if animation is None:
            return
        self._scroll_anim = None
        self._suppress_tab_sync = False
        stop_animation(animation)
        self.on_scroll_updated(self._host.scroll.verticalScrollBar().value())

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
        if only_if_needed and self.cube_widget_is_mostly_visible(route_key):
            if on_finished is not None:
                on_finished()
            return

        scroll = self._host.scroll
        scroll_content = scroll.widget()
        if scroll_content is None:
            return
        target_value = self.cube_scroll_target_value(route_key)
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

        self._animate_scrollbar_value(
            scrollbar=scrollbar,
            target_value=target_value,
            animated=animated,
            duration_ms=SCROLL_DURATION_MS if duration is None else duration,
            animation_attr_name="_scroll_anim",
            suppress_tab_sync=True,
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
        is_mostly_visible = self.cube_widget_is_mostly_visible(route_key)
        if not force_navigation and is_mostly_visible:
            self.emit_current_cube_visible(route_key)
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

        signature = self.cube_reveal_geometry_signature(route_key)
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

    def cube_reveal_geometry_signature(
        self,
        route_key: str,
    ) -> tuple[int, ...] | None:
        """Return reveal metrics that must be stable before loaded-cube navigation."""

        cube_widget = self._cube_widget(route_key)
        scroll_content = self._host.scroll.widget()
        if (
            cube_widget is None
            or not isValid(cube_widget)
            or scroll_content is None
            or cube_widget.height() <= 0
        ):
            return None
        target_value = self.cube_scroll_target_value(route_key)
        if target_value is None:
            return None
        target_content_y = self.cube_scroll_target_content_y(route_key)
        if target_content_y is None:
            return None
        overscroll_top = getattr(self._host.scroll, "overscroll_top", None)
        top_overscroll = int(overscroll_top()) if callable(overscroll_top) else 0
        unclamped_target_value = max(0, target_content_y + top_overscroll)
        scrollbar = self._host.scroll.verticalScrollBar()
        maximum_value = int(scrollbar.maximum())
        height_getter = getattr(scroll_content, "height", None)
        content_height = int(height_getter()) if callable(height_getter) else 0
        viewport_getter = getattr(self._host.scroll, "viewport", None)
        viewport = viewport_getter() if callable(viewport_getter) else None
        viewport_height_getter = getattr(viewport, "height", None)
        viewport_height = (
            int(viewport_height_getter()) if callable(viewport_height_getter) else 0
        )
        return (
            unclamped_target_value,
            maximum_value,
            int(target_value),
            int(cube_widget.height()),
            content_height,
            viewport_height,
        )

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
        self._animate_scrollbar_value(
            scrollbar=scrollbar,
            target_value=target_value,
            animated=animated,
            duration_ms=INPUT_SCROLL_DURATION_MS if duration is None else duration,
            animation_attr_name="_input_scroll_anim",
            suppress_tab_sync=False,
        )

    def on_scroll_updated(self, _value: int) -> None:
        """Sync the visible cube tab with the current editor scroll position."""

        if self._suppress_tab_sync:
            return
        if self._programmatic_navigation_route_key is not None:
            self.emit_current_cube_visible(self._programmatic_navigation_route_key)
            return
        if not self._host._stack_order:
            return

        scroll_content = self._host.scroll.widget()
        if scroll_content is None:
            return
        visible_y = self._host.scroll.visible_content_top()
        visible_bottom = self._host.scroll.visible_content_bottom()

        first_visible_cube: str | None = None
        best_y: int | None = None

        for alias in self._host._stack_order:
            widget = self._cube_widget(alias)
            if widget is None or not isValid(widget):
                continue

            pos_y = widget.mapTo(scroll_content, QPoint(0, 0)).y()

            if pos_y + widget.height() < visible_y:
                continue
            if pos_y > visible_bottom:
                continue

            if best_y is None or pos_y < best_y:
                best_y = pos_y
                first_visible_cube = alias

        if first_visible_cube:
            self.emit_current_cube_visible(first_visible_cube)

    def cube_widget_is_mostly_visible(
        self,
        route_key: str,
        *,
        visibility_threshold: float = 0.65,
    ) -> bool:
        """Return whether the requested cube section is already mostly visible."""

        cube_widget = self._cube_widget(route_key)
        scroll_content = self._host.scroll.widget()
        if (
            cube_widget is None
            or not isValid(cube_widget)
            or scroll_content is None
            or cube_widget.height() <= 0
        ):
            return False

        visible_top = self._host.scroll.visible_content_top()
        visible_bottom = self._host.scroll.visible_content_bottom()
        widget_top = cube_widget.mapTo(scroll_content, QPoint(0, 0)).y()
        widget_bottom = widget_top + cube_widget.height()
        visible_height = max(
            0,
            min(widget_bottom, visible_bottom) - max(widget_top, visible_top),
        )
        return (visible_height / max(1, cube_widget.height())) >= visibility_threshold

    def cube_reveal_anchor_content_y(self, route_key: str) -> int | None:
        """Return the content-space title/header anchor for one cube section."""

        cube_widget = self._cube_widget(route_key)
        scroll_content = self._host.scroll.widget()
        if cube_widget is None or scroll_content is None:
            return None

        anchor_y = 0
        reveal_anchor_y = getattr(cube_widget, "reveal_anchor_y", None)
        if callable(reveal_anchor_y):
            try:
                anchor_y = max(0, int(reveal_anchor_y()))
            except (RuntimeError, TypeError, ValueError):
                anchor_y = 0
        try:
            return cube_widget.mapTo(scroll_content, QPoint(0, anchor_y)).y()
        except (RuntimeError, TypeError, AttributeError):
            return None

    def cube_header_viewport_anchor_y(self) -> int:
        """Return where cube title/header centers should land in the viewport."""

        for route_key in self._host._stack_order or ():
            anchor_y = self.cube_reveal_anchor_content_y(route_key)
            if anchor_y is not None:
                return max(0, anchor_y)
        try:
            return max(0, self._host.scroll.viewport().height() // 2)
        except (RuntimeError, AttributeError):
            return 0

    def cube_scroll_target_value(self, route_key: str) -> int | None:
        """Return the scroll value that aligns a cube's title/header anchor."""

        content_target_y = self.cube_scroll_target_content_y(route_key)
        if content_target_y is None:
            return None
        return self._host.scroll.content_y_to_scroll_value(content_target_y)

    def cube_scroll_target_content_y(self, route_key: str) -> int | None:
        """Return the unclamped content-space target for cube header alignment."""

        anchor_y = self.cube_reveal_anchor_content_y(route_key)
        if anchor_y is None:
            return None
        return anchor_y - self.cube_header_viewport_anchor_y()

    def emit_current_cube_visible(self, route_key: str) -> None:
        """Emit the visible-cube signal when the target signal is available."""

        signal = getattr(self._host, "currentCubeVisibleChanged", None)
        emit = getattr(signal, "emit", None)
        if callable(emit):
            emit(route_key)

    def _animate_scrollbar_value(
        self,
        *,
        scrollbar: ScrollBarProtocol,
        target_value: int,
        animated: bool,
        duration_ms: int,
        animation_attr_name: str,
        suppress_tab_sync: bool,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Move one scrollbar either immediately or through shared Fluent motion."""

        existing_animation = cast(
            QPropertyAnimation | None,
            getattr(self, animation_attr_name),
        )
        stop_animation(existing_animation)
        setattr(self, animation_attr_name, None)

        if not animated:
            if suppress_tab_sync:
                self._suppress_tab_sync = True
            scrollbar.setValue(target_value)
            if suppress_tab_sync:
                self._suppress_tab_sync = False
                self.on_scroll_updated(self._host.scroll.verticalScrollBar().value())
            if on_finished is not None:
                on_finished()
            return

        animation = QPropertyAnimation(
            cast(QObject, scrollbar),
            b"value",
            cast(QObject, self._host),
        )
        setattr(self, animation_attr_name, animation)

        if suppress_tab_sync:
            self._suppress_tab_sync = True

        def finish_animation() -> None:
            """Restore reveal state after one scrollbar animation completes."""

            if getattr(self, animation_attr_name) is not animation:
                return
            setattr(self, animation_attr_name, None)
            if suppress_tab_sync:
                self._suppress_tab_sync = False
                self.on_scroll_updated(self._host.scroll.verticalScrollBar().value())
            if on_finished is not None:
                on_finished()

        animation.finished.connect(finish_animation)
        restart_property_animation(
            animation,
            start_value=scrollbar.value(),
            end_value=target_value,
            duration_ms=duration_ms,
            easing_curve=TRANSFORM_EASING_CURVE,
        )

    def _clear_pending_reveal(self) -> None:
        """Clear pending delayed-reveal state."""

        self._pending_reveal_route_key = None
        self._pending_reveal_attempts = 0
        self._pending_reveal_force_navigation = False
        self._pending_reveal_geometry_signature = None

    def _cube_widget(self, route_key: str) -> RevealedWidgetProtocol | None:
        """Return one cube widget as geometry protocol when available."""

        widget = self._host.cube_sections.get(route_key)
        if widget is None:
            return None
        return cast(RevealedWidgetProtocol, widget)


__all__ = [
    "EditorPanelCubeRevealController",
    "EditorPanelCubeRevealHost",
]
