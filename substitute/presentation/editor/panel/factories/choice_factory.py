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

from collections.abc import Callable, Mapping, Sequence
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
    extract_live_list_options,
    is_choice_field_type,
)
from substitute.application.overrides.link_policy import (
    build_sampler_choice_items,
    build_scheduler_choice_items,
    resolve_linked_choice_label,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshot,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.presentation.widgets import ComboBox
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
    ModelPickerThumbnailPreloadRoute,
)

_EDITOR_COMBO_MAX_HINT_WIDTH = 360
_COMBO_ITEM_CACHE_MAX_SIZE = 256
_COMBO_ITEM_CACHE: dict[
    tuple[str, tuple[str, ...], tuple[tuple[str, str, str], ...]],
    tuple[tuple[str, object], ...],
] = {}


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


def _resolve_live_choice_options(
    *,
    node_definition_gateway: NodeDefinitionGateway,
    node_type: str,
    key: str,
) -> list[str]:
    """Return normalized live choice options for one node input when available."""

    live_def = node_definition_gateway.get_node_definition(node_type)
    node_def = live_def.get(node_type, {})
    if not isinstance(node_def, dict):
        return []
    input_section = node_def.get("input", {})
    if not isinstance(input_section, dict):
        return []
    required = input_section.get("required", {})
    optional = input_section.get("optional", {})
    live_info = (required.get(key) if isinstance(required, dict) else None) or (
        optional.get(key) if isinstance(optional, dict) else None
    )
    return list(extract_live_list_options(live_info))


def _resolve_list_choice_options(
    *,
    key: str,
    node_type: object,
    node_definition_gateway: object,
    field_info: object,
) -> list[str]:
    """Return exact Comfy choice options from live definitions or field info."""

    options: list[str] | None = None
    if (
        node_type
        and isinstance(node_type, str)
        and isinstance(node_definition_gateway, NodeDefinitionGateway)
    ):
        options = _resolve_live_choice_options(
            node_definition_gateway=node_definition_gateway,
            node_type=node_type,
            key=key,
        )
    if options:
        return options
    return list(extract_live_list_options(field_info))


def _prepared_combo_items(
    *,
    key: str,
    node_data: object,
    options: Sequence[str],
) -> list[tuple[str, object]]:
    """Return combo display/value items from an immutable preparation cache."""

    option_tuple = tuple(options)
    link_signature = _combo_link_signature(key=key, node_data=node_data)
    cache_key = (key, option_tuple, link_signature)
    prepared = _COMBO_ITEM_CACHE.get(cache_key)
    if prepared is None:
        if key == "sampler_name" and isinstance(node_data, dict):
            raw_items = build_sampler_choice_items(node_data, option_tuple)
        elif key == "scheduler" and isinstance(node_data, dict):
            raw_items = build_scheduler_choice_items(node_data, option_tuple)
        else:
            raw_items = [(option, option) for option in option_tuple]
        prepared = tuple(
            (label, _freeze_combo_item_value(value)) for label, value in raw_items
        )
        if len(_COMBO_ITEM_CACHE) >= _COMBO_ITEM_CACHE_MAX_SIZE:
            _COMBO_ITEM_CACHE.clear()
        _COMBO_ITEM_CACHE[cache_key] = prepared
    return [(label, _thaw_combo_item_value(value)) for label, value in prepared]


def _combo_link_signature(
    *,
    key: str,
    node_data: object,
) -> tuple[tuple[str, str, str], ...]:
    """Return immutable link-choice inputs for combo item cache keys."""

    if not isinstance(node_data, dict):
        return ()
    link_key = (
        "sampler_links"
        if key == "sampler_name"
        else "scheduler_links"
        if key == "scheduler"
        else ""
    )
    if not link_key:
        return ()
    link_items = node_data.get(link_key)
    if not isinstance(link_items, list):
        return ()
    signature: list[tuple[str, str, str]] = []
    for item in link_items:
        if isinstance(item, str):
            signature.append(("literal", item, ""))
            continue
        if isinstance(item, dict):
            signature.append(
                (
                    str(item.get("label", "")),
                    str(item.get("from_cube", "")),
                    str(item.get("from_node", "")),
                )
            )
    return tuple(signature)


def _freeze_combo_item_value(value: object) -> object:
    """Return an immutable representation of one combo item backend value."""

    if isinstance(value, Mapping):
        return (
            "__linked_choice__",
            str(value.get("from_cube", "")),
            str(value.get("from_node", "")),
        )
    return value


def _thaw_combo_item_value(value: object) -> object:
    """Return an independent mutable combo backend value when needed."""

    if isinstance(value, tuple) and len(value) == 3 and value[0] == "__linked_choice__":
        return {"from_cube": value[1], "from_node": value[2]}
    return value


def _clear_combo_item_cache_for_tests() -> None:
    """Clear combo item preparation cache for focused tests."""

    _COMBO_ITEM_CACHE.clear()


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
    options = _resolve_list_choice_options(
        key=key,
        node_type=node_type,
        node_definition_gateway=node_definition_gateway,
        field_info=field_info,
    )
    return tuple(options)


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
    live_or_field_options = resolve_choice_options_for_field(
        key=key,
        node_type=node_type,
        node_definition_gateway=kwargs.get("node_definition_gateway"),
        field_info=kwargs.get("field_info"),
        value=value,
    )
    log_panel_projection_timing(
        "choice_factory.combo_resolve_options",
        started_at=resolve_started_at,
        option_count=len(live_or_field_options),
        **trace_context,
    )
    options = list(live_or_field_options)
    if not options:
        raise RuntimeError(
            f"Failed to resolve live Comfy options for {node_type}.{key}."
        )
    node_data = field_meta.get("node_data") if isinstance(field_meta, dict) else None
    prepare_started_at = panel_projection_observability_started_at()
    combo_items = _prepared_combo_items(
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
    label_to_value = {label: choice_value for label, choice_value in combo_items}
    combo = ComboBox(parent)
    combo.setMaxHintWidth(_EDITOR_COMBO_MAX_HINT_WIDTH)
    combo.addItems([label for label, _ in combo_items])
    setattr(combo, "_editor_choice_values_by_label", label_to_value)

    selected_label = None
    if key == "sampler_name" and isinstance(node_data, dict):
        sampler_link = node_data.get("sampler_link")
        if sampler_link and isinstance(sampler_link, dict):
            selected_label = resolve_linked_choice_label(combo_items, sampler_link)
        else:
            for label, val in combo_items:
                if val == value:
                    selected_label = label
                    break
        if not selected_label and combo_items:
            selected_label = combo_items[0][0]
        combo.setCurrentText(selected_label or "")

    elif key == "scheduler" and isinstance(node_data, dict):
        scheduler_link = node_data.get("scheduler_link")
        if scheduler_link and isinstance(scheduler_link, dict):
            selected_label = resolve_linked_choice_label(combo_items, scheduler_link)
        else:
            for label, val in combo_items:
                if val == value:
                    selected_label = label
                    break
        if not selected_label and combo_items:
            selected_label = combo_items[0][0]

        combo.setCurrentText(selected_label or "")

    else:
        combo.setCurrentText(str(value) if value is not None else "")

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
