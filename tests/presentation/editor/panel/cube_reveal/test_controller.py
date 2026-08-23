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

"""Contract tests for editor-panel cube reveal controller behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from _pytest.monkeypatch import MonkeyPatch
from PySide6.QtCore import QPropertyAnimation

import substitute.presentation.editor.panel.cube_reveal_controller as mod
from substitute.presentation.editor.panel.cube_reveal_controller import (
    EditorPanelCubeRevealController,
    EditorPanelCubeRevealHost,
    ScrollBarProtocol,
)


class _Point:
    """Minimal QPoint-like test double."""

    def __init__(self, y: int) -> None:
        """Store one y coordinate."""

        self._y = y

    def y(self) -> int:
        """Return the stored y coordinate."""

        return self._y


class _Rect:
    """Minimal QRect-like test double."""

    def center(self) -> object:
        """Return a point accepted by the widget double."""

        return _Point(0)


class _CubeWidget:
    """Simple cube-section double with configurable geometry."""

    def __init__(self, *, top: int, height: int, reveal_anchor_y: int = 0) -> None:
        """Initialize geometry state."""

        self._top = top
        self._height = height
        self._reveal_anchor_y = reveal_anchor_y

    def mapTo(self, _parent: object, point: object) -> _Point:  # noqa: N802
        """Return this widget's content-space y position."""

        point_y = point.y() if hasattr(point, "y") else 0
        return _Point(self._top + int(point_y))

    def height(self) -> int:
        """Return the configured widget height."""

        return self._height

    def rect(self) -> _Rect:
        """Return a rectangle double."""

        return _Rect()

    def reveal_anchor_y(self) -> int:
        """Return the configured title/header anchor."""

        return self._reveal_anchor_y


class _ScrollBar:
    """Minimal scrollbar double."""

    def __init__(self, *, value: int = 0, maximum: int = 1000) -> None:
        """Initialize scrollbar state."""

        self._value = value
        self._maximum = maximum
        self.values: list[int] = []

    def value(self) -> int:
        """Return the current scrollbar value."""

        return self._value

    def setValue(self, value: int) -> None:  # noqa: N802
        """Set and record the current scrollbar value."""

        self._value = value
        self.values.append(value)

    def maximum(self) -> int:
        """Return the configured maximum value."""

        return self._maximum

    def set_maximum(self, maximum: int) -> None:
        """Update the configured maximum value."""

        self._maximum = maximum


class _Viewport:
    """Minimal viewport double."""

    def __init__(self, *, height: int = 500) -> None:
        """Initialize viewport state."""

        self._height = height

    def height(self) -> int:
        """Return the configured viewport height."""

        return self._height


class _Content:
    """Minimal scroll content double."""

    def __init__(self, *, height: int = 1200) -> None:
        """Initialize content state."""

        self._height = height

    def height(self) -> int:
        """Return the configured content height."""

        return self._height

    def set_height(self, height: int) -> None:
        """Update the configured content height."""

        self._height = height


class _ScrollSurface:
    """Minimal editor-panel scroll surface double."""

    def __init__(
        self,
        *,
        content: _Content | None = None,
        viewport: _Viewport | None = None,
        scrollbar: _ScrollBar | None = None,
        visible_top: int = 0,
        visible_bottom: int = 500,
    ) -> None:
        """Initialize scroll-surface state."""

        self._content = content or _Content()
        self._viewport = viewport or _Viewport()
        self._scrollbar = scrollbar or _ScrollBar()
        self._visible_top = visible_top
        self._visible_bottom = visible_bottom
        self.schedule_calls = 0

    def widget(self) -> _Content | None:
        """Return the configured content widget."""

        return self._content

    def viewport(self) -> _Viewport:
        """Return the configured viewport."""

        return self._viewport

    def verticalScrollBar(self) -> _ScrollBar:  # noqa: N802
        """Return the configured scrollbar."""

        return self._scrollbar

    def visible_content_top(self) -> int:
        """Return the configured visible top."""

        return self._visible_top

    def visible_content_bottom(self) -> int:
        """Return the configured visible bottom."""

        return self._visible_bottom

    def content_y_to_scroll_value(self, content_y: int) -> int:
        """Clamp content y to the scrollbar range."""

        return min(max(0, content_y), self._scrollbar.maximum())

    def overscroll_top(self) -> int:
        """Return the top overscroll value."""

        return 0

    def schedule_metrics_refresh(self) -> None:
        """Record one deferred metrics refresh request."""

        self.schedule_calls += 1


class _OffsetScrollSurface(_ScrollSurface):
    """Scroll surface that applies an offset to scroll-model conversion."""

    def content_y_to_scroll_value(self, content_y: int) -> int:
        """Return one offset scroll value for target-alignment tests."""

        return content_y + 37


class _Signal:
    """Minimal signal double."""

    def __init__(self) -> None:
        """Initialize emitted route storage."""

        self.emitted: list[str] = []

    def emit(self, route_key: str) -> None:
        """Record one emitted route key."""

        self.emitted.append(route_key)


