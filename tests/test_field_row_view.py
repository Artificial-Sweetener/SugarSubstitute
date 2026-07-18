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

"""Contract tests for editor field-row layout ownership."""

from __future__ import annotations

import os
from typing import Protocol, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CaptionLabel, CheckBox, LineEdit  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    CustomStyleSheet,
    styleSheetManager,
)

from substitute.application.model_metadata import (
    ModelCatalogItem,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    ResolvedFieldSpec,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    build_widget_for_field_spec,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
    EDITOR_ROW_HEIGHT,
    GROUPED_FIELD_DIVIDER_WIDTH,
)
from substitute.presentation.editor.panel.factories.numeric_factory import (
    _build_color_slider_widget,
    _build_int_spinner_slider_widget,
    _build_spinner_slider_widget,
)
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder
from substitute.presentation.widgets import (
    ComboBox,
    DoubleSpinBox,
    DragOnlySlider,
    SeedBox,
    SpinBox,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)


class _ProgressSurface(Protocol):
    """Expose model-picker progress geometry for focused widget contracts."""

    def _model_load_progress_rect(self) -> QRect:
        """Return the private progress paint rect."""


class _Panel(QWidget):
    """Minimal panel stand-in that exposes row visibility state."""

    def __init__(self) -> None:
        """Initialize row tracking used by FieldRowBuilder."""

        super().__init__()
        self.row_widgets: dict[object, tuple[QWidget, QWidget | None]] = {}
        self.col_widgets: dict[object, tuple[QWidget, QWidget, QWidget]] = {}
        self._hidden_field_keys: set[object] = set()
        self.sampler_link_widgets: dict[object, QWidget] = {}
        self.scheduler_link_widgets: dict[object, QWidget] = {}


class _FakeModelCatalog:
    """Return deterministic model metadata for model-picker row tests."""

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return one fake model row for the requested kind."""

        return (
            ModelCatalogItem(
                kind=kind,
                backend_value="models/base.safetensors",
                display_name="Base Model",
                display_subtitle="v1",
                relative_path="models/base.safetensors",
                folder="models",
                basename="base.safetensors",
                extension=".safetensors",
                thumbnail_variants=(),
                base_model=None,
                trained_words=(),
                tags=(),
                model_page_url=None,
                collision_key="base",
                collision_count=1,
                has_collision=False,
                search_text="base model v1",
            ),
        )

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return the same fake model row for refresh calls."""

        return self.list_models(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation because tests control fake catalog rows directly."""

        _ = kind

    def current_resolution(self) -> RichChoiceResolution:
        """Return the fake model row as a rich-choice source resolution."""

        item = self.list_models("checkpoints")[0]
        return RichChoiceResolution(
            items=(
                RichChoiceItem(
                    value=item.backend_value,
                    title=item.display_name,
                    subtitle=item.display_subtitle,
                    search_text=item.search_text,
                    model_kind=item.kind,
                    catalog_item=item,
                    thumbnail_variants=item.thumbnail_variants,
                    is_enriched=True,
                    is_ambiguous=False,
                ),
            ),
            should_use_rich_picker=True,
            matched_kinds=("checkpoints",),
            option_count=1,
            enriched_count=1,
            ambiguous_count=0,
            unmatched_count=0,
            reason="test fixture",
        )

    def refresh(self) -> RichChoiceResolution:
        """Return the same fake rich-choice resolution for refresh calls."""

        return self.current_resolution()


class _KSamplerNodeDefinitionGateway:
    """Return live KSampler options for production field factory tests."""

    def get_node_definition(self, node_type: str) -> dict[str, object]:
        """Return the minimal KSampler node definition used by combo factories."""

        if node_type != "KSampler":
            return {}
        return {
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": (["er_sde", "euler"], {}),
                        "scheduler": (["simple", "normal"], {}),
                    }
                }
            }
        }

    def get_required_node_definition(self, node_type: str) -> dict[str, object]:
        """Return the KSampler definition or an empty mapping."""

        return self.get_node_definition(node_type)


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication used by field-row widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _builder(panel: _Panel) -> FieldRowBuilder:
    """Return a FieldRowBuilder with inert icon collaborators."""

    def _resolve_icon(
        node_name: str, label: str, column_index: int | None = None
    ) -> None:
        """Return no icon for row-builder tests."""

        _ = (node_name, label, column_index)
        return None

    return FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=_resolve_icon,
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


def _ksampler_field_spec(
    *,
    field_key: str,
    field_type: str,
    value: object,
    field_info: list[object] | None = None,
) -> ResolvedFieldSpec:
    """Build one production-style KSampler field spec for row rendering tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="ksampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info={"cube_alias": "A", "node_data": {"cube_alias": "A"}},
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(field_key=field_key),
    )


