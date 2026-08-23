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

"""Test prompt role resolution through typed graph flow."""

from __future__ import annotations

from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.node_behavior.prompt_graph import (
    PromptFieldLocator,
    PromptEvidenceKind,
    PromptGraphInput,
    PromptGraphSource,
    PromptGraphOutput,
    PromptSemanticGraph,
    PromptSinkLocator,
)
from substitute.domain.node_behavior.prompt_graph_analyzer import PromptGraphAnalyzer
from tests.domain.node_behavior.prompt_graph.support import (
    conditioning_output,
    field,
    node,
    roles,
    string_output,
)


def test_analyzer_detects_unknown_inline_encoder_from_typed_flow() -> None:
    """Class-agnostic conditioning flow should identify an inline prompt field."""

    prompt = field("encoder", "text", title="Mystery Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                title="Mystery Encoder",
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

    assert roles(result) == {PromptFieldLocator("encoder", "text"): PromptRole.POSITIVE}
    assert result.detections[0].semantic_sinks == (
        PromptSinkLocator("sampler", "positive"),
    )
    assert result.ambiguities == ()


def test_analyzer_records_shared_model_and_text_encoder_lineage() -> None:
    """Shared loader ancestry should corroborate but not establish polarity."""

    prompt = field("encoder", "text", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "loader": node(
                "loader",
                outputs=(
                    PromptGraphOutput(0, "MODEL", "MODEL"),
                    PromptGraphOutput(1, "CLIP", "CLIP"),
                ),
            ),
            "encoder": node(
                "encoder",
                inputs=(
                    PromptGraphInput("text", "STRING", field=prompt),
                    PromptGraphInput(
                        "clip",
                        "CLIP",
                        source=PromptGraphSource("loader", 1),
                    ),
                ),
                outputs=conditioning_output(),
                fields=(prompt,),
            ),
            "sampler": node(
                "sampler",
                inputs=(
                    PromptGraphInput(
                        "model",
                        "MODEL",
                        source=PromptGraphSource("loader", 0),
                    ),
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

    evidence_kinds = {item.kind for item in result.detections[0].evidence}
    assert PromptEvidenceKind.TEXT_ENCODER_INTERFACE in evidence_kinds
    assert PromptEvidenceKind.SHARED_MODEL_LINEAGE in evidence_kinds


def test_analyzer_assigns_role_to_upstream_string_owner() -> None:
    """An upstream primitive should own the prompt card instead of its encoder."""

    prompt = field("primitive", "value", title="Prompt")
    graph = PromptSemanticGraph(
        nodes={
            "primitive": node(
                "primitive",
                title="Prompt",
                outputs=string_output(),
                fields=(prompt,),
            ),
            "encoder": node(
                "encoder",
                inputs=(
                    PromptGraphInput(
                        "text",
                        "STRING",
                        source=PromptGraphSource("primitive", 0),
                    ),
                ),
                outputs=conditioning_output(),
            ),
            "sampler": node(
                "sampler",
                inputs=(
                    PromptGraphInput(
                        "negative",
                        "CONDITIONING",
                        source=PromptGraphSource("encoder", 0),
                    ),
                ),
            ),
        }
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert roles(result) == {
        PromptFieldLocator("primitive", "value"): PromptRole.NEGATIVE
    }


def test_typed_flow_can_resolve_one_single_line_upstream_string() -> None:
    """A unique typed owner should resolve when proxy metadata loses multiline."""

    prompt = field(
        "primitive",
        "value",
        title="Text",
        label="value",
        multiline=False,
    )
    graph = PromptSemanticGraph(
        nodes={
            "primitive": node(
                "primitive",
                title="Text",
                outputs=string_output(),
                fields=(prompt,),
            ),
            "encoder": node(
                "encoder",
                inputs=(
                    PromptGraphInput(
                        "text",
                        "STRING",
                        source=PromptGraphSource("primitive", 0),
                    ),
                ),
                outputs=conditioning_output(),
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
        PromptFieldLocator("primitive", "value"): PromptRole.POSITIVE
    }


def test_analyzer_traces_conditioning_transforms_without_class_names() -> None:
    """Typed conditioning transforms should preserve downstream polarity."""

    prompt = field("encoder", "text", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": node(
                "encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=conditioning_output(),
                fields=(prompt,),
            ),
            "transform": node(
                "transform",
                inputs=(
                    PromptGraphInput(
                        "conditioning",
                        "CONDITIONING",
                        source=PromptGraphSource("encoder", 0),
                    ),
                ),
                outputs=conditioning_output(),
            ),
            "sampler": node(
                "sampler",
                inputs=(
                    PromptGraphInput(
                        "positive",
                        "CONDITIONING",
                        source=PromptGraphSource("transform", 0),
                    ),
                ),
            ),
        }
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert roles(result) == {PromptFieldLocator("encoder", "text"): PromptRole.POSITIVE}
