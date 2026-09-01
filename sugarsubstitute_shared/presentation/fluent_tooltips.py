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

"""Own every QFluent tooltip installed by SugarSubstitute presentation code."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeGuard, cast
from weakref import ReferenceType, ref

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import ToolTipFilter, ToolTipPosition  # type: ignore[import-untyped]
from shiboken6 import isValid

from sugarsubstitute_shared.presentation._fluent_tooltip_geometry import (
    DEFAULT_CURSOR_OFFSET,
    configure_tooltip_bounds,
    cursor_tooltip_position,
    event_global_position,
)

_FILTER_ATTRIBUTE = "_sugarsubstitute_fluent_tooltip_filter"
_DEFAULT_VISIBLE_DURATION_MS = 10_000
_HOVER_GUARD_INTERVAL_MS = 100


class ToolTipTarget(Protocol):
    """Describe an object exposing Qt's tooltip property."""

    def setToolTip(self, text: str) -> None:
        """Set tooltip text."""


ToolTipProvider = Callable[[object, object], str | None]


class _FluentToolTip(Protocol):
    """Describe the QFluent tooltip widget surface extended by this adapter."""

    def adjustSize(self) -> None:
        """Refresh tooltip geometry."""

    def size(self) -> QSize:
        """Return current tooltip size."""

    def move(self, position: QPoint) -> None:
        """Move the tooltip to a global position."""

    def setDuration(self, duration: int) -> None:  # noqa: N802
        """Set the maximum visible lifetime in milliseconds."""

    def setText(self, text: str) -> None:  # noqa: N802
        """Replace the displayed tooltip content."""


