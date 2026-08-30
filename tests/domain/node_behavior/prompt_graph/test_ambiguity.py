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

"""Test fail-closed prompt graph ambiguity handling."""

from __future__ import annotations

from substitute.domain.node_behavior.prompt_graph import (
    PromptAmbiguityReason,
    PromptGraphInput,
    PromptGraphSource,
    PromptSemanticGraph,
)
from substitute.domain.node_behavior.prompt_graph_analyzer import PromptGraphAnalyzer
from tests.domain.node_behavior.prompt_graph.support import (
    conditioning_output,
    field,
    node,
)


def test_generic_conditioning_sink_does_not_establish_polarity() -> None:
    """A BasicGuider-style conditioning input should not invent prompt polarity."""

    prompt = field("encoder", "text", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=conditioning_output(),
                fields=(prompt,),
            ),
            "guider": node(
                "guider",
                inputs=(
                    PromptGraphInput(
                        "conditioning",
                        "CONDITIONING",
                        source=PromptGraphSource("encoder", 0),
                    ),
                ),
            ),
        }
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert result.detections == ()
    assert result.ambiguities == ()


def test_multiple_multiline_encoderfields_fail_closed() -> None:
    """Topology cannot choose between equally plausible multiline strings."""

    first = field("encoder", "text_a", title="Encoder")
    second = field("encoder", "text_b", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                inputs=(
                    PromptGraphInput("text_a", "STRING", field=first),
                    PromptGraphInput("text_b", "STRING", field=second),
                ),
                outputs=conditioning_output(),
                fields=(first, second),
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

    assert result.detections == ()
    assert result.ambiguities[0].reason is PromptAmbiguityReason.INDETERMINATE_FIELD


def test_conflicting_authored_name_and_sink_role_fail_closed() -> None:
    """Authored negative polarity cannot be silently changed by a positive sink."""

    prompt = field("encoder", "text", title="Negative Prompt")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                title="Negative Prompt",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=conditioning_output(),
                fields=(prompt,),
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

    assert result.detections == ()
    assert result.ambiguities


def test_analyzer_fails_closed_when_onefield_reaches_bothroles() -> None:
    """A shared conditioning source cannot be assigned either prompt polarity."""

    prompt = field("encoder", "text", title="Encoder")
    source = PromptGraphSource("encoder", 0)
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=conditioning_output(),
                fields=(prompt,),
            ),
            "sampler": node(
                "sampler",
                inputs=(
                    PromptGraphInput("positive", "CONDITIONING", source=source),
                    PromptGraphInput("negative", "CONDITIONING", source=source),
                ),
            ),
        }
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert result.detections == ()
    assert any(
        ambiguity.reason is PromptAmbiguityReason.CONFLICTING_ROLES
        for ambiguity in result.ambiguities
    )
