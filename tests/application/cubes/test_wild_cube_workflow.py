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

"""Prove headless wild Cube loading, rearrangement, capture, and dispatch."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from substitute.application.cubes import CubeStackService, WorkflowCubeLibraryService
from substitute.application.cubes.graph_backed_cube_stack_service import (
    GraphBackedCubeStackService,
)
from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.application.ports import QueueVisualRunContext
from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.comfy_workflow.cube_analysis import (
    AnalyzedCubeInstance,
    AnalyzedCubeSegment,
)
from substitute.domain.common import JsonObject
from substitute.domain.cube_library import (
    WorkflowCubeAccess,
    WorkflowCubeCaptureResult,
    WorkflowCubeClassification,
    WorkflowCubeClassificationReport,
    WorkflowCubeLibraryClass,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.domain.workflow import WorkflowState
from substitute.infrastructure.comfy.native_cube_execution_client import (
    NativeCubeExecutionClient,
)


def test_wild_cube_workflow_loads_reorders_captures_and_dispatches_headlessly(
    tmp_path: Path,
) -> None:
    """Keep embedded Cube truth usable without any tracked or personal pack."""

    source = _wild_workflow()
    graph = _GraphGateway()
    library = _LibraryGateway()
    service = WorkflowCubeLibraryService(graph, library)
    document = DirectWorkflowLoadService(
        _Repository(source),
        service,
    ).load(tmp_path / "wild.json")
    workflow = WorkflowState(direct_workflow=document)

    assert workflow.stack_order == ["Wild A", "Wild B"]
    assert all(
        cube.library_classification is not None
        and cube.library_classification.primary_class is WorkflowCubeLibraryClass.NONE
        for cube in workflow.cubes.values()
    )

    CubeStackService(GraphBackedCubeStackService(service)).apply_reordered_aliases(
        workflow,
        ["Wild B", "Wild A"],
    )

    assert workflow.stack_order == ["Wild B", "Wild A"]
    assert workflow.direct_workflow is not None
    embedded_before_capture = deepcopy(workflow.direct_workflow.source_workflow)

    capture = service.capture_cube(workflow, "Wild A")

    assert capture.created is True
    assert workflow.cubes["Wild A"].library_classification is not None
    assert (
        workflow.cubes["Wild A"].library_classification.primary_class
        is WorkflowCubeLibraryClass.CAPTURED
    )
    assert workflow.direct_workflow.source_workflow == embedded_before_capture

    http = _ExecutionHttp()
    queued = NativeCubeExecutionClient(
        ComfyEndpoint("127.0.0.1", 8188),
        http=http,
    ).queue(
        workflow=workflow.direct_workflow.source_workflow,
        client_id="headless-client",
        visual_context=QueueVisualRunContext(
            workflow_id="wild-workflow",
            generation_run_id="headless-run",
            client_id="headless-client",
            sources={},
        ),
    )

    assert queued.prompt_id == "wild-prompt"
    assert http.queued_workflow == workflow.direct_workflow.source_workflow


class _Repository:
    """Return one detached in-memory workflow."""

    def __init__(self, workflow: JsonObject) -> None:
        """Store the source fixture."""

        self._workflow = workflow

    def can_load(self, _path: Path) -> bool:
        """Report the synthetic source as available."""

        return True

    def load(self, _path: Path) -> JsonObject:
        """Return a detached workflow copy."""

        return deepcopy(self._workflow)


class _GraphGateway:
    """Recognize two embedded Cubes without consulting a Cube catalog."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return canonical topology derived only from embedded graph markers."""

        return CanonicalCubeGraphAnalysis(
            workflow_semantic_hash="wild-workflow",
            instances=(
                _instance("instance-a", "1", "definition-a", "Wild/A.cube", "Wild A"),
                _instance("instance-b", "2", "definition-b", "Wild/B.cube", "Wild B"),
            ),
            edges=(),
            proximity_edges=(),
            segments=(
                AnalyzedCubeSegment(
                    instance_ids=("instance-a", "instance-b"),
                    reorderable=True,
                    boundary_node_ids=(),
                ),
            ),
            workflow=deepcopy(workflow),
        )

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject network reorder because Substitute uses cached authorization."""

        raise AssertionError("Cached Cube rearrangement should avoid target IO.")

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unrelated append operations."""

        raise AssertionError("Unexpected Cube append.")

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unrelated graph creation."""

        raise AssertionError("Unexpected Cube graph creation.")

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unrelated removal."""

        raise AssertionError("Unexpected Cube removal.")

    def replace_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unrelated replacement."""

        raise AssertionError("Unexpected Cube replacement.")


class _LibraryGateway:
    """Classify every embedded definition as wild until exact capture."""

    def classify(self, workflow: JsonObject) -> WorkflowCubeClassificationReport:
        """Return wild classifications without using installed catalog data."""

        del workflow
        return WorkflowCubeClassificationReport(
            definitions=(
                _classification("definition-a", "instance-a", "Wild/A.cube"),
                _classification("definition-b", "instance-b", "Wild/B.cube"),
            )
        )

    def capture(
        self,
        workflow: JsonObject,
        *,
        definition_id: str,
        expected_semantic_hash: str,
    ) -> WorkflowCubeCaptureResult:
        """Return Captured state while asserting the exact embedded request."""

        assert workflow["definitions"]
        assert definition_id == "definition-a"
        assert expected_semantic_hash == "a" * 64
        classification = _classification(
            definition_id,
            "instance-a",
            "Wild/A.cube",
            primary_class=WorkflowCubeLibraryClass.CAPTURED,
            operations=frozenset({"keep"}),
        )
        return WorkflowCubeCaptureResult(
            cube_id=classification.cube_id,
            cube_version=classification.cube_version,
            semantic_hash=classification.semantic_hash,
            created=True,
            classification=classification,
        )


@dataclass
class _Response:
    """Return one successful execution HTTP payload."""

    payload: object
    status_code: int = 200

    def raise_for_status(self) -> None:
        """Accept the response."""

    def json(self) -> object:
        """Return the configured payload."""

        return self.payload


class _ExecutionHttp:
    """Negotiate and capture one native execution without a GUI."""

    def __init__(self) -> None:
        """Initialize queued workflow capture."""

        self.queued_workflow: object = None

    def get(self, url: str, *, timeout: float) -> _Response:
        """Return exact supported backend or SugarCubes capabilities."""

        assert timeout == 3.0
        if url.endswith("/substitute/v1/capabilities"):
            return _Response(
                {
                    "features": ["native-cube-queue-context"],
                    "nativeCubeQueueContext": {
                        "schemaVersion": 1,
                        "queueObserverApiVersion": 1,
                        "requiredObserver": True,
                        "preQueuePersistence": True,
                        "sourceIdentityFromExecutionReport": True,
                    },
                }
            )
        return _Response(
            {
                "available": True,
                "schema_version": 1,
                "workflow_schema_version": 1,
                "report_schema_version": 1,
                "queue_observer_api_version": 1,
                "queue_route": "/sugarcubes/v2/executions/queue",
                "execution_owner": "sugarcubes",
                "atomic_queueing": True,
                "cube_scoped_optimization": True,
                "validated_queue_observers": True,
            }
        )

    def post(self, url: str, *, json: object, timeout: float) -> _Response:
        """Capture the workflow sent to SugarCubes' native queue."""

        assert url.endswith("/sugarcubes/v2/executions/queue")
        assert timeout == 10.0
        assert isinstance(json, dict)
        self.queued_workflow = json.get("workflow")
        return _Response({"prompt_id": "wild-prompt", "report": {}})


