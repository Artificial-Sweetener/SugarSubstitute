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

"""Protect graph-authored Cube state across the complete headless cache lifecycle."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
import json
from pathlib import Path

from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.application.workspace_state import RestoreProjectionCacheState
from substitute.application.workspace_state.workspace_runtime_hydration_service import (
    WorkspaceRuntimeHydrationService,
)
from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.common import GlobalOverrideMap, JsonObject
from substitute.domain.session import session_snapshot_from_json
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from tests.application.workspace_state.restoration.fixture_harness import (
    HeadlessWorkspaceRestoreHarness,
)
from tests.support.canonical_cube_graph import graph_backed_cube_workflow_from_states

_POSITIVE = "global positive\n[SEP]\nfirst region\n[SEP]\nsecond region"
_NEGATIVE = "global negative\n[SEP]\nfirst exclusion\n[SEP]\nsecond exclusion"
_OVERRIDES: GlobalOverrideMap = {"seed": {"value": 8675309}}


@dataclass
class _EchoGraphAnalyzer:
    """Echo submitted source graphs through one stable SugarCubes analysis shape."""

    template: CanonicalCubeGraphAnalysis
    calls: list[JsonObject] = field(default_factory=list)

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return a detached normalized graph while recording the submitted source."""

        self.calls.append(deepcopy(workflow))
        if not isinstance(workflow.get("definitions"), Mapping):
            return CanonicalCubeGraphAnalysis(
                workflow_semantic_hash="ordinary-graph",
                instances=(),
                edges=(),
                proximity_edges=(),
                segments=(),
                workflow=deepcopy(workflow),
            )
        return replace(self.template, workflow=deepcopy(workflow))

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject the unrelated legacy migration path."""

        raise AssertionError(f"Unexpected legacy Cube migration: {cubes!r}")


@dataclass
class _PresentationNormalizingAnalyzer(_EchoGraphAnalyzer):
    """Apply one stable derived presentation revision during graph analysis."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return the graph with one deterministic normalized presentation value."""

        normalized = deepcopy(workflow)
        definitions = normalized["definitions"]
        assert isinstance(definitions, dict)
        subgraphs = definitions["subgraphs"]
        assert isinstance(subgraphs, list)
        for subgraph in subgraphs:
            assert isinstance(subgraph, dict)
            extra = subgraph["extra"]
            assert isinstance(extra, dict)
            document = extra["sugarcubes_document"]
            assert isinstance(document, dict)
            metadata = document["metadata"]
            assert isinstance(metadata, dict)
            metadata["target_model"] = "Anima normalized"
        self.calls.append(deepcopy(workflow))
        return replace(self.template, workflow=normalized)


