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
from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CheckBox, LineEdit  # type: ignore[import-untyped]
from substitute.application.node_behavior import (
    FieldBehavior,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_ROW_HEIGHT,
    GROUPED_FIELD_DIVIDER_WIDTH,
)
from substitute.presentation.editor.panel.factories.numeric_factory import (
    _build_color_slider_widget,
    _build_int_spinner_slider_widget,
    _build_spinner_slider_widget,
)
from substitute.presentation.widgets import (
    ComboBox,
    DoubleSpinBox,
    DragOnlySlider,
    SeedBox,
    SpinBox,
)
from tests.support.qt.lifecycle import activate_widget_layouts, destroy_widget_roots
from .geometry_support import (
    _Panel,
    _add_inline_row,
    _assert_field_row_divider_theme_style,
    _assert_scalar_row_height,
    _builder,
    _content_with_layout,
    _ensure_qapp,
    _model_picker,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
)
from .geometry_support import (
    _build_factory_widget,
    _ksampler_field_spec,
)
from typing import cast
from qfluentwidgets import CaptionLabel
from substitute.application.node_behavior import (
    FieldPresentation,
)


@pytest.fixture(autouse=True)
def dispose_owned_panels() -> Iterator[None]:
    """Destroy this owner's panels after each geometry contract."""

    yield
    application = _ensure_qapp()
    destroy_widget_roots(
        widget for widget in application.topLevelWidgets() if isinstance(widget, _Panel)
    )


def test_seed_alias_rows_preserve_shared_widget_geometry_and_visible_labels() -> None:
    """Cube and Comfy seed aliases should differ only in authored label text."""

    app = _ensure_qapp()
    panel = _Panel()
    panel.resize(600, 160)
    seed = SeedBox(panel)
    noise_seed = SeedBox(panel)
    builder = _builder(panel)

    seed_row = builder.build_input_row(
        label="seed",
        widget=seed,
        field_behavior=FieldBehavior(
            field_key="seed",
            presentation=FieldPresentation.SEED_BOX,
        ),
    ).row
    noise_seed_row = builder.build_input_row(
        label="noise_seed",
        widget=noise_seed,
        field_behavior=FieldBehavior(
            field_key="noise_seed",
            presentation=FieldPresentation.SEED_BOX,
        ),
    ).row
    seed_row.setGeometry(0, 0, 600, EDITOR_FIELD_ROW_HEIGHT)
    noise_seed_row.setGeometry(0, EDITOR_FIELD_ROW_HEIGHT, 600, EDITOR_FIELD_ROW_HEIGHT)
    panel.show()
    seed_row.show()
    noise_seed_row.show()
    for row in (seed_row, noise_seed_row):
        layout = row.layout()
        assert isinstance(layout, QHBoxLayout)
        layout.activate()
    app.processEvents()

    seed_layout = cast(QHBoxLayout, seed_row.layout())
    noise_layout = cast(QHBoxLayout, noise_seed_row.layout())
    seed_label_item = seed_layout.itemAt(1)
    noise_label_item = noise_layout.itemAt(1)
    assert seed_label_item is not None
    assert noise_label_item is not None
    seed_label = seed_label_item.widget()
    noise_label = noise_label_item.widget()
    assert isinstance(seed_label, CaptionLabel)
    assert isinstance(noise_label, CaptionLabel)
    assert seed_label.text() == "Seed"
    assert noise_label.text() == "Noise Seed"
    assert seed_label.isVisible()
    assert noise_label.isVisible()
    assert seed.size() == noise_seed.size()
    assert seed.sizeHint() == noise_seed.sizeHint()
    assert seed.minimumSizeHint() == noise_seed.minimumSizeHint()
    assert seed.sizePolicy() == noise_seed.sizePolicy()
    assert seed.line_edit.geometry() == noise_seed.line_edit.geometry()
    assert seed.split_button.geometry() == noise_seed.split_button.geometry()

    panel.close()


