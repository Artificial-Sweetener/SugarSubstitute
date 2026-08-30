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

"""Test generation batch-count titlebar editing."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.shell.titlebar_buttons import (
    GenerationBatchCountAccessory,
)
from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
)

from tests.presentation.shell.generation.titlebar.support import app


def test_generation_batch_count_accessory_clamps_and_emits_changes() -> None:
    """Batch accessory should keep a positive count and report real changes."""

    app()
    accessory = GenerationBatchCountAccessory()
    changes: list[int] = []
    accessory.valueChanged.connect(lambda value: changes.append(value))

    assert accessory.batch_count() == 1
    assert accessory.down_chevron_enabled() is False

    accessory.set_batch_count(0)
    assert accessory.batch_count() == 1
    assert changes == []

    accessory.increment()
    assert accessory.batch_count() == 2
    assert accessory.down_chevron_enabled() is True

    accessory.decrement()
    accessory.decrement()

    assert accessory.batch_count() == 1
    assert accessory.down_chevron_enabled() is False
    assert changes == [2, 1]


def test_generation_batch_count_accessory_chevron_clicks_adjust_value() -> None:
    """Chevron hit zones should increment and decrement the batch value."""

    app()
    accessory = GenerationBatchCountAccessory()

    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._role_rect("up").center().toPoint(),
    )
    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._role_rect("down").center().toPoint(),
    )
    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._role_rect("down").center().toPoint(),
    )

    assert accessory.batch_count() == 1


def test_generation_batch_count_accessory_uses_body_material_wash() -> None:
    """Batch accessory should use the window wash instead of accent fill."""

    app()
    accessory = GenerationBatchCountAccessory()

    assert accessory._surface_color() == QColor(*body_material_wash_color(None))


def test_generation_batch_count_accessory_accepts_manual_number_entry() -> None:
    """Clicking the value region should allow direct numeric entry."""

    app()
    accessory = GenerationBatchCountAccessory()

    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._value_rect().center().toPoint(),
    )
    accessory._editor.clear()
    QTest.keyClicks(accessory._editor, "777")
    QTest.keyClick(accessory._editor, Qt.Key.Key_Return)

    assert accessory.batch_count() == 777
    assert accessory._editor.isHidden() is True


def test_generation_batch_count_accessory_commits_manual_entry_on_outside_click() -> (
    None
):
    """Clicking outside the spinner should commit typed text and close editing."""

    app()
    container = QWidget()
    accessory = GenerationBatchCountAccessory(container)
    outside = QWidget(container)
    accessory.setGeometry(0, 0, accessory.width(), accessory.height())
    outside.setGeometry(accessory.width() + 20, 0, 40, accessory.height())
    outside.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    container.show()

    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._value_rect().center().toPoint(),
    )
    accessory._editor.clear()
    QTest.keyClicks(accessory._editor, "42")
    QTest.mouseClick(outside, Qt.MouseButton.LeftButton)

    assert accessory.batch_count() == 42
    assert accessory._editor.isHidden() is True
    assert not accessory._editor.hasFocus()
    container.close()


def test_generation_batch_count_accessory_centers_three_digit_value_region() -> None:
    """The value region should leave centered room for three digits."""

    app()
    accessory = GenerationBatchCountAccessory()

    assert accessory._value_width() >= 44
    assert accessory._value_rect().center().x() < accessory._role_rect("up").left()
    assert accessory._editor.validator() is not None
