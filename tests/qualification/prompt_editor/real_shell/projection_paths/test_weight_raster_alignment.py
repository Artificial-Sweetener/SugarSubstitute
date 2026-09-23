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

"""Compare rendered display and editable weight glyph placement."""

from __future__ import annotations

from collections import Counter
from math import ceil

import pytest
from PySide6.QtCore import QPoint, QRect, QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.presentation.editor.prompt_editor.interactions.weight.mounting import (
    start_exact_weight_edit,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def _render_viewport(viewport: QWidget, *, device_pixel_ratio: float) -> QImage:
    """Capture production viewport paint at the requested display scale."""

    image = QImage(
        QSize(
            ceil(viewport.width() * device_pixel_ratio),
            ceil(viewport.height() * device_pixel_ratio),
        ),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.setDevicePixelRatio(device_pixel_ratio)
    image.fill(QColor("transparent"))
    painter = QPainter(image)
    try:
        viewport.render(painter, QPoint())
    finally:
        painter.end()
    return image


def _glyph_bounds(image: QImage, rect: QRectF) -> QRect:
    """Bound magenta text pixels without including shadow or chip backing."""

    pixels = [
        (x, y)
        for x in range(
            max(0, int(rect.left()) - 2), min(image.width(), int(rect.right()) + 3)
        )
        for y in range(
            max(0, int(rect.top()) - 2), min(image.height(), int(rect.bottom()) + 3)
        )
        if (color := image.pixelColor(x, y)).red() > 160
        and color.blue() > 160
        and color.green() < 100
    ]
    assert len(pixels) > 10, Counter(
        image.pixelColor(x, y).name()
        for x in range(
            max(0, int(rect.left()) - 2), min(image.width(), int(rect.right()) + 3)
        )
        for y in range(
            max(0, int(rect.top()) - 2), min(image.height(), int(rect.bottom()) + 3)
        )
    ).most_common(12)
    return QRect(
        min(x for x, _ in pixels),
        min(y for _, y in pixels),
        max(x for x, _ in pixels) - min(x for x, _ in pixels) + 1,
        max(y for _, y in pixels) - min(y for _, y in pixels) + 1,
    )


def _physical_rect(rect: QRectF, device_pixel_ratio: float) -> QRectF:
    """Map viewport-local label geometry into image pixel coordinates."""

    return QRectF(
        rect.left() * device_pixel_ratio,
        rect.top() * device_pixel_ratio,
        rect.width() * device_pixel_ratio,
        rect.height() * device_pixel_ratio,
    )


@pytest.mark.parametrize(
    ("source", "value_text"),
    [
        ("(red cube:1.25), portrait", "1.25"),
        ("((atmospheric:2.80) perspective:1.15), portrait", "2.80"),
        ("<lora:detail:1.25>, portrait", "1.25"),
    ],
    ids=["emphasis", "nested-emphasis", "lora"],
)
@pytest.mark.parametrize("device_pixel_ratio", [1.0, 1.5, 2.0])
def test_weight_raster_alignment(
    real_shell_scenario: PromptEditorRealShellScenario,
    source: str,
    value_text: str,
    device_pixel_ratio: float,
) -> None:
    """Place painted and native-edit weight glyphs in the same viewport pixels."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.focus_editor(field)
    surface = surface_for(field.editor)
    token = next(
        item
        for item in surface.projection_document().tokens
        if item.value_text == value_text
    )
    palette = QPalette(surface.palette())
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 0, 255))
    surface.setPalette(palette)
    assert surface.palette().color(QPalette.ColorRole.Text) == QColor(255, 0, 255)
    surface.refresh_geometry()
    weight_rect = surface.token_weight_edit_rect(token)
    assert weight_rect is not None
    glyph_region = _physical_rect(weight_rect, device_pixel_ratio)
    before = _render_viewport(surface.viewport(), device_pixel_ratio=device_pixel_ratio)
    painted = _glyph_bounds(before, glyph_region)
    start_exact_weight_edit(field.editor, token)
    native_input = surface.exact_weight_editor
    native_input.setPalette(palette)
    native_input.deselect()
    native_input.setCursorPosition(0)
    real_shell_scenario.wait_for_queued_delivery()
    after = _render_viewport(surface.viewport(), device_pixel_ratio=device_pixel_ratio)
    editable = _glyph_bounds(after, glyph_region)

    tolerance = ceil(device_pixel_ratio)
    assert abs(editable.left() - painted.left()) <= tolerance, (painted, editable)
    assert abs(editable.top() - painted.top()) <= tolerance, (painted, editable)
    assert abs(editable.right() - painted.right()) <= tolerance + 1, (
        painted,
        editable,
    )
    assert abs(editable.bottom() - painted.bottom()) <= tolerance, (
        painted,
        editable,
    )

    native_input.selectAll()
    QTest.keyClicks(native_input, "0.95")
    native_input.setCursorPosition(0)
    real_shell_scenario.wait_for_queued_delivery()
    updated = _render_viewport(
        surface.viewport(), device_pixel_ratio=device_pixel_ratio
    )
    updated_glyph = _glyph_bounds(updated, glyph_region)

    assert abs(updated_glyph.left() - painted.left()) <= tolerance, (
        painted,
        updated_glyph,
    )
    assert abs(updated_glyph.top() - painted.top()) <= tolerance, (
        painted,
        updated_glyph,
    )
    assert native_input.text() == "0.95"
    assert field.editor.toPlainText() == source
