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

"""Resolve a cube's canonical target model independently from its alias."""

from __future__ import annotations

from collections.abc import Mapping


def cube_target_model(cube_state: object | None) -> str:
    """Return the canonical target model retained in loaded cube metadata."""

    ui_payload = getattr(cube_state, "ui", None)
    if not isinstance(ui_payload, Mapping):
        return ""
    canonical_cube = ui_payload.get("canonical_cube")
    if not isinstance(canonical_cube, Mapping):
        return ""
    metadata = canonical_cube.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    target_model = metadata.get("target_model")
    return target_model.strip() if isinstance(target_model, str) else ""


def cube_name_from_alias(alias: str, target_model: str) -> str:
    """Remove only a matching canonical target-model route from an alias."""

    stripped_alias = alias.strip()
    stripped_target = target_model.strip()
    prefix = f"{stripped_target}/"
    if stripped_target and stripped_alias.casefold().startswith(prefix.casefold()):
        cube_name = stripped_alias[len(prefix) :].strip()
        if cube_name:
            return cube_name
    return stripped_alias


__all__ = ["cube_name_from_alias", "cube_target_model"]
