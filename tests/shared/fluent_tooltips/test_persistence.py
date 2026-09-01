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

"""Prove QFluent tooltips cannot persist after their hover relationship ends."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, QPoint, QSize
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QWidget

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    ensure_fluent_tooltip_filter,
    set_fluent_tooltip_text,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _TooltipProbe:
    """Record presentation state without relying on a native tooltip window."""

    def __init__(self) -> None:
        """Initialize hidden content with Qt's automatic duration sentinel."""

        self.duration = -1
        self.hidden = False
        self.shown = False
        self.text = ""

    def setDuration(self, duration: int) -> None:  # noqa: N802
        """Record the configured maximum visible lifetime."""

        self.duration = duration

    def setText(self, text: str) -> None:  # noqa: N802
        """Record the current tooltip content."""

        self.text = text

    def adjustPos(self, _owner: QWidget, _position: object) -> None:  # noqa: N802
        """Accept QFluent's owner-relative positioning pass."""

    def adjustSize(self) -> None:  # noqa: N802
        """Accept the shared bounded-size pass."""

    def size(self) -> QSize:
        """Return deterministic geometry for cursor positioning."""

        return QSize(120, 40)

    def move(self, _position: QPoint) -> None:
        """Accept cursor-relative positioning."""

    def show(self) -> None:
        """Record visible presentation."""

        self.shown = True
        self.hidden = False

    def hide(self) -> None:
        """Record dismissed presentation."""

        self.hidden = True
        self.shown = False


class _GlobalPositionEvent(QEvent):
    """Expose a deterministic Qt 6 global pointer position."""

    def __init__(self, event_type: QEvent.Type, global_position: QPoint) -> None:
        """Store the requested type and global position."""

        super().__init__(event_type)
        self._global_position = global_position

    def globalPosition(self) -> object:  # noqa: N802
        """Return a QPointF-like object accepted by the tooltip owner."""

        return type(
            "_PointF",
            (),
            {"toPoint": lambda _self: self._global_position},
        )()


def _enter(position: QPoint) -> _GlobalPositionEvent:
    """Create one deterministic enter event."""

    return _GlobalPositionEvent(QEvent.Type.Enter, position)


def _leave(position: QPoint) -> _GlobalPositionEvent:
    """Create one deterministic leave event."""

    return _GlobalPositionEvent(QEvent.Type.Leave, position)


def test_nested_target_transition_keeps_tooltip_until_all_targets_are_left(
    qt_application_owner: QApplication,
) -> None:
    """Parent leave ordering must not dismiss or strand a child hover."""

    _ = qt_application_owner
    owner = QWidget()
    watched = QWidget(owner)
    owner.setToolTip("details")
    tooltip = _TooltipProbe()
    tooltip_filter = ensure_fluent_tooltip_filter(
        owner, owner, watched, show_delay_ms=0
    )
    tooltip_filter._tooltip = tooltip
    try:
        tooltip_filter.eventFilter(owner, _enter(QPoint(50, 60)))
        tooltip_filter.show_tooltip()
        tooltip_filter.eventFilter(watched, _enter(QPoint(51, 61)))
        tooltip_filter.eventFilter(owner, _leave(QPoint(51, 61)))

        assert tooltip.shown is True
        assert tooltip_filter.isEnter is True

        tooltip_filter.eventFilter(watched, _leave(QPoint(52, 62)))

        assert tooltip.hidden is True
        assert tooltip_filter.isEnter is False
    finally:
        destroy_qt_object(owner)


def test_default_qt_duration_becomes_a_finite_tooltip_lifetime(
    qt_application_owner: QApplication,
) -> None:
    """Qt's automatic duration sentinel must not create an immortal tooltip."""

    _ = qt_application_owner
    owner = QWidget()
    owner.setToolTip("details")
    tooltip = _TooltipProbe()
    tooltip_filter = ensure_fluent_tooltip_filter(owner, show_delay_ms=0)
    tooltip_filter._tooltip = tooltip
    try:
        tooltip_filter.eventFilter(owner, _enter(QPoint(50, 60)))

        assert owner.toolTipDuration() == -1
        assert tooltip.duration > 0
    finally:
        destroy_qt_object(owner)


