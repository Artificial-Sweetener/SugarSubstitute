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

"""Enrich field metadata with authoritative cube runtime context."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.cubes import cube_target_model


def field_runtime_metadata(
    metadata: Mapping[str, object],
    alias: str,
    node_data: Mapping[str, object],
    cube_state: object,
) -> dict[str, object]:
    """Return live metadata plus stable cube identity needed by presentation."""

    return {
        **metadata,
        "cube_alias": alias,
        "node_data": dict(node_data),
        "target_model": cube_target_model(cube_state),
    }


__all__ = ["field_runtime_metadata"]