def test_graph_authored_state_survives_cache_hit_invalidation_and_resave(
    tmp_path: Path,
) -> None:
    """Keep authored values in session authority while projection cache stays reusable."""

    harness = HeadlessWorkspaceRestoreHarness(tmp_path)
    graph_workflow, analyzer = _linked_graph_workflow()
    harness.capture_port.workflows["cube"] = graph_workflow

    assert harness.force_save() is True
    session_path = tmp_path / "session" / "session.json"
    initial_session_bytes = session_path.read_bytes()
    cold_plan = harness.build_restore_plan()
    assert cold_plan.workspace is not None
    assert cold_plan.restore_projection_validation is not None
    assert (
        cold_plan.restore_projection_validation.state
        is RestoreProjectionCacheState.MISSING
    )
    _assert_authoritative_state(cold_plan.workspace)

    cold_hydrated = _hydrate(harness, cold_plan.workspace, analyzer)
    _assert_authoritative_state(cold_hydrated)
    harness.capture_projection_cache(cold_hydrated)
    cache_path = harness.cache_repository.path
    cache_bytes = cache_path.read_bytes()
    cache_text = cache_bytes.decode("utf-8")
    assert _POSITIVE not in cache_text
    assert _NEGATIVE not in cache_text
    assert session_path.read_bytes() == initial_session_bytes

    warm_plan = harness.build_restore_plan()
    assert warm_plan.workspace is not None
    assert warm_plan.provisional_restore_projection is not None
    assert warm_plan.restore_projection_validation is not None
    assert (
        warm_plan.restore_projection_validation.state
        is RestoreProjectionCacheState.BACKEND_PENDING
    )
    assert (
        harness.validate_after_backend(warm_plan).state
        is RestoreProjectionCacheState.VALID
    )
    assert cache_path.read_bytes() == cache_bytes
    assert session_path.read_bytes() == initial_session_bytes
    _assert_authoritative_state(_hydrate(harness, warm_plan.workspace, analyzer))

    artifact = harness.cache_repository.load()
    assert artifact is not None
    harness.cache_repository.save(replace(artifact, workspace_fingerprint="stale"))
    invalidated_plan = harness.build_restore_plan()
    assert invalidated_plan.workspace is not None
    assert invalidated_plan.restore_projection_validation is not None
    assert (
        invalidated_plan.restore_projection_validation.state
        is RestoreProjectionCacheState.WORKSPACE_MISMATCH
    )
    assert not cache_path.exists()
    assert session_path.read_bytes() == initial_session_bytes
    _assert_authoritative_state(invalidated_plan.workspace)

    rebuilt = _hydrate(harness, invalidated_plan.workspace, analyzer)
    harness.capture_projection_cache(rebuilt)
    rebuilt_cache_bytes = cache_path.read_bytes()
    assert _POSITIVE not in rebuilt_cache_bytes.decode("utf-8")
    assert _NEGATIVE not in rebuilt_cache_bytes.decode("utf-8")
    rebuilt_plan = harness.build_restore_plan()
    assert rebuilt_plan.provisional_restore_projection is not None
    assert (
        harness.validate_after_backend(rebuilt_plan).state
        is RestoreProjectionCacheState.VALID
    )

    harness.capture_port.workflows["cube"] = rebuilt.workflows[0].workflow
    assert harness.force_save() is True
    assert harness.force_save() is True
    final_plan = harness.build_restore_plan()
    assert final_plan.workspace is not None
    assert final_plan.provisional_restore_projection is not None
    assert (
        harness.validate_after_backend(final_plan).state
        is RestoreProjectionCacheState.VALID
    )
    _assert_authoritative_state(_hydrate(harness, final_plan.workspace, analyzer))
    backup = session_snapshot_from_json(
        json.loads((tmp_path / "session" / "session.json.bak").read_text("utf-8"))
    )
    _assert_authoritative_state(backup.workspace)
    cube_analysis_calls = [
        call for call in analyzer.calls if isinstance(call.get("definitions"), Mapping)
    ]
    assert len(cube_analysis_calls) == 4


def test_normalized_graph_cache_is_reused_after_authoritative_shutdown_save(
    tmp_path: Path,
) -> None:
    """Reuse derived projection after normalized authority is saved at shutdown."""

    harness = HeadlessWorkspaceRestoreHarness(tmp_path)
    graph_workflow, echo = _linked_graph_workflow()
    analyzer = _PresentationNormalizingAnalyzer(echo.template)
    harness.capture_port.workflows["cube"] = graph_workflow
    assert harness.force_save() is True

    cold_plan = harness.build_restore_plan()
    assert cold_plan.workspace is not None
    hydrated = _hydrate(harness, cold_plan.workspace, analyzer)
    _assert_authoritative_state(hydrated)
    harness.capture_projection_cache(hydrated)

    harness.capture_port.workflows["cube"] = hydrated.workflows[0].workflow
    assert harness.force_save() is True
    warm_plan = harness.build_restore_plan()

    assert warm_plan.provisional_restore_projection is not None
    assert (
        harness.validate_after_backend(warm_plan).state
        is RestoreProjectionCacheState.VALID
    )
    assert warm_plan.workspace is not None
    _assert_authoritative_state(_hydrate(harness, warm_plan.workspace, analyzer))


