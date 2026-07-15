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

"""Adapter tests for output set picker behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.shared import output_set_picker as picker_mod
from substitute.presentation.canvas.shared.output_set_picker import OutputSetPicker
from substitute.presentation.widgets.anchored_row_picker import AnchoredRowPickerItem


def _app() -> QApplication:
    """Return a QApplication for lightweight widget construction."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def test_output_set_picker_builds_rows_descending() -> None:
    """Higher set indexes should appear above lower indexes."""

    assert OutputSetPicker._build_row_indexes(
        set_count=4,
        include_grid=False,
    ) == (4, 3, 2, 1)


def test_output_set_picker_builds_grid_row_before_sets() -> None:
    """Grid mode should appear as row zero before concrete output sets."""

    assert OutputSetPicker._build_row_indexes(
        set_count=3,
        include_grid=True,
    ) == (0, 1, 2, 3)


def test_output_set_picker_configures_centered_numeric_rows(monkeypatch: Any) -> None:
    """Output set picker should configure centered numeric anchored rows."""

    _app()
    created: list[_FakeAnchoredPicker] = []

    class _FakeAnchoredPicker:
        """Record anchored picker calls for adapter assertions."""

        def __init__(self, parent: QWidget) -> None:
            self.parent = parent
            self.show_calls: list[dict[str, object]] = []
            created.append(self)

        def show_for(
            self,
            anchor: QWidget,
            *,
            items: tuple[AnchoredRowPickerItem, ...],
            active_key: str,
            active_text_mode: str,
            inactive_text_mode: str,
            selected_callback: Callable[[str], None],
            row_width: int | None = None,
        ) -> None:
            """Record one picker display request."""

            self.show_calls.append(
                {
                    "anchor": anchor,
                    "items": items,
                    "active_key": active_key,
                    "row_width": row_width,
                    "active_text_mode": active_text_mode,
                    "inactive_text_mode": inactive_text_mode,
                    "selected_callback": selected_callback,
                }
            )

        def close(self) -> None:
            """Close the fake picker."""

        def is_visible(self) -> bool:
            """Return fake visibility."""

            return False

    monkeypatch.setattr(picker_mod, "AnchoredRowPicker", _FakeAnchoredPicker)
    parent = QWidget()
    anchor = QWidget()
    selected: list[int] = []
    picker = OutputSetPicker(parent)

    picker.show_for(
        anchor,
        set_count=3,
        active_set_index=2,
        include_grid=True,
        selected_callback=selected.append,
    )

    fake = created[0]
    call = fake.show_calls[0]
    assert fake.parent is parent
    assert call["anchor"] is anchor
    assert call["items"] == (
        AnchoredRowPickerItem("0", "0"),
        AnchoredRowPickerItem("1", "1"),
        AnchoredRowPickerItem("2", "2"),
        AnchoredRowPickerItem("3", "3"),
    )
    assert call["active_key"] == "2"
    assert call["active_text_mode"] == "row_center"
    assert call["inactive_text_mode"] == "row_center"

    callback = cast(Callable[[str], None], call["selected_callback"])
    callback("0")

    assert selected == [0]
