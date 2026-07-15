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

"""Show QFluent-styled tooltips next to the cursor."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

try:
    from PySide6.QtCore import QObject, QEvent, QPoint, QRect, QSize, QTimer
    from PySide6.QtGui import QCursor, QGuiApplication
    from PySide6.QtWidgets import QWidget
except ImportError:  # pragma: no cover - lightweight test stubs

    class QObject:  # type: ignore[no-redef]
        """Fallback QObject for lightweight tests."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept QObject construction without side effects."""

        def parent(self) -> object | None:
            """Return no QObject parent in fallback mode."""

            return None

        def eventFilter(self, _watched: object, _event: object) -> bool:
            """Do not consume events in fallback mode."""

            return False

    class QEvent:  # type: ignore[no-redef]
        """Fallback QEvent enum container for lightweight tests."""

        class Type:
            """Fallback event names."""

            Enter = "enter"
            MouseMove = "mouse-move"
            ToolTip = "tooltip"
            Hide = "hide"
            Leave = "leave"
            MouseButtonPress = "mouse-press"
            Wheel = "wheel"

    class QPoint:  # type: ignore[no-redef]
        """Fallback QPoint with the methods used by tests."""

        def __init__(self, x: int = 0, y: int = 0) -> None:
            """Store coordinates."""

            self._x = x
            self._y = y

        def __add__(self, other: "QPoint") -> "QPoint":
            """Return coordinate addition."""

            this = cast(Any, self)
            that = cast(Any, other)
            return QPoint(this._x + that._x, this._y + that._y)

        def x(self) -> int:
            """Return x."""

            return self._x

        def y(self) -> int:
            """Return y."""

            return self._y

    class QSize:  # type: ignore[no-redef]
        """Fallback QSize with width and height."""

        def __init__(self, width: int = 0, height: int = 0) -> None:
            """Store dimensions."""

            self._width = width
            self._height = height

        def width(self) -> int:
            """Return width."""

            return self._width

        def height(self) -> int:
            """Return height."""

            return self._height

    class QRect:  # type: ignore[no-redef]
        """Fallback QRect with screen-bound helpers."""

        def __init__(
            self,
            left: int = 0,
            top: int = 0,
            width: int = 0,
            height: int = 0,
        ) -> None:
            """Store rectangle geometry."""

            self._left = left
            self._top = top
            self._width = width
            self._height = height

        def left(self) -> int:
            """Return left edge."""

            return self._left

        def top(self) -> int:
            """Return top edge."""

            return self._top

        def right(self) -> int:
            """Return right edge."""

            return self._left + self._width

        def bottom(self) -> int:
            """Return bottom edge."""

            return self._top + self._height

    class QTimer:  # type: ignore[no-redef]
        """Fallback timer that records state without scheduling."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Create a fallback timer."""

            self._active = False
            self.timeout = cast(Any, self)

        def setSingleShot(self, _single_shot: bool) -> None:
            """Accept single-shot configuration."""

        def connect(self, _slot: object) -> None:
            """Accept timeout connection."""

        def start(self, _delay: int) -> None:
            """Record active state."""

            self._active = True

        def stop(self) -> None:
            """Record inactive state."""

            self._active = False

        def isActive(self) -> bool:
            """Return active state."""

            return self._active

    class QCursor:  # type: ignore[no-redef]
        """Fallback cursor position provider."""

        @staticmethod
        def pos() -> QPoint:
            """Return origin in fallback mode."""

            return QPoint()

    class QGuiApplication:  # type: ignore[no-redef]
        """Fallback screen lookup provider."""

        @staticmethod
        def screenAt(_point: QPoint) -> object | None:
            """Return no screen in fallback mode."""

            return None

        @staticmethod
        def primaryScreen() -> object | None:
            """Return no primary screen in fallback mode."""

            return None

    class QWidget(QObject):  # type: ignore[no-redef]
        """Fallback widget type for annotations."""


try:
    from qfluentwidgets.components.widgets.tool_tip import ToolTip  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs
    ToolTip = None


_DEFAULT_TOOLTIP_OFFSET = QPoint(14, 18)
_SCREEN_MARGIN = 4
_MAX_TOOLTIP_WIDTH_PX = 420
_MIN_TOOLTIP_CONTENT_WIDTH_PX = 120


class _TooltipWidget(Protocol):
    """Describe the QFluent tooltip methods used by the cursor filter."""

    def setText(self, text: str) -> None:
        """Set tooltip text."""

    def setDuration(self, duration: int) -> None:
        """Set tooltip duration."""

    def adjustSize(self) -> None:
        """Update size hint before positioning."""

    def size(self) -> QSize:
        """Return current tooltip size."""

    def move(self, position: QPoint) -> None:
        """Move tooltip to a global position."""

    def show(self) -> None:
        """Show tooltip."""

    def hide(self) -> None:
        """Hide tooltip."""


