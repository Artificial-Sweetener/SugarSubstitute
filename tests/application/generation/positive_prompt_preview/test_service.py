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

"""Tests for generation queue Positive Prompt preview extraction."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.generation.positive_prompt_preview import (
    positive_prompt_preview_from_workflow,
    prompt_preview_text,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole


def _snapshot(*endpoints: PromptEndpoint) -> EditorBehaviorSnapshot:
    """Return a minimal behavior snapshot with prompt endpoints."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=PromptEndpointIndex.from_endpoints(endpoints),
    )


def _endpoint(
    cube_alias: str,
    *,
    role: PromptRole = PromptRole.POSITIVE,
    node_name: str = "positive_prompt",
    field_key: str = "prompt_template",
) -> PromptEndpoint:
    """Return one prompt endpoint."""

    return PromptEndpoint(
        cube_alias=cube_alias,
        role=role,
        node_name=node_name,
        field_key=field_key,
    )


def _workflow(
    stack_order: list[str],
    buffers: dict[str, object],
) -> SimpleNamespace:
    """Return a workflow-shaped object for preview tests."""

    return SimpleNamespace(
        stack_order=stack_order,
        cubes={
            alias: SimpleNamespace(buffer=buffer) for alias, buffer in buffers.items()
        },
    )


def _buffer(prompt_value: object) -> dict[str, object]:
    """Return a buffer with a standard Positive Prompt node."""

    return {
        "nodes": {
            "positive_prompt": {
                "inputs": {
                    "prompt_template": prompt_value,
                },
            },
        },
    }


def test_positive_prompt_preview_uses_first_semantic_positive_prompt() -> None:
    """Preview extraction should follow workflow order and prompt role metadata."""

    workflow = _workflow(
        ["A", "B"],
        {
            "A": _buffer("first prompt"),
            "B": _buffer("second prompt"),
        },
    )

    preview = positive_prompt_preview_from_workflow(
        workflow=workflow,
        behavior_snapshot=_snapshot(_endpoint("B"), _endpoint("A")),
    )

    assert preview == "first prompt"


def test_positive_prompt_preview_handles_custom_positive_endpoint() -> None:
    """Preview extraction should use endpoint node and field metadata."""

    workflow = _workflow(
        ["A"],
        {
            "A": {
                "nodes": {
                    "custom_positive": {
                        "inputs": {
                            "text": "custom prompt",
                        },
                    },
                },
            },
        },
    )

    preview = positive_prompt_preview_from_workflow(
        workflow=workflow,
        behavior_snapshot=_snapshot(
            _endpoint("A", node_name="custom_positive", field_key="text")
        ),
    )

    assert preview == "custom prompt"


def test_positive_prompt_preview_returns_none_without_behavior_snapshot() -> None:
    """Missing prompt semantics should produce no preview."""

    assert (
        positive_prompt_preview_from_workflow(
            workflow=_workflow(["A"], {"A": _buffer("prompt")}),
            behavior_snapshot=None,
        )
        is None
    )


def test_positive_prompt_preview_returns_none_without_positive_endpoint() -> None:
    """A workflow with no semantic Positive Prompt should produce no preview."""

    preview = positive_prompt_preview_from_workflow(
        workflow=_workflow(["A"], {"A": _buffer("prompt")}),
        behavior_snapshot=_snapshot(
            _endpoint("A", role=PromptRole.NEGATIVE, node_name="negative_prompt")
        ),
    )

    assert preview is None


def test_positive_prompt_preview_returns_none_for_missing_or_malformed_shape() -> None:
    """Malformed workflow buffers should not crash or produce garbage."""

    snapshot = _snapshot(_endpoint("A"))

    cases = (
        _workflow(["A"], {}),
        _workflow(["A"], {"A": {}}),
        _workflow(["A"], {"A": {"nodes": {}}}),
        _workflow(["A"], {"A": {"nodes": {"positive_prompt": {}}}}),
        _workflow(
            ["A"],
            {"A": {"nodes": {"positive_prompt": {"inputs": []}}}},
        ),
        _workflow(
            ["A"],
            {"A": {"nodes": {"positive_prompt": {"inputs": {"prompt_template": 7}}}}},
        ),
        _workflow(["A"], {"A": _buffer("   \n\t   ")}),
    )

    for workflow in cases:
        assert (
            positive_prompt_preview_from_workflow(
                workflow=workflow,
                behavior_snapshot=snapshot,
            )
            is None
        )


def test_prompt_preview_text_normalizes_and_elides() -> None:
    """Prompt preview text should normalize whitespace and elide long text."""

    assert prompt_preview_text("  one\n two\tthree  ") == "one two three"
    assert prompt_preview_text("abcdef", limit=3) == "..."


def test_prompt_preview_text_wraps_elided_prompt_for_multiline_tooltip() -> None:
    """Long prompt previews should fit QFluent tooltips as wrapped text."""

    prompt = " ".join(f"token{index}" for index in range(40))

    preview = prompt_preview_text(prompt)

    assert preview is not None
    assert "\n" in preview
    assert preview.endswith("...")
    assert len(preview.replace("\n", "")) <= 200
