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

"""Build choice and model-picker field widgets from prepared field inputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    is_choice_field_type,
    resolve_choice_inventory_for_field,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshot,
)
from substitute.presentation.editor.panel.choice_items import (
    prepare_choice_items,
    selected_choice_label,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.widgets.fields.choice_combo import (
    EditorChoiceComboBox,
)
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
    ModelPickerThumbnailPreloadRoute,
)

_EDITOR_COMBO_MAX_HINT_WIDTH = 360


@dataclass(frozen=True, slots=True)
class ChoiceFieldBuildRequest:
    """Carry prepared choice field data and injected model-choice services."""

    parent: Any
    field_behavior: FieldBehavior
    node_name: str
    key: str
    value: object
    field_meta: dict[str, object]
    model_choice_snapshot: PanelModelChoiceSnapshot | None = None
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None
    node_definition_gateway: NodeDefinitionGateway | None = None
    thumbnail_preload_route_factory: (
        Callable[[QWidget], ModelPickerThumbnailPreloadRoute] | None
    ) = None
    node_type: object = None
    field_type: object = None
    field_info: object = None


class ChoiceFieldFactory:
    """Build explicit model pickers, inferred model choices, and combo boxes."""

    def build_field_widget(self, request: ChoiceFieldBuildRequest) -> object | None:
        """Return a choice widget, or None when this field is not choice-like."""

        if request.field_behavior.presentation == FieldPresentation.MODEL_PICKER:
            model_kind = request.field_behavior.style.get("model_kind")
            if not isinstance(model_kind, str) or not model_kind.strip():
                raise RuntimeError(
                    f"MODEL_PICKER field {request.node_name}.{request.key} "
                    "requires style['model_kind']."
                )
            return _build_prepared_model_picker(
                parent=request.parent,
                key=request.key,
                value=request.value,
                model_choice_snapshot=request.model_choice_snapshot,
                thumbnail_asset_repository=request.thumbnail_asset_repository,
                model_metadata_action_handler=request.model_metadata_action_handler,
                thumbnail_preload_route_factory=request.thumbnail_preload_route_factory,
            )

        if request.field_behavior.presentation != FieldPresentation.STANDARD:
            return None
        if not is_choice_field_type(request.field_type):
            return None

        if (
            request.model_choice_snapshot is not None
            and request.model_choice_snapshot.should_build_picker
        ):
            return _build_prepared_model_picker(
                parent=request.parent,
                key=request.key,
                value=request.value,
                model_choice_snapshot=request.model_choice_snapshot,
                thumbnail_asset_repository=request.thumbnail_asset_repository,
                model_metadata_action_handler=request.model_metadata_action_handler,
                thumbnail_preload_route_factory=request.thumbnail_preload_route_factory,
            )

        return widget_factory_list_str(
            request.parent,
            request.node_name,
            request.key,
            request.value,
            request.field_meta,
            field_type=request.field_type,
            node_type=request.node_type,
            node_definition_gateway=request.node_definition_gateway,
            field_info=request.field_info,
        )


def resolve_choice_options_for_field(
    *,
    key: str,
    node_type: object,
    node_definition_gateway: object,
    field_info: object,
    value: object,
) -> tuple[str, ...]:
    """Return renderable choice options from live Comfy definitions only."""

    _ = value
    inventory = resolve_choice_inventory_for_field(
        key=key,
        node_type=node_type,
        node_definition_gateway=node_definition_gateway,
        field_info=field_info,
    )
    return inventory.string_options


def _build_prepared_model_picker(
    *,
    parent: Any,
    key: str,
    value: object,
    model_choice_snapshot: PanelModelChoiceSnapshot | None,
    thumbnail_asset_repository: ThumbnailAssetRepository | None,
    model_metadata_action_handler: ModelMetadataContextActionHandler | None,
    thumbnail_preload_route_factory: (
        Callable[[QWidget], ModelPickerThumbnailPreloadRoute] | None
    ),
) -> object:
    """Build a model picker from a prepared model-choice snapshot."""

    if model_choice_snapshot is None or model_choice_snapshot.choice_source is None:
        raise RuntimeError(f"Model picker field {key} requires a prepared snapshot.")
    picker_started_at = panel_projection_observability_started_at()
    picker = ModelPickerField(
        parent,
        choice_source=model_choice_snapshot.choice_source,
        thumbnail_asset_repository=thumbnail_asset_repository,
        current_value=str(value) if value is not None else "",
        search_placeholder=model_choice_snapshot.search_placeholder,
        metadata_action_handler=model_metadata_action_handler,
        thumbnail_preload_route_factory=thumbnail_preload_route_factory,
    )
    log_panel_projection_timing(
        "choice_factory.model_picker_construct",
        started_at=picker_started_at,
        field_key=key,
        model_kind=model_choice_snapshot.model_kind or "",
        option_count=len(model_choice_snapshot.options),
        readiness=model_choice_snapshot.status.readiness.value,
    )
    return picker


def widget_factory_list_str(
    parent: QWidget | None,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build combo widgets for choice inputs using injected live node definitions."""

    if not is_choice_field_type(kwargs.get("field_type")):
        return None
    node_type = kwargs.get("node_type")
    trace_context = {
        "cube_alias": (
            str(field_meta.get("cube_alias", ""))
            if isinstance(field_meta, dict)
            else ""
        ),
        "node_name": node_name,
        "field_key": key,
        "node_class": node_type if isinstance(node_type, str) else "",
        "projection_mode": "live",
    }
    resolve_started_at = panel_projection_observability_started_at()
    inventory = resolve_choice_inventory_for_field(
        key=key,
        node_type=node_type,
        node_definition_gateway=kwargs.get("node_definition_gateway"),
        field_info=kwargs.get("field_info"),
    )
    log_panel_projection_timing(
        "choice_factory.combo_resolve_options",
        started_at=resolve_started_at,
        option_count=len(inventory.options),
        **trace_context,
    )
    options = list(inventory.string_options)
    node_data = field_meta.get("node_data") if isinstance(field_meta, dict) else None
    prepare_started_at = panel_projection_observability_started_at()
    combo_items = prepare_choice_items(
        key=key,
        node_data=node_data,
        options=options,
    )
    log_panel_projection_timing(
        "choice_factory.combo_prepare_items",
        started_at=prepare_started_at,
        option_count=len(options),
        **trace_context,
    )
    combo = EditorChoiceComboBox(parent)
    combo.setMaxHintWidth(_EDITOR_COMBO_MAX_HINT_WIDTH)
    set_property = getattr(combo, "setProperty", None)
    if callable(set_property):
        set_property("choice_availability", inventory.availability.value)
    set_enabled = getattr(combo, "setEnabled", None)
    if callable(set_enabled):
        set_enabled(bool(options))
    selected_label = selected_choice_label(
        key=key,
        node_data=node_data,
        items=combo_items,
        value=value,
    )
    combo.reconcile_choice_items(combo_items, selected_label)

    parent_with_registries = cast(Any, parent)

    if (
        key == "sampler_name"
        and node_data is not None
        and hasattr(parent_with_registries, "sampler_link_widgets")
    ):
        cube_alias = (
            field_meta.get("cube_alias") if isinstance(field_meta, dict) else None
        )
        if (
            cube_alias is None
            and isinstance(node_data, dict)
            and "cube_alias" in node_data
        ):
            cube_alias = node_data["cube_alias"]
        if cube_alias is not None:
            parent_with_registries.sampler_link_widgets[(cube_alias, node_name)] = combo

    if (
        key == "scheduler"
        and node_data is not None
        and hasattr(parent_with_registries, "scheduler_link_widgets")
    ):
        cube_alias = (
            field_meta.get("cube_alias") if isinstance(field_meta, dict) else None
        )
        if (
            cube_alias is None
            and isinstance(node_data, dict)
            and "cube_alias" in node_data
        ):
            cube_alias = node_data["cube_alias"]
        if cube_alias is not None:
            parent_with_registries.scheduler_link_widgets[(cube_alias, node_name)] = (
                combo
            )

    return combo
