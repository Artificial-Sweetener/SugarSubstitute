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

"""Resolve executable Comfy prompt nodes from compiled workflow payloads."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.common import JsonValue


def executable_prompt_nodes(
    workflow_payload: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    """Return executable Comfy prompt nodes from supported compiled payload shapes.

    Compilers may return either a legacy raw node map or an artifact envelope with a
    `prompt` node map and optional `workflow` UI metadata. Graph analysis and node
    inspection must use the executable `prompt` map when it is present.
    """

    prompt = workflow_payload.get("prompt")
    if isinstance(prompt, Mapping):
        return prompt
    return workflow_payload


__all__ = ["executable_prompt_nodes"]
