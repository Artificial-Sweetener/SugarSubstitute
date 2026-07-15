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

"""Resolve model-load telemetry source metadata from queued workflow payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from substitute.infrastructure.comfy.comfy_payload_fields import strict_string_or_none
from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    normalize_node_id,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    typed_prompt_nodes,
)

ModelLoadSourceMetadataLogLevel = Literal["info"]


@dataclass(frozen=True)
class ModelLoadSourceMetadataDiagnostic:
    """Describe one prompt-safe source metadata diagnostic."""

    level: ModelLoadSourceMetadataLogLevel
    message: str
    fields: Mapping[str, object]


@dataclass(frozen=True)
class ModelLoadSourceMetadataResolution:
    """Describe resolved editor source metadata and the selected diagnostic."""

    cube_alias: str | None
    workflow_node_name: str | None
    diagnostic: ModelLoadSourceMetadataDiagnostic


def resolve_model_load_source_metadata(
    *,
    workflow_payload: dict[str, object],
    workflow_id: str,
    prompt_id: str,
    source_node_id: str,
    all_node_ids: set[str],
) -> ModelLoadSourceMetadataResolution:
    """Return editor cube/node identity for one model-load source node."""

    owner_node_id = normalize_node_id(
        node_id=source_node_id,
        all_node_ids=all_node_ids,
    )
    if owner_node_id is None:
        return _unresolved(
            message="Model-load source node was not found in queued workflow",
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            source_node_id=source_node_id,
        )

    node_data = typed_prompt_nodes(workflow_payload).get(owner_node_id)
    if node_data is None:
        return _unresolved(
            message="Model-load source node metadata was unavailable",
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            source_node_id=source_node_id,
        )

    metadata = node_data.get("_meta")
    if not isinstance(metadata, dict):
        return _unresolved(
            message="Model-load source node has no structured metadata",
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            source_node_id=source_node_id,
        )

    substitute_metadata = metadata.get("substitute")
    if not isinstance(substitute_metadata, dict):
        return _unresolved(
            message="Model-load source node has no Substitute metadata",
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            source_node_id=source_node_id,
        )

    cube_alias = strict_string_or_none(substitute_metadata.get("cube_alias"))
    node_name = strict_string_or_none(substitute_metadata.get("node_name"))
    if cube_alias is None or node_name is None:
        return _unresolved(
            message="Model-load source node Substitute metadata was incomplete",
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            source_node_id=source_node_id,
        )

    return ModelLoadSourceMetadataResolution(
        cube_alias=cube_alias,
        workflow_node_name=node_name,
        diagnostic=ModelLoadSourceMetadataDiagnostic(
            level="info",
            message="Model-load source metadata resolved",
            fields={
                "workflow_id": workflow_id,
                "prompt_id": prompt_id,
                "source_node_id": source_node_id,
                "cube_alias": cube_alias,
                "node_name": node_name,
            },
        ),
    )


def _unresolved(
    *,
    message: str,
    workflow_id: str,
    prompt_id: str,
    source_node_id: str,
) -> ModelLoadSourceMetadataResolution:
    """Return a failed source metadata resolution with its diagnostic."""

    return ModelLoadSourceMetadataResolution(
        cube_alias=None,
        workflow_node_name=None,
        diagnostic=ModelLoadSourceMetadataDiagnostic(
            level="info",
            message=message,
            fields={
                "workflow_id": workflow_id,
                "prompt_id": prompt_id,
                "source_node_id": source_node_id,
            },
        ),
    )


__all__ = [
    "ModelLoadSourceMetadataDiagnostic",
    "ModelLoadSourceMetadataResolution",
    "resolve_model_load_source_metadata",
]