class _Host:
    """Controller host double."""

    def __init__(
        self,
        *,
        scroll: _ScrollSurface | None = None,
        cube_sections: dict[str, object] | None = None,
        stack_order: list[str] | None = None,
    ) -> None:
        """Initialize host state."""

        self.scroll = scroll or _ScrollSurface()
        self.cube_sections = cube_sections or {}
        self._stack_order = stack_order
        self.currentCubeVisibleChanged = _Signal()


class _RecordingRevealController(EditorPanelCubeRevealController):
    """Reveal controller that records scroll requests instead of animating."""

    def __init__(self, host: EditorPanelCubeRevealHost) -> None:
        """Initialize recording state."""

        super().__init__(host, layout_attempt_limit=6)
        self.scroll_calls: list[dict[str, object]] = []
        self.animation_targets: list[int] = []

    def scroll_to_cube(
        self,
        route_key: str,
        animated: bool = False,
        duration: int | None = None,
        *,
        only_if_needed: bool = False,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Record one cube scroll request."""

        self.scroll_calls.append(
            {
                "route_key": route_key,
                "animated": animated,
                "duration": duration,
                "only_if_needed": only_if_needed,
            }
        )
        if on_finished is not None:
            on_finished()

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
        """Record one animation target."""

        _ = scrollbar, animated, duration_ms, animation_attr_name, suppress_tab_sync
        self.animation_targets.append(target_value)
        if on_finished is not None:
            on_finished()


def _controller(host: _Host) -> EditorPanelCubeRevealController:
    """Return one controller for a host double."""

    return EditorPanelCubeRevealController(
        cast(EditorPanelCubeRevealHost, host),
        layout_attempt_limit=6,
    )


def test_reveal_when_layout_ready_waits_for_repeated_geometry(
    monkeypatch: MonkeyPatch,
) -> None:
    """Non-forced reveal should wait for metrics and stable repeated geometry."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    host = _Host(
        cube_sections={"CubeA": _CubeWidget(top=0, height=200)},
        stack_order=["CubeA"],
    )
    controller = _controller(host)

    controller.reveal_cube_when_layout_ready("CubeA")

    assert host.scroll.schedule_calls == 1
    controller.complete_pending_cube_reveal()
    assert host.currentCubeVisibleChanged.emitted == []

    controller.complete_pending_cube_reveal()

    assert host.currentCubeVisibleChanged.emitted == ["CubeA"]


def test_reveal_loaded_cube_scrolls_on_first_valid_geometry(
    monkeypatch: MonkeyPatch,
) -> None:
    """Forced loaded-cube navigation should not wait for repeated geometry."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    host = _Host(
        cube_sections={"CubeA": _CubeWidget(top=400, height=240)},
        stack_order=["CubeA"],
    )
    controller = _RecordingRevealController(cast(EditorPanelCubeRevealHost, host))

    controller.reveal_loaded_cube("CubeA")
    controller.complete_pending_cube_reveal()

    assert controller.scroll_calls == [
        {
            "route_key": "CubeA",
            "animated": True,
            "duration": 220,
            "only_if_needed": False,
        }
    ]
    assert controller._pending_reveal_route_key is None
    assert controller._pending_reveal_attempts == 0
    assert controller._pending_reveal_force_navigation is False


def test_reveal_loaded_cube_replaces_pending_reveal() -> None:
    """Replacing a pending reveal should keep the latest requested cube."""

    host = _Host(
        cube_sections={
            "CubeA": _CubeWidget(top=0, height=200),
            "CubeB": _CubeWidget(top=240, height=200),
        }
    )
    controller = _controller(host)

    controller.reveal_loaded_cube("CubeA")
    controller.reveal_loaded_cube("CubeB")

    assert host.scroll.schedule_calls == 2
    assert controller._pending_reveal_route_key == "CubeB"


def test_scroll_target_aligns_header_anchor_through_scroll_model(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cube scroll targets should align the title/header anchor."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    scroll = _OffsetScrollSurface(scrollbar=_ScrollBar(maximum=1000))
    host = _Host(
        scroll=scroll,
        cube_sections={
            "Header": _CubeWidget(top=14, height=20),
            "CubeA": _CubeWidget(top=400, height=240, reveal_anchor_y=32),
        },
        stack_order=["Header", "CubeA"],
    )
    controller = _controller(host)

    assert controller.cube_scroll_target_value("CubeA") == 455


def test_reveal_readiness_uses_unclamped_scroll_target(
    monkeypatch: MonkeyPatch,
) -> None:
    """Loaded-cube reveal should wait until unclamped target metrics are stable."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    scrollbar = _ScrollBar(maximum=300)
    host = _Host(
        scroll=_ScrollSurface(scrollbar=scrollbar),
        cube_sections={
            "CubeA": _CubeWidget(top=0, height=200),
            "CubeB": _CubeWidget(top=800, height=200),
        },
        stack_order=["CubeA", "CubeB"],
    )
    controller = _controller(host)

    assert controller.cube_scroll_target_value("CubeB") == 300
    assert controller.cube_section_ready_for_reveal("CubeB") is False

    scrollbar.set_maximum(900)

    assert controller.cube_section_ready_for_reveal("CubeB") is False
    assert controller.cube_section_ready_for_reveal("CubeB") is True


