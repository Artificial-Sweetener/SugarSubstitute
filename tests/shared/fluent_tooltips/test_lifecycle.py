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

"""Verify Fluent tooltip filters cannot retain deleted floating-window children."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    release_fluent_tooltips,
    set_fluent_tooltip_text,
)
from tests.support.qt.lifecycle import destroy_qt_object


class _Tooltip:
    """Record the hide operation expected before an ancestor window closes."""

    def __init__(self) -> None:
        """Initialize visible semantic state."""

        self.hidden = False

    def hide(self) -> None:
        """Record Fluent's public hide call."""

        self.hidden = True


@pytest.fixture
def tooltip_control(qt_application_owner: QApplication) -> Iterator[QWidget]:
    """Yield a tooltip control with a fixture-managed Qt lifetime."""

    control = QWidget()
    try:
        yield control
    finally:
        destroy_qt_object(control)


def test_release_fluent_tooltips_invalidates_surviving_filter_window(
    tooltip_control: QWidget,
) -> None:
    """A redocked control should create a new tooltip in its new window."""

    set_fluent_tooltip_text(tooltip_control, "Tooltip")
    tooltip_filter = tooltip_control.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    tooltip = _Tooltip()
    setattr(tooltip_filter, "_tooltip", tooltip)

    release_fluent_tooltips(tooltip_control)

    assert tooltip.hidden
    assert getattr(tooltip_filter, "_tooltip", None) is None


def test_final_owner_event_tolerates_platform_deleted_tooltip(
    tooltip_control: QWidget,
) -> None:
    """Owner teardown must remain safe when Qt deletes its tooltip window first."""

    set_fluent_tooltip_text(tooltip_control, "Tooltip")
    tooltip_filter = tooltip_control.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    tooltip_filter.isEnter = True
    tooltip_filter.show_tooltip()
    tooltip = cast(QWidget, tooltip_filter._tooltip)
    delete(tooltip)
    assert not isValid(tooltip)

    tooltip_filter.eventFilter(
        tooltip_control,
        QEvent(QEvent.Type.Hide),
    )

    assert tooltip_filter._tooltip is None
    assert tooltip_filter.isEnter is False


def test_owner_teardown_tolerates_platform_deleted_tooltip_timers(
    tooltip_control: QWidget,
) -> None:
    """Late owner callbacks must tolerate Qt deleting both timers first."""

    set_fluent_tooltip_text(tooltip_control, "Tooltip")
    tooltip_filter = tooltip_control.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    hover_guard_timer = tooltip_filter._hover_guard_timer
    assert hover_guard_timer is not None
    show_timer = tooltip_filter.timer
    delete(hover_guard_timer)
    delete(show_timer)
    assert not isValid(hover_guard_timer)
    assert not isValid(show_timer)

    tooltip_filter.eventFilter(
        tooltip_control,
        QEvent(QEvent.Type.Destroy),
    )

    assert tooltip_filter.isEnter is False
