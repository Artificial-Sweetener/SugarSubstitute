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

"""Contract tests for the output compare material-gap overlay."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from substitute.presentation.canvas.output.output_compare_material_gap import (
    OUTPUT_COMPARE_MATERIAL_GAP_OVERLAY_NAME,
    OutputCompareMaterialGapOverlay,
)


class _FakePane:
    """QPane-like test double exposing overlay and divider APIs."""

    def __init__(self, divider_state: object | None = None) -> None:
        """Create a fake pane with optional comparison divider state."""

        self.divider_state = divider_state
        self.registered_overlays: dict[str, Any] = {}
        self.unregistered_overlays: list[str] = []

    def registerOverlay(self, name: str, draw_fn: Any) -> None:  # noqa: N802
        """Record a public QPane overlay registration."""

        self.registered_overlays[name] = draw_fn

    def unregisterOverlay(self, name: str) -> None:  # noqa: N802
        """Record a public QPane overlay unregistration."""

        self.unregistered_overlays.append(name)

    def comparisonDividerState(self) -> object:  # noqa: N802
        """Return the configured public comparison-divider state."""

        return self.divider_state or SimpleNamespace(enabled=False)


class _FakePainter:
    """Record the QPainter calls used by the material-gap overlay."""

    def __init__(self) -> None:
        """Create an empty painter call recorder."""

        self.calls: list[tuple[str, Any]] = []

    def save(self) -> None:
        """Record painter state save."""

        self.calls.append(("save", None))

    def restore(self) -> None:
        """Record painter state restore."""

        self.calls.append(("restore", None))

    def setRenderHint(self, hint: object, enabled: bool) -> None:  # noqa: N802
        """Record render hint changes."""

        self.calls.append(("setRenderHint", (hint, enabled)))

    def setCompositionMode(self, mode: object) -> None:  # noqa: N802
        """Record composition mode changes."""

        self.calls.append(("setCompositionMode", mode))

    def setPen(self, pen: object) -> None:  # noqa: N802
        """Record the pen used for drawing."""

        self.calls.append(("setPen", pen))

    def drawLine(self, line: object) -> None:  # noqa: N802
        """Record line drawing."""

        self.calls.append(("drawLine", line))


def _assert_color_nearly_equal(actual: QColor, expected: QColor) -> None:
    """Assert colors match within QImage premultiplied-channel rounding."""

    assert abs(actual.red() - expected.red()) <= 1
    assert abs(actual.green() - expected.green()) <= 1
    assert abs(actual.blue() - expected.blue()) <= 1
    assert abs(actual.alpha() - expected.alpha()) <= 1


def test_material_gap_registers_qpane_overlay() -> None:
    """Construction should register one stable public QPane overlay."""

    pane = _FakePane()

    overlay = OutputCompareMaterialGapOverlay(
        pane=pane,
        compare_enabled=lambda: True,
    )

    assert pane.registered_overlays == {
        OUTPUT_COMPARE_MATERIAL_GAP_OVERLAY_NAME: overlay.draw
    }


def test_material_gap_noops_when_compare_disabled() -> None:
    """The overlay should not draw when Substitute compare mode is inactive."""

    pane = _FakePane(
        SimpleNamespace(
            enabled=True,
            visible_segment=QLineF(QPointF(1.0, 2.0), QPointF(3.0, 4.0)),
        )
    )
    overlay = OutputCompareMaterialGapOverlay(
        pane=pane,
        compare_enabled=lambda: False,
    )
    painter = _FakePainter()

    overlay.draw(painter, None)

    assert painter.calls == []


def test_material_gap_noops_without_visible_segment() -> None:
    """The overlay should not draw until QPane reports visible divider geometry."""

    pane = _FakePane(SimpleNamespace(enabled=True, visible_segment=None))
    overlay = OutputCompareMaterialGapOverlay(
        pane=pane,
        compare_enabled=lambda: True,
    )
    painter = _FakePainter()

    overlay.draw(painter, None)

    assert painter.calls == []


def test_material_gap_draws_two_pixel_body_wash_stroke() -> None:
    """The overlay should replace the divider band with the shell body wash."""

    segment = QLineF(QPointF(10.0, 0.0), QPointF(10.0, 100.0))
    pane = _FakePane(SimpleNamespace(enabled=True, visible_segment=segment))
    wash = QColor(10, 20, 30, 180)
    overlay = OutputCompareMaterialGapOverlay(
        pane=pane,
        compare_enabled=lambda: True,
        material_color=lambda: wash,
    )
    painter = _FakePainter()

    overlay.draw(painter, None)

    assert painter.calls[0] == ("save", None)
    assert painter.calls[1] == (
        "setRenderHint",
        (QPainter.RenderHint.Antialiasing, False),
    )
    assert painter.calls[2] == (
        "setCompositionMode",
        QPainter.CompositionMode.CompositionMode_Clear,
    )
    assert painter.calls[4] == ("drawLine", segment)
    assert painter.calls[5] == (
        "setCompositionMode",
        QPainter.CompositionMode.CompositionMode_SourceOver,
    )
    assert painter.calls[7] == ("drawLine", segment)
    assert painter.calls[8] == ("restore", None)

    clear_pen = painter.calls[3][1]
    assert clear_pen.width() == 2
    assert clear_pen.capStyle() == Qt.PenCapStyle.SquareCap

    wash_pen = painter.calls[6][1]
    assert wash_pen.width() == 2
    assert wash_pen.capStyle() == Qt.PenCapStyle.SquareCap
    assert wash_pen.color() == wash


def test_material_gap_replaces_two_pixel_band_with_body_wash() -> None:
    """The real painter path should leave only body wash in the divider band."""

    image = QImage(8, 8, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(255, 0, 0, 255))
    segment = QLineF(QPointF(4.0, 0.0), QPointF(4.0, 7.0))
    pane = _FakePane(SimpleNamespace(enabled=True, visible_segment=segment))
    wash = QColor(10, 20, 30, 180)
    overlay = OutputCompareMaterialGapOverlay(
        pane=pane,
        compare_enabled=lambda: True,
        material_color=lambda: wash,
    )
    painter = QPainter(image)
    try:
        overlay.draw(painter, None)
    finally:
        painter.end()

    _assert_color_nearly_equal(image.pixelColor(3, 4), wash)
    _assert_color_nearly_equal(image.pixelColor(4, 4), wash)
    assert image.pixelColor(2, 4).alpha() == 255
    assert image.pixelColor(5, 4).alpha() == 255
