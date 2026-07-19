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

"""Import genuine managed Comfy workflows through the pure headless compiler."""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from substitute.domain.comfy_workflow import (
    ComfyApiGraphBuilder,
    ComfyImageOutputDiscovery,
    ComfyWorkflowConverter,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)

_API_FORBIDDEN_CLASSES = frozenset({"MarkdownNote", "Note", "PrimitiveNode", "Reroute"})


@dataclass(frozen=True, slots=True)
class WorkflowCorpusFailure:
    """Describe one workflow import or lowering failure."""

    workflow: str
    exception_type: str
    message: str


@dataclass(frozen=True, slots=True)
class WorkflowCorpusReport:
    """Summarize a complete managed workflow corpus run."""

    workflow_count: int
    editor_node_count: int
    api_node_count: int
    primitive_node_count: int
    image_source_count: int
    input_image_endpoint_count: int
    input_mask_endpoint_count: int
    editable_mask_binding_count: int
    synthetic_canvas_surface_count: int
    rejected_mask_endpoint_count: int
    failures: tuple[WorkflowCorpusFailure, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether every workflow imported and lowered cleanly."""

        return not self.failures


class HeadlessComfyWorkflowCorpusHarness:
    """Compile real workflow JSON without constructing or showing Qt widgets."""

    def __init__(
        self,
        *,
        template_root: Path,
        node_definitions: Mapping[str, Mapping[str, object]],
    ) -> None:
        """Store the corpus and recorded or live Comfy definition snapshot."""

        self._template_root = template_root.resolve()
        self._node_definitions = node_definitions
        self._repository = ComfyWorkflowDocumentRepository()

    def run(self, paths: Sequence[Path] | None = None) -> WorkflowCorpusReport:
        """Import and lower each selected workflow while collecting all failures."""

        workflow_paths = tuple(paths or sorted(self._template_root.glob("*.json")))
        editor_node_count = 0
        api_node_count = 0
        primitive_node_count = 0
        image_source_count = 0
        input_image_endpoint_count = 0
        input_mask_endpoint_count = 0
        editable_mask_binding_count = 0
        synthetic_canvas_surface_count = 0
        rejected_mask_endpoint_count = 0
        failures: list[WorkflowCorpusFailure] = []
        definition_service = WorkflowNodeDefinitionService()
        endpoint_service = InputAssetEndpointService(definition_service)
        plan_service = InputCanvasPlanService(
            node_definition_service=definition_service,
            endpoint_service=endpoint_service,
        )
        for path in workflow_paths:
            try:
                workflow = self._repository.load(path)
                graph = ComfyWorkflowConverter().convert(
                    workflow,
                    node_definitions=self._node_definitions,
                )
                api_graph = ComfyApiGraphBuilder().build(graph)
                output_manifest = ComfyImageOutputDiscovery().discover(
                    api_graph,
                    node_definitions=self._node_definitions,
                )
                input_index = endpoint_service.build_index(
                    "__direct_comfy_workflow__",
                    graph,
                    node_definitions=self._node_definitions,
                )
                input_plan = plan_service.build_plan(
                    "__direct_comfy_workflow__",
                    graph,
                    node_definitions=self._node_definitions,
                )
                nodes = graph.get("nodes")
                if not isinstance(nodes, Mapping):
                    raise ValueError("compiled editor graph has no node mapping")
                forbidden = {
                    str(node.get("class_type"))
                    for node in api_graph.values()
                    if isinstance(node, Mapping)
                    and node.get("class_type") in _API_FORBIDDEN_CLASSES
                }
                if forbidden:
                    raise ValueError(
                        "API graph retained frontend-only classes: "
                        + ", ".join(sorted(forbidden))
                    )
                editor_node_count += len(nodes)
                api_node_count += len(api_graph)
                primitive_node_count += sum(
                    1
                    for node in nodes.values()
                    if isinstance(node, Mapping)
                    and node.get("class_type") == "PrimitiveNode"
                )
                image_source_count += len(output_manifest.sources)
                input_image_endpoint_count += len(input_index.image_endpoints)
                input_mask_endpoint_count += len(input_index.mask_endpoints)
                editable_mask_binding_count += len(input_plan.mask_bindings)
                synthetic_canvas_surface_count += sum(
                    1
                    for surface in input_plan.surfaces
                    if surface.image_endpoint is None
                )
                rejected_mask_endpoint_count += len(input_plan.rejected_mask_nodes)
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                failures.append(
                    WorkflowCorpusFailure(
                        workflow=path.name,
                        exception_type=type(error).__name__,
                        message=str(error),
                    )
                )
        return WorkflowCorpusReport(
            workflow_count=len(workflow_paths),
            editor_node_count=editor_node_count,
            api_node_count=api_node_count,
            primitive_node_count=primitive_node_count,
            image_source_count=image_source_count,
            input_image_endpoint_count=input_image_endpoint_count,
            input_mask_endpoint_count=input_mask_endpoint_count,
            editable_mask_binding_count=editable_mask_binding_count,
            synthetic_canvas_surface_count=synthetic_canvas_surface_count,
            rejected_mask_endpoint_count=rejected_mask_endpoint_count,
            failures=tuple(failures),
        )


def _load_object_info(url: str) -> dict[str, Mapping[str, object]]:
    """Read one Comfy object-info snapshot for a standalone harness run."""

    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, Mapping):
        raise ValueError("Comfy object_info response is not a mapping")
    return {
        str(class_type): definition
        for class_type, definition in payload.items()
        if isinstance(definition, Mapping)
    }


def main() -> int:
    """Run the harness from PowerShell and optionally persist a JSON report."""

    parser = argparse.ArgumentParser()
    parser.add_argument("template_root", type=Path)
    parser.add_argument(
        "--object-info-url",
        default="http://127.0.0.1:8188/object_info",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = HeadlessComfyWorkflowCorpusHarness(
        template_root=args.template_root,
        node_definitions=_load_object_info(args.object_info_url),
    ).run()
    rendered = json.dumps(asdict(report), indent=2, sort_keys=True)
    if args.report is not None:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "HeadlessComfyWorkflowCorpusHarness",
    "WorkflowCorpusFailure",
    "WorkflowCorpusReport",
]
