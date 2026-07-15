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

"""Tests for prompt wildcard seed selection policy."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.prompt_wildcards import PromptWildcardSeedPolicy


def _cube(*, controls: list[dict[str, object]], nodes: dict[str, object]) -> object:
    """Build one lightweight cube state for seed policy tests."""

    return SimpleNamespace(
        original_cube={"surface": {"controls": controls}},
        buffer={"nodes": nodes},
    )


def test_prompt_cube_first_seed_is_used() -> None:
    """The prompt cube's first authored seed control should win."""

    workflow = SimpleNamespace(
        stack_order=["Prompt", "Other"],
        cubes={
            "Prompt": _cube(
                controls=[
                    {
                        "control_id": "sampler.seed",
                        "symbol": "sampler",
                        "input_name": "seed",
                    }
                ],
                nodes={"sampler": {"inputs": {"seed": 123}}},
            ),
            "Other": _cube(
                controls=[
                    {
                        "control_id": "other.seed",
                        "symbol": "other",
                        "input_name": "seed",
                    }
                ],
                nodes={"other": {"inputs": {"seed": 456}}},
            ),
        },
    )

    selection = PromptWildcardSeedPolicy().select_seed(
        workflow=workflow,
        prompt_cube_alias="Prompt",
        workflow_id="wf",
        prompt_node_name="positive_prompt",
        prompt_field_key="prompt_template",
    )

    assert selection.seed == 123
    assert selection.cube_alias == "Prompt"
    assert selection.control_id == "sampler.seed"


def test_workflow_first_seed_is_used_when_prompt_cube_has_no_seed() -> None:
    """Workflow stack order should provide the fallback seed."""

    workflow = SimpleNamespace(
        stack_order=["First", "Prompt"],
        cubes={
            "First": _cube(
                controls=[
                    {
                        "control_id": "first.seed",
                        "symbol": "sampler",
                        "input_name": "seed",
                    }
                ],
                nodes={"sampler": {"inputs": {"seed": 111}}},
            ),
            "Prompt": _cube(controls=[], nodes={}),
        },
    )

    selection = PromptWildcardSeedPolicy().select_seed(
        workflow=workflow,
        prompt_cube_alias="Prompt",
        workflow_id="wf",
        prompt_node_name="positive_prompt",
        prompt_field_key="prompt_template",
    )

    assert selection.seed == 111
    assert selection.cube_alias == "First"


def test_non_integer_seed_is_ignored() -> None:
    """Boolean and non-integer seed values should not be selected."""

    workflow = SimpleNamespace(
        stack_order=["Prompt"],
        cubes={
            "Prompt": _cube(
                controls=[
                    {
                        "control_id": "bad.seed",
                        "symbol": "bad",
                        "input_name": "seed",
                    }
                ],
                nodes={"bad": {"inputs": {"seed": True}}},
            )
        },
    )

    selection = PromptWildcardSeedPolicy().select_seed(
        workflow=workflow,
        prompt_cube_alias="Prompt",
        workflow_id="wf",
        prompt_node_name="positive_prompt",
        prompt_field_key="prompt_template",
    )

    assert selection.seed is None
