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

"""Tests for the application-owned QFluent tooltip adapter."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QApplication, QWidget

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    cursor_tooltip_position,
    ensure_fluent_tooltip_filter,
)


@pytest.fixture(autouse=True)
def _qapp() -> QApplication:
    """Ensure QWidget tests have a QApplication."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


class _Owner(QWidget):
    """Small widget exposing deterministic tooltip state."""

    def __init__(self) -> None:
        """Create an owner with inspectable filter installs."""

        super().__init__()
        self.filters: list[object] = []

    def installEventFilter(self, event_filter: object) -> None:  # noqa: N802
        """Record filter installation before delegating to Qt."""

        self.filters.append(event_filter)
        super().installEventFilter(cast(Any, event_filter))


class _Watched(QWidget):
    """Small watched widget with inspectable filter installs."""

    def __init__(self) -> None:
        """Create a watched target with inspectable filter installs."""

        super().__init__()
        self.filters: list[object] = []

    def installEventFilter(self, event_filter: object) -> None:  # noqa: N802
        """Record filter installation before delegating to Qt."""

        self.filters.append(event_filter)
        super().installEventFilter(cast(Any, event_filter))


class _Tooltip:
    """Tooltip stand-in used to verify positioning side effects."""

    def __init__(self, size: QSize = QSize(120, 40)) -> None:
        """Create a tooltip with deterministic size."""

        self.text = ""
        self.duration = 0
        self.hidden = False
        self.shown = False
        self.position = QPoint()
        self._size = size
        self.maximum_width: int | None = None
        self.label = _TooltipLabel()
        self.container = _TooltipContainer()
        self.containerLayout = _TooltipLayout(8, 8)
        self._layout = _TooltipLayout(12, 12)

    def setText(self, text: str) -> None:  # noqa: N802
        """Record tooltip text."""

        self.text = text

    def setDuration(self, duration: int) -> None:  # noqa: N802
        """Record tooltip duration."""

        self.duration = duration

    def adjustSize(self) -> None:  # noqa: N802
        """Accept size adjustment."""

        if self.maximum_width is not None and self._size.width() > self.maximum_width:
            self._size = QSize(self.maximum_width, self._size.height())

    def size(self) -> QSize:
        """Return tooltip size."""

        return self._size

    def move(self, position: QPoint) -> None:
        """Record tooltip position."""

        self.position = position

    def adjustPos(self, _owner: QWidget, _position: object) -> None:  # noqa: N802
        """Accept QFluent's normal owner-relative positioning pass."""

    def show(self) -> None:
        """Record show call."""

        self.shown = True
        self.hidden = False

    def hide(self) -> None:
        """Record hide call."""

        self.hidden = True
        self.shown = False

    def setMaximumWidth(self, width: int) -> None:  # noqa: N802
        """Record the applied tooltip width clamp."""

        self.maximum_width = width

    def layout(self) -> "_TooltipLayout":
        """Return a layout double with QFluent tooltip margins."""

        return self._layout


class _TooltipLabel:
    """QLabel stand-in with inspectable wrapping configuration."""

    def __init__(self) -> None:
        """Create an unwrapped label double."""

        self.word_wrap = False
        self.maximum_width: int | None = None

    def setWordWrap(self, enabled: bool) -> None:  # noqa: N802
        """Record word-wrap state."""

        self.word_wrap = enabled

    def setMaximumWidth(self, width: int) -> None:  # noqa: N802
        """Record the label width clamp."""

        self.maximum_width = width


class _TooltipContainer:
    """Container stand-in with inspectable width configuration."""

    def __init__(self) -> None:
        """Create a container double."""

        self.maximum_width: int | None = None

    def setMaximumWidth(self, width: int) -> None:  # noqa: N802
        """Record the container width clamp."""

        self.maximum_width = width


class _TooltipLayout:
    """Layout stand-in exposing horizontal contents margins."""

    def __init__(self, left: int, right: int) -> None:
        """Store left and right margins."""

        self._margins = _TooltipMargins(left, right)

    def contentsMargins(self) -> "_TooltipMargins":  # noqa: N802
        """Return deterministic margins."""

        return self._margins


class _TooltipMargins:
    """Margins stand-in exposing left and right values."""

    def __init__(self, left: int, right: int) -> None:
        """Store margin values."""

        self._left = left
        self._right = right

    def left(self) -> int:
        """Return left margin."""

        return self._left

    def right(self) -> int:
        """Return right margin."""

        return self._right


