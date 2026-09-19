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

"""Define mutable direct-workflow state consumed by shared editor services."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from substitute.domain.common import JsonObject

from .cube_analysis import CanonicalCubeGraphAnalysis
from .cube_projection import (
    CubeGraphInstance,
    CubeGraphProjection,
    CubeGraphSegment,
)
from .canonical_value_mutation import (
    infer_canonical_node_origin,
    infer_canonical_widget_origin,
    set_canonical_node_value,
    set_canonical_widget_value,
)


class NodeActivationStorage(StrEnum):
    """Describe how an editable graph persists node activation changes."""

    ENABLED_OVERRIDE = "enabled_override"
    COMFY_MODE = "comfy_mode"


@dataclass(frozen=True)
class ProjectedCubeDocument:
    """Expose one embedded Cube document as a view of its owning Comfy graph."""

    node_id: str | int
    alias: str
    active: bool
    document: JsonObject


@dataclass
class DirectWorkflowState:
    """Store one normalized Comfy workflow as a complete editor document."""

    source_path: Path
    source_workflow: JsonObject
    buffer: JsonObject
    ui: dict[str, object] = field(default_factory=dict)
    dirty: bool = False
    cube_analysis: CanonicalCubeGraphAnalysis | None = None
    cube_projection_state: JsonObject = field(default_factory=dict)

    @property
    def cube_projection(self) -> CubeGraphProjection:
        """Project SugarCubes-owned analysis into the stack's presentation model."""

        analysis = self.cube_analysis
        if analysis is None:
            return CubeGraphProjection(instances=(), segments=())
        instances = {
            instance.instance_id: CubeGraphInstance(
                node_id=instance.node_id,
                alias=instance.alias,
                active=instance.execution_mode != 4,
            )
            for instance in analysis.instances
        }
        segments = tuple(
            CubeGraphSegment(
                segment_id=_segment_id(segment.instance_ids),
                instances=tuple(
                    instances[instance_id] for instance_id in segment.instance_ids
                ),
                reorderable=segment.reorderable,
                fixed_reason=None if segment.reorderable else "sugarcubes-fixed",
            )
            for segment in analysis.segments
        )
        return CubeGraphProjection(
            instances=tuple(
                instance for segment in segments for instance in segment.instances
            ),
            segments=segments,
        )

    def projected_cube_documents(self) -> tuple[ProjectedCubeDocument, ...]:
        """Return embedded documents in graph-derived projection order."""

        definitions = self.source_workflow.get("definitions")
        subgraphs = (
            definitions.get("subgraphs") if isinstance(definitions, Mapping) else None
        )
        nodes = self.source_workflow.get("nodes")
        if not isinstance(subgraphs, list) or not isinstance(nodes, list):
            return ()
        documents = _cube_documents_by_definition(subgraphs)
        nodes_by_id = {
            str(node.get("id")): node
            for node in nodes
            if isinstance(node, Mapping)
            and not isinstance(node.get("id"), bool)
            and isinstance(node.get("id"), str | int)
        }
        result: list[ProjectedCubeDocument] = []
        for instance in self.cube_projection.instances:
            node = nodes_by_id.get(str(instance.node_id))
            definition_id = node.get("type") if isinstance(node, Mapping) else None
            document = (
                documents.get(definition_id) if isinstance(definition_id, str) else None
            )
            if document is None:
                raise ValueError(
                    f"Marked Cube graph node {instance.node_id!r} has no embedded document."
                )
            result.append(
                ProjectedCubeDocument(
                    node_id=instance.node_id,
                    alias=instance.alias,
                    active=instance.active,
                    document=document,
                )
            )
        return tuple(result)

    @property
    def activation_storage(self) -> NodeActivationStorage:
        """Use Comfy node modes as the authoritative activation state."""

        return NodeActivationStorage.COMFY_MODE

    @property
    def shows_cube_section_title(self) -> bool:
        """Hide cube title chrome because this state represents a whole document."""

        return False

    @property
    def uses_node_titles_as_card_labels(self) -> bool:
        """Render preserved Comfy node titles instead of numeric graph identifiers."""

        return True

    def set_node_activation(self, node_name: str, enabled: bool) -> None:
        """Persist an editor switch change using Comfy active and bypass modes."""

        nodes = self.buffer.get("nodes")
        if not isinstance(nodes, dict):
            return
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            return
        next_mode = 0 if enabled else 4
        if node.get("mode", 0) == next_mode:
            return
        self.set_editor_value(
            node_name,
            field_key="mode",
            value=next_mode,
            storage_kind="node",
        )

    def set_editor_value(
        self,
        node_name: str,
        *,
        field_key: str,
        value: object,
        storage_kind: str = "input",
    ) -> bool:
        """Commit one projected editor value to its canonical Comfy graph origin."""

        nodes = self.buffer.get("nodes")
        node = nodes.get(node_name) if isinstance(nodes, dict) else None
        if not isinstance(node, dict):
            return False
        workflow_metadata = node.get("_workflow")
        metadata = workflow_metadata if isinstance(workflow_metadata, Mapping) else {}
        if storage_kind == "node":
            previous = node.get(field_key)
            if previous == value:
                return False
            origin = metadata.get("canonical_node_origin")
            if not isinstance(origin, Mapping):
                origin = infer_canonical_node_origin(self.source_workflow, node_name)
            if not isinstance(origin, Mapping):
                raise ValueError(
                    f"Direct editor node {node_name!r} has no canonical node origin."
                )
            set_canonical_node_value(
                self.source_workflow,
                origin,
                field_key,
                value,
            )
            node[field_key] = deepcopy(value)
            self.dirty = True
            return True
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            return False
        previous = inputs.get(field_key)
        if previous == value:
            return False
        origins = metadata.get("canonical_value_origins")
        origin = origins.get(field_key) if isinstance(origins, Mapping) else None
        if not isinstance(origin, Mapping):
            origin = infer_canonical_widget_origin(
                self.source_workflow,
                node_name,
                field_key,
            )
        if not isinstance(origin, Mapping):
            raise ValueError(
                f"Direct editor field {node_name}.{field_key} has no canonical value origin."
            )
        set_canonical_widget_value(self.source_workflow, origin, value)
        inputs[field_key] = deepcopy(value)
        self.dirty = True
        return True

    def reconcile_canonical_projection(self) -> tuple[str, ...]:
        """Copy legacy persisted editor values into canonical graph storage."""

        nodes = self.buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            return ()
        unresolved: list[str] = []
        for node_name, node in nodes.items():
            if not isinstance(node_name, str) or not isinstance(node, Mapping):
                continue
            metadata = node.get("_workflow")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            node_origin = metadata.get("canonical_node_origin")
            if not isinstance(node_origin, Mapping):
                node_origin = infer_canonical_node_origin(
                    self.source_workflow,
                    node_name,
                )
            if isinstance(node_origin, Mapping) and "mode" in node:
                set_canonical_node_value(
                    self.source_workflow,
                    node_origin,
                    "mode",
                    node["mode"],
                )
            inputs = node.get("inputs")
            origins = metadata.get("canonical_value_origins")
            if not isinstance(inputs, Mapping):
                continue
            for field_key, value in inputs.items():
                if not isinstance(field_key, str) or _is_connection_value(value):
                    continue
                origin = (
                    origins.get(field_key) if isinstance(origins, Mapping) else None
                )
                if not isinstance(origin, Mapping):
                    origin = infer_canonical_widget_origin(
                        self.source_workflow,
                        node_name,
                        field_key,
                    )
                if not isinstance(origin, Mapping):
                    unresolved.append(f"{node_name}.{field_key}")
                    continue
                set_canonical_widget_value(self.source_workflow, origin, value)
        return tuple(unresolved)

    def duplicate(self) -> DirectWorkflowState:
        """Return an independent authoring copy without live editor runtime objects."""

        return DirectWorkflowState(
            source_path=self.source_path,
            source_workflow=deepcopy(self.source_workflow),
            buffer=deepcopy(self.buffer),
            ui={
                key: deepcopy(value)
                for key, value in self.ui.items()
                if key != "node_behavior_runtime"
            },
            dirty=self.dirty,
            cube_analysis=deepcopy(self.cube_analysis),
            cube_projection_state=deepcopy(self.cube_projection_state),
        )


def _segment_id(instance_ids: tuple[str, ...]) -> str:
    """Build the presentation key for one SugarCubes-owned segment."""

    return "cube-series:" + ",".join(instance_ids)


def _is_connection_value(value: object) -> bool:
    """Return whether one editor input is a graph edge rather than authored data."""

    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str | int)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    )


def _cube_documents_by_definition(
    definitions: list[object],
) -> dict[str, JsonObject]:
    """Index mutable embedded Cube documents by canonical definition id."""

    result: dict[str, JsonObject] = {}
    for definition in definitions:
        if not isinstance(definition, Mapping):
            continue
        definition_id = definition.get("id")
        extra = definition.get("extra")
        document = (
            extra.get("sugarcubes_document") if isinstance(extra, Mapping) else None
        )
        if isinstance(definition_id, str) and isinstance(document, dict):
            result[definition_id] = document
    return result