def test_clearing_tooltip_text_immediately_dismisses_visible_content(
    qt_application_owner: QApplication,
) -> None:
    """Recycled controls must not retain tooltip content from prior state."""

    _ = qt_application_owner
    owner = QWidget()
    set_fluent_tooltip_text(owner, "details")
    tooltip_filter = owner.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    tooltip = _TooltipProbe()
    tooltip.shown = True
    tooltip_filter._tooltip = tooltip
    try:
        set_fluent_tooltip_text(owner, "")

        assert owner.toolTip() == ""
        assert tooltip.hidden is True
    finally:
        destroy_qt_object(owner)


def test_empty_tooltip_text_does_not_install_inert_presentation(
    qt_application_owner: QApplication,
) -> None:
    """Clearing child content must not create competing tooltip filters."""

    _ = qt_application_owner
    owner = QWidget()
    try:
        set_fluent_tooltip_text(owner, "")

        assert owner.findChild(FluentToolTipFilter) is None
    finally:
        destroy_qt_object(owner)


def test_dynamic_content_can_resume_during_one_viewport_hover(
    qt_application_owner: QApplication,
) -> None:
    """An empty dynamic region must not discard the surrounding hover session."""

    _ = qt_application_owner
    owner = QWidget()
    set_fluent_tooltip_text(owner, "first item")
    tooltip_filter = owner.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    tooltip = _TooltipProbe()
    tooltip_filter._tooltip = tooltip
    try:
        tooltip_filter.eventFilter(owner, _enter(QPoint(50, 60)))
        tooltip_filter.show_tooltip()
        assert tooltip.shown is True

        set_fluent_tooltip_text(owner, "")

        assert tooltip.hidden is True
        assert tooltip_filter.isEnter is True

        set_fluent_tooltip_text(owner, "second item")
        tooltip_filter.show_tooltip()

        assert tooltip.shown is True
        assert tooltip.text == "second item"
    finally:
        destroy_qt_object(owner)


def test_visible_tooltip_self_dismisses_when_leave_delivery_is_lost(
    qt_application_owner: QApplication,
) -> None:
    """A visible tooltip must recover when the platform omits a leave event."""

    _ = qt_application_owner
    original_cursor_position = QCursor.pos()
    owner = QWidget()
    owner.setGeometry(100, 100, 120, 60)
    owner.show()
    owner.setToolTip("details")
    tooltip = _TooltipProbe()
    tooltip_filter = ensure_fluent_tooltip_filter(
        owner,
        show_delay_ms=0,
        cursor_anchor=True,
    )
    tooltip_filter._tooltip = tooltip
    try:
        inside = owner.mapToGlobal(owner.rect().center())
        QCursor.setPos(inside)
        tooltip_filter.eventFilter(owner, _enter(inside))
        tooltip_filter.show_tooltip()
        assert tooltip.shown is True

        QCursor.setPos(owner.mapToGlobal(QPoint(owner.width() + 40, 0)))

        wait_for_qt_condition(
            lambda: tooltip.hidden,
            timeout_ms=500,
            description="tooltip self-dismissal after a lost leave event",
            state=lambda: {
                "cursor": QCursor.pos(),
                "owner_rect": owner.rect(),
                "tooltip_shown": tooltip.shown,
            },
        )
    finally:
        QCursor.setPos(original_cursor_position)
        destroy_qt_object(owner)


def test_real_tooltip_window_recovers_from_lost_leave_delivery_headlessly(
    qt_application_owner: QApplication,
) -> None:
    """The mounted QFluent window must disappear without a delivered leave event."""

    _ = qt_application_owner
    original_cursor_position = QCursor.pos()
    owner = QWidget()
    owner.setGeometry(100, 100, 120, 60)
    owner.show()
    set_fluent_tooltip_text(owner, "real tooltip")
    tooltip_filter = owner.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    try:
        inside = owner.mapToGlobal(owner.rect().center())
        QCursor.setPos(inside)
        tooltip_filter.eventFilter(owner, _enter(inside))
        tooltip_filter.show_tooltip()
        tooltip = cast(QWidget, tooltip_filter._tooltip)
        assert tooltip.isVisible()

        QCursor.setPos(owner.mapToGlobal(QPoint(owner.width() + 40, 0)))

        wait_for_qt_condition(
            lambda: not tooltip.isVisible(),
            timeout_ms=500,
            description="real QFluent tooltip self-dismissal",
        )
    finally:
        QCursor.setPos(original_cursor_position)
        destroy_qt_object(owner)