class FluentToolTipFilter(ToolTipFilter):  # type: ignore[misc]
    """Extend QFluent's filter with app-required cursor and dynamic behavior."""

    def __init__(
        self,
        owner: QWidget,
        *,
        show_delay_ms: int = 300,
        position: ToolTipPosition = ToolTipPosition.TOP,
        cursor_anchor: bool = False,
        cursor_offset: QPoint | None = None,
        show_when_disabled: bool = False,
        tooltip_provider: ToolTipProvider | None = None,
    ) -> None:
        """Configure one QFluent filter without creating a parallel tooltip widget."""

        super().__init__(owner, show_delay_ms, position)
        self._show_delay_ms = show_delay_ms
        self._cursor_anchor = cursor_anchor
        self._cursor_offset = cursor_offset or DEFAULT_CURSOR_OFFSET
        self._show_when_disabled = show_when_disabled
        self._tooltip_provider = tooltip_provider
        self._cursor_global_position = QCursor.pos()
        self._tooltip: _FluentToolTip | None = None
        self._watched_widget_ids: set[int] = set()
        self._watched_widget_refs: dict[int, ReferenceType[QWidget]] = {
            id(owner): ref(owner)
        }
        self._hovered_widget_ids: set[int] = set()
        self._hover_guard_timer = QTimer(self)
        self._hover_guard_timer.setInterval(_HOVER_GUARD_INTERVAL_MS)
        self._hover_guard_timer.timeout.connect(self._dismiss_if_pointer_outside)

    @property
    def show_delay_ms(self) -> int:
        """Return the configured QFluent hover delay in milliseconds."""

        return self._show_delay_ms

    def setToolTipDelay(self, delay: int) -> None:  # noqa: N802
        """Update QFluent's delay and the adapter's observable configuration."""

        self._show_delay_ms = delay
        super().setToolTipDelay(delay)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Own hover state without relying on QFluent's shared boolean flag."""

        event_type = event.type()
        if event_type in {
            QEvent.Type.Enter,
            QEvent.Type.MouseMove,
            QEvent.Type.ToolTip,
        }:
            self._cursor_global_position = event_global_position(watched, event)
            self._refresh_dynamic_tooltip(watched, event)
        if event_type == QEvent.Type.ToolTip:
            return True
        if event_type == QEvent.Type.Enter:
            self._enter_watched_widget(watched)
        elif event_type in {
            QEvent.Type.Close,
            QEvent.Type.Destroy,
            QEvent.Type.Hide,
            QEvent.Type.Leave,
        }:
            self._leave_watched_widget(watched)
        elif event_type in {
            QEvent.Type.MouseButtonPress,
            QEvent.Type.Wheel,
            QEvent.Type.WindowDeactivate,
        }:
            self.hideToolTip()
        return bool(QObject.eventFilter(self, watched, event))

    def showToolTip(self) -> None:  # noqa: N802
        """Show QFluent's tooltip and optionally move it beside the cursor."""

        if not self.isEnter or not self._canShowToolTip():
            return
        focused_widget = QApplication.focusWidget()
        if self._live_tooltip() is None and self._canShowToolTip():
            self._tooltip = self._createToolTip()
        super().showToolTip()
        if focused_widget is not None:
            focused_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            QTimer.singleShot(
                0,
                lambda focused_ref=ref(focused_widget): (
                    _restore_focus_after_tooltip_show(focused_ref)
                ),
            )
        tooltip = self._live_tooltip()
        if tooltip is None:
            return
        self._hover_guard_timer.start()
        configure_tooltip_bounds(tooltip)
        tooltip.adjustSize()
        if self._cursor_anchor:
            tooltip.move(
                cursor_tooltip_position(
                    cursor_global_pos=self._cursor_global_position,
                    tooltip_size=tooltip.size(),
                    offset=self._cursor_offset,
                )
            )

    def hideToolTip(self) -> None:  # noqa: N802
        """Dismiss visible and pending presentation and reset hover ownership."""

        self._hovered_widget_ids.clear()
        self._dismiss_tooltip()

    def hide_tooltip(self) -> None:
        """Expose the app's snake-case lifecycle API over QFluent."""

        self.hideToolTip()

    def show_tooltip(self) -> None:
        """Expose the app's snake-case display API over QFluent."""

        self.showToolTip()

    def _createToolTip(self) -> _FluentToolTip:  # noqa: N802
        """Create QFluent's tooltip and apply the shared wrapping contract."""

        tooltip = cast(_FluentToolTip, super()._createToolTip())
        tooltip_widget = cast(QWidget, tooltip)
        tooltip_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tooltip_widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        tooltip_widget.setWindowFlag(
            Qt.WindowType.WindowDoesNotAcceptFocus,
            True,
        )
        configure_tooltip_bounds(tooltip)
        return tooltip

    def _canShowToolTip(self) -> bool:  # noqa: N802
        """Allow explicitly configured explanatory help on disabled controls."""

        owner = cast(QWidget, self.parent())
        return bool(
            owner.isWidgetType()
            and owner.toolTip()
            and (owner.isEnabled() or self._show_when_disabled)
        )

    def _refresh_dynamic_tooltip(self, watched: QObject, event: QEvent) -> None:
        """Resolve event-aware content through the single tooltip property owner."""

        if self._tooltip_provider is None:
            return
        owner = cast(QWidget, self.parent())
        set_fluent_tooltip_text(owner, self._tooltip_provider(watched, event) or "")

    def _enter_watched_widget(self, watched: QObject) -> None:
        """Start or retain presentation when one installed target is entered."""

        watched_id = id(watched)
        self._hovered_widget_ids.add(watched_id)
        self.isEnter = True
        self._schedule_tooltip_show()

    def _schedule_tooltip_show(self) -> None:
        """Create and schedule tooltip presentation for the current content."""

        if not self._canShowToolTip():
            return
        if self._live_tooltip() is None:
            self._tooltip = self._createToolTip()
        owner = cast(QWidget, self.parent())
        tooltip = self._live_tooltip()
        if tooltip is None:
            return
        configured_duration = owner.toolTipDuration()
        tooltip.setDuration(
            configured_duration
            if configured_duration > 0
            else _DEFAULT_VISIBLE_DURATION_MS
        )
        self.timer.start(self._show_delay_ms)

    def _leave_watched_widget(self, watched: QObject) -> None:
        """Dismiss only after the pointer has left every installed target."""

        self._hovered_widget_ids.discard(id(watched))
        self.isEnter = bool(self._hovered_widget_ids)
        if not self.isEnter:
            self._dismiss_tooltip()

    def _dismiss_tooltip(self) -> None:
        """Stop every presentation timer and hide the shared tooltip window."""

        self._hover_guard_timer.stop()
        self._live_tooltip()
        super().hideToolTip()
        self.isEnter = bool(self._hovered_widget_ids)

    def _live_tooltip(self) -> _FluentToolTip | None:
        """Return the tooltip only while its platform-owned Qt object survives."""

        tooltip = self._tooltip
        if tooltip is None or isValid(tooltip):
            return tooltip
        self._tooltip = None
        return None

    def _tooltip_text_changed(self, text: str, *, changed: bool) -> None:
        """Synchronize visible and pending presentation with owner text changes."""

        tooltip = self._live_tooltip()
        if not text:
            self._dismiss_tooltip()
            return
        if tooltip is not None:
            tooltip.setText(text)
            configure_tooltip_bounds(tooltip)
            tooltip.adjustSize()
        if changed and self._hovered_widget_ids:
            self._schedule_tooltip_show()

    def _dismiss_if_pointer_outside(self) -> None:
        """Recover when a platform transition omits the expected leave event."""

        cursor_position = QCursor.pos()
        if any(
            self._widget_contains_global_position(watched_id, cursor_position)
            for watched_id in tuple(self._hovered_widget_ids)
        ):
            return
        self.hideToolTip()

    def _widget_contains_global_position(
        self,
        watched_id: int,
        global_position: QPoint,
    ) -> bool:
        """Return whether one live, visible target contains a global position."""

        watched_ref = self._watched_widget_refs.get(watched_id)
        watched = watched_ref() if watched_ref is not None else None
        if watched is None:
            return False
        try:
            return watched.isVisible() and watched.rect().contains(
                watched.mapFromGlobal(global_position)
            )
        except RuntimeError:
            self._forget_watched_widget(watched_id)
            return False

    def _remember_watched_widget(self, watched: QWidget) -> None:
        """Retain a weak target reference for hover validity checks."""

        self._watched_widget_refs[id(watched)] = ref(watched)

    def _forget_watched_widget(self, watched_id: int) -> None:
        """Release one destroyed widget identity from idempotent installation state."""

        self._watched_widget_ids.discard(watched_id)
        self._watched_widget_refs.pop(watched_id, None)
        self._hovered_widget_ids.discard(watched_id)
        self.isEnter = bool(self._hovered_widget_ids)
        if not self.isEnter:
            self._dismiss_tooltip()


