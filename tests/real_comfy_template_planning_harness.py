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

"""Plan genuine bundled image workflows against isolated live Comfy metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tests.headless_comfy_workflow_corpus_harness import (
    HeadlessComfyWorkflowCorpusHarness,
)
from tests.real_comfy_direct_output_harness import (
    ManagedComfyDirectOutputHarness,
)

_BUNDLED_SDXL_WORKFLOWS = (
    "sdxl_simple_example.json",
    "sdxl_refiner_prompt_example.json",
    "sdxl_revision_text_prompts.json",
    "sdxlturbo_example.json",
    "flux_canny_model_example.json",
    "flux_fill_inpaint_example.json",
)
_INPUT_WORKFLOWS = frozenset(
    {"flux_canny_model_example.json", "flux_fill_inpaint_example.json"}
)


@dataclass(frozen=True, slots=True)
class BundledWorkflowPlanningResult:
    """Summarize one real bundled workflow import and output plan."""

    workflow: str
    editor_node_count: int
    api_node_count: int
    image_source_count: int
    input_image_endpoint_count: int
    input_mask_endpoint_count: int
    editable_mask_binding_count: int
    synthetic_canvas_surface_count: int
    rejected_mask_endpoint_count: int


def run_real_comfy_template_planning_harness(
    repository_root: Path,
) -> tuple[BundledWorkflowPlanningResult, ...]:
    """Import representative SDXL templates using an isolated live Comfy process."""

    repository_root = repository_root.resolve()
    results: list[BundledWorkflowPlanningResult] = []
    with ManagedComfyDirectOutputHarness(repository_root) as managed_comfy:
        template_root = managed_comfy.image_template_root()
        corpus = HeadlessComfyWorkflowCorpusHarness(
            template_root=template_root,
            node_definitions=managed_comfy.node_definitions(),
        )
        for workflow_name in _BUNDLED_SDXL_WORKFLOWS:
            report = corpus.run((template_root / workflow_name,))
            if report.failures:
                failure = report.failures[0]
                raise AssertionError(
                    f"{workflow_name}: {failure.exception_type}: {failure.message}"
                )
            if report.image_source_count < 1:
                raise AssertionError(
                    f"{workflow_name}: no terminal image output source was planned"
                )
            if (
                workflow_name in _INPUT_WORKFLOWS
                and report.input_image_endpoint_count < 1
            ):
                raise AssertionError(
                    f"{workflow_name}: no semantic input image endpoint was planned"
                )
            results.append(
                BundledWorkflowPlanningResult(
                    workflow=workflow_name,
                    editor_node_count=report.editor_node_count,
                    api_node_count=report.api_node_count,
                    image_source_count=report.image_source_count,
                    input_image_endpoint_count=report.input_image_endpoint_count,
                    input_mask_endpoint_count=report.input_mask_endpoint_count,
                    editable_mask_binding_count=report.editable_mask_binding_count,
                    synthetic_canvas_surface_count=(
                        report.synthetic_canvas_surface_count
                    ),
                    rejected_mask_endpoint_count=report.rejected_mask_endpoint_count,
                )
            )
    return tuple(results)


if __name__ == "__main__":
    harness_results = run_real_comfy_template_planning_harness(
        Path(__file__).resolve().parents[1]
    )
    for harness_result in harness_results:
        print(harness_result)


__all__ = [
    "BundledWorkflowPlanningResult",
    "run_real_comfy_template_planning_harness",
]