def test_horizontal_divider_keeps_geometry_and_uses_qfluent_theme_style() -> None:
    """Horizontal field dividers should not change geometry while becoming themed."""

    _ensure_qapp()
    panel = _Panel()
    divider = _builder(panel).make_horizontal_divider(panel)

    assert isinstance(divider, QWidget)
    assert divider.height() == 1
    assert divider.minimumHeight() == 1
    assert divider.maximumHeight() == 1
    assert divider.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert divider.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    _assert_field_row_divider_theme_style(divider)


def test_scalar_single_field_rows_share_combo_row_height() -> None:
    """Scalar inline rows should center controls inside the visual field-row height."""

    _ensure_qapp()
    panel = _Panel()
    combo = ComboBox(panel)
    combo.addItem("AIDXLVAE.safetensors")
    scalar_widgets = {
        "combo": combo,
        "line_edit": LineEdit(panel),
        "spinbox": SpinBox(panel),
        "double_spinbox": DoubleSpinBox(panel),
        "seed": SeedBox(panel),
        "checkbox": CheckBox("Enable", panel),
        "model_picker": _model_picker(panel),
        "spinner_slider": _build_spinner_slider_widget(panel, 0.5, 0.0, 1.0, 0.1),
    }

    for field_key, widget in scalar_widgets.items():
        content, row = _add_inline_row(
            panel=panel,
            widget=widget,
            field_key=field_key,
        )

        host = _assert_scalar_row_height(row, content)
        destroy_widget_roots([host])


def test_editor_spinbox_geometry_matches_pre_qfluent_contract() -> None:
    """Editor spin boxes should keep the old panel-stylesheet geometry."""

    _ensure_qapp()
    panel = _Panel()
    panel.setStyleSheet(
        """
        QSpinBox, QDoubleSpinBox {
            min-width: 48px;
            max-width: 48px;
            height: 32px;
        }
        """
    )
    spinbox = SpinBox(panel)
    double_spinbox = DoubleSpinBox(panel)
    spinbox.setSymbolVisible(False)
    double_spinbox.setSymbolVisible(False)
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(0, 0, 0, 0)
    panel_layout.setSpacing(0)
    rendered_fields: list[tuple[QWidget, QWidget, SpinBox | DoubleSpinBox]] = []

    for field_key, widget in (
        ("steps", spinbox),
        ("cfg", double_spinbox),
    ):
        content, row = _add_inline_row(
            panel=panel,
            widget=widget,
            field_key=field_key,
        )
        panel_layout.addWidget(content)
        rendered_fields.append((content, row, widget))

    panel.resize(500, panel.sizeHint().height())
    panel.show()
    activate_widget_layouts(
        panel,
        *(content for content, _row, _widget in rendered_fields),
        *(row for _content, row, _widget in rendered_fields),
    )
    try:
        for _content, _row, widget in rendered_fields:
            assert widget.width() == 54
            assert widget.minimumWidth() == 54
            assert widget.maximumWidth() == 54
            assert widget.lineEdit().geometry() == QRect(3, 3, 48, 27)
    finally:
        destroy_widget_roots([panel])


