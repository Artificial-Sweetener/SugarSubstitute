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

"""Provide recorded Comfy node definitions to headless production harnesses."""

from __future__ import annotations

from collections.abc import Mapping


class RecordedNodeDefinitionGateway:
    """Serve deterministic node metadata without contacting a Comfy process."""

    def __init__(self, definitions: Mapping[str, Mapping[str, object]]) -> None:
        """Store the recorded definitions for one fixture."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a detached-enough mapping for optional behavior lookup."""

        definition = self._definitions.get(node_class)
        return {node_class: dict(definition)} if definition is not None else {}

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the same deterministic definition for required lookup."""

        return self.get_node_definition(node_class)


__all__ = ["RecordedNodeDefinitionGateway"]