class _TimeoutSignal(Protocol):
    """Describe a timer timeout signal."""

    def connect(self, slot: object) -> None:
        """Connect a timeout slot."""


class _TooltipTimer(Protocol):
    """Describe timer behavior used by the tooltip filter."""

    timeout: _TimeoutSignal

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Set single-shot behavior."""

    def start(self, delay: int) -> None:
        """Start the timer."""

    def stop(self) -> None:
        """Stop the timer."""


TooltipProvider = Callable[[object, object], str | None]


class _NoOpTimeoutSignal:
    """No-op timeout signal for lightweight widget stubs."""

    def connect(self, _slot: object) -> None:
        """Ignore signal connections."""


class _NoOpTimer:
    """No-op timer for lightweight widget stubs."""

    timeout: _TimeoutSignal = _NoOpTimeoutSignal()

    def setSingleShot(self, _single_shot: bool) -> None:  # noqa: N802
        """Ignore single-shot configuration."""

    def start(self, _delay: int) -> None:
        """Ignore timer start."""

    def stop(self) -> None:
        """Ignore timer stop."""


def cursor_tooltip_position(
    *,
    cursor_global_pos: QPoint,
    tooltip_size: QSize,
    offset: QPoint | None = None,
    screen_geometry: QRect | None = None,
) -> QPoint:
    """Return a tooltip position offset from the cursor and clamped to screen."""

    geometry = screen_geometry or _screen_geometry(cursor_global_pos)
    desired = cursor_global_pos + (offset or _DEFAULT_TOOLTIP_OFFSET)
    maximum_x = max(
        geometry.left(),
        geometry.right() - tooltip_size.width() - _SCREEN_MARGIN,
    )
    maximum_y = max(
        geometry.top(),
        geometry.bottom() - tooltip_size.height() - _SCREEN_MARGIN,
    )
    x = min(max(desired.x(), geometry.left()), maximum_x)
    y = min(max(desired.y(), geometry.top()), maximum_y)
    return QPoint(x, y)


class CursorToolTipFilter(QObject):
    """Show a QFluent tooltip near the cursor for one tooltip owner."""

    _is_filter_initialized = False
    _tooltip_provider: TooltipProvider | None = None
    _timer: _TooltipTimer = _NoOpTimer()
    _tooltip: _TooltipWidget | None = None

    def __init__(
        self,
        parent: QWidget,
        *,
        show_delay_ms: int = 300,
        offset: QPoint | None = None,
        show_when_disabled: bool = False,
        tooltip_provider: TooltipProvider | None = None,
    ) -> None:
        """Create a tooltip filter with optional disabled-owner display."""

        try:
            super().__init__(parent)
        except (
            AttributeError,
            TypeError,
            RuntimeError,
        ):  # pragma: no cover - stub safety
            super().__init__()
        self._owner = parent
        self._show_delay_ms = show_delay_ms
        self._offset = offset or _DEFAULT_TOOLTIP_OFFSET
        self._show_when_disabled = show_when_disabled
        self._tooltip_provider = tooltip_provider
        self._cursor_global_pos = QCursor.pos()
        self._is_entered = False
        self._tooltip: _TooltipWidget | None = None
        self._timer = self._create_timer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.show_tooltip)
        self._is_filter_initialized = True

    def eventFilter(self, watched: object, event: object) -> bool:
        """Track hover events and suppress native widget-anchored tooltips."""

        if not self._is_filter_initialized:
            return False
        tooltip_changed = self._refresh_dynamic_tooltip(watched, event)
        if _event_is(event, "ToolTip"):
            self._update_cursor_global_pos(watched, event)
            return True
        if _event_is(event, "Enter"):
            self._is_entered = True
            self._update_cursor_global_pos(watched, event)
            self._start_timer_if_available()
        elif _event_is(event, "MouseMove"):
            self._update_cursor_global_pos(watched, event)
            if tooltip_changed:
                self._restart_timer_after_dynamic_tooltip_change()
        elif _event_is_any(
            event,
            ("Hide", "Leave", "MouseButtonPress", "Wheel"),
        ):
            self.hide_tooltip()

        return False

    def show_tooltip(self) -> None:
        """Show the tooltip beside the latest cursor position."""

        owner = getattr(self, "_owner", None)
        if owner is None or not self._is_entered or not _widget_tooltip(owner):
            return
        if not self._show_when_disabled and not _widget_is_enabled(owner):
            return

        tooltip = self._tooltip or self._create_tooltip()
        if tooltip is None:
            return
        self._tooltip = tooltip
        _configure_tooltip_bounds(tooltip)
        tooltip.setText(_widget_tooltip(owner))
        _configure_tooltip_bounds(tooltip)
        tooltip.setDuration(_widget_tooltip_duration(owner))
        tooltip.adjustSize()
        tooltip.move(
            cursor_tooltip_position(
                cursor_global_pos=self._cursor_global_pos,
                tooltip_size=tooltip.size(),
                offset=self._offset,
            )
        )
        tooltip.show()

    def hide_tooltip(self) -> None:
        """Hide the tooltip and stop pending display."""

        self._is_entered = False
        self._timer.stop()
        if self._tooltip is not None:
            self._tooltip.hide()

    def _create_tooltip(self) -> _TooltipWidget | None:
        """Create the QFluent tooltip widget when available."""

        owner = getattr(self, "_owner", None)
        if ToolTip is None or owner is None or not hasattr(owner, "metaObject"):
            return None
        return cast(
            _TooltipWidget,
            ToolTip(_widget_tooltip(owner), owner.window()),
        )

    def _create_timer(self) -> _TooltipTimer:
        """Create a Qt timer only when the owner is a real Qt widget."""

        if not hasattr(self._owner, "metaObject"):
            return _NoOpTimer()
        try:
            return cast(_TooltipTimer, QTimer(self))
        except (
            AttributeError,
            TypeError,
            RuntimeError,
        ):  # pragma: no cover - stub safety
            return _NoOpTimer()

    def _start_timer_if_available(self) -> None:
        """Start the show timer only when the owner has tooltip text."""

        owner = getattr(self, "_owner", None)
        if owner is not None and _widget_tooltip(owner):
            self._timer.start(self._show_delay_ms)

    def _restart_timer_after_dynamic_tooltip_change(self) -> None:
        """Restart delayed display when a dynamic tooltip target changes."""

        self._timer.stop()
        if self._tooltip is not None:
            self._tooltip.hide()
        if self._is_entered:
            self._start_timer_if_available()

    def _refresh_dynamic_tooltip(self, watched: object, event: object) -> bool:
        """Refresh owner tooltip text from an optional event-aware provider."""

        if self._tooltip_provider is None or not _event_is_any(
            event,
            ("Enter", "MouseMove", "ToolTip"),
        ):
            return False
        owner = getattr(self, "_owner", None)
        if owner is None:
            return False
        previous_text = _widget_tooltip(owner)
        next_text = self._tooltip_provider(watched, event) or ""
        set_tooltip = getattr(owner, "setToolTip", None)
        if callable(set_tooltip):
            set_tooltip(next_text)
        return next_text != previous_text

    def _update_cursor_global_pos(self, watched: object, event: object) -> None:
        """Refresh the latest cursor position from an event or cursor fallback."""

        position = _global_event_position(event)
        if position is None:
            position = _watched_local_to_global(watched, event)
        self._cursor_global_pos = position or QCursor.pos()


def install_cursor_tooltip_filter(
    owner: QWidget,
    *watched_widgets: QWidget,
    show_delay_ms: int = 300,
    offset: QPoint | None = None,
    show_when_disabled: bool = False,
    tooltip_provider: TooltipProvider | None = None,
) -> CursorToolTipFilter:
    """Install an owner-backed tooltip filter across watched widgets.

    Args:
        owner: Widget that owns tooltip text and filter lifetime.
        *watched_widgets: Widgets whose hover events should show the owner tooltip.
        show_delay_ms: Hover delay before showing the QFluent tooltip.
        offset: Optional cursor-relative tooltip offset.
        show_when_disabled: Allow explanatory tooltips on disabled owner widgets.
        tooltip_provider: Optional event-aware source for dynamic tooltip text.
    """

    tooltip_filter = CursorToolTipFilter(
        owner,
        show_delay_ms=show_delay_ms,
        offset=offset,
        show_when_disabled=show_when_disabled,
        tooltip_provider=tooltip_provider,
    )
    targets = watched_widgets or (owner,)
    for widget in targets:
        _enable_mouse_tracking(widget)
        install_event_filter = getattr(widget, "installEventFilter", None)
        if callable(install_event_filter):
            install_event_filter(cast(Any, tooltip_filter))
    return tooltip_filter


def _screen_geometry(cursor_global_pos: QPoint) -> QRect:
    """Return the available screen geometry for a cursor position."""

    screen = QGuiApplication.screenAt(cursor_global_pos)
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    available_geometry = getattr(screen, "availableGeometry", None)
    if callable(available_geometry):
        return cast(QRect, available_geometry())
    return QRect(0, 0, 1920, 1080)


def _event_is(event: object, name: str) -> bool:
    """Return whether an event reports the named Qt type."""

    event_type = getattr(event, "type", None)
    if not callable(event_type):
        return False
    return bool(event_type() == _qt_event_type(name))


def _event_is_any(event: object, names: tuple[str, ...]) -> bool:
    """Return whether an event reports any of the named Qt types."""

    return any(_event_is(event, name) for name in names)


def _qt_event_type(name: str) -> object:
    """Return a QEvent type across Qt enum layouts and lightweight stubs."""

    type_namespace = getattr(QEvent, "Type", None)
    namespaced_value = getattr(type_namespace, name, None)
    if namespaced_value is not None:
        return namespaced_value
    return getattr(QEvent, name, name)


def _global_event_position(event: object) -> QPoint | None:
    """Return an event's global position when the Qt API exposes one."""

    global_position = getattr(event, "globalPosition", None)
    if callable(global_position):
        position = global_position()
        to_point = getattr(position, "toPoint", None)
        if callable(to_point):
            return cast(QPoint, to_point())
    global_pos = getattr(event, "globalPos", None)
    if callable(global_pos):
        return cast(QPoint, global_pos())
    return None


