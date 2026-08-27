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

"""Tests for shared QFluent scroll interaction policy."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (  # type: ignore[import-untyped]
    PlainTextEdit,
    ScrollArea,
    SingleDirectionScrollArea,
)
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
    disable_qfluent_smooth_scrolling,
)
from tests.support.qt.lifecycle import destroy_qt_object


class _GeometryLike(Protocol):
    """Describe QRect methods used by scrollbar geometry assertions."""

    def x(self) -> int:
        """Return the rectangle x coordinate."""

    def y(self) -> int:
        """Return the rectangle y coordinate."""

    def width(self) -> int:
        """Return the rectangle width."""

    def height(self) -> int:
        """Return the rectangle height."""


class _ScrollBarLike(Protocol):
    """Describe scrollbar methods used by geometry assertions."""

    def geometry(self) -> _GeometryLike:
        """Return the scrollbar geometry."""


class _ScrollOwnerLike(Protocol):
    """Describe owning widget dimensions used by geometry assertions."""

    def width(self) -> int:
        """Return the owner width."""

    def height(self) -> int:
        """Return the owner height."""


@pytest.fixture
def scroll_area(qt_application_owner: QApplication) -> Iterator[ScrollArea]:
    """Yield a QFluent scroll area with a fixture-managed Qt lifetime."""

    widget = ScrollArea()
    try:
        yield widget
    finally:
        destroy_qt_object(widget)


@pytest.fixture
def text_edit(qt_application_owner: QApplication) -> Iterator[PlainTextEdit]:
    """Yield a QFluent text editor with a fixture-managed Qt lifetime."""

    widget = PlainTextEdit()
    try:
        yield widget
    finally:
        destroy_qt_object(widget)


@pytest.fixture
def single_direction_area(
    qt_application_owner: QApplication,
) -> Iterator[SingleDirectionScrollArea]:
    """Yield a horizontal QFluent area with a fixture-managed Qt lifetime."""

    widget = SingleDirectionScrollArea(orient=Qt.Orientation.Horizontal)
    try:
        yield widget
    finally:
        destroy_qt_object(widget)


def test_disable_qfluent_smooth_scrolling_handles_scroll_area_delegate(
    scroll_area: ScrollArea,
) -> None:
    """QFluent ScrollArea should keep chrome but use immediate wheel handling."""

    disable_qfluent_smooth_scrolling(scroll_area)

    scroll_delegate = scroll_area.scrollDelagate
    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0


def test_configure_qfluent_scroll_surface_places_scroll_area_chrome_like_editor(
    scroll_area: ScrollArea,
) -> None:
    """QFluent ScrollArea chrome should sit at the editor panel's relative edge."""

    scroll_area.resize(320, 240)

    configure_qfluent_scroll_surface(scroll_area)

    _assert_editor_vertical_scrollbar_geometry(
        scroll_area.scrollDelagate.vScrollBar,
        scroll_area,
    )
    _assert_editor_horizontal_scrollbar_geometry(
        scroll_area.scrollDelagate.hScrollBar,
        scroll_area,
    )


def test_disable_qfluent_smooth_scrolling_handles_text_edit_delegate(
    text_edit: PlainTextEdit,
) -> None:
    """QFluent text edits should use the same no-smooth wheel policy."""

    disable_qfluent_smooth_scrolling(text_edit)

    scroll_delegate = text_edit.scrollDelegate
    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0


def test_configure_qfluent_scroll_surface_places_text_edit_chrome_like_editor(
    text_edit: PlainTextEdit,
) -> None:
    """QFluent text-edit chrome should use editor panel edge positioning."""

    text_edit.resize(360, 180)

    configure_qfluent_scroll_surface(text_edit)

    _assert_editor_vertical_scrollbar_geometry(
        text_edit.scrollDelegate.vScrollBar,
        text_edit,
    )
    _assert_editor_horizontal_scrollbar_geometry(
        text_edit.scrollDelegate.hScrollBar,
        text_edit,
    )


def test_disable_qfluent_smooth_scrolling_handles_single_direction_area(
    single_direction_area: SingleDirectionScrollArea,
) -> None:
    """Single-direction QFluent scroll areas should keep scrolling without smoothing."""

    disable_qfluent_smooth_scrolling(single_direction_area)

    assert single_direction_area.smoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert single_direction_area.vScrollBar.duration == 0
    assert single_direction_area.hScrollBar.duration == 0


def test_configure_qfluent_scroll_surface_places_single_direction_chrome_like_editor(
    single_direction_area: SingleDirectionScrollArea,
) -> None:
    """Single-direction scroll chrome should use editor panel edge positioning."""

    single_direction_area.resize(420, 96)

    configure_qfluent_scroll_surface(single_direction_area)

    _assert_editor_vertical_scrollbar_geometry(
        single_direction_area.vScrollBar,
        single_direction_area,
    )
    _assert_editor_horizontal_scrollbar_geometry(
        single_direction_area.hScrollBar,
        single_direction_area,
    )


def test_disable_qfluent_smooth_scrolling_ignores_plain_objects() -> None:
    """Objects without QFluent scroll attributes should be accepted as no-ops."""

    disable_qfluent_smooth_scrolling(object())


def _assert_editor_vertical_scrollbar_geometry(
    scroll_bar: _ScrollBarLike,
    owner: _ScrollOwnerLike,
) -> None:
    """Assert vertical scrollbar geometry matches the editor panel formula."""

    geometry = scroll_bar.geometry()
    assert geometry.x() == owner.width() - 13
    assert geometry.y() == 1
    assert geometry.width() == 12
    assert geometry.height() == owner.height() - 2


def _assert_editor_horizontal_scrollbar_geometry(
    scroll_bar: _ScrollBarLike,
    owner: _ScrollOwnerLike,
) -> None:
    """Assert horizontal scrollbar geometry mirrors the vertical editor formula."""

    geometry = scroll_bar.geometry()
    assert geometry.x() == 1
    assert geometry.y() == owner.height() - 13
    assert geometry.width() == owner.width() - 2
    assert geometry.height() == 12
