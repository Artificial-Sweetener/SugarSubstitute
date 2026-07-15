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

from __future__ import annotations

from typing import Callable, cast

from substitute.domain.links import (
    PromptEndpoint,
    PromptEndpointIndex,
    find_first_cube_with_prompt,
    valid_link_options,
)
from substitute.domain.node_behavior import PromptRole
from substitute.domain.recipes.sugar_links import prompt_field_reference

_find_first_cube_with_prompt = cast(
    Callable[[PromptEndpointIndex, PromptRole, list[str]], str | None],
    find_first_cube_with_prompt,
)
_valid_link_options = cast(
    Callable[[str, PromptEndpointIndex, PromptRole, list[str]], list[str]],
    valid_link_options,
)


def _index_from_buffers(
    all_buffers: dict[str, object],
    *,
    node_name: str = "positive_prompt",
    field_key: str = "prompt_template",
) -> PromptEndpointIndex:
    """Build a prompt endpoint index for deterministic prompt-link helper tests."""

    endpoints: list[PromptEndpoint] = []
    for cube_alias, cube in all_buffers.items():
        nodes = cube.get("nodes", {}) if isinstance(cube, dict) else {}
        if isinstance(nodes, dict) and node_name in nodes:
            endpoints.append(
                PromptEndpoint(
                    cube_alias=cube_alias,
                    role=PromptRole.POSITIVE,
                    node_name=node_name,
                    field_key=field_key,
                )
            )
    return PromptEndpointIndex.from_endpoints(endpoints)


def test_prompt_first_cube_and_options_follow_stack_order() -> None:
    all_buffers = {
        "A": {"nodes": {"positive_prompt": {"inputs": {}}}},
        "B": {"nodes": {}},
        "C": {"nodes": {"positive_prompt": {"inputs": {}}}},
    }
    endpoint_index = _index_from_buffers(all_buffers)

    # Order: A, B, C -> first is A
    order1 = ["A", "B", "C"]
    assert (
        _find_first_cube_with_prompt(endpoint_index, PromptRole.POSITIVE, order1) == "A"
    )
    # Options for C should include only A (before C)
    opts_c = _valid_link_options("C", endpoint_index, PromptRole.POSITIVE, order1)
    assert opts_c == ["A"]

    # Reordered stack: C, B, A -> first is C
    order2 = ["C", "B", "A"]
    assert (
        _find_first_cube_with_prompt(endpoint_index, PromptRole.POSITIVE, order2) == "C"
    )
    # Options for A should include only C (before A)
    opts_a = _valid_link_options("A", endpoint_index, PromptRole.POSITIVE, order2)
    assert opts_a == ["C"]


def test_prompt_link_options_follow_endpoint_identity_not_node_names() -> None:
    """Prompt-link helper ordering should work for arbitrary endpoint fields."""

    all_buffers = {
        "A": {"nodes": {"custom_positive": {"inputs": {"text": ""}}}},
        "B": {"nodes": {"custom_positive": {"inputs": {"text": ""}}}},
    }
    endpoint_index = _index_from_buffers(
        all_buffers,
        node_name="custom_positive",
        field_key="text",
    )

    assert (
        _find_first_cube_with_prompt(
            endpoint_index,
            PromptRole.POSITIVE,
            ["A", "B"],
        )
        == "A"
    )
    assert _valid_link_options(
        "B",
        endpoint_index,
        PromptRole.POSITIVE,
        ["A", "B"],
    ) == ["A"]


def test_prompt_link_reference_quotes_non_identifier_aliases() -> None:
    assert (
        prompt_field_reference(
            "Cube A",
            "positive_prompt",
            "prompt_template",
        )
        == '"Cube A".positive_prompt.prompt_template'
    )
