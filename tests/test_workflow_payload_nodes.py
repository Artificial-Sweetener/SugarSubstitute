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

"""Tests for compiled workflow payload node extraction helpers."""

from __future__ import annotations

from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)


def test_executable_prompt_nodes_returns_raw_node_map() -> None:
    """Raw compiled prompt maps should remain valid executable node payloads."""

    payload = {"1": {"class_type": "KSampler", "inputs": {}}}

    assert executable_prompt_nodes(payload) is payload


def test_executable_prompt_nodes_returns_wrapped_prompt_nodes() -> None:
    """Wrapped compiled artifacts should expose their nested executable prompt map."""

    prompt = {"1": {"class_type": "KSampler", "inputs": {}}}
    payload = {"prompt": prompt, "workflow": {"nodes": []}}

    assert executable_prompt_nodes(payload) is prompt


def test_executable_prompt_nodes_preserves_payload_for_invalid_prompt_member() -> None:
    """Invalid artifact envelopes should fall back to the original payload."""

    payload = {"prompt": "bad", "workflow": {"nodes": []}}

    assert executable_prompt_nodes(payload) is payload