def test_spinner_slider_visuals_center_inside_editor_control_height() -> None:
    """Spinner-slider composites should center native slider visuals on the spinbox."""

    _ensure_qapp()
    panel = _Panel()
    fields = (
        _build_spinner_slider_widget(panel, 0.5, 0.0, 1.0, 0.1),
        _build_int_spinner_slider_widget(panel, 5, 1, 9, 1),
        _build_color_slider_widget(panel, 0.5, 0.0, 1.0, 0.1),
    )

    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(0)
    for field in fields:
        host_layout.addWidget(field)
    host.resize(260, EDITOR_ROW_HEIGHT * len(fields))
    host.show()
    activate_widget_layouts(host, *fields)
    try:
        for field in fields:
            slider = field.findChild(DragOnlySlider)
            spinbox = field.findChild(DoubleSpinBox) or field.findChild(SpinBox)
            assert slider is not None
            assert spinbox is not None
            assert field.height() == EDITOR_ROW_HEIGHT
            assert spinbox.height() == EDITOR_ROW_HEIGHT
            assert slider.height() == 22
            slider_visual_center_y = slider.geometry().y() + (slider.height() // 2)
            assert slider_visual_center_y == spinbox.geometry().center().y()
    finally:
        destroy_widget_roots([host])


def test_grouped_scalar_row_uses_combo_row_height_for_shorter_controls() -> None:
    """Grouped spinbox-only rows should not shrink below the scalar row contract."""

    _ensure_qapp()
    panel = _Panel()
    content, content_layout = _content_with_layout(panel)
    spinbox = SpinBox(panel)
    double_spinbox = DoubleSpinBox(panel)

    _builder(panel).add_n_column_row(
        fields=[("steps", spinbox), ("cfg", double_spinbox)],
        field_behaviors={
            "steps": FieldBehavior(field_key="steps"),
            "cfg": FieldBehavior(field_key="cfg"),
        },
        content_layout=content_layout,
        node_name="ksampler",
    )

    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    host = _assert_scalar_row_height(row_container, content)
    destroy_widget_roots([host])


def test_grouped_scalar_vertical_divider_uses_row_height() -> None:
    """Grouped scalar row dividers should follow the scalar row height metric."""

    _ensure_qapp()
    panel = _Panel()
    content, content_layout = _content_with_layout(panel)
    combo = ComboBox(panel)
    combo.addItem("euler")
    field_key = ("cube", "ksampler", "sampler_name")
    combo.setProperty(
        "input_metadata",
        {"cube_alias": "cube", "node_name": "ksampler", "key": "sampler_name"},
    )

    _builder(panel).add_n_column_row(
        fields=[("sampler_name", combo), ("steps", SpinBox(panel))],
        field_behaviors={
            "sampler_name": FieldBehavior(field_key="sampler_name"),
            "steps": FieldBehavior(field_key="steps"),
        },
        content_layout=content_layout,
        node_name="ksampler",
    )

    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    row_layout = row_container.layout()
    assert isinstance(row_layout, QHBoxLayout)
    divider_item = row_layout.itemAt(1)
    assert divider_item is not None
    divider = divider_item.widget()
    assert divider is not None

    host = _assert_scalar_row_height(row_container, content)
    try:
        assert divider.width() == GROUPED_FIELD_DIVIDER_WIDTH
        assert divider.minimumWidth() == GROUPED_FIELD_DIVIDER_WIDTH
        assert divider.maximumWidth() == GROUPED_FIELD_DIVIDER_WIDTH
        assert divider.height() == EDITOR_ROW_HEIGHT
        assert divider.minimumHeight() == EDITOR_ROW_HEIGHT
        assert divider.maximumHeight() == EDITOR_ROW_HEIGHT
        assert divider.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
        assert divider.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
        assert tuple(divider.property("vertical_divider_for_field")) == field_key
        _assert_field_row_divider_theme_style(divider)
    finally:
        destroy_widget_roots([host])


def test_grouped_sampler_scheduler_seed_row_uses_equal_columns_when_rendered() -> None:
    """Rendered grouped scalar rows should divide row width across columns."""

    app = _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    sampler = ComboBox(panel)
    sampler.addItem("er_sde")
    scheduler = ComboBox(panel)
    scheduler.addItem("simple")
    seed = SeedBox(panel)
    seed.setFixedWidth(190)

    _builder(panel).add_n_column_row(
        fields=[
            ("sampler_name", sampler),
            ("scheduler", scheduler),
            ("seed", seed),
        ],
        field_behaviors={
            "sampler_name": FieldBehavior(field_key="sampler_name"),
            "scheduler": FieldBehavior(field_key="scheduler"),
            "seed": FieldBehavior(field_key="seed"),
        },
        content_layout=content_layout,
        node_name="ksampler",
    )
    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    panel.resize(1500, EDITOR_FIELD_ROW_HEIGHT)
    content.resize(1500, EDITOR_FIELD_ROW_HEIGHT)
    row_container.resize(1500, EDITOR_FIELD_ROW_HEIGHT)
    content.show()
    panel.show()
    row_container.show()

    app.processEvents()
    content_layout.activate()
    layout = row_container.layout()
    assert isinstance(layout, QHBoxLayout)
    layout.activate()
    app.processEvents()

    columns: list[QWidget] = []
    for item in (layout.itemAt(0), layout.itemAt(2), layout.itemAt(4)):
        assert item is not None
        column = item.widget()
        assert column is not None
        columns.append(column)
    first_column = columns[0]
    second_column = columns[1]
    third_column = columns[2]
    column_widths = [column.geometry().width() for column in columns]
    for column in (first_column, second_column, third_column):
        column_layout = column.layout()
        assert isinstance(column_layout, QHBoxLayout)
        column_layout.activate()
        label_item = column_layout.itemAt(1)
        control_item = column_layout.itemAt(2)
        assert label_item is not None
        assert control_item is not None
        label = label_item.widget()
        control = control_item.widget()
        assert label is not None
        assert control is not None
        assert control.geometry().x() - label.geometry().right() - 1 == 6

    assert second_column.geometry().x() - first_column.geometry().right() - 1 <= 16
    assert third_column.geometry().x() - second_column.geometry().right() - 1 <= 16
    assert max(column_widths) - min(column_widths) <= 1
    assert row_container.width() - third_column.geometry().right() <= 40


def test_factory_built_grouped_sampler_scheduler_seed_row_uses_equal_columns() -> None:
    """Production-built KSampler grouped rows should divide available row width."""

    app = _ensure_qapp()
    panel = _Panel()
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    sampler_spec = _ksampler_field_spec(
        field_key="sampler_name",
        field_type="LIST",
        value="er_sde",
        field_info=[["er_sde", "euler"], {"default": "er_sde"}],
    )
    scheduler_spec = _ksampler_field_spec(
        field_key="scheduler",
        field_type="LIST",
        value="simple",
        field_info=[["simple", "normal"], {"default": "simple"}],
    )
    seed_spec = _ksampler_field_spec(
        field_key="seed",
        field_type="INT",
        value=49961946963557422,
    )
    sampler = _build_factory_widget(panel, sampler_spec)
    scheduler = _build_factory_widget(panel, scheduler_spec)
    seed = _build_factory_widget(panel, seed_spec)

    _builder(panel).add_n_column_row(
        fields=[
            ("sampler_name", sampler),
            ("scheduler", scheduler),
            ("seed", seed),
        ],
        field_behaviors={
            "sampler_name": sampler_spec.field_behavior,
            "scheduler": scheduler_spec.field_behavior,
            "seed": seed_spec.field_behavior,
        },
        content_layout=content_layout,
        node_name="ksampler",
    )
    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row_container = row_item.widget()
    assert row_container is not None
    panel.resize(1500, EDITOR_FIELD_ROW_HEIGHT)
    content.resize(1500, EDITOR_FIELD_ROW_HEIGHT)
    row_container.resize(1500, EDITOR_FIELD_ROW_HEIGHT)
    content.show()
    panel.show()
    row_container.show()

    app.processEvents()
    content_layout.activate()
    layout = row_container.layout()
    assert isinstance(layout, QHBoxLayout)
    layout.activate()
    app.processEvents()

    columns: list[QWidget] = []
    for item in (layout.itemAt(0), layout.itemAt(2), layout.itemAt(4)):
        assert item is not None
        column = item.widget()
        assert column is not None
        columns.append(column)

    column_widths = [column.geometry().width() for column in columns]
    previous_right: int | None = None
    for column in columns:
        column_layout = column.layout()
        assert isinstance(column_layout, QHBoxLayout)
        column_layout.activate()
        label_item = column_layout.itemAt(1)
        control_item = column_layout.itemAt(2)
        assert label_item is not None
        assert control_item is not None
        label = label_item.widget()
        control = control_item.widget()
        assert label is not None
        assert control is not None
        assert control.geometry().x() - label.geometry().right() - 1 == 6
        if previous_right is not None:
            assert column.geometry().x() - previous_right - 1 <= 16
        previous_right = column.geometry().right()

    assert max(column_widths) - min(column_widths) <= 1
    assert row_container.width() - columns[-1].geometry().right() <= 40
