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

"""Build typed Sugar serialization requests for focused domain tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from substitute.domain.common import (
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    JsonValue,
)
from substitute.domain.generation.seed_control import SeedControlState
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.domain.recipes.sugar_script_serializer import (
    SugarScriptLabelResolver,
    SugarScriptSerializationRequest,
    SugarScriptSerializer,
)


def serialize_sugar_script(
    buffers: Mapping[str, Mapping[str, JsonValue]],
    ordered_aliases: Iterable[str],
    global_overrides: GlobalOverrideMap | None = None,
    global_override_selections: GlobalOverrideSelectionMap | None = None,
    enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
    disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
    global_override_scopes: Mapping[str, GlobalOverrideSerializationScope]
    | None = None,
    label_resolver: SugarScriptLabelResolver | None = None,
    model_hashes_by_field: Mapping[tuple[str, str, str], str] | None = None,
    prompt_lora_hashes_by_field: Mapping[tuple[str, str, str], Mapping[str, str]]
    | None = None,
    field_control_states_by_alias: Mapping[
        str,
        Mapping[str, Mapping[str, SeedControlState]],
    ]
    | None = None,
    override_control_states: Mapping[str, SeedControlState] | None = None,
) -> str:
    """Serialize test state through the production typed request boundary."""

    return SugarScriptSerializer().serialize(
        SugarScriptSerializationRequest(
            buffers=buffers,
            ordered_aliases=tuple(ordered_aliases),
            global_overrides=global_overrides or {},
            global_override_selections=global_override_selections or {},
            enabled_node_keys_by_alias=enabled_node_keys_by_alias,
            disabled_node_keys_by_alias=disabled_node_keys_by_alias,
            global_override_scopes=global_override_scopes,
            label_resolver=label_resolver,
            model_hashes_by_field=model_hashes_by_field,
            prompt_lora_hashes_by_field=prompt_lora_hashes_by_field,
            field_control_states_by_alias=field_control_states_by_alias,
            override_control_states=override_control_states,
        )
    )


__all__ = ["serialize_sugar_script"]
