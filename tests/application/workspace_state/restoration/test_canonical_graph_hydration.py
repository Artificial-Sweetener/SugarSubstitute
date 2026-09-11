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

"""Test canonical Comfy-graph authority during workspace hydration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path

from substitute.application.cubes import cube_target_model
from substitute.application.workspace_state.workspace_runtime_hydration_service import (
    WorkspaceRuntimeHydrationService,
)
from substitute.domain.comfy_workflow import (
    CanonicalCubeGraphAnalysis,
    DirectWorkflowState,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.domain.workspace_snapshot.cube_projection_codec import (
    capture_cube_projection_state,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from tests.support.canonical_cube_graph import graph_backed_cube_workflow
from tests.support.workspace_runtime_hydration import CubeLoaderStub
from tests.support.workspace_runtime_hydration import NodeBehaviorStub
from tests.support.workspace_runtime_hydration import cube_state
from tests.support.workspace_runtime_hydration import workspace_snapshot


@dataclass
class _GraphAnalyzer:
    """Return one SugarCubes-owned analysis and record whole-graph calls."""

    analysis: CanonicalCubeGraphAnalysis
    calls: list[dict[str, object]] = field(default_factory=list)
    create_calls: list[Sequence[Mapping[str, object]]] = field(default_factory=list)

    def analyze(self, workflow: dict[str, object]) -> CanonicalCubeGraphAnalysis:
        """Record the exact graph and return the canonical analysis."""

        self.calls.append(workflow)
        return self.analysis

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Record migration and echo canonical documents like SugarCubes."""

        self.create_calls.append(cubes)
        workflow = deepcopy(self.analysis.workflow)
        definitions = workflow.get("definitions")
        subgraphs = (
            definitions.get("subgraphs") if isinstance(definitions, dict) else None
        )
        if not isinstance(subgraphs, list) or len(subgraphs) != len(cubes):
            raise ValueError("fixture analysis does not match migration request")
        for subgraph, cube in zip(subgraphs, cubes, strict=True):
            extra = subgraph.get("extra") if isinstance(subgraph, dict) else None
            document = cube.get("document")
            if not isinstance(extra, dict) or not isinstance(document, Mapping):
                raise ValueError("fixture migration requires canonical documents")
            extra["sugarcubes_document"] = deepcopy(dict(document))
        return replace(self.analysis, workflow=workflow)


