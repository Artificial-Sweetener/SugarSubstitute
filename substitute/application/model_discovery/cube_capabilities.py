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

"""Derive model categories from validated cube surface control contracts."""

from __future__ import annotations

from collections.abc import Collection

from substitute.application.model_metadata.model_field_kind_resolver import (
    model_kind_for_field,
)
from substitute.domain.cubes import CanonicalCubeDocument
from sugarsubstitute_shared.model_discovery import (
    CubeModelCapability,
    ModelCategory,
)


def cube_model_capabilities(
    documents: Collection[CanonicalCubeDocument],
) -> tuple[CubeModelCapability, ...]:
    """Return categories users can select through each cube's exposed controls."""

    capabilities: list[CubeModelCapability] = []
    for document in documents:
        categories: set[ModelCategory] = set()
        controls = document.surface.get("controls", [])
        for control in controls:
            if not isinstance(control, dict):
                continue
            class_type = control.get("class_type")
            input_name = control.get("input_name")
            if not isinstance(class_type, str) or not isinstance(input_name, str):
                continue
            kind = model_kind_for_field(
                class_type=class_type,
                input_key=input_name,
            )
            try:
                category = ModelCategory(kind) if kind is not None else None
            except ValueError:
                category = None
            if category is not None:
                categories.add(category)
        capabilities.append(
            CubeModelCapability(document.cube_id, frozenset(categories))
        )
    return tuple(capabilities)


__all__ = ["cube_model_capabilities"]