class _GlobalPositionEvent(QEvent):
    """Event double exposing Qt 6 globalPosition."""

    def __init__(self, event_type: QEvent.Type, global_pos: QPoint) -> None:
        """Store event type and global position."""

        super().__init__(event_type)
        self._global_pos = global_pos

    def globalPosition(self) -> object:  # noqa: N802
        """Return a QPointF-like object with toPoint()."""

        return type(
            "_PointF",
            (),
            {"toPoint": lambda _self: self._global_pos},
        )()


def test_cursor_tooltip_position_offsets_from_cursor() -> None:
    """Tooltip position should start from cursor plus the configured offset."""

    position = cursor_tooltip_position(
        cursor_global_pos=QPoint(20, 30),
        tooltip_size=QSize(100, 40),
        offset=QPoint(10, 15),
        screen_geometry=QRect(0, 0, 500, 400),
    )

    assert position == QPoint(30, 45)


def test_cursor_tooltip_position_clamps_right_and_bottom_edges() -> None:
    """Tooltip position should stay inside the screen near far edges."""

    position = cursor_tooltip_position(
        cursor_global_pos=QPoint(490, 390),
        tooltip_size=QSize(100, 40),
        offset=QPoint(14, 18),
        screen_geometry=QRect(0, 0, 500, 400),
    )

    assert position == QPoint(395, 355)


def test_cursor_tooltip_position_clamps_left_and_top_edges() -> None:
    """Tooltip position should stay inside the screen near near edges."""

    position = cursor_tooltip_position(
        cursor_global_pos=QPoint(-50, -20),
        tooltip_size=QSize(100, 40),
        offset=QPoint(0, 0),
        screen_geometry=QRect(10, 20, 500, 400),
    )

    assert position == QPoint(10, 20)


def test_fluent_tooltip_filter_uses_one_owner_filter_for_targets() -> None:
    """The installer should share one owner-backed filter across watched widgets."""

    owner = _Owner()
    watched = _Watched()

    tooltip_filter = ensure_fluent_tooltip_filter(
        owner,
        owner,
        watched,
        show_delay_ms=25,
    )

    assert isinstance(tooltip_filter, FluentToolTipFilter)
    assert owner.filters == [tooltip_filter]
    assert watched.filters == [tooltip_filter]

    repeated = ensure_fluent_tooltip_filter(
        owner,
        owner,
        watched,
        show_delay_ms=25,
    )

    assert repeated is tooltip_filter
    assert owner.filters == [tooltip_filter]
    assert watched.filters == [tooltip_filter]


def test_dynamic_tooltip_text_does_not_reset_specialized_filter_policy() -> None:
    """Refreshing content must retain cursor anchoring and provider ownership."""

    owner = _Owner()

    def provider(_watched: object, _event: object) -> str:
        """Return stable dynamic tooltip text for the filter contract."""

        return "dynamic details"

    tooltip_filter = ensure_fluent_tooltip_filter(
        owner,
        cursor_anchor=True,
        show_when_disabled=True,
        tooltip_provider=provider,
    )

    tooltip_filter._refresh_dynamic_tooltip(
        owner,
        QEvent(QEvent.Type.MouseMove),
    )

    assert owner.toolTip() == "dynamic details"
    assert tooltip_filter._cursor_anchor is True
    assert tooltip_filter._show_when_disabled is True
    assert tooltip_filter._tooltip_provider is provider
    assert owner.filters == [tooltip_filter]


def test_fluent_tooltip_filter_shows_tooltip_at_event_cursor_position() -> None:
    """The filter should display tooltip text beside the latest cursor position."""

    owner = _Owner()
    owner.setToolTip("details")
    tooltip = _Tooltip()
    tooltip_filter = FluentToolTipFilter(
        owner,
        show_delay_ms=0,
        cursor_anchor=True,
        cursor_offset=QPoint(5, 6),
    )
    tooltip_filter._tooltip = tooltip

    event = _GlobalPositionEvent(QEvent.Type.Enter, QPoint(50, 60))

    assert tooltip_filter.eventFilter(owner, event) is False
    tooltip_filter.show_tooltip()

    assert tooltip.text == "details"
    assert tooltip.position == QPoint(55, 66)
    assert tooltip.shown is True


