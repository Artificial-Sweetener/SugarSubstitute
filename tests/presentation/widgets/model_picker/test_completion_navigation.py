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

"""Verify model picker completion navigation contracts."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _item,
)
from tests.presentation.widgets.model_picker.support import (
    _open_picker_surface,
    ensure_qapp,
)


def test_model_picker_field_shows_filename_inline_completion() -> None:
    """Typing a filename-only match should show a display-only suffix."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (
            _item(
                "Illustrious/notFriendlyName_v11.safetensors",
                "Completely Different",
                "v11",
            ),
        ),
        current_value="Illustrious/notFriendlyName_v11.safetensors",
    )

    QTest.keyClicks(surface, "Friendly")
    app.processEvents()

    assert surface.inline_completion_suffix() == "Name_v11"
    assert surface.text() == "Friendly"
    assert field.currentText() == "Illustrious/notFriendlyName_v11.safetensors"
    destroy_qt_object(host)


def test_model_picker_field_shows_path_inline_completion() -> None:
    """Typing a path prefix should show a suffix for the current visible path."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, r"Illustrious\aman")
    app.processEvents()

    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"
    destroy_qt_object(host)


def test_model_picker_field_shows_friendly_name_inline_completion() -> None:
    """Typing a CivitAI display prefix should complete the friendly label."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/tNoobnai3_v9.safetensors", "T-noobnai3", "v9"),),
        current_value="Illustrious/tNoobnai3_v9.safetensors",
    )

    QTest.keyClicks(surface, "T-noob")
    app.processEvents()

    assert surface.inline_completion_suffix() == "nai3 - v9"
    destroy_qt_object(host)


def test_model_picker_field_tab_accepts_inline_completion_without_selecting() -> None:
    """Tab should accept ghost text into search text but not select a backend value."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="models/alpha.safetensors",
        extra_items=(_item("models/alpha.safetensors", "Alpha", None),),
    )
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Tab)
    app.processEvents()

    assert surface.text() == "amanatsuIllustrious_v11"
    assert surface.inline_completion_suffix() == ""
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    destroy_qt_object(host)


def test_model_picker_field_right_navigates_and_tab_accepts_completion() -> None:
    """Plain Right should navigate while Tab remains the completion accept key."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    surface.setCursorPosition(2)
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Right)
    app.processEvents()

    assert surface.text() == "aman"
    assert surface.cursorPosition() == 2
    assert surface.inline_completion_suffix() == ""

    surface.setCursorPosition(len(surface.text()))
    surface.set_inline_completion_suffix("atsuIllustrious_v11")
    QTest.keyClick(surface, Qt.Key.Key_Right)
    app.processEvents()

    assert surface.text() == "aman"
    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"

    QTest.keyClick(surface, Qt.Key.Key_Tab)
    app.processEvents()

    assert surface.text() == "amanatsuIllustrious_v11"
    destroy_qt_object(host)


def test_model_picker_field_arrow_keys_navigate_open_picker_wall() -> None:
    """Open combo-search fields should reuse LoRA-style wall arrow navigation."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        tuple(
            _item(f"models/model_{index}.safetensors", f"Model {index}", None)
            for index in range(12)
        ),
        current_value="models/model_0.safetensors",
    )
    popup = field._popup
    assert popup is not None
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(surface, Qt.Key.Key_Right)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 1"

    QTest.keyClick(surface, Qt.Key.Key_Left)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(surface, Qt.Key.Key_Down)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title != "Model 0"

    destroy_qt_object(host)


def test_model_picker_field_ctrl_arrows_preserve_native_text_navigation() -> None:
    """Ctrl-arrow should stay available for caret movement in the search text."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        tuple(
            _item(f"models/model_{index}.safetensors", f"Model {index}", None)
            for index in range(3)
        ),
        current_value="models/model_0.safetensors",
    )
    popup = field._popup
    assert popup is not None
    QTest.keyClicks(surface, "model")
    surface.setCursorPosition(0)
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(
        surface,
        Qt.Key.Key_Right,
        Qt.KeyboardModifier.ControlModifier,
    )
    app.processEvents()

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"
    assert surface.cursorPosition() > 0
    destroy_qt_object(host)


def test_model_picker_field_text_selection_suppresses_inline_completion() -> None:
    """Selecting search text should clear the display-only suffix."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"

    surface.selectAll()
    app.processEvents()

    assert surface.hasSelectedText() is True
    assert surface.inline_completion_suffix() == ""
    assert surface._should_paint_search_caret() is False
    destroy_qt_object(host)


def test_model_picker_field_escape_clears_inline_completion_and_restores_label() -> (
    None
):
    """Dismissing search should clear ghost text and restore closed combo display."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"

    QTest.keyClick(surface, Qt.Key.Key_Escape)
    app.processEvents()

    assert surface.inline_completion_suffix() == ""
    assert field.displayText() == "Amanatsu - v11"
    assert field.currentText() == "Illustrious/amanatsuIllustrious_v11.safetensors"
    destroy_qt_object(host)


def test_model_picker_field_enter_still_selects_current_backend_value() -> None:
    """Enter should activate the current item instead of accepting ghost text."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        ),
        current_value="models/alpha.safetensors",
    )
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    QTest.keyClicks(surface, "beta")
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Return)
    app.processEvents()

    assert field.currentText() == "models/beta.safetensors"
    assert changed == ["models/beta.safetensors"]
    assert field.displayText() == "Beta"
    destroy_qt_object(host)
