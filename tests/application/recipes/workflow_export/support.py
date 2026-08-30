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

"""Provide typed workflow-export collaborators."""

from __future__ import annotations

from pathlib import Path

from substitute.application.recipes.workflow_export_service import WorkflowExportService


class FakeWorkflowRepository:
    """Capture workflow JSON persistence payloads."""

    def __init__(self) -> None:
        self.saved: list[tuple[Path, dict[str, object]]] = []

    def save_workflow_json(
        self,
        path: Path,
        workflow_payload: dict[str, object],
    ) -> None:
        """Capture one workflow save call."""
        self.saved.append((path, workflow_payload))


class FakeWorkflowPayloadCompiler:
    """Capture Sugar source and output directory compilation arguments."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, Path]] = []

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> dict[str, object]:
        """Return the configured workflow payload."""
        self.calls.append((sugar_script_text, output_dir))
        return self.payload


class FakeNodeDefinitionGateway:
    """Return configured Comfy object-info payloads by class type."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the non-blocking definition shape."""
        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required Comfy object-info definition."""
        definition = self._definitions.get(node_class)
        return {node_class: definition} if definition is not None else {}


def build_service(
    payload: dict[str, object] | None = None,
    *,
    node_definition_gateway: FakeNodeDefinitionGateway | None = None,
) -> tuple[
    WorkflowExportService,
    FakeWorkflowRepository,
    FakeWorkflowPayloadCompiler,
]:
    """Build an export service with observable collaborators."""
    repository = FakeWorkflowRepository()
    compiler = FakeWorkflowPayloadCompiler(payload or {})
    return (
        WorkflowExportService(
            workflow_repository=repository,
            workflow_payload_compiler=compiler,
            node_definition_gateway=node_definition_gateway,
        ),
        repository,
        compiler,
    )
