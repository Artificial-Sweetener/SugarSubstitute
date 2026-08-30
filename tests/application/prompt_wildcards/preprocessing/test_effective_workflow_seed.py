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

"""Verify effective workflow seeds drive wildcard preprocessing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from substitute.application.prompt_wildcards import (
    PromptWildcardPreprocessingService,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
    FilePromptWildcardCatalogGateway,
)


def test_global_seed_drives_resolution_when_downstream_cube_seed_is_stale(
    tmp_path: Path,
) -> None:
    """A global seed should beat the stale fallback seed from a later cube."""

    service = _service(tmp_path)
    workflow = _workflow(global_seed=5, downstream_seed=1)

    resolved = service.preprocess_workflow_copy(
        workflow=workflow,
        workflow_id="Scene Test",
    )

    assert _prompt(resolved) == "portrait third"
    assert _prompt(workflow) == "portrait {subject}"


def test_first_workflow_seed_drives_resolution_without_global_override(
    tmp_path: Path,
) -> None:
    """The first surfaced workflow seed should drive fallback resolution."""

    service = _service(tmp_path)
    workflow = _workflow(global_seed=None, downstream_seed=1)

    resolved = service.preprocess_workflow_copy(
        workflow=workflow,
        workflow_id="Scene Test",
    )

    assert _prompt(resolved) == "portrait first"


def _service(tmp_path: Path) -> PromptWildcardPreprocessingService:
    """Create production preprocessing over one isolated wildcard file."""

    user_root = tmp_path / "user" / "wildcards"
    user_root.mkdir(parents=True)
    (user_root / "subject.txt").write_text(
        "first\nsecond\nthird\n",
        encoding="utf-8",
    )
    gateway = FilePromptWildcardCatalogGateway(
        user_wildcards_root=user_root,
        comfy_custom_nodes_root=None,
    )
    return PromptWildcardPreprocessingService(source_provider=gateway)


def _workflow(*, global_seed: int | None, downstream_seed: int) -> WorkflowState:
    """Build the failing topology from the production Scene Test workflow."""

    prompt_cube = CubeState(
        cube_id="owner/repo/prompt.cube",
        version="1.0.0",
        alias="Prompt",
        original_cube={"surface": {"controls": []}},
        buffer={
            "nodes": {
                "positive_prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "portrait {subject}"},
                }
            }
        },
    )
    downstream_cube = CubeState(
        cube_id="owner/repo/downstream.cube",
        version="1.0.0",
        alias="Downstream",
        original_cube={
            "surface": {
                "controls": [
                    {
                        "control_id": "ksampler.seed",
                        "symbol": "ksampler",
                        "input_name": "seed",
                    }
                ]
            }
        },
        buffer={
            "nodes": {
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"seed": downstream_seed},
                }
            }
        },
    )
    global_overrides = (
        {}
        if global_seed is None
        else {"seed": {"value": global_seed, "mode": "global"}}
    )
    return WorkflowState(
        cubes={"Prompt": prompt_cube, "Downstream": downstream_cube},
        stack_order=["Prompt", "Downstream"],
        global_overrides=global_overrides,
    )


def _prompt(workflow: WorkflowState) -> str:
    """Return the prompt value from the test workflow."""

    workflow_state = cast(Any, workflow)
    return cast(
        str,
        workflow_state.cubes["Prompt"].buffer["nodes"]["positive_prompt"]["inputs"][
            "text"
        ],
    )
