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

"""Resolve listener output-source identities and emit selected diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceDiagnostic,
    OutputSourceGraph,
    OutputSourceIdentity,
    build_output_source_graph,
    resolve_output_source_identity_for_node,
)


@dataclass
class ListenerOutputSourceResolver:
    """Resolve output-source identities for a single listener run."""

    workflow_id: str
    prompt_id: str
    workflow_payload: dict[str, object]
    cube_output_node_ids: set[str]
    on_diagnostic: Callable[[OutputSourceDiagnostic], None]
    _output_source_graph: OutputSourceGraph = field(init=False)
    _ambiguous_warning_keys: set[tuple[str, tuple[str, ...]]] = field(
        default_factory=set,
        init=False,
    )

    def __post_init__(self) -> None:
        """Build output-source graph state for this listener run."""

        self._output_source_graph = build_output_source_graph(
            self.workflow_payload,
            self.cube_output_node_ids,
        )

    def resolve(self, node_id: str) -> OutputSourceIdentity:
        """Return the downstream cube output identity for one prompt node."""

        resolution = resolve_output_source_identity_for_node(
            node_id,
            workflow_id=self.workflow_id,
            prompt_id=self.prompt_id,
            workflow_payload=self.workflow_payload,
            output_source_graph=self._output_source_graph,
            cube_output_node_ids=self.cube_output_node_ids,
            ambiguous_warning_keys=self._ambiguous_warning_keys,
        )
        if resolution.diagnostic is not None:
            self.on_diagnostic(resolution.diagnostic)
        return resolution.source_identity


__all__ = ["ListenerOutputSourceResolver"]
