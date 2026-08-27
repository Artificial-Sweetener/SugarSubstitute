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

"""Provide capability-local Qt geometry fixtures, builders, and fakes."""

from __future__ import annotations

from typing import Protocol, cast


from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    CustomStyleSheet,
    styleSheetManager,
)

from substitute.application.model_metadata import (
    ModelCatalogItem,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.node_behavior import (
    FieldBehavior,
    ResolvedFieldSpec,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    build_widget_for_field_spec,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
)
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder
from substitute.presentation.widgets.model_picker import ModelPickerField
from tests.support.qt.lifecycle import activate_widget_layouts


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


class _EmptyPromptAutocompleteGateway:
    """Return no suggestions while factory tests construct non-prompt fields."""

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


class _EmptyPromptWildcardCatalogGateway:
    """Return unresolved wildcard metadata for non-prompt factory construction."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard suggestions."""

        _ = (prefix, limit)
        return ()

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return unresolved references in their input order."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


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
        prompt_autocomplete_gateway=_EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_EmptyPromptWildcardCatalogGateway(),
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

    _ensure_qapp()
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.addWidget(content)
    host.resize(500, content.sizeHint().height())
    host.show()
    activate_widget_layouts(host, content)
    return host


def _assert_scalar_row_height(row: QWidget, content: QWidget) -> QWidget:
    """Mount one scalar row, assert its visual height, and return its host."""

    host = _layout_content_at_natural_height(content)
    assert row.sizeHint().height() == EDITOR_FIELD_ROW_HEIGHT
    assert row.minimumSizeHint().height() == EDITOR_FIELD_ROW_HEIGHT
    assert row.height() == EDITOR_FIELD_ROW_HEIGHT
    return host


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
