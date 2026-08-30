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

"""Test authored prompt-role fallback resolution."""

from __future__ import annotations

from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.node_behavior.prompt_graph import (
    PromptFieldLocator,
    PromptGraphInput,
    PromptGraphSource,
    PromptSemanticGraph,
)
from substitute.domain.node_behavior.prompt_graph_analyzer import PromptGraphAnalyzer
from tests.domain.node_behavior.prompt_graph.support import (
    conditioning_output,
    field,
    node,
    roles,
)


def test_authored_role_selects_one_of_multiple_multilinefields() -> None:
    """Authored polarity should dispel otherwise indistinguishable fields."""

    positive = field(
        "encoder",
        "positive_prompt",
        title="Encoder",
        label="Positive Prompt",
    )
    style = field("encoder", "style_notes", title="Encoder", label="Style Notes")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                inputs=(
                    PromptGraphInput("positive_prompt", "STRING", field=positive),
                    PromptGraphInput("style_notes", "STRING", field=style),
                ),
                outputs=conditioning_output(),
                fields=(positive, style),
            ),
            "sampler": node(
                "sampler",
                inputs=(
                    PromptGraphInput(
                        "positive",
                        "CONDITIONING",
                        source=PromptGraphSource("encoder", 0),
                    ),
                ),
            ),
        }
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert roles(result) == {
        PromptFieldLocator("encoder", "positive_prompt"): PromptRole.POSITIVE
    }


def test_multiline_prompt_candidate_without_polarity_remains_standard() -> None:
    """Multiline and prompt naming alone must not invent a positive role."""

    prompt = field("note", "prompt", title="Prompt", label="Prompt")
    graph = PromptSemanticGraph(
        nodes={"note": node("note", title="Prompt", fields=(prompt,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert result.detections == ()
    assert result.ambiguities == ()


def test_authored_polarity_and_multiline_can_resolve_without_topology() -> None:
    """A clearly authored prompt field should retain existing title inference."""

    prompt = field("node", "text", title="Positive Prompt")
    graph = PromptSemanticGraph(
        nodes={"node": node("node", title="Positive Prompt", fields=(prompt,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert roles(result) == {PromptFieldLocator("node", "text"): PromptRole.POSITIVE}


def test_authored_positive_name_can_resolve_without_prompt_word() -> None:
    """A concise authored polarity name should suffice with multiline text."""

    prompt = field("node", "text", title="Positive")
    graph = PromptSemanticGraph(
        nodes={"node": node("node", title="Positive", fields=(prompt,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert roles(result) == {PromptFieldLocator("node", "text"): PromptRole.POSITIVE}


def test_unconnected_multiline_filename_is_not_a_prompt() -> None:
    """Ordinary multiline strings must remain standard fields."""

    filename = field("save", "filename", title="Save Metadata")
    graph = PromptSemanticGraph(
        nodes={"save": node("save", title="Save Metadata", fields=(filename,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert result.detections == ()
    assert result.ambiguities == ()