def test_fluent_tooltip_filter_clamps_qfluent_tooltip_width() -> None:
    """The filter should bound and wrap the QFluent tooltip before positioning."""

    owner = _Owner()
    owner.setToolTip("x" * 800)
    tooltip = _Tooltip(QSize(900, 40))
    tooltip_filter = FluentToolTipFilter(
        owner,
        show_delay_ms=0,
        cursor_anchor=True,
        cursor_offset=QPoint(5, 6),
    )
    tooltip_filter._tooltip = tooltip

    event = _GlobalPositionEvent(QEvent.Type.Enter, QPoint(50, 60))

    assert tooltip_filter.eventFilter(owner, event) is False
    tooltip_filter.show_tooltip()

    assert tooltip.maximum_width == 420
    assert tooltip.container.maximum_width == 396
    assert tooltip.label.word_wrap is True
    assert tooltip.label.maximum_width == 380
    assert tooltip.size().width() == 420


def test_fluent_tooltip_filter_suppresses_native_tooltip_event() -> None:
    """Native tooltip events should not create a second Qt tooltip."""

    owner = _Owner()
    tooltip_filter = FluentToolTipFilter(owner)
    event = _GlobalPositionEvent(QEvent.Type.ToolTip, QPoint(50, 60))

    assert tooltip_filter.eventFilter(owner, event) is True


def test_fluent_tooltip_window_never_accepts_or_steals_focus() -> None:
    """QFluent help must remain non-activating while users edit text."""

    owner = _Owner()
    owner.setToolTip("details")
    tooltip_filter = FluentToolTipFilter(owner)

    tooltip = cast(QWidget, tooltip_filter._createToolTip())

    assert tooltip.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert tooltip.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert tooltip.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    tooltip.close()


def test_fluent_tooltip_filter_hides_on_dismissal_events() -> None:
    """Dismissal events should stop pending display and hide visible tooltip."""

    owner = _Owner()
    tooltip = _Tooltip()
    tooltip.shown = True
    tooltip_filter = FluentToolTipFilter(owner)
    tooltip_filter._tooltip = tooltip

    event = _GlobalPositionEvent(QEvent.Type.Leave, QPoint(50, 60))

    assert tooltip_filter.eventFilter(owner, event) is False
    assert tooltip.hidden is True


def test_fluent_tooltip_filter_does_not_show_without_tooltip_text() -> None:
    """An empty owner tooltip should prevent display."""

    owner = _Owner()
    tooltip = _Tooltip()
    tooltip_filter = FluentToolTipFilter(owner)
    tooltip_filter._tooltip = tooltip

    tooltip_filter.show_tooltip()

    assert tooltip.shown is False


def test_fluent_tooltip_filter_skips_disabled_owner_by_default() -> None:
    """Disabled owner widgets should keep the existing no-tooltip default."""

    owner = _Owner()
    owner.setToolTip("disabled details")
    owner.setEnabled(False)
    tooltip = _Tooltip()
    tooltip_filter = FluentToolTipFilter(owner, show_delay_ms=0)
    tooltip_filter._tooltip = tooltip

    event = _GlobalPositionEvent(QEvent.Type.Enter, QPoint(50, 60))

    assert tooltip_filter.eventFilter(owner, event) is False
    tooltip_filter.show_tooltip()

    assert tooltip.shown is False


def test_fluent_tooltip_filter_can_show_disabled_owner_tooltip() -> None:
    """Opted-in disabled owner widgets should still show explanatory tooltips."""

    owner = _Owner()
    owner.setToolTip("disabled details")
    owner.setEnabled(False)
    tooltip = _Tooltip()
    tooltip_filter = FluentToolTipFilter(
        owner,
        show_delay_ms=0,
        cursor_anchor=True,
        cursor_offset=QPoint(5, 6),
        show_when_disabled=True,
    )
    tooltip_filter._tooltip = tooltip

    event = _GlobalPositionEvent(QEvent.Type.Enter, QPoint(50, 60))

    assert tooltip_filter.eventFilter(owner, event) is False
    tooltip_filter.show_tooltip()

    assert tooltip.text == "disabled details"
    assert tooltip.position == QPoint(55, 66)
    assert tooltip.shown is True


def test_fluent_tooltip_filter_preserves_disabled_owner_opt_in() -> None:
    """The installer should pass disabled-tooltip ownership into the filter."""

    owner = _Owner()

    tooltip_filter = ensure_fluent_tooltip_filter(
        owner,
        show_when_disabled=True,
    )

    assert tooltip_filter._show_when_disabled is True