class _OrdinaryGraphAnalyzer:
    """Echo one canonical ordinary graph after recording its restored values."""

    def __init__(self) -> None:
        """Initialize the analysis call ledger."""

        self.calls: list[dict[str, object]] = []

    def analyze(self, workflow: dict[str, object]) -> CanonicalCubeGraphAnalysis:
        """Return a detached no-Cube analysis of the supplied graph."""

        self.calls.append(deepcopy(workflow))
        return CanonicalCubeGraphAnalysis(
            workflow_semantic_hash="ordinary",
            instances=(),
            edges=(),
            proximity_edges=(),
            segments=(),
            workflow=deepcopy(workflow),
        )

    def create_cube_workflow(
        self,
        _cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject the unrelated legacy migration route."""

        raise AssertionError("Ordinary graph restore attempted Cube migration.")


def test_restore_reconciles_legacy_direct_editor_values_into_canonical_graph() -> None:
    """Persisted pre-origin projections should update graph authority before analysis."""

    source_graph: dict[str, object] = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "inputs": [
                    {
                        "name": "seed",
                        "type": "INT",
                        "widget": {"name": "seed"},
                        "link": None,
                    }
                ],
                "outputs": [],
                "widgets_values": [17],
            }
        ],
        "links": [],
    }
    direct = DirectWorkflowState(
        source_path=Path("workflows/direct.json"),
        source_workflow=source_graph,
        buffer={
            "nodes": {
                "1": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 99},
                }
            }
        },
        dirty=True,
    )
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="direct",
                tab_label="Direct",
                workflow=WorkflowState(direct_workflow=direct),
            ),
        ),
        tab_order=("direct",),
        active_route="direct",
        active_workflow_id="direct",
    )
    analyzer = _OrdinaryGraphAnalyzer()

    result = WorkspaceRuntimeHydrationService(
        cube_load_service=CubeLoaderStub(),
        node_behavior_service=NodeBehaviorStub(),
        cube_workflow_analyzer=analyzer,
    ).hydrate(snapshot)

    restored = result.snapshot.workflows[0].workflow.direct_workflow
    assert restored is not None
    assert analyzer.calls[0]["nodes"][0]["widgets_values"] == [99]  # type: ignore[index]
    assert restored.source_workflow["nodes"][0]["widgets_values"] == [99]  # type: ignore[index]
    assert restored.buffer["nodes"]["1"]["inputs"]["seed"] == 99  # type: ignore[index]


def test_restore_reanalyzes_native_graph_and_hydrates_exact_cube_definitions() -> None:
    """Restore graph state and presentation from exact pinned Cube definitions."""

    canonical = graph_backed_cube_workflow("First", "Second")
    canonical_direct = canonical.direct_workflow
    assert canonical_direct is not None
    assert canonical_direct.cube_analysis is not None
    normalized_graph = deepcopy(canonical_direct.source_workflow)
    definitions = normalized_graph.get("definitions")
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    assert isinstance(subgraphs, list)
    for subgraph in subgraphs:
        assert isinstance(subgraph, dict)
        extra = subgraph.get("extra")
        assert isinstance(extra, dict)
        document = extra.get("sugarcubes_document")
        assert isinstance(document, dict)
        document["metadata"] = {
            "default_alias": "Anima/Prompt by Region",
            "target_model": "Anima",
        }
    canonical.cubes["Second"].ui = {
        **(canonical.cubes["Second"].ui or {}),
        "advanced_input_visibility": {"sampler": True},
    }
    canonical.cubes["Second"].field_control_states = {
        "sampler": {"seed": SeedControlState(SeedMode.FIXED)}
    }
    restored_direct = DirectWorkflowState(
        source_path=canonical_direct.source_path,
        source_workflow=canonical_direct.source_workflow,
        buffer={"nodes": {}},
        cube_projection_state=capture_cube_projection_state(canonical.cubes),
    )
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="native",
                tab_label="Native",
                workflow=WorkflowState(direct_workflow=restored_direct),
            ),
        ),
        tab_order=("native",),
        active_route="native",
        active_workflow_id="native",
    )
    analyzer = _GraphAnalyzer(
        replace(canonical_direct.cube_analysis, workflow=normalized_graph)
    )
    loader = CubeLoaderStub()

    result = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=NodeBehaviorStub(),
        cube_workflow_analyzer=analyzer,
    ).hydrate(snapshot)

    restored = result.snapshot.workflows[0]
    assert len(analyzer.calls) == 1
    assert analyzer.calls[0] == canonical_direct.source_workflow
    assert loader.load_calls == [
        ("test/First.cube", "1.0.0"),
        ("test/Second.cube", "1.0.0"),
    ]
    assert restored.workflow.is_graph_backed_cube_workflow is True
    assert restored.workflow.stack_order == ["First", "Second"]
    assert restored.workflow.cubes["Second"].ui is not None
    assert restored.workflow.cubes["Second"].ui["advanced_input_visibility"] == {
        "sampler": True
    }
    assert cube_target_model(restored.workflow.cubes["First"]) == "Anima"
    assert cube_target_model(restored.workflow.cubes["Second"]) == "Anima"
    assert (
        restored.workflow.cubes["Second"].field_control_states["sampler"]["seed"].mode
        is SeedMode.FIXED
    )
    assert restored.active_cube_alias == "First"
    assert result.warnings == ()


def test_restore_migrates_all_legacy_cubes_in_one_sugarcubes_request() -> None:
    """Replace hydrated stack authority with one returned native graph."""

    canonical = graph_backed_cube_workflow("Old", "New")
    direct = canonical.direct_workflow
    assert direct is not None and direct.cube_analysis is not None
    analyzer = _GraphAnalyzer(direct.cube_analysis)
    loader = CubeLoaderStub()
    snapshot = workspace_snapshot(
        [
            cube_state(alias="Old", version="1.0", bypassed=True),
            cube_state(alias="New", version="2.0"),
        ]
    )
    snapshot = WorkspaceSnapshot(
        schema_version=snapshot.schema_version,
        workflows=(
            replace(
                snapshot.workflows[0],
                active_cube_alias="New",
                document_source_path=Path("legacy.sugar"),
            ),
        ),
        tab_order=snapshot.tab_order,
        active_route=snapshot.active_route,
        active_workflow_id=snapshot.active_workflow_id,
    )

    result = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=NodeBehaviorStub(),
        cube_workflow_analyzer=analyzer,
    ).hydrate(snapshot)

    restored = result.snapshot.workflows[0]
    assert len(analyzer.create_calls) == 1
    assert [cube["alias"] for cube in analyzer.create_calls[0]] == ["Old", "New"]
    assert [cube["bypassed"] for cube in analyzer.create_calls[0]] == [True, False]
    migrated_document = analyzer.create_calls[0][0]["document"]
    assert isinstance(migrated_document, Mapping)
    assert migrated_document["description"] == "Canonical description"
    assert migrated_document["metadata"] == {
        "default_alias": "Anima/Prompt by Region",
        "target_model": "Anima",
    }
    assert migrated_document["surface"] == {
        "default_flavor_id": "default",
        "controls": [],
    }
    assert analyzer.calls == []
    assert restored.workflow.is_graph_backed_cube_workflow is True
    assert restored.workflow.stack_order == ["Old", "New"]
    assert cube_target_model(restored.workflow.cubes["Old"]) == "Anima"
    assert restored.active_cube_alias == "New"
    assert restored.document_dirty is True
    assert restored.document_source_path == Path("legacy.sugar")
    assert result.warnings == ()
