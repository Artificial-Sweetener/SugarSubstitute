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

"""Adapter tests for canvas navigation picker configuration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.shared import canvas_nav_picker as picker_mod
from substitute.presentation.canvas.shared.canvas_nav_picker import (
    CanvasNavPicker,
    CanvasNavPickerItem,
)


def _app() -> QApplication:
    """Return a QApplication for lightweight widget construction."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def test_canvas_nav_picker_item_preserves_keys_labels_and_disabled_state() -> None:
    """Canvas navigation items should preserve row identity and labels."""

    item = CanvasNavPickerItem("portrait", "Portrait", enabled=False)

    assert item.key == "portrait"
    assert item.label == "Portrait"
    assert item.enabled is False


def test_canvas_nav_picker_configures_scene_text_modes(monkeypatch: Any) -> None:
    """Canvas navigation should configure active anchor text and inactive row text."""

    _app()
    created: list[_FakeAnchoredPicker] = []

    class _FakeAnchoredPicker:
        """Record anchored picker calls for adapter assertions."""

        def __init__(self, parent: QWidget) -> None:
            self.parent = parent
            self.show_calls: list[dict[str, object]] = []
            self.closed = False
            created.append(self)

        def show_for(
            self,
            anchor: QWidget,
            *,
            items: tuple[CanvasNavPickerItem, ...],
            active_key: str,
            row_width: int | None = None,
            active_text_mode: str,
            inactive_text_mode: str,
            selected_callback: Callable[[str], None],
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
            """Record a close request."""

            self.closed = True

        def is_visible(self) -> bool:
            """Return whether this fake picker has not been closed."""

            return not self.closed

    monkeypatch.setattr(picker_mod, "AnchoredRowPicker", _FakeAnchoredPicker)
    parent = QWidget()
    anchor = QWidget()
    picker = CanvasNavPicker(parent)
    items = (
        CanvasNavPickerItem("all", "All"),
        CanvasNavPickerItem("scene1", "scene1"),
    )

    picker.show_for(
        anchor,
        items=items,
        active_key="all",
        row_width=128,
        selected_callback=lambda _key: None,
    )

    fake = created[0]
    assert fake.parent is parent
    assert fake.show_calls[0]["anchor"] is anchor
    assert fake.show_calls[0]["items"] == items
    assert fake.show_calls[0]["active_key"] == "all"
    assert fake.show_calls[0]["row_width"] == 128
    assert fake.show_calls[0]["active_text_mode"] == "anchor_center"
    assert fake.show_calls[0]["inactive_text_mode"] == "row_left"
    assert picker.is_visible() is True

    picker.close()

    assert fake.closed is True