def _watched_local_to_global(watched: object, event: object) -> QPoint | None:
    """Map a local event position to global coordinates when possible."""

    position = getattr(event, "pos", None)
    map_to_global = getattr(watched, "mapToGlobal", None)
    if callable(position) and callable(map_to_global):
        return cast(QPoint, map_to_global(position()))
    return None


def _widget_tooltip(widget: object) -> str:
    """Return widget tooltip text when available."""

    tooltip = getattr(widget, "toolTip", None)
    if callable(tooltip):
        value = tooltip()
        if isinstance(value, str):
            return value
    return ""


def _widget_tooltip_duration(widget: object) -> int:
    """Return Qt tooltip duration, falling back to persistent QFluent display."""

    duration = getattr(widget, "toolTipDuration", None)
    if callable(duration):
        value = duration()
        if isinstance(value, int) and value > 0:
            return value
    return -1


def _widget_is_enabled(widget: object) -> bool:
    """Return whether a widget is enabled, defaulting to enabled for stubs."""

    is_enabled = getattr(widget, "isEnabled", None)
    if not callable(is_enabled):
        return True
    return bool(is_enabled())


def _configure_tooltip_bounds(tooltip: object) -> None:
    """Apply the application tooltip width contract to a QFluent tooltip."""

    _set_maximum_width(tooltip, _MAX_TOOLTIP_WIDTH_PX)
    container = getattr(tooltip, "container", None)
    container_width = _inner_width(
        _MAX_TOOLTIP_WIDTH_PX,
        _layout_horizontal_margins(_widget_layout(tooltip)),
    )
    if container is not None:
        _set_maximum_width(container, container_width)

    label = getattr(tooltip, "label", None)
    if label is None:
        return

    _set_word_wrap(label, True)
    label_width = _inner_width(
        container_width,
        _layout_horizontal_margins(getattr(tooltip, "containerLayout", None)),
    )
    _set_maximum_width(label, label_width)


