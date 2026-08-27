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

"""Verify native Comfy palette editing through its presentation owner."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.panel.widgets.fields.native import ColorsField
from tests.support.qt.lifecycle import destroy_qt_object


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication required by Fluent field controls."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def test_colors_field_normalizes_supported_containers_and_invalid_entries() -> None:
    """Preserve order while replacing malformed RGB entries with neutral white."""

    _ensure_qapp()
    field = ColorsField({"first": "#AABBCC", "second": "red", "third": 7})
    try:
        assert field.value() == ["#aabbcc", "#ffffff", "#ffffff"]

        field.setValue("#123456")

        assert field.value() == []
        assert field.pickers == []
    finally:
        destroy_qt_object(field)


def test_colors_field_adds_removes_and_reorders_an_ordered_palette() -> None:
    """Publish complete palette values for each explicit structural edit."""

    _ensure_qapp()
    field = ColorsField(["#111111", "#222222"])
    published: list[object] = []
    field.valueChanged.connect(published.append)
    try:
        field.pickers[1].pressed.emit()
        field.move_up_button.click()
        field.add_button.click()
        field.remove_button.click()

        assert published == [
            ["#222222", "#111111"],
            ["#222222", "#111111", "#ffffff"],
            ["#222222", "#111111"],
        ]
        assert field.value() == ["#222222", "#111111"]
        assert field.move_down_button.isEnabled() is False
    finally:
        destroy_qt_object(field)


def test_colors_field_edits_selected_rgb_without_alpha_or_reordering() -> None:
    """Commit one picker value in place through the semantic field signal."""

    _ensure_qapp()
    field = ColorsField(["#111111", "#222222"])
    published: list[object] = []
    field.valueChanged.connect(published.append)
    try:
        field.pickers[0].colorChanged.emit(QColor("#abcdef"))

        assert field.value() == ["#abcdef", "#222222"]
        assert published == [["#abcdef", "#222222"]]
        assert all(picker.enableAlpha is False for picker in field.pickers)
    finally:
        destroy_qt_object(field)


def test_colors_field_enforces_comfys_sixteen_color_limit() -> None:
    """Limit initialization and additions to Comfy's native palette capacity."""

    _ensure_qapp()
    field = ColorsField([f"#{index:06x}" for index in range(17)])
    try:
        assert len(field.value()) == 16
        assert field.add_button.isEnabled() is False

        field.add_button.click()

        assert len(field.value()) == 16
    finally:
        destroy_qt_object(field)
