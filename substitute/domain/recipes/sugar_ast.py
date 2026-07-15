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

"""Define typed recipe-domain value objects for Sugar script codec operations."""

from __future__ import annotations

from collections.abc import Mapping
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from substitute.domain.common import (
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    JsonValue,
)
from substitute.domain.generation.seed_control import SeedControlState

SugarBuffer: TypeAlias = OrderedDict[str, JsonValue]
SugarBufferMap: TypeAlias = OrderedDict[str, SugarBuffer]
RecipeSourceKind = Literal["text", "png"]
GlobalOverrideFieldKey: TypeAlias = tuple[str, str, str]
RecipeModelFieldKey: TypeAlias = tuple[str, str, str]


@dataclass(frozen=True)
class LoadedRecipeDocument:
    """Represent loaded recipe text and source metadata."""

    sugar_script_text: str
    source_path: Path
    source_kind: RecipeSourceKind


@dataclass(frozen=True)
class ParsedSugarScript:
    """Represent parsed Sugar script content used by recipe orchestration."""

    buffers: SugarBufferMap
    global_overrides: GlobalOverrideMap
    global_override_selections: GlobalOverrideSelectionMap
    field_control_states_by_alias: Mapping[
        str,
        Mapping[str, Mapping[str, SeedControlState]],
    ]
    override_control_states: Mapping[str, SeedControlState]
    model_hashes_by_field: Mapping[RecipeModelFieldKey, str]
    prompt_lora_hashes_by_field: Mapping[
        RecipeModelFieldKey,
        Mapping[str, str],
    ]
    project_name: str | None


@dataclass(frozen=True)
class GlobalOverrideSerializationScope:
    """Describe how one active global override should be emitted to SugarScript."""

    override_key: str
    value: object
    mode: str
    full_participation: bool
    participant_fields: frozenset[GlobalOverrideFieldKey]


__all__ = [
    "LoadedRecipeDocument",
    "GlobalOverrideFieldKey",
    "GlobalOverrideSerializationScope",
    "ParsedSugarScript",
    "RecipeSourceKind",
    "RecipeModelFieldKey",
    "SugarBuffer",
    "SugarBufferMap",
]
