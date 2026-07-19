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

"""Load and normalize complete Comfy workflow documents."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol

from substitute.application.ports import NodeDefinitionGateway, NodeDefinitionHydrator
from substitute.domain.comfy_workflow import (
    ComfyWorkflowConverter,
    DirectWorkflowState,
    executable_node_classes,
)
from substitute.domain.common import JsonObject
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.direct_workflows.load_service")


class DirectWorkflowRepository(Protocol):
    """Read and classify direct Comfy workflow source documents."""

    def can_load(self, path: Path) -> bool:
        """Return whether a path identifies an available direct Comfy workflow."""

    def load(self, path: Path) -> JsonObject:
        """Return one decoded workflow object."""


class DirectWorkflowLoadService:
    """Build editor-ready direct workflow state from a repository document."""

    def __init__(
        self,
        repository: DirectWorkflowRepository,
        converter: ComfyWorkflowConverter | None = None,
        node_definition_gateway: NodeDefinitionGateway | None = None,
    ) -> None:
        """Store filesystem and pure graph conversion collaborators."""

        self._repository = repository
        self._converter = converter or ComfyWorkflowConverter()
        self._node_definition_gateway = node_definition_gateway

    def load(self, path: Path) -> DirectWorkflowState:
        """Load, validate, normalize, and detach one Comfy workflow document."""

        source_path = path.resolve()
        workflow = self._repository.load(source_path)
        if not _looks_like_ui_workflow(workflow):
            raise ValueError(
                "JSON is not a Comfy UI workflow: expected top-level nodes and links."
            )
        buffer = self._converter.convert(
            workflow,
            node_definitions=self._load_node_definitions(workflow),
        )
        nodes = buffer.get("nodes")
        node_count = len(nodes) if isinstance(nodes, Mapping) else 0
        log_info(
            _LOGGER,
            "Loaded direct Comfy workflow document",
            source_path=source_path,
            node_count=node_count,
        )
        return DirectWorkflowState(
            source_path=source_path,
            source_workflow=workflow,
            buffer=buffer,
        )

    def can_load(self, path: Path) -> bool:
        """Return whether the repository exposes a direct workflow at the path."""

        return self._repository.can_load(path)

    def _load_node_definitions(
        self,
        workflow: Mapping[str, object],
    ) -> dict[str, Mapping[str, object]]:
        """Return available live definitions needed to decode serialized widgets."""

        gateway = self._node_definition_gateway
        if gateway is None:
            return {}
        class_types = executable_node_classes(workflow)
        if isinstance(gateway, NodeDefinitionHydrator):
            gateway.ensure_node_definitions(class_types)
        definitions: dict[str, Mapping[str, object]] = {}
        for class_type in class_types:
            payload = gateway.get_node_definition(class_type)
            definition = payload.get(class_type)
            if not isinstance(definition, Mapping):
                payload = gateway.get_required_node_definition(class_type)
                definition = payload.get(class_type)
            if isinstance(definition, Mapping):
                definitions[class_type] = definition
        return definitions


def _looks_like_ui_workflow(payload: Mapping[str, object]) -> bool:
    """Return whether a JSON object exposes the Comfy UI workflow boundary."""

    return isinstance(payload.get("nodes"), list) and isinstance(
        payload.get("links", []),
        list,
    )


__all__ = ["DirectWorkflowLoadService", "DirectWorkflowRepository"]
