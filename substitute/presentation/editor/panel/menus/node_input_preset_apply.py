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

"""Apply saved node input presets to live node state and widgets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
    EditorPanelFieldStateController,
    write_live_widget_value,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.menus.node_input_preset_apply")
JsonObject: TypeAlias = dict[str, object]
JsonValue: TypeAlias = object


@dataclass(frozen=True, slots=True)
class NodeInputPresetSkippedField:
    """Describe one preset input skipped during apply."""

    field_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class NodeInputPresetApplyReport:
    """Report node input preset apply results."""

    applied_keys: tuple[str, ...]
    skipped_fields: tuple[NodeInputPresetSkippedField, ...]


def apply_node_input_preset(
    *,
    cube_state: object,
    cube_alias: str | None,
    node_name: str,
    node_type: str,
    preset_id: str,
    preset_label: str,
    preset_inputs: JsonObject,
    node_inputs: Mapping[str, object],
    field_specs: Mapping[str, ResolvedFieldSpec],
    is_connection: Callable[[object], bool],
    input_widgets_by_field_key: Mapping[tuple[str, str, str], object] | None = None,
) -> NodeInputPresetApplyReport:
    """Apply valid preset inputs to the cube buffer and matching live widgets."""

    applied_keys: list[str] = []
    skipped_fields: list[NodeInputPresetSkippedField] = []
    field_state = EditorPanelFieldStateController()

    for field_key, value in preset_inputs.items():
        skip_reason = _skip_reason(
            field_key=field_key,
            value=value,
            field_specs=field_specs,
            node_inputs=node_inputs,
            is_connection=is_connection,
        )
        if skip_reason is not None:
            skipped_fields.append(
                _log_skipped_field(
                    field_key=field_key,
                    reason=skip_reason,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    node_type=node_type,
                    preset_id=preset_id,
                    preset_label=preset_label,
                )
            )
            continue
        field_state.set_field_value(
            cube_state,
            EditorFieldBinding(
                cube_alias=cube_alias,
                node_name=node_name,
                field_key=field_key,
                storage_kind="input",
                value_source=None,
                resolved_display_value=None,
                prompt_field_identity=f"{node_name}.{field_key}",
                node_type=node_type,
                field_type=field_specs[field_key].field_type,
            ),
            value,
        )
        _write_live_widget(
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            value=value,
            input_widgets_by_field_key=input_widgets_by_field_key,
        )
        applied_keys.append(field_key)

    return NodeInputPresetApplyReport(
        applied_keys=tuple(applied_keys),
        skipped_fields=tuple(skipped_fields),
    )


def _skip_reason(
    *,
    field_key: str,
    value: JsonValue,
    field_specs: Mapping[str, ResolvedFieldSpec],
    node_inputs: Mapping[str, object],
    is_connection: Callable[[object], bool],
) -> str | None:
    """Return why a preset field should be skipped, or ``None`` when applicable."""

    field_spec = field_specs.get(field_key)
    if field_spec is None:
        return "missing_field_spec"
    current_value = node_inputs.get(field_key)
    if current_value is not None and is_connection(current_value):
        return "connected_field"
    if not _value_matches_field_type(value, field_spec.field_type):
        return "incompatible_field_type"
    return None


def _value_matches_field_type(value: JsonValue, field_type: str | None) -> bool:
    """Return whether a preset value is compatible with a resolved field type."""

    if field_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "FLOAT":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type in {"STRING", "COMBO"}:
        return isinstance(value, str)
    if field_type == "BOOLEAN":
        return isinstance(value, bool)
    return True


def _write_live_widget(
    *,
    cube_alias: str | None,
    node_name: str,
    field_key: str,
    value: JsonValue,
    input_widgets_by_field_key: Mapping[tuple[str, str, str], object] | None,
) -> None:
    """Write a preset value into the live widget when one is registered."""

    if cube_alias is None or input_widgets_by_field_key is None:
        return
    widget = input_widgets_by_field_key.get((cube_alias, node_name, field_key))
    if widget is None:
        return
    write_live_widget_value(widget, value)


def _log_skipped_field(
    *,
    field_key: str,
    reason: str,
    cube_alias: str | None,
    node_name: str,
    node_type: str,
    preset_id: str,
    preset_label: str,
) -> NodeInputPresetSkippedField:
    """Log and return one skipped-field report."""

    log_warning(
        _LOGGER,
        "Skipped node input preset field",
        cube_alias=cube_alias or "",
        node_name=node_name,
        node_type=node_type,
        preset_id=preset_id,
        preset_label_length=len(preset_label),
        field_key=field_key,
        reason=reason,
    )
    return NodeInputPresetSkippedField(field_key=field_key, reason=reason)


__all__ = [
    "NodeInputPresetApplyReport",
    "NodeInputPresetSkippedField",
    "apply_node_input_preset",
]
