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

"""Test focused field-row geometry contracts."""

from __future__ import annotations

from collections.abc import Iterator
import pytest
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]
from substitute.application.node_behavior import (
    FieldBehavior,
)
from substitute.presentation.widgets import (
    ComboBox,
)
from tests.support.qt.lifecycle import destroy_widget_roots
from .geometry_support import (
    _Panel,
    _builder,
    _ensure_qapp,
)
from typing import cast
from substitute.presentation.widgets.model_picker import ModelPickerField
from .geometry_support import (
    _FakeModelCatalog,
    _ProgressSurface,
)
from PySide6.QtCore import Qt
from .geometry_support import (
    _single_row_layout,
)


@pytest.fixture(autouse=True)
def dispose_owned_panels() -> Iterator[None]:
    """Destroy this owner's panels after each geometry contract."""

    yield
    application = _ensure_qapp()
    destroy_widget_roots(
        widget for widget in application.topLevelWidgets() if isinstance(widget, _Panel)
    )


def test_model_picker_single_row_gives_surplus_to_field_not_label() -> None:
    """Model picker rows should let the wide field own flexible row width."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = ModelPickerField(
        panel,
        choice_source=_FakeModelCatalog(),
        current_value="models/base.safetensors",
    )

    _builder(panel).add_input_row(
        label="ckpt_name",
        widget=field,
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        content_layout=content_layout,
    )

    row_layout = _single_row_layout(content_layout)

    assert row_layout.stretch(1) == 0
    assert row_layout.stretch(2) == 1


def test_string_line_edit_single_row_gives_surplus_to_field_not_label() -> None:
    """Node-card string rows should let the line edit fill available row width."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = LineEdit(panel)
    field.setProperty(
        "input_metadata",
        {"cube_alias": "cube", "node_name": "node", "key": "text", "type": "STRING"},
    )

    _builder(panel).add_input_row(
        label="text",
        widget=field,
        field_behavior=FieldBehavior(field_key="text"),
        content_layout=content_layout,
    )

    row_layout = _single_row_layout(content_layout)

    assert row_layout.stretch(1) == 0
    assert row_layout.stretch(2) == 1
    field_item = row_layout.itemAt(2)
    assert field_item is not None
    assert field_item.alignment() == Qt.AlignmentFlag.AlignVCenter


def test_non_string_line_edit_single_row_keeps_label_surplus() -> None:
    """Line edits used for non-string scalar fallbacks should keep compact sizing."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = LineEdit(panel)
    field.setProperty(
        "input_metadata",
        {"cube_alias": "cube", "node_name": "node", "key": "big_int", "type": "INT"},
    )

    _builder(panel).add_input_row(
        label="big_int",
        widget=field,
        field_behavior=FieldBehavior(field_key="big_int"),
        content_layout=content_layout,
    )

    row_layout = _single_row_layout(content_layout)

    assert row_layout.stretch(1) == 1
    assert row_layout.stretch(2) == 0


def test_model_picker_progress_clamps_clears_and_preserves_size_hint() -> None:
    """Model-load progress should not change model picker layout geometry."""

    _ensure_qapp()
    panel = _Panel()
    field = ModelPickerField(
        panel,
        choice_source=_FakeModelCatalog(),
        current_value="models/base.safetensors",
    )
    size_hint = field.sizeHint()
    minimum_hint = field.minimumSizeHint()

    field.set_model_load_progress(percent=42.6, active=True)

    assert field.model_load_progress() == (42.6, True)
    assert field.model_load_progress_pulsing() is False
    assert field.sizeHint() == size_hint
    assert field.minimumSizeHint() == minimum_hint

    field.set_model_load_progress(percent=99.0, active=True)

    assert field.model_load_progress() == (99.0, True)
    assert field.model_load_progress_pulsing() is True
    assert field.sizeHint() == size_hint
    assert field.minimumSizeHint() == minimum_hint

    field.set_model_load_progress(percent=None, active=False)

    assert field.model_load_progress() == (None, False)
    assert field.model_load_progress_pulsing() is False


def test_model_picker_progress_uses_straight_bottom_edge() -> None:
    """Model-load progress should avoid the combo's rounded bottom corners."""

    _ensure_qapp()
    panel = _Panel()
    field = ModelPickerField(
        panel,
        choice_source=_FakeModelCatalog(),
        current_value="models/base.safetensors",
    )
    field.resize(210, 34)
    field.set_model_load_progress(percent=100.0, active=True)
    surface = field.findChild(QWidget, "modelPickerComboSurface")

    assert surface is not None
    progress_rect = cast(_ProgressSurface, surface)._model_load_progress_rect()
    assert progress_rect.left() > 0
    assert progress_rect.right() < surface.width() - 1
    assert progress_rect.width() == surface.width() - (2 * progress_rect.left())


