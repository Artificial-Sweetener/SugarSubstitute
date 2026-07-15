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

"""Coordinate Sugar-to-Comfy workflow export orchestration."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, cast

from substitute.application.ports.recipe_repository import (
    WorkflowRepository,
)
from substitute.application.ports.workflow_payload_compiler import (
    WorkflowPayloadCompiler,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.recipes.picker_defaults import (
    hydrate_prompt_picker_defaults,
)
from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.domain.common import JsonObject
from substitute.shared.util.path_safety import (
    ensure_within_root,
    validate_top_level_name,
)


class WorkflowExportService:
    """Build and persist Comfy workflow JSON from Sugar script input."""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        workflow_payload_compiler: WorkflowPayloadCompiler,
        node_definition_gateway: NodeDefinitionGateway | None = None,
    ) -> None:
        """Create service with an injected workflow repository port implementation."""

        self._workflow_repository = workflow_repository
        self._workflow_payload_compiler = workflow_payload_compiler
        self._node_definition_gateway = node_definition_gateway

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
        workflow: object | None = None,
    ) -> JsonObject:
        """Compile Sugar script text into a Comfy artifact payload."""

        _ = workflow
        compile_kwargs: dict[str, object] = {
            "sugar_script_text": sugar_script_text,
            "output_dir": output_dir,
        }
        compiler = cast(Any, self._workflow_payload_compiler)
        workflow_payload = cast(
            JsonObject,
            compiler.compile_workflow_payload(**compile_kwargs),
        )
        workflow_nodes = _mutable_executable_prompt_nodes(workflow_payload)
        if workflow_nodes is not None:
            normalize_csv_wildcard_nodes(workflow_nodes)
            if self._node_definition_gateway is not None:
                hydrate_prompt_picker_defaults(
                    workflow_nodes,
                    node_definition_gateway=self._node_definition_gateway,
                )
        return workflow_payload

    def export_workflow_json(
        self,
        *,
        destination_path: Path,
        sugar_script_text: str,
        output_dir: Path,
        workflow: object | None = None,
    ) -> JsonObject:
        """Compile and persist workflow JSON to destination path."""

        workflow_payload = self.compile_workflow_payload(
            sugar_script_text=sugar_script_text,
            output_dir=output_dir,
            workflow=workflow,
        )
        self._workflow_repository.save_workflow_json(destination_path, workflow_payload)
        return workflow_payload

    def build_default_export_path(self, workflow_name: str, output_dir: Path) -> Path:
        """Build the canonical workflow JSON export path in the project folder."""

        safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
        workflow_dir = ensure_within_root(
            Path(output_dir) / safe_workflow_name,
            root_path=output_dir,
            subject="Workflow directory",
            require_top_level=True,
        )
        return ensure_within_root(
            workflow_dir / f"{safe_workflow_name}.json",
            root_path=workflow_dir,
            subject="Workflow export",
            require_top_level=True,
        )

    def validate_export_destination(
        self,
        destination_path: Path,
    ) -> Path:
        """Validate a user-selected workflow export destination."""

        return _validate_workflow_export_destination_path(Path(destination_path))


def _mutable_executable_prompt_nodes(
    payload: JsonObject,
) -> MutableMapping[str, object] | None:
    """Return mutable executable nodes when the compiled payload exposes them."""

    nodes = executable_prompt_nodes(payload)
    if not isinstance(nodes, MutableMapping):
        return None
    return cast(MutableMapping[str, object], nodes)


def normalize_csv_wildcard_nodes(
    workflow_nodes: MutableMapping[str, object],
) -> None:
    """Replace backend CSVWildcardNode payload nodes with plain String nodes."""

    for node in workflow_nodes.values():
        if not isinstance(node, MutableMapping):
            continue
        if node.get("class_type") != "CSVWildcardNode":
            continue
        inputs = node.get("inputs")
        prompt_template = ""
        if isinstance(inputs, MutableMapping):
            raw_prompt_template = inputs.get("prompt_template")
            if isinstance(raw_prompt_template, str):
                prompt_template = raw_prompt_template
        node["class_type"] = "String"
        node["inputs"] = {"value": prompt_template}


def _validate_workflow_export_destination_path(destination_path: Path) -> Path:
    """Return a resolved workflow export path that is safe to write explicitly."""

    resolved_path = destination_path.resolve()
    if resolved_path.exists() and resolved_path.is_dir():
        raise ValueError(f"Workflow export destination is a directory: {resolved_path}")
    if resolved_path.suffix.lower() != ".json":
        raise ValueError(f"Workflow export destination must use .json: {resolved_path}")
    parent = resolved_path.parent
    if parent.exists() and not parent.is_dir():
        raise ValueError(f"Workflow export parent path is not a directory: {parent}")
    return resolved_path


__all__ = [
    "WorkflowExportService",
    "normalize_csv_wildcard_nodes",
]
