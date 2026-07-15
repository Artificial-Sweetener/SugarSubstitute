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

"""Expose recipe-domain AST and codec helpers."""

from __future__ import annotations

from substitute.domain.recipes.sugar_ast import (
    GlobalOverrideSerializationScope,
    LoadedRecipeDocument,
    ParsedSugarScript,
    RecipeSourceKind,
    SugarBuffer,
    SugarBufferMap,
)
from substitute.domain.recipes.recipe_buffers import (
    merge_recipe_buffer,
    restore_recipe_cube_state,
    strip_recipe_buffers,
)
from substitute.domain.recipes.sugar_links import (
    linkable_prompt_fields,
    node_reference,
    prompt_field_reference,
    prompt_link_source_alias,
)
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.recipes.sugar_script_serializer import (
    SugarScriptLabelResolver,
    SugarScriptSerializationError,
    SugarScriptSerializationRequest,
    SugarScriptSerializer,
)

__all__ = [
    "ParsedSugarScript",
    "GlobalOverrideSerializationScope",
    "LoadedRecipeDocument",
    "RecipeSourceKind",
    "SugarBuffer",
    "SugarBufferMap",
    "linkable_prompt_fields",
    "merge_recipe_buffer",
    "node_reference",
    "parse_sugar_script_document",
    "prompt_field_reference",
    "prompt_link_source_alias",
    "restore_recipe_cube_state",
    "strip_recipe_buffers",
    "SugarScriptLabelResolver",
    "SugarScriptSerializationError",
    "SugarScriptSerializationRequest",
    "SugarScriptSerializer",
]