def set_fluent_tooltip_text(target: ToolTipTarget, text: str) -> None:
    """Set tooltip text and ensure QWidget targets use QFluent presentation."""

    if isinstance(target, QWidget):
        rendered_text = str(text)
        text_changed = target.toolTip() != rendered_text
        QWidget.setToolTip(target, rendered_text)
        existing_filter = getattr(target, _FILTER_ATTRIBUTE, None)
        if isinstance(existing_filter, FluentToolTipFilter):
            existing_filter._tooltip_text_changed(
                rendered_text,
                changed=text_changed,
            )
        elif rendered_text:
            ensure_fluent_tooltip_filter(target)
        return
    target.setToolTip(str(text))


def supports_fluent_tooltip(target: object) -> TypeGuard[ToolTipTarget]:
    """Return whether an object can receive text through the tooltip owner."""

    return callable(getattr(target, "setToolTip", None))


def ensure_fluent_tooltip_filter(
    owner: QWidget,
    *watched_widgets: QWidget,
    show_delay_ms: int = 300,
    position: ToolTipPosition = ToolTipPosition.TOP,
    cursor_anchor: bool = False,
    cursor_offset: QPoint | None = None,
    show_when_disabled: bool = False,
    tooltip_provider: ToolTipProvider | None = None,
) -> FluentToolTipFilter:
    """Return and configure the sole QFluent tooltip filter for one owner."""

    existing = getattr(owner, _FILTER_ATTRIBUTE, None)
    if isinstance(existing, FluentToolTipFilter):
        tooltip_filter = existing
        tooltip_filter.setToolTipDelay(show_delay_ms)
        tooltip_filter.position = position
        tooltip_filter._cursor_anchor = cursor_anchor
        tooltip_filter._cursor_offset = cursor_offset or DEFAULT_CURSOR_OFFSET
        tooltip_filter._show_when_disabled = show_when_disabled
        tooltip_filter._tooltip_provider = tooltip_provider
    else:
        tooltip_filter = FluentToolTipFilter(
            owner,
            show_delay_ms=show_delay_ms,
            position=position,
            cursor_anchor=cursor_anchor,
            cursor_offset=cursor_offset,
            show_when_disabled=show_when_disabled,
            tooltip_provider=tooltip_provider,
        )
        setattr(owner, _FILTER_ATTRIBUTE, tooltip_filter)
    for watched in watched_widgets or (owner,):
        watched.setMouseTracking(cursor_anchor or tooltip_provider is not None)
        watched_id = id(watched)
        tooltip_filter._remember_watched_widget(watched)
        if watched_id not in tooltip_filter._watched_widget_ids:
            watched.installEventFilter(tooltip_filter)
            tooltip_filter._watched_widget_ids.add(watched_id)
            watched.destroyed.connect(
                lambda _object=None, watched_id=watched_id: (
                    tooltip_filter._forget_watched_widget(watched_id)
                )
            )
    return tooltip_filter


def release_fluent_tooltips(root: QWidget) -> None:
    """Release tooltip windows before their surviving controls are reparented."""

    for tooltip_filter in root.findChildren(FluentToolTipFilter):
        tooltip = tooltip_filter._tooltip
        if tooltip is None:
            continue
        try:
            tooltip_filter.hideToolTip()
        except RuntimeError as error:
            if "already deleted" not in str(error):
                raise
        tooltip_filter._tooltip = None


def _restore_focus_after_tooltip_show(
    focused_ref: ReferenceType[QWidget],
) -> None:
    """Restore editor focus after backends that activate tooltip windows."""

    focused_widget = focused_ref()
    if focused_widget is None:
        return
    try:
        if not focused_widget.hasFocus():
            focused_widget.window().activateWindow()
            focused_widget.setFocus(Qt.FocusReason.OtherFocusReason)
    except RuntimeError:
        return


__all__ = [
    "FluentToolTipFilter",
    "ToolTipPosition",
    "ToolTipProvider",
    "ToolTipTarget",
    "cursor_tooltip_position",
    "ensure_fluent_tooltip_filter",
    "set_fluent_tooltip_text",
    "supports_fluent_tooltip",
]