def test_restore_uses_live_graph_inputs_without_rewriting_flavor_presets(
    tmp_path: Path,
) -> None:
    """Keep instance inputs authoritative while preserving independent presets."""

    harness = HeadlessWorkspaceRestoreHarness(tmp_path)
    workflow, analyzer = _linked_graph_workflow()
    direct = workflow.direct_workflow
    assert direct is not None
    definitions = direct.source_workflow["definitions"]
    assert isinstance(definitions, dict)
    subgraphs = definitions["subgraphs"]
    assert isinstance(subgraphs, list)
    source = _embedded_document(subgraphs[0])
    flavors = source["flavors"]
    assert isinstance(flavors, dict)
    authored = flavors["authored"]
    assert isinstance(authored, list)
    default_flavor = authored[0]
    assert isinstance(default_flavor, dict)
    default_flavor["values"] = {
        "positive_prompt.value": "",
        "negative_prompt.value": "",
    }
    workspace = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="cube",
                tab_label="Cube",
                workflow=workflow,
            ),
        ),
        tab_order=("cube",),
        active_route="cube",
        active_workflow_id="cube",
    )

    restored = _hydrate(harness, workspace, analyzer)

    assert len(analyzer.calls) == 1
    submitted = analyzer.calls[0]
    submitted_definitions = submitted["definitions"]
    assert isinstance(submitted_definitions, dict)
    submitted_subgraphs = submitted_definitions["subgraphs"]
    assert isinstance(submitted_subgraphs, list)
    submitted_source = _embedded_document(submitted_subgraphs[0])
    submitted_flavors = submitted_source["flavors"]
    assert isinstance(submitted_flavors, dict)
    submitted_authored = submitted_flavors["authored"]
    assert isinstance(submitted_authored, list)
    submitted_default = submitted_authored[0]
    assert isinstance(submitted_default, dict)
    assert submitted_default["values"] == {
        "positive_prompt.value": "",
        "negative_prompt.value": "",
    }
    assert _node_input(submitted_source, "positive_prompt", "text") == _POSITIVE
    assert _node_input(submitted_source, "negative_prompt", "text") == _NEGATIVE
    _assert_authoritative_state(restored)


def _linked_graph_workflow() -> tuple[WorkflowState, _EchoGraphAnalyzer]:
    """Return one source/follower graph with durable links and authored values."""

    source = _prompt_cube("Source", positive=_POSITIVE, negative=_NEGATIVE)
    follower = _prompt_cube(
        "Follower",
        positive="",
        negative="",
        linked_from="Source",
    )
    workflow = graph_backed_cube_workflow_from_states(source, follower)
    workflow.global_overrides = deepcopy(_OVERRIDES)
    direct = workflow.direct_workflow
    if direct is None or direct.cube_analysis is None:
        raise AssertionError("Fixture did not create a graph-backed Cube workflow.")
    return workflow, _EchoGraphAnalyzer(direct.cube_analysis)


def _prompt_cube(
    alias: str,
    *,
    positive: str,
    negative: str,
    linked_from: str | None = None,
) -> CubeState:
    """Build one exact-definition-shaped Cube with stable prompt controls."""

    nodes: JsonObject = {
        "positive_prompt": _prompt_node(
            positive,
            linked_from=linked_from,
            linked_node="positive_prompt",
        ),
        "negative_prompt": _prompt_node(
            negative,
            linked_from=linked_from,
            linked_node="negative_prompt",
        ),
    }
    return CubeState(
        cube_id="cube.scene",
        version="1.0.0",
        alias=alias,
        original_cube={
            "description": "Prompt fixture",
            "metadata": {"default_alias": alias, "target_model": "Anima"},
        },
        buffer={
            "nodes": nodes,
            "inputs": {},
            "outputs": {},
            "layout": {},
            "definitions": {},
            "subgraphs": [],
            "surface": {
                "default_flavor_id": "default",
                "controls": [
                    {
                        "control_id": "positive_prompt.value",
                        "symbol": "positive_prompt",
                        "input_name": "text",
                    },
                    {
                        "control_id": "negative_prompt.value",
                        "symbol": "negative_prompt",
                        "input_name": "text",
                    },
                ],
            },
            "flavors": {
                "authored": [{"id": "default", "name": "Default", "values": {}}]
            },
        },
    )


