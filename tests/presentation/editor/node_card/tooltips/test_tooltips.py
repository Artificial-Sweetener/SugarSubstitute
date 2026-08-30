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

"""Verify Comfy node and field tooltips on their semantic surfaces."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from tests.presentation.editor.node_card.body_layout.support import mount_body_card
from tests.presentation.editor.node_card.support import (
    content_body_for,
    content_layout_for,
    editor_tooltip_filter,
    title_row_for,
)


def test_card_applies_comfy_node_description(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose the resolved Comfy node description across the title surface."""

    node_tooltip = "Samples an image from latent noise."
    mounted = mount_body_card(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
        inputs={"steps": 20},
        definitions={
            "KSampler": {
                "description": node_tooltip,
                "input": {"required": {"steps": ["INT", {}]}},
            }
        },
    )
    try:
        title_row = title_row_for(mounted.wrapper)
        title_labels = title_row.findChildren(CaptionLabel)
        title_filter = editor_tooltip_filter(title_row)
        assert title_row.toolTip() == node_tooltip
        assert title_filter is not None
        assert title_filter.eventFilter(title_row, QEvent(QEvent.Type.ToolTip))
        assert len(title_labels) == 1
        assert title_labels[0].toolTip() == ""
        assert title_filter.eventFilter(
            title_labels[0],
            QEvent(QEvent.Type.ToolTip),
        )
    finally:
        mounted.destroy()


def test_scalar_row_applies_comfy_input_tooltip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose one field tooltip across its row, label, and input surface."""

    field_tooltip = "Number of denoise steps."
    mounted = mount_body_card(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
        inputs={"steps": 20},
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "steps": ["INT", {"tooltip": field_tooltip}],
                    }
                }
            }
        },
    )
    try:
        field_widget = mounted.panel.input_widgets_by_field_key[
            ("A", "ksampler", "steps")
        ]
        content_layout = content_layout_for(content_body_for(mounted.wrapper))
        field_item = content_layout.itemAt(1)
        assert field_item is not None
        field_row = field_item.widget()
        assert field_row is not None
        labels = field_row.findChildren(CaptionLabel)
        row_filter = editor_tooltip_filter(field_row)
        assert row_filter is not None
        assert field_row.toolTip() == field_tooltip
        assert field_widget.toolTip() == ""
        assert row_filter.eventFilter(field_widget, QEvent(QEvent.Type.ToolTip))
        assert len(labels) == 1
        assert labels[0].toolTip() == ""
        assert row_filter.eventFilter(labels[0], QEvent(QEvent.Type.ToolTip))
    finally:
        mounted.destroy()


def test_grouped_row_keeps_comfy_tooltips_column_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep each grouped field tooltip on its own column surface."""

    steps_tooltip = "Number of denoise steps."
    cfg_tooltip = "Classifier-free guidance scale."
    mounted = mount_body_card(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
        inputs={"steps": 20, "cfg": 7.0},
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "steps": ["INT", {"tooltip": steps_tooltip}],
                        "cfg": ["FLOAT", {"tooltip": cfg_tooltip}],
                    }
                }
            }
        },
    )
    try:
        steps_row, steps_column, steps_widget = mounted.panel.col_widgets[
            ("A", "ksampler", "steps")
        ]
        cfg_row, cfg_column, cfg_widget = mounted.panel.col_widgets[
            ("A", "ksampler", "cfg")
        ]
        assert isinstance(steps_row, QWidget)
        assert isinstance(steps_column, QWidget)
        assert isinstance(steps_widget, QWidget)
        assert isinstance(cfg_column, QWidget)
        assert isinstance(cfg_widget, QWidget)
        steps_filter = editor_tooltip_filter(steps_column)
        cfg_filter = editor_tooltip_filter(cfg_column)
        assert steps_row is cfg_row
        assert steps_filter is not None
        assert cfg_filter is not None
        assert steps_widget.toolTip() == ""
        assert steps_column.toolTip() == steps_tooltip
        assert steps_filter.eventFilter(steps_widget, QEvent(QEvent.Type.ToolTip))
        assert cfg_widget.toolTip() == ""
        assert cfg_column.toolTip() == cfg_tooltip
        assert cfg_filter.eventFilter(cfg_widget, QEvent(QEvent.Type.ToolTip))
        assert steps_row.toolTip() == ""
        assert editor_tooltip_filter(steps_row) is None
    finally:
        mounted.destroy()