def _instance(
    instance_id: str,
    node_id: str,
    definition_id: str,
    cube_id: str,
    alias: str,
) -> AnalyzedCubeInstance:
    """Build one analyzed embedded Cube instance."""

    return AnalyzedCubeInstance(
        instance_id=instance_id,
        node_id=node_id,
        definition_id=definition_id,
        cube_id=cube_id,
        cube_version="1.0.0",
        alias=alias,
        execution_mode=0,
    )


def _classification(
    definition_id: str,
    instance_id: str,
    cube_id: str,
    *,
    primary_class: WorkflowCubeLibraryClass = WorkflowCubeLibraryClass.NONE,
    operations: frozenset[str] = frozenset({"keep", "capture"}),
) -> WorkflowCubeClassification:
    """Build one transient workflow classification."""

    return WorkflowCubeClassification(
        definition_id=definition_id,
        cube_id=cube_id,
        cube_version="1.0.0",
        semantic_hash="a" * 64,
        instance_ids=(instance_id,),
        primary_class=primary_class,
        access=WorkflowCubeAccess.READ_ONLY,
        source_available=False,
        permitted_operations=operations,
    )


def _wild_workflow() -> JsonObject:
    """Return two valid embedded Cube definitions with no catalog dependency."""

    documents = {
        "definition-a": _document("Wild/A.cube"),
        "definition-b": _document("Wild/B.cube"),
    }
    return {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "definition-a",
                "pos": [0, 0],
                "size": [100, 100],
                "inputs": [],
                "outputs": [],
            },
            {
                "id": 2,
                "type": "definition-b",
                "pos": [160, 0],
                "size": [100, 100],
                "inputs": [],
                "outputs": [],
            },
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": definition_id,
                    "nodes": [],
                    "links": [],
                    "inputs": [],
                    "outputs": [],
                    "extra": {"sugarcubes_document": document},
                }
                for definition_id, document in documents.items()
            ]
        },
    }


def _document(cube_id: str) -> JsonObject:
    """Return one minimal embedded Cube document."""

    return {
        "cube_id": cube_id,
        "version": "1.0.0",
        "implementation": {"nodes": {}, "inputs": {}, "outputs": {}},
    }