def _prompt_node(
    value: str,
    *,
    linked_from: str | None,
    linked_node: str,
) -> JsonObject:
    """Return one prompt node with optional Substitute-owned relation metadata."""

    node: JsonObject = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": value},
    }
    if linked_from is not None:
        node["node_link"] = {
            "from_cube": linked_from,
            "from_node": linked_node,
        }
    return node


def _hydrate(
    harness: HeadlessWorkspaceRestoreHarness,
    workspace: WorkspaceSnapshot,
    analyzer: _EchoGraphAnalyzer,
) -> WorkspaceSnapshot:
    """Hydrate one lifecycle stage through the production application owner."""

    return (
        WorkspaceRuntimeHydrationService(
            cube_load_service=harness.cube_loader,
            node_behavior_service=_NoOpNodeBehavior(),
            cube_workflow_analyzer=analyzer,
        )
        .hydrate(workspace)
        .snapshot
    )


class _NoOpNodeBehavior:
    """Return the real empty node-behavior runtime value for hydration."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Return empty behavior state without interpreting authored fields."""

        _ = loaded_cube, alias_name
        return NodeBehaviorRuntimeState()


def _assert_authoritative_state(workspace: WorkspaceSnapshot) -> None:
    """Assert exact graph values, relations, and overrides in session authority."""

    snapshot = next(item for item in workspace.workflows if item.workflow_id == "cube")
    direct = snapshot.workflow.direct_workflow
    assert direct is not None
    definitions = direct.source_workflow["definitions"]
    assert isinstance(definitions, dict)
    subgraphs = definitions["subgraphs"]
    assert isinstance(subgraphs, list)
    source = _embedded_document(subgraphs[0])
    follower = _embedded_document(subgraphs[1])
    assert _node_input(source, "positive_prompt", "text") == _POSITIVE
    assert _node_input(source, "negative_prompt", "text") == _NEGATIVE
    assert _node_input(follower, "positive_prompt", "text") == ""
    assert _node_input(follower, "negative_prompt", "text") == ""
    assert _node(follower, "positive_prompt").get("node_link") == {
        "from_cube": "Source",
        "from_node": "positive_prompt",
    }
    assert _node(follower, "negative_prompt").get("node_link") == {
        "from_cube": "Source",
        "from_node": "negative_prompt",
    }
    assert snapshot.workflow.global_overrides == _OVERRIDES


def _embedded_document(subgraph: object) -> JsonObject:
    """Return one fixture's embedded authoritative Cube document."""

    if not isinstance(subgraph, dict):
        raise AssertionError("Expected a subgraph object.")
    extra = subgraph.get("extra")
    document = extra.get("sugarcubes_document") if isinstance(extra, dict) else None
    if not isinstance(document, dict):
        raise AssertionError("Expected an embedded Cube document.")
    return document


def _node(document: Mapping[str, object], node_name: str) -> Mapping[str, object]:
    """Return one implementation node from an embedded Cube document."""

    implementation = document.get("implementation")
    nodes = implementation.get("nodes") if isinstance(implementation, Mapping) else None
    node = nodes.get(node_name) if isinstance(nodes, Mapping) else None
    if not isinstance(node, Mapping):
        raise AssertionError(f"Expected implementation node {node_name!r}.")
    return node


def _node_input(
    document: Mapping[str, object],
    node_name: str,
    input_name: str,
) -> object:
    """Return one authored implementation input value."""

    inputs = _node(document, node_name).get("inputs")
    if not isinstance(inputs, Mapping) or input_name not in inputs:
        raise AssertionError(f"Expected input {node_name}.{input_name}.")
    return inputs[input_name]
