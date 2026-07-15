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

"""Resolve listener-scoped model-load source metadata and diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.infrastructure.comfy.model_load_source_metadata_resolver import (
    ModelLoadSourceMetadataDiagnostic,
    resolve_model_load_source_metadata,
)


@dataclass(frozen=True)
class ListenerModelLoadSourceMetadataResolver:
    """Resolve model-load source metadata for a single listener run."""

    workflow_payload: dict[str, object]
    workflow_id: str
    prompt_id: str
    on_diagnostic: Callable[[ModelLoadSourceMetadataDiagnostic], None]

    def resolve(
        self,
        source_node_id: str,
        all_node_ids: set[str],
    ) -> tuple[str | None, str | None]:
        """Return editor cube/node identity from structured prompt metadata."""

        resolution = resolve_model_load_source_metadata(
            workflow_payload=self.workflow_payload,
            workflow_id=self.workflow_id,
            prompt_id=self.prompt_id,
            source_node_id=source_node_id,
            all_node_ids=all_node_ids,
        )
        self.on_diagnostic(resolution.diagnostic)
        return resolution.cube_alias, resolution.workflow_node_name


__all__ = ["ListenerModelLoadSourceMetadataResolver"]
