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

"""Verify workflow export persistence orchestration."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from tests.application.recipes.workflow_export.support import build_service


class _ManifestAnnotator:
    """Mark detached graphs observed by the export path."""

    def __init__(self) -> None:
        self.graphs: list[dict[str, object]] = []

    def annotate(self, graph: dict[str, object]) -> object:
        """Add optional metadata without touching executable nodes."""

        self.graphs.append(graph)
        extra = graph.setdefault("extra", {})
        assert isinstance(extra, dict)
        extra["sugarsubstitute_model_manifest"] = {"schema_version": 1}
        return ()


def test_workflow_export_service_compiles_and_persists_json() -> None:
    """Compile a workflow payload before persisting it through the repository."""
    expected_payload: dict[str, object] = {
        "1": {"class_type": "KSampler", "inputs": {"steps": 20}}
    }
    service, repository, compiler = build_service(expected_payload)
    destination = Path("recipes") / "export.json"
    output_dir = Path("projects")

    payload = service.export_workflow_json(
        destination_path=destination,
        sugar_script_text="use Cube as A",
        output_dir=output_dir,
    )

    assert compiler.calls == [("use Cube as A", output_dir)]
    assert payload == expected_payload
    assert repository.saved == [(destination, expected_payload)]


def test_graph_backed_export_persists_canonical_graph_without_sugarscript() -> None:
    """Keep modern export on graph authority and leave the compiler untouched."""

    service, repository, compiler = build_service({"legacy": {}})
    destination = Path("recipes") / "native.json"
    graph: dict[str, object] = {
        "version": 0.4,
        "nodes": [{"id": 1, "type": "Note", "widgets_values": ["exact"]}],
        "links": [],
    }
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("native.json"),
            source_workflow=graph,
            buffer={"nodes": {}},
        )
    )

    payload = service.export_workflow_json(
        destination_path=destination,
        sugar_script_text=None,
        output_dir=Path("projects"),
        workflow=workflow,
    )

    assert payload == graph
    assert payload is not graph
    assert compiler.calls == []
    assert repository.saved == [(destination, payload)]


def test_graph_backed_export_refreshes_portable_model_metadata() -> None:
    """Canonical JSON export must invoke the shared manifest owner on its copy."""

    annotator = _ManifestAnnotator()
    service, _repository, _compiler = build_service(
        {"legacy": {}},
        model_manifest_annotator=annotator,
    )
    graph: dict[str, object] = {"version": 0.4, "nodes": [], "links": []}
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("native.json"),
            source_workflow=graph,
            buffer={"nodes": {}},
        )
    )

    payload = service.compile_workflow_payload(
        sugar_script_text=None,
        output_dir=Path("projects"),
        workflow=workflow,
    )

    assert annotator.graphs == [payload]
    assert "extra" not in graph
    assert payload["extra"] == {"sugarsubstitute_model_manifest": {"schema_version": 1}}
