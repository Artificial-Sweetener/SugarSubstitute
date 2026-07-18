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

"""Define Qt-free restore projection cache domain contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from substitute.domain.common import JsonObject
from substitute.domain.workflow import WorkflowDocumentKind

RESTORE_PROJECTION_CACHE_SCHEMA_VERSION = 2
APP_PROJECTION_VERSION = 3


@dataclass(frozen=True, slots=True)
class RestoreProjectionCacheKey:
    """Identify the backend target and workspace owned by one artifact."""

    target_key: str
    workspace_fingerprint: str


@dataclass(frozen=True, slots=True)
class CachedNodeProjection:
    """Store resolved node-card projection data without Qt objects."""

    node_name: str
    node_class: str
    field_order: tuple[str, ...] = ()
    resolved_field_specs: JsonObject = field(default_factory=dict)
    resolved_card_visibility: JsonObject = field(default_factory=dict)
    prompt_field_metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CachedEditorSectionProjection:
    """Store the shared node-card projection for one editor section."""

    section_key: str
    buffer_fingerprint: str
    node_classes: tuple[str, ...]
    node_definition_fingerprint_by_class: Mapping[str, str]
    projected_node_order: tuple[str, ...]
    resolved_field_specs: JsonObject = field(default_factory=dict)
    resolved_card_visibility: JsonObject = field(default_factory=dict)
    field_order: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    prompt_field_metadata: JsonObject = field(default_factory=dict)
    nodes: tuple[CachedNodeProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class CachedCubeProjection:
    """Store cube identity around its shared editor-section projection."""

    requested_cube_id: str
    canonical_cube_id: str
    cube_version: str
    content_hash: str
    catalog_revision: str
    section: CachedEditorSectionProjection

    @property
    def alias(self) -> str:
        """Return the cube alias used as the editor section key."""

        return self.section.section_key


@dataclass(frozen=True, slots=True)
class CachedCubeStackProjection:
    """Store the cube-specific document projection for one workflow tab."""

    stack_order: tuple[str, ...]
    active_cube_alias: str | None
    cubes: tuple[CachedCubeProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class CachedDirectWorkflowProjection:
    """Store direct-document identity around one shared editor section."""

    durable_ui_fingerprint: str
    section: CachedEditorSectionProjection


@dataclass(frozen=True, slots=True)
class CachedWorkflowProjection:
    """Store one discriminated workflow document projection."""

    workflow_id: str
    tab_label: str
    document_kind: WorkflowDocumentKind
    workflow_fingerprint: str
    cube_stack: CachedCubeStackProjection | None = None
    direct_workflow: CachedDirectWorkflowProjection | None = None

    def __post_init__(self) -> None:
        """Reject cache records whose payload contradicts their document kind."""

        expects_cube = self.document_kind is WorkflowDocumentKind.CUBE_STACK
        if expects_cube != (self.cube_stack is not None):
            raise ValueError("Cached workflow cube-stack payload is inconsistent.")
        if expects_cube == (self.direct_workflow is not None):
            raise ValueError("Cached workflow direct payload is inconsistent.")


@dataclass(frozen=True, slots=True)
class RestoreProjectionArtifact:
    """Store one last-known-good restored editor projection artifact."""

    schema_version: int
    created_at: str
    app_projection_version: int
    target_key: str
    workspace_fingerprint: str
    active_route: str
    active_workflow_id: str
    workflows: tuple[CachedWorkflowProjection, ...]
    prompt_editor_feature_profile_fingerprint: str
    node_definition_fingerprints: Mapping[str, str]
    cube_definition_fingerprints: Mapping[str, str]
    projection: JsonObject = field(default_factory=dict)


class RestoreProjectionCacheRepository(Protocol):
    """Persist and load restore projection artifacts."""

    def load(self) -> RestoreProjectionArtifact | None:
        """Return the latest readable artifact."""

    def save(self, artifact: RestoreProjectionArtifact) -> None:
        """Persist one artifact atomically."""

    def clear(self) -> None:
        """Remove invalid or obsolete cache state."""


__all__ = [
    "APP_PROJECTION_VERSION",
    "RESTORE_PROJECTION_CACHE_SCHEMA_VERSION",
    "CachedCubeProjection",
    "CachedCubeStackProjection",
    "CachedDirectWorkflowProjection",
    "CachedEditorSectionProjection",
    "CachedNodeProjection",
    "CachedWorkflowProjection",
    "RestoreProjectionArtifact",
    "RestoreProjectionCacheKey",
    "RestoreProjectionCacheRepository",
]
