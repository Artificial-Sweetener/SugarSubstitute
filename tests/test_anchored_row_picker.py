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

"""Contract tests for reusable anchored row picker behavior."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication

from substitute.presentation.widgets.anchored_row_picker import (
    AnchoredRowPickerItem,
    AnchoredRowPickerRow,
    AnchoredRowPickerView,
    active_row_index_from_top,
)


def _app() -> QApplication:
    """Return a QApplication for lightweight widget construction."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def test_anchored_row_picker_row_click_emits_key() -> None:
    """Clicking an enabled row should emit its string key."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("portrait", "Portrait"),
        active=True,
        row_size=QSize(80, 28),
        anchor_slot_width=80,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )
    selected: list[str] = []
    row.selected.connect(selected.append)

    row.click()

    assert selected == ["portrait"]


def test_anchored_row_picker_disabled_row_does_not_emit_key() -> None:
    """Disabled rows should remain visible but unavailable."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("skipped", "Skipped", enabled=False),
        active=False,
        row_size=QSize(80, 28),
        anchor_slot_width=80,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )
    selected: list[str] = []
    row.selected.connect(selected.append)

    row.click()

    assert selected == []


def test_anchored_row_picker_anchor_center_uses_anchor_slot() -> None:
    """Anchor-centered active text should paint inside the anchor-width slot."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("all", "All"),
        active=True,
        row_size=QSize(180, 28),
        anchor_slot_width=58,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )

    assert row.text_rect_for_paint() == row.rect().adjusted(0, 0, -122, 0)
    assert row.text_alignment_for_paint() == Qt.AlignmentFlag.AlignCenter


def test_anchored_row_picker_anchor_left_uses_anchor_slot_with_padding() -> None:
    """Anchor-left active text should paint inside the padded anchor-width slot."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("all", "All"),
        active=True,
        row_size=QSize(180, 28),
        anchor_slot_width=58,
        active_text_mode="anchor_left",
        inactive_text_mode="row_left",
    )

    assert row.text_rect_for_paint() == row.rect().adjusted(12, 0, -134, 0)
    assert row.text_alignment_for_paint() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )


def test_anchored_row_picker_row_center_uses_full_row() -> None:
    """Row-centered text should paint inside the full row slot."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("2", "2"),
        active=True,
        row_size=QSize(34, 28),
        anchor_slot_width=34,
        active_text_mode="row_center",
        inactive_text_mode="row_center",
    )

    assert row.text_rect_for_paint() == row.rect()
    assert row.text_alignment_for_paint() == Qt.AlignmentFlag.AlignCenter


def test_anchored_row_picker_row_left_uses_full_row_with_padding() -> None:
    """Row-left text should paint inside the padded full row slot."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("scene1", "scene1"),
        active=False,
        row_size=QSize(180, 28),
        anchor_slot_width=58,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )

    assert row.text_rect_for_paint() == row.rect().adjusted(12, 0, -12, 0)
    assert row.text_alignment_for_paint() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )


def test_anchored_row_picker_set_active_updates_text_geometry() -> None:
    """Active state changes should switch between active and inactive text modes."""

    _app()
    row = AnchoredRowPickerRow(
        AnchoredRowPickerItem("all", "All"),
        active=False,
        row_size=QSize(180, 28),
        anchor_slot_width=58,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )

    assert row.text_rect_for_paint() == row.rect().adjusted(12, 0, -12, 0)

    row.set_active(True)

    assert row.text_rect_for_paint() == row.rect().adjusted(0, 0, -122, 0)
    assert row.text_alignment_for_paint() == Qt.AlignmentFlag.AlignCenter


def test_anchored_row_picker_view_renders_supplied_labels() -> None:
    """View rows should preserve caller-provided keys and labels."""

    _app()
    view = AnchoredRowPickerView(
        items=(
            AnchoredRowPickerItem("all", "All"),
            AnchoredRowPickerItem("portrait", "Portrait"),
        ),
        active_key="all",
        anchor_size=QSize(80, 28),
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )

    row = view.row_for_key("portrait")

    assert view.item_keys() == ("all", "portrait")
    assert row is not None
    assert row.text() == "Portrait"


def test_anchored_row_picker_view_can_use_row_width_larger_than_anchor() -> None:
    """Rows should be able to size to labels instead of the anchor button."""

    _app()
    view = AnchoredRowPickerView(
        items=(
            AnchoredRowPickerItem("all", "All"),
            AnchoredRowPickerItem("long", "A Long Scene Name"),
        ),
        active_key="long",
        anchor_size=QSize(58, 28),
        row_width=180,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )

    row = view.row_for_key("long")

    assert row is not None
    assert row.width() == 180
    assert view.row_slot_width() == 180


def test_anchored_row_picker_view_normalizes_invalid_or_disabled_active_key() -> None:
    """Active key normalization should choose the first enabled row."""

    _app()
    view = AnchoredRowPickerView(
        items=(
            AnchoredRowPickerItem("all", "All", enabled=False),
            AnchoredRowPickerItem("portrait", "Portrait"),
        ),
        active_key="missing",
        anchor_size=QSize(80, 28),
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )

    assert view.active_key() == "portrait"


def test_anchored_row_picker_view_keyboard_skips_disabled_rows() -> None:
    """Keyboard movement should only commit enabled rows."""

    _app()
    view = AnchoredRowPickerView(
        items=(
            AnchoredRowPickerItem("all", "All"),
            AnchoredRowPickerItem("skipped", "Skipped", enabled=False),
            AnchoredRowPickerItem("portrait", "Portrait"),
        ),
        active_key="all",
        anchor_size=QSize(80, 28),
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )
    selected: list[str] = []
    view.itemSelected.connect(selected.append)

    view.keyPressEvent(type("KeyEvent", (), {"key": lambda _self: Qt.Key.Key_Down})())
    view.keyPressEvent(type("KeyEvent", (), {"key": lambda _self: Qt.Key.Key_Return})())

    assert selected == ["portrait"]


def test_anchored_row_picker_disabled_rows_count_for_visual_placement() -> None:
    """Disabled rows should stay in the visual row count for active-row placement."""

    items = (
        AnchoredRowPickerItem("all", "All"),
        AnchoredRowPickerItem("skipped", "Skipped", enabled=False),
        AnchoredRowPickerItem("portrait", "Portrait"),
    )

    assert active_row_index_from_top(items=items, active_key="portrait") == 2
    assert active_row_index_from_top(items=items, active_key="all") == 0
