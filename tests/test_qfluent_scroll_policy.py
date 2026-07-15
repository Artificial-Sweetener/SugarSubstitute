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

import os
from typing import Protocol, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


def _app() -> QApplication:
    """Return the shared QApplication for QFluent widget construction."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_disable_qfluent_smooth_scrolling_handles_scroll_area_delegate() -> None:
    """QFluent ScrollArea should keep chrome but use immediate wheel handling."""

    app = _app()
    scroll_area = ScrollArea()
    try:
        disable_qfluent_smooth_scrolling(scroll_area)

        scroll_delegate = scroll_area.scrollDelagate
        assert scroll_delegate.useAni is False
        assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
        assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
        assert scroll_delegate.vScrollBar.duration == 0
        assert scroll_delegate.hScrollBar.duration == 0
    finally:
        scroll_area.close()
        scroll_area.deleteLater()
        app.processEvents()


def test_configure_qfluent_scroll_surface_places_scroll_area_chrome_like_editor() -> (
    None
):
    """QFluent ScrollArea chrome should sit at the editor panel's relative edge."""

    app = _app()
    scroll_area = ScrollArea()
    try:
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
    finally:
        scroll_area.close()
        scroll_area.deleteLater()
        app.processEvents()


def test_disable_qfluent_smooth_scrolling_handles_text_edit_delegate() -> None:
    """QFluent text edits should use the same no-smooth wheel policy."""

    app = _app()
    editor = PlainTextEdit()
    try:
        disable_qfluent_smooth_scrolling(editor)

        scroll_delegate = editor.scrollDelegate
        assert scroll_delegate.useAni is False
        assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
        assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
        assert scroll_delegate.vScrollBar.duration == 0
        assert scroll_delegate.hScrollBar.duration == 0
    finally:
        editor.close()
        editor.deleteLater()
        app.processEvents()


def test_configure_qfluent_scroll_surface_places_text_edit_chrome_like_editor() -> None:
    """QFluent text-edit chrome should use editor panel edge positioning."""

    app = _app()
    editor = PlainTextEdit()
    try:
        editor.resize(360, 180)

        configure_qfluent_scroll_surface(editor)

        _assert_editor_vertical_scrollbar_geometry(
            editor.scrollDelegate.vScrollBar,
            editor,
        )
        _assert_editor_horizontal_scrollbar_geometry(
            editor.scrollDelegate.hScrollBar,
            editor,
        )
    finally:
        editor.close()
        editor.deleteLater()
        app.processEvents()


def test_disable_qfluent_smooth_scrolling_handles_single_direction_area() -> None:
    """Single-direction QFluent scroll areas should keep scrolling without smoothing."""

    app = _app()
    scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Horizontal)
    try:
        disable_qfluent_smooth_scrolling(scroll_area)

        assert scroll_area.smoothScroll.smoothMode is SmoothMode.NO_SMOOTH
        assert scroll_area.vScrollBar.duration == 0
        assert scroll_area.hScrollBar.duration == 0
    finally:
        scroll_area.close()
        scroll_area.deleteLater()
        app.processEvents()


def test_configure_qfluent_scroll_surface_places_single_direction_chrome_like_editor() -> (
    None
):
    """Single-direction scroll chrome should use editor panel edge positioning."""

    app = _app()
    scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Horizontal)
    try:
        scroll_area.resize(420, 96)

        configure_qfluent_scroll_surface(scroll_area)

        _assert_editor_vertical_scrollbar_geometry(scroll_area.vScrollBar, scroll_area)
        _assert_editor_horizontal_scrollbar_geometry(
            scroll_area.hScrollBar,
            scroll_area,
        )
    finally:
        scroll_area.close()
        scroll_area.deleteLater()
        app.processEvents()


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
