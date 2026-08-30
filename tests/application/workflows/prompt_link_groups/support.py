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

"""Prompt-link group workflow test support."""

from __future__ import annotations


from types import SimpleNamespace
from typing import Mapping, cast

from substitute.application.workflows import PromptLinkGroupService
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole


class _PromptEndpointProvider:
    """Build prompt endpoints for the minimal buffers used by service tests."""

    _endpoint_specs = {
        "positive_prompt": ("prompt_template", PromptRole.POSITIVE),
        "negative_prompt": ("prompt_template", PromptRole.NEGATIVE),
        "custom_positive": ("text", PromptRole.POSITIVE),
    }

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return endpoints for known prompt nodes in stack order."""

        endpoints: list[PromptEndpoint] = []
        for cube_alias in stack_order:
            cube_state = cube_states.get(cube_alias)
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            if not isinstance(nodes, Mapping):
                continue
            for node_name, (field_key, role) in self._endpoint_specs.items():
                if node_name in nodes:
                    endpoints.append(
                        PromptEndpoint(
                            cube_alias=cube_alias,
                            role=role,
                            node_name=node_name,
                            field_key=field_key,
                        )
                    )
        return PromptEndpointIndex.from_endpoints(endpoints)


def _cube_state(buffer: dict[str, object]) -> SimpleNamespace:
    """Build a minimal cube-state test double exposing a mutable buffer."""

    return SimpleNamespace(buffer=buffer)


def _service() -> PromptLinkGroupService:
    """Return the prompt-link service with a deterministic endpoint provider."""

    return PromptLinkGroupService(_PromptEndpointProvider())


def _prompt_node(
    prompt_template: str,
    *,
    from_cube: str | None | object = ...,
    from_node: str | None = "positive_prompt",
    field_key: str = "prompt_template",
    legacy: bool = False,
) -> dict[str, object]:
    """Build one prompt node payload with optional node-link metadata."""

    node: dict[str, object] = {"inputs": {field_key: prompt_template}}
    if from_cube is not ...:
        if legacy:
            node["prompt_link"] = {"from_cube": from_cube}
        else:
            node["node_link"] = {"from_cube": from_cube, "from_node": from_node}
    return node


def _link_payload(node: dict[str, object]) -> dict[str, object]:
    """Return the canonical node-link payload for one prompt node."""

    return cast(dict[str, object], node["node_link"])


def _prompt_text(node: dict[str, object], field_key: str = "prompt_template") -> str:
    """Return the local prompt text stored on one prompt node."""

    inputs = cast(dict[str, object], node["inputs"])
    return cast(str, inputs[field_key])
