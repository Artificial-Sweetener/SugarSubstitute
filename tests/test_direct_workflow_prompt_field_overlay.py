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

"""Verify transient prompt overlays on direct Comfy authoring state."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from substitute.application.direct_workflows import (
    DirectWorkflowPromptFieldOverlayService,
    DirectWorkflowPromptProjector,
)
from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.comfy_workflow.output_manifest import (
    DirectWorkflowGenerationPlan,
    DirectWorkflowOutputManifest,
)


def test_prompt_projector_lowers_detached_overlay_and_preserves_output_manifest() -> (
    None
):
    """Projection should lower transient values while retaining discovered outputs."""

    document = _document()
    manifest = DirectWorkflowOutputManifest(
        sources=(),
        hijacked_sink_node_ids=frozenset({"sink"}),
        preserved_output_node_ids=("other",),
    )
    plan = DirectWorkflowGenerationPlan(
        authored_api_graph={
            "encoder": {
                "class_type": "Encoder",
                "inputs": {"text": "authored"},
            }
        },
        output_manifest=manifest,
    )

    projected = DirectWorkflowPromptProjector().project(
        document,
        plan,
        prompt_field_overrides={
            (DIRECT_WORKFLOW_SECTION_KEY, "value", "text"): "scene prompt"
        },
    )

    graph = cast(Any, projected.authored_api_graph)
    assert graph["encoder"]["inputs"]["text"] == "scene prompt"
    assert "value" not in graph
    assert projected.output_manifest is manifest
    assert cast(Any, document.buffer)["nodes"]["value"]["inputs"]["text"] == (
        "authored"
    )
    assert plan.authored_api_graph["encoder"] == {
        "class_type": "Encoder",
        "inputs": {"text": "authored"},
    }


@pytest.mark.parametrize(
    ("locator", "message"),
    (
        (("wrong", "value", "text"), "Unexpected direct prompt section: wrong"),
        (
            (DIRECT_WORKFLOW_SECTION_KEY, "missing", "text"),
            "Direct prompt node is unavailable: missing",
        ),
        (
            (DIRECT_WORKFLOW_SECTION_KEY, "value", "missing"),
            "Direct prompt input is unavailable: value.missing",
        ),
    ),
)
def test_prompt_field_overlay_rejects_stale_locators(
    locator: tuple[str, str, str],
    message: str,
) -> None:
    """Stale prompt locators should fail with actionable authoring identities."""

    with pytest.raises(ValueError, match=message):
        DirectWorkflowPromptFieldOverlayService().apply(
            _document(),
            prompt_field_overrides={locator: "scene prompt"},
        )


def _document() -> DirectWorkflowState:
    """Return a value-proxy prompt feeding one executable encoder."""

    return DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "value": {
                    "class_type": "PrimitiveNode",
                    "inputs": {"text": "authored"},
                    "mode": 0,
                    "_workflow": {
                        "execution_role": "value_proxy",
                        "value_field": "text",
                    },
                },
                "encoder": {
                    "class_type": "Encoder",
                    "inputs": {"text": ["value", 0]},
                    "mode": 0,
                },
            }
        },
    )