def _build_factory_widget(panel: QWidget, spec: ResolvedFieldSpec) -> QWidget:
    """Build one field widget through the production field factory pipeline."""

    widget = build_widget_for_field_spec(
        parent=panel,
        field_spec=spec,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        node_definition_gateway=_KSamplerNodeDefinitionGateway(),
    )
    assert isinstance(widget, QWidget)
    return widget


def _single_row_layout(content_layout: QVBoxLayout) -> QHBoxLayout:
    """Return the generated single-field row layout from a content layout."""

    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row = row_item.widget()
    assert row is not None
    layout = row.layout()
    assert isinstance(layout, QHBoxLayout)
    return layout


def _content_with_layout(parent: QWidget) -> tuple[QWidget, QVBoxLayout]:
    """Return a content widget using the node-card body layout defaults."""

    content = QWidget(parent)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(12)
    return content, content_layout


def _layout_content_at_natural_height(content: QWidget) -> QWidget:
    """Show content at its natural height so row actual heights are meaningful."""

    app = _ensure_qapp()
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.addWidget(content)
    host.resize(500, content.sizeHint().height())
    host.show()
    for _ in range(6):
        app.processEvents()
    return host


def _assert_scalar_row_height(row: QWidget, content: QWidget) -> None:
    """Assert one scalar row contributes and receives the standard visual height."""

    host = _layout_content_at_natural_height(content)
    try:
        assert row.sizeHint().height() == EDITOR_FIELD_ROW_HEIGHT
        assert row.minimumSizeHint().height() == EDITOR_FIELD_ROW_HEIGHT
        assert row.height() == EDITOR_FIELD_ROW_HEIGHT
    finally:
        host.close()
        host.deleteLater()
        _ensure_qapp().processEvents()


def _assert_field_row_divider_theme_style(divider: QWidget) -> None:
    """Assert one divider uses QFluent-owned theme QSS instead of palette fill."""

    light_qss = divider.property(CustomStyleSheet.LIGHT_QSS_KEY)
    dark_qss = divider.property(CustomStyleSheet.DARK_QSS_KEY)
    assert isinstance(light_qss, str)
    assert isinstance(dark_qss, str)
    assert "rgba(0, 0, 0, 15)" in light_qss
    assert "rgba(0, 0, 0, 25)" in dark_qss
    assert "palette(window)" not in divider.styleSheet()
    assert "palette(window)" not in light_qss
    assert "palette(window)" not in dark_qss
    assert divider in styleSheetManager.widgets


def _add_inline_row(
    *,
    panel: _Panel,
    widget: QWidget,
    field_key: str,
) -> tuple[QWidget, QWidget]:
    """Build one scalar inline row and return the content plus generated row."""

    content, content_layout = _content_with_layout(panel)
    _builder(panel).add_input_row(
        label=field_key,
        widget=widget,
        field_behavior=FieldBehavior(field_key=field_key),
        content_layout=content_layout,
    )
    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row = row_item.widget()
    assert row is not None
    return content, row


def _model_picker(parent: QWidget) -> ModelPickerField:
    """Return a deterministic model picker for row-height assertions."""

    return ModelPickerField(
        parent,
        choice_source=_FakeModelCatalog(),
        current_value="models/base.safetensors",
    )


def test_horizontal_divider_keeps_geometry_and_uses_qfluent_theme_style() -> None:
    """Horizontal field dividers should not change geometry while becoming themed."""

    _ensure_qapp()
    panel = _Panel()
    try:
        divider = _builder(panel).make_horizontal_divider(panel)

        assert isinstance(divider, QWidget)
        assert divider.height() == 1
        assert divider.minimumHeight() == 1
        assert divider.maximumHeight() == 1
        assert divider.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert divider.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
        _assert_field_row_divider_theme_style(divider)
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


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

        _assert_scalar_row_height(row, content)


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

    for field_key, widget in (
        ("steps", spinbox),
        ("cfg", double_spinbox),
    ):
        content, _row = _add_inline_row(
            panel=panel,
            widget=widget,
            field_key=field_key,
        )

        assert widget.width() == 54
        assert widget.minimumWidth() == 54
        assert widget.maximumWidth() == 54
        assert widget.lineEdit().geometry() == QRect(3, 3, 48, 27)
        content.deleteLater()

    panel.deleteLater()
    _ensure_qapp().processEvents()


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
    for _ in range(6):
        _ensure_qapp().processEvents()
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
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


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
    _assert_scalar_row_height(row_container, content)


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

    _assert_scalar_row_height(row_container, content)
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
