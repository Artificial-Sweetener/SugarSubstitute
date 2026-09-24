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

"""Enrich Cube graph operations with transient library state and capture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Protocol

from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.common import JsonObject
from substitute.domain.cube_library import (
    WorkflowCubeCaptureResult,
    WorkflowCubeClassificationReport,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.cubes.workflow_cube_library_service")


class CubeGraphGatewayProtocol(Protocol):
    """Expose canonical SugarCubes graph operations used by this decorator."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Normalize and analyze one complete native workflow."""

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Atomically reorder one SugarCubes-authorized segment."""

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Append one exact Cube document."""

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Create one native workflow from an ordered Cube stack."""

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Remove one recognized Cube."""

    def replace_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Replace one embedded Cube definition."""


class WorkflowCubeLibraryGateway(Protocol):
    """Expose workflow classification and exact capture persistence."""

    def classify(self, workflow: JsonObject) -> WorkflowCubeClassificationReport:
        """Classify all embedded definitions in one workflow."""

    def capture(
        self,
        workflow: JsonObject,
        *,
        definition_id: str,
        expected_semantic_hash: str,
    ) -> WorkflowCubeCaptureResult:
        """Persist one exact workflow-embedded definition."""


class WorkflowCubeLibraryService:
    """Keep graph behavior independent while attaching machine-local library state."""

    def __init__(
        self,
        graph_gateway: CubeGraphGatewayProtocol,
        library_gateway: WorkflowCubeLibraryGateway,
    ) -> None:
        """Bind canonical graph and workflow library collaborators."""

        self._graph_gateway = graph_gateway
        self._library_gateway = library_gateway

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Analyze a graph and attach best-effort transient classifications."""

        return self._classify(self._graph_gateway.analyze(workflow))

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Reorder a graph and refresh transient classifications."""

        return self._classify(
            self._graph_gateway.reorder(
                workflow,
                segment_instance_ids=segment_instance_ids,
                ordered_instance_ids=ordered_instance_ids,
            )
        )

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Append an exact Cube and refresh transient classifications."""

        return self._classify(
            self._graph_gateway.append_cube(
                workflow,
                instance_id=instance_id,
                alias=alias,
                bypassed=bypassed,
                document=document,
            )
        )

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Create a native graph and attach transient classifications."""

        return self._classify(self._graph_gateway.create_cube_workflow(cubes))

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Remove a Cube and refresh transient classifications."""

        return self._classify(
            self._graph_gateway.remove_cube(workflow, instance_id=instance_id)
        )

    def replace_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Replace a definition and refresh transient classifications."""

        return self._classify(
            self._graph_gateway.replace_cube(
                workflow,
                instance_id=instance_id,
                document=document,
            )
        )

    def capture_cube(
        self,
        workflow: WorkflowState,
        alias: str,
    ) -> WorkflowCubeCaptureResult:
        """Capture one exact embedded definition and refresh every shared view."""

        direct = workflow.direct_workflow
        cube = workflow.cubes.get(alias)
        classification = cube.library_classification if cube is not None else None
        if direct is None or classification is None:
            raise ValueError(f"Cube {alias!r} has no workflow library classification.")
        if not classification.can_capture:
            raise ValueError(f"Cube {alias!r} is not available for capture.")
        result = self._library_gateway.capture(
            direct.source_workflow,
            definition_id=classification.definition_id,
            expected_semantic_hash=classification.semantic_hash,
        )
        self._install_captured_classification(workflow, result)
        log_info(
            _LOGGER,
            "Captured workflow Cube through SugarCubes",
            cube_alias=alias,
            cube_id=result.cube_id,
            semantic_hash=result.semantic_hash,
            created=result.created,
        )
        return result

    def _classify(
        self,
        analysis: CanonicalCubeGraphAnalysis,
    ) -> CanonicalCubeGraphAnalysis:
        """Attach classifications while preserving loadability on optional failure."""

        try:
            report = self._library_gateway.classify(analysis.workflow)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Loaded Cube workflow without optional library classification",
                error_type=type(error).__name__,
                error_message=str(error),
                workflow_semantic_hash=analysis.workflow_semantic_hash,
            )
            return analysis
        return replace(analysis, cube_classifications=report.definitions)

    @staticmethod
    def _install_captured_classification(
        workflow: WorkflowState,
        result: WorkflowCubeCaptureResult,
    ) -> None:
        """Replace transient state without changing embedded Cube content."""

        classification = result.classification
        direct = workflow.direct_workflow
        if direct is None:
            raise ValueError("Workflow does not own a canonical Comfy graph.")
        analysis = direct.cube_analysis
        if analysis is not None:
            retained = tuple(
                item
                for item in analysis.cube_classifications
                if item.definition_id != classification.definition_id
            )
            direct.cube_analysis = replace(
                analysis,
                cube_classifications=(*retained, classification),
            )
        for cube in workflow.cubes.values():
            current = cube.library_classification
            if (
                current is not None
                and current.definition_id == classification.definition_id
            ):
                cube.library_classification = classification


__all__ = [
    "CubeGraphGatewayProtocol",
    "WorkflowCubeLibraryGateway",
    "WorkflowCubeLibraryService",
]