def test_reveal_readiness_requires_stable_content_geometry(
    monkeypatch: MonkeyPatch,
) -> None:
    """Loaded-cube reveal should wait while scrollable content geometry changes."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    content = _Content(height=900)
    host = _Host(
        scroll=_ScrollSurface(content=content, scrollbar=_ScrollBar(maximum=900)),
        cube_sections={
            "CubeA": _CubeWidget(top=0, height=200),
            "CubeB": _CubeWidget(top=800, height=200),
        },
        stack_order=["CubeA", "CubeB"],
    )
    controller = _controller(host)

    assert controller.cube_section_ready_for_reveal("CubeB") is False

    content.set_height(1200)

    assert controller.cube_section_ready_for_reveal("CubeB") is False
    assert controller.cube_section_ready_for_reveal("CubeB") is True


def test_programmatic_navigation_emits_target_instead_of_first_visible_cube(
    monkeypatch: MonkeyPatch,
) -> None:
    """Programmatic navigation should keep tab sync on the intended cube alias."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    host = _Host(
        scroll=_ScrollSurface(visible_top=0, visible_bottom=220),
        cube_sections={
            "CubeA": _CubeWidget(top=0, height=200),
            "CubeB": _CubeWidget(top=180, height=200),
        },
        stack_order=["CubeA", "CubeB"],
    )
    controller = _controller(host)
    controller._programmatic_navigation_route_key = "CubeB"

    controller.on_scroll_updated(0)

    assert host.currentCubeVisibleChanged.emitted == ["CubeB"]


def test_user_scroll_interruption_cancels_pending_reveal_animation(
    monkeypatch: MonkeyPatch,
) -> None:
    """Manual scroll intent should cancel active automated reveal state."""

    stopped: list[object] = []
    monkeypatch.setattr(mod, "stop_animation", lambda anim: stopped.append(anim))
    host = _Host(scroll=_ScrollSurface(scrollbar=_ScrollBar(value=42)))
    controller = _controller(host)
    animation = cast(QPropertyAnimation, object())
    controller._scroll_anim = animation
    controller._suppress_tab_sync = True
    controller._programmatic_navigation_route_key = "CubeA"
    controller._pending_reveal_route_key = "CubeA"
    controller._pending_reveal_attempts = 2
    controller._pending_reveal_force_navigation = True
    controller._pending_reveal_geometry_signature = (1, 1, 1, 1, 1, 1)

    controller.cancel_active_cube_reveal_scroll()

    assert stopped == [animation]
    assert controller._scroll_anim is None
    assert controller._suppress_tab_sync is False
    assert controller._programmatic_navigation_route_key is None
    assert controller._pending_reveal_route_key is None
    assert controller._pending_reveal_attempts == 0
    assert controller._pending_reveal_force_navigation is False
    assert controller._pending_reveal_geometry_signature is None


def test_user_scroll_interruption_clears_pending_reveal_without_animation() -> None:
    """Manual scroll should clear pending reveal before animation starts."""

    host = _Host()
    controller = _controller(host)
    controller._programmatic_navigation_route_key = "CubeA"
    controller._pending_reveal_route_key = "CubeA"
    controller._pending_reveal_attempts = 3
    controller._pending_reveal_force_navigation = False
    controller._pending_reveal_geometry_signature = (1, 1, 1, 1, 1, 1)

    controller.cancel_active_cube_reveal_scroll()

    assert controller._programmatic_navigation_route_key is None
    assert controller._pending_reveal_route_key is None
    assert controller._pending_reveal_attempts == 0
    assert controller._pending_reveal_force_navigation is False
    assert controller._pending_reveal_geometry_signature is None


def test_cube_widget_visibility_threshold_uses_viewport_overlap(
    monkeypatch: MonkeyPatch,
) -> None:
    """Visibility checks should depend on viewport overlap."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    host = _Host(
        scroll=_ScrollSurface(visible_top=120, visible_bottom=300),
        cube_sections={"CubeA": _CubeWidget(top=100, height=240)},
    )
    controller = _controller(host)

    assert (
        controller.cube_widget_is_mostly_visible(
            "CubeA",
            visibility_threshold=0.60,
        )
        is True
    )
    assert (
        controller.cube_widget_is_mostly_visible(
            "CubeA",
            visibility_threshold=0.90,
        )
        is False
    )


def test_scroll_to_input_widget_centers_widget(monkeypatch: MonkeyPatch) -> None:
    """Input scroll navigation should center widgets through the scroll model."""

    monkeypatch.setattr(mod, "isValid", lambda _widget: True)
    host = _Host(cube_sections={})
    controller = _RecordingRevealController(cast(EditorPanelCubeRevealHost, host))
    widget = _CubeWidget(top=700, height=40)

    controller.scroll_to_input_widget(widget, animated=False)

    assert controller.animation_targets == [450]
