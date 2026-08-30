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

"""Verify prompt-link source and option policy."""

from __future__ import annotations

from substitute.domain.links import (
    PromptEndpoint,
    PromptEndpointIndex,
    find_first_cube_with_prompt,
    valid_link_options,
)
from substitute.domain.node_behavior import PromptRole


def test_prompt_link_options_choose_first_matching_cube_and_exclude_self() -> None:
    """Offer prior compatible prompt sources while excluding the target cube."""

    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Cube1",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="prompt_template",
            ),
            PromptEndpoint(
                cube_alias="Cube3",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="prompt_template",
            ),
        )
    )
    stack_order = ["Cube1", "Cube2", "Cube3"]

    assert (
        find_first_cube_with_prompt(
            endpoint_index,
            PromptRole.POSITIVE,
            stack_order,
        )
        == "Cube1"
    )

    options = valid_link_options(
        "Cube3",
        endpoint_index,
        PromptRole.POSITIVE,
        stack_order,
    )

    assert "Cube1" in options
    assert "Cube3" not in options