def _inner_width(width: int, horizontal_margins: int) -> int:
    """Return a bounded content width after subtracting layout margins."""

    return max(_MIN_TOOLTIP_CONTENT_WIDTH_PX, width - horizontal_margins)


def _widget_layout(widget: object) -> object | None:
    """Return a widget layout when the object exposes Qt's layout method."""

    layout = getattr(widget, "layout", None)
    if not callable(layout):
        return None
    return cast(object | None, layout())


def _layout_horizontal_margins(layout: object | None) -> int:
    """Return left plus right layout margins for Qt or test doubles."""

    if layout is None:
        return 0
    contents_margins = getattr(layout, "contentsMargins", None)
    if not callable(contents_margins):
        return 0
    margins = contents_margins()
    left = getattr(margins, "left", None)
    right = getattr(margins, "right", None)
    if not callable(left) or not callable(right):
        return 0
    left_value = left()
    right_value = right()
    if not isinstance(left_value, int) or not isinstance(right_value, int):
        return 0
    return left_value + right_value


def _set_maximum_width(widget: object, width: int) -> None:
    """Set a maximum width when a Qt widget-like object supports it."""

    set_maximum_width = getattr(widget, "setMaximumWidth", None)
    if callable(set_maximum_width):
        set_maximum_width(width)


def _set_word_wrap(widget: object, enabled: bool) -> None:
    """Enable word wrapping when a label-like object supports it."""

    set_word_wrap = getattr(widget, "setWordWrap", None)
    if callable(set_word_wrap):
        set_word_wrap(enabled)


def _enable_mouse_tracking(widget: object) -> None:
    """Enable mouse tracking so cursor position updates before the tooltip shows."""

    set_mouse_tracking = getattr(widget, "setMouseTracking", None)
    if callable(set_mouse_tracking):
        set_mouse_tracking(True)


__all__ = [
    "CursorToolTipFilter",
    "TooltipProvider",
    "cursor_tooltip_position",
    "install_cursor_tooltip_filter",
]
