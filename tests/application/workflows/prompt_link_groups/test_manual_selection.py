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

"""Prompt-link manual-selection contracts."""

from __future__ import annotations

from substitute.domain.node_behavior import PromptRole

from tests.application.workflows.prompt_link_groups.support import (
    _cube_state,
    _link_payload,
    _prompt_node,
    _prompt_text,
    _service,
)


def test_apply_manual_selection_preserves_local_prompt_until_unlinked() -> None:
    """Manual prompt-link selection should not erase local prompt experimentation state."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state(
            {
                "nodes": {
                    "positive_prompt": _prompt_node(
                        "local",
                        from_cube=None,
                        from_node=None,
                    )
                }
            }
        ),
    }

    service.apply_manual_selection(
        cube_states=cubes,
        stack_order=["A", "B"],
        cube_alias="B",
        role=PromptRole.POSITIVE,
        from_cube="A",
    )

    linked_node = cubes["B"].buffer["nodes"]["positive_prompt"]
    assert _link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _prompt_text(linked_node) == "local"

    service.apply_manual_selection(
        cube_states=cubes,
        stack_order=["A", "B"],
        cube_alias="B",
        role=PromptRole.POSITIVE,
        from_cube=None,
    )

    assert _link_payload(linked_node) == {"from_cube": None, "from_node": None}
    assert _prompt_text(linked_node) == "local"
