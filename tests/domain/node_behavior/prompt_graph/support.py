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

"""Build typed prompt graph analyzer scenarios."""

from __future__ import annotations

from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.node_behavior.prompt_graph import (
    PromptFieldLocator,
    PromptGraphField,
    PromptGraphInput,
    PromptGraphNode,
    PromptGraphOutput,
)


def field(
    node_name: str,
    field_key: str,
    *,
    title: str,
    label: str | None = None,
    multiline: bool = True,
) -> PromptGraphField:
    """Return one editable string candidate for analyzer fixtures."""

    return PromptGraphField(
        locator=PromptFieldLocator(node_name, field_key),
        node_title=title,
        label=label or field_key,
        multiline=multiline,
    )


def node(
    name: str,
    *,
    title: str | None = None,
    inputs: tuple[PromptGraphInput, ...] = (),
    outputs: tuple[PromptGraphOutput, ...] = (),
    fields: tuple[PromptGraphField, ...] = (),
) -> PromptGraphNode:
    """Return one typed semantic node for analyzer fixtures."""

    return PromptGraphNode(
        name=name,
        title=title or name,
        inputs=inputs,
        outputs=outputs,
        fields=fields,
    )


def conditioning_output() -> tuple[PromptGraphOutput, ...]:
    """Return one conventional conditioning output."""

    return (PromptGraphOutput(0, "CONDITIONING", "CONDITIONING"),)


def string_output() -> tuple[PromptGraphOutput, ...]:
    """Return one conventional string output."""

    return (PromptGraphOutput(0, "STRING", "STRING"),)


def roles(result: object) -> dict[PromptFieldLocator, PromptRole]:
    """Return locator-to-role assertions from an analyzer result."""

    detections = getattr(result, "detections")
    return {detection.locator: detection.role for detection in detections}
