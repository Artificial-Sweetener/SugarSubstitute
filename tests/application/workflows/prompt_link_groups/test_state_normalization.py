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

"""Prompt-link state-normalization contracts."""

from __future__ import annotations

from tests.application.workflows.prompt_link_groups.support import (
    _cube_state,
    _link_payload,
    _prompt_node,
    _service,
)


def test_sanitize_current_state_collapses_multi_hop_and_clears_invalid_links() -> None:
    """Normalization should rewrite multi-hop links to the anchor and clear illegal links."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("beta", from_cube="A")}},
        ),
        "C": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("gamma", from_cube="B")}},
        ),
        "D": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("delta", from_cube="Z")}},
        ),
    }

    service.sanitize_current_state(cubes, ["A", "B", "C", "D"])

    assert _link_payload(cubes["B"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _link_payload(cubes["C"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _link_payload(cubes["D"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": None,
        "from_node": None,
    }


def test_sanitize_current_state_migrates_legacy_prompt_link_metadata() -> None:
    """Legacy prompt-link payloads should become canonical node-link payloads."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state(
            {
                "nodes": {
                    "positive_prompt": _prompt_node(
                        "local",
                        from_cube="A",
                        legacy=True,
                    )
                }
            }
        ),
    }

    service.sanitize_current_state(cubes, ["A", "B"])

    linked_node = cubes["B"].buffer["nodes"]["positive_prompt"]
    assert "prompt_link" not in linked_node
    assert _link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
