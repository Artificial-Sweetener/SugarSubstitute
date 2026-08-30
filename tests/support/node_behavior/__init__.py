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

"""Expose typed node-behavior scenario support."""

from tests.support.node_behavior.payloads import behavior_payload
from tests.support.node_behavior.snapshots import (
    DummyNodeDefinitionGateway,
    build_behavior_snapshot,
    cube_state,
)

__all__ = [
    "DummyNodeDefinitionGateway",
    "behavior_payload",
    "build_behavior_snapshot",
    "cube_state",
]