def test_combo_single_row_keeps_label_surplus() -> None:
    """Ordinary combo rows should keep surplus allocation on the label."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = ComboBox(panel)
    field.addItem("AIDXLVAE.safetensors")

    _builder(panel).add_input_row(
        label="vae_name",
        widget=field,
        field_behavior=FieldBehavior(field_key="vae_name"),
        content_layout=content_layout,
    )

    row_layout = _single_row_layout(content_layout)

    assert row_layout.stretch(1) == 1
    assert row_layout.stretch(2) == 0


def test_plain_widget_single_row_keeps_label_surplus() -> None:
    """Non-wide rows should preserve the existing label-owned surplus behavior."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = QWidget(panel)

    _builder(panel).add_input_row(
        label="plain_field",
        widget=field,
        field_behavior=FieldBehavior(field_key="plain_field"),
        content_layout=content_layout,
    )

    row_layout = _single_row_layout(content_layout)

    assert row_layout.stretch(1) == 1
    assert row_layout.stretch(2) == 0


def test_combo_grouped_column_keeps_label_surplus() -> None:
    """Ordinary combo columns should match normal scalar row spacing."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = ComboBox(panel)
    field.addItem("Straight Abs.")

    _builder(panel).add_n_column_row(
        fields=[("method", field)],
        field_behaviors={"method": FieldBehavior(field_key="method")},
        content_layout=content_layout,
        node_name="vectorscopecc",
    )

    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    row_layout = row_container.layout()
    assert isinstance(row_layout, QHBoxLayout)
    col_item = row_layout.itemAt(0)
    assert col_item is not None
    col = col_item.widget()
    assert col is not None
    col_layout = col.layout()
    assert isinstance(col_layout, QHBoxLayout)

    assert col_layout.stretch(1) == 1
    assert col_layout.stretch(2) == 0


def test_model_picker_grouped_column_gives_surplus_to_field_not_label() -> None:
    """Grouped model picker columns should allocate flexible width to the field."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = ModelPickerField(
        panel,
        choice_source=_FakeModelCatalog(),
        current_value="models/base.safetensors",
    )

    _builder(panel).add_n_column_row(
        fields=[("ckpt_name", field)],
        field_behaviors={"ckpt_name": FieldBehavior(field_key="ckpt_name")},
        content_layout=content_layout,
        node_name="checkpoint_loader",
    )

    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    row_layout = row_container.layout()
    assert isinstance(row_layout, QHBoxLayout)
    col_item = row_layout.itemAt(0)
    assert col_item is not None
    col = col_item.widget()
    assert col is not None
    col_layout = col.layout()
    assert isinstance(col_layout, QHBoxLayout)

    assert col_layout.stretch(1) == 0
    assert col_layout.stretch(2) == 1


def test_string_line_edit_grouped_column_gives_surplus_to_field_not_label() -> None:
    """Grouped string line edits should also own flexible column width."""

    _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = LineEdit(panel)
    field.setProperty(
        "input_metadata",
        {"cube_alias": "cube", "node_name": "node", "key": "text", "type": "STRING"},
    )

    _builder(panel).add_n_column_row(
        fields=[("text", field)],
        field_behaviors={"text": FieldBehavior(field_key="text")},
        content_layout=content_layout,
        node_name="node",
    )

    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    row_layout = row_container.layout()
    assert isinstance(row_layout, QHBoxLayout)
    col_item = row_layout.itemAt(0)
    assert col_item is not None
    col = col_item.widget()
    assert col is not None
    col_layout = col.layout()
    assert isinstance(col_layout, QHBoxLayout)

    assert col_layout.stretch(1) == 0
    assert col_layout.stretch(2) == 1
