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

"""Verify conservative graph-semantic prompt-role analysis."""

from __future__ import annotations

from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.node_behavior.prompt_graph import (
    PromptAmbiguityReason,
    PromptFieldLocator,
    PromptEvidenceKind,
    PromptGraphField,
    PromptGraphInput,
    PromptGraphNode,
    PromptGraphOutput,
    PromptGraphSource,
    PromptSemanticGraph,
    PromptSinkLocator,
)
from substitute.domain.node_behavior.prompt_graph_analyzer import PromptGraphAnalyzer


def _field(
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


def _node(
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


def _conditioning_output() -> tuple[PromptGraphOutput, ...]:
    """Return one conventional conditioning output."""

    return (PromptGraphOutput(0, "CONDITIONING", "CONDITIONING"),)


def _string_output() -> tuple[PromptGraphOutput, ...]:
    """Return one conventional string output."""

    return (PromptGraphOutput(0, "STRING", "STRING"),)


def _roles(result: object) -> dict[PromptFieldLocator, PromptRole]:
    """Return locator-to-role assertions from an analyzer result."""

    detections = getattr(result, "detections")
    return {detection.locator: detection.role for detection in detections}


def test_analyzer_detects_unknown_inline_encoder_from_typed_flow() -> None:
    """Class-agnostic conditioning flow should identify an inline prompt field."""

    prompt = _field("encoder", "text", title="Mystery Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                title="Mystery Encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=_conditioning_output(),
                fields=(prompt,),
            ),
            "sampler": _node(
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

    assert _roles(result) == {
        PromptFieldLocator("encoder", "text"): PromptRole.POSITIVE
    }
    assert result.detections[0].semantic_sinks == (
        PromptSinkLocator("sampler", "positive"),
    )
    assert result.ambiguities == ()


def test_analyzer_records_shared_model_and_text_encoder_lineage() -> None:
    """Shared loader ancestry should corroborate but not establish polarity."""

    prompt = _field("encoder", "text", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "loader": _node(
                "loader",
                outputs=(
                    PromptGraphOutput(0, "MODEL", "MODEL"),
                    PromptGraphOutput(1, "CLIP", "CLIP"),
                ),
            ),
            "encoder": _node(
                "encoder",
                inputs=(
                    PromptGraphInput("text", "STRING", field=prompt),
                    PromptGraphInput(
                        "clip",
                        "CLIP",
                        source=PromptGraphSource("loader", 1),
                    ),
                ),
                outputs=_conditioning_output(),
                fields=(prompt,),
            ),
            "sampler": _node(
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

    prompt = _field("primitive", "value", title="Prompt")
    graph = PromptSemanticGraph(
        nodes={
            "primitive": _node(
                "primitive",
                title="Prompt",
                outputs=_string_output(),
                fields=(prompt,),
            ),
            "encoder": _node(
                "encoder",
                inputs=(
                    PromptGraphInput(
                        "text",
                        "STRING",
                        source=PromptGraphSource("primitive", 0),
                    ),
                ),
                outputs=_conditioning_output(),
            ),
            "sampler": _node(
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

    assert _roles(result) == {
        PromptFieldLocator("primitive", "value"): PromptRole.NEGATIVE
    }


def test_typed_flow_can_resolve_one_single_line_upstream_string() -> None:
    """A unique typed owner should resolve when proxy metadata loses multiline."""

    prompt = _field(
        "primitive",
        "value",
        title="Text",
        label="value",
        multiline=False,
    )
    graph = PromptSemanticGraph(
        nodes={
            "primitive": _node(
                "primitive",
                title="Text",
                outputs=_string_output(),
                fields=(prompt,),
            ),
            "encoder": _node(
                "encoder",
                inputs=(
                    PromptGraphInput(
                        "text",
                        "STRING",
                        source=PromptGraphSource("primitive", 0),
                    ),
                ),
                outputs=_conditioning_output(),
            ),
            "sampler": _node(
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

    assert _roles(result) == {
        PromptFieldLocator("primitive", "value"): PromptRole.POSITIVE
    }


def test_analyzer_traces_conditioning_transforms_without_class_names() -> None:
    """Typed conditioning transforms should preserve downstream polarity."""

    prompt = _field("encoder", "text", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=_conditioning_output(),
                fields=(prompt,),
            ),
            "transform": _node(
                "transform",
                inputs=(
                    PromptGraphInput(
                        "conditioning",
                        "CONDITIONING",
                        source=PromptGraphSource("encoder", 0),
                    ),
                ),
                outputs=_conditioning_output(),
            ),
            "sampler": _node(
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

    assert _roles(result) == {
        PromptFieldLocator("encoder", "text"): PromptRole.POSITIVE
    }


def test_generic_conditioning_sink_does_not_establish_polarity() -> None:
    """A BasicGuider-style conditioning input should not invent prompt polarity."""

    prompt = _field("encoder", "text", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=_conditioning_output(),
                fields=(prompt,),
            ),
            "guider": _node(
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


def test_multiple_multiline_encoder_fields_fail_closed() -> None:
    """Topology cannot choose between equally plausible multiline strings."""

    first = _field("encoder", "text_a", title="Encoder")
    second = _field("encoder", "text_b", title="Encoder")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                inputs=(
                    PromptGraphInput("text_a", "STRING", field=first),
                    PromptGraphInput("text_b", "STRING", field=second),
                ),
                outputs=_conditioning_output(),
                fields=(first, second),
            ),
            "sampler": _node(
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

    prompt = _field("encoder", "text", title="Negative Prompt")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                title="Negative Prompt",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=_conditioning_output(),
                fields=(prompt,),
            ),
            "sampler": _node(
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


def test_analyzer_fails_closed_when_one_field_reaches_both_roles() -> None:
    """A shared conditioning source cannot be assigned either prompt polarity."""

    prompt = _field("encoder", "text", title="Encoder")
    source = PromptGraphSource("encoder", 0)
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                inputs=(PromptGraphInput("text", "STRING", field=prompt),),
                outputs=_conditioning_output(),
                fields=(prompt,),
            ),
            "sampler": _node(
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


def test_authored_role_selects_one_of_multiple_multiline_fields() -> None:
    """Authored polarity should dispel otherwise indistinguishable fields."""

    positive = _field(
        "encoder",
        "positive_prompt",
        title="Encoder",
        label="Positive Prompt",
    )
    style = _field("encoder", "style_notes", title="Encoder", label="Style Notes")
    graph = PromptSemanticGraph(
        nodes={
            "encoder": _node(
                "encoder",
                inputs=(
                    PromptGraphInput("positive_prompt", "STRING", field=positive),
                    PromptGraphInput("style_notes", "STRING", field=style),
                ),
                outputs=_conditioning_output(),
                fields=(positive, style),
            ),
            "sampler": _node(
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

    assert _roles(result) == {
        PromptFieldLocator("encoder", "positive_prompt"): PromptRole.POSITIVE
    }


def test_multiline_prompt_candidate_without_polarity_remains_standard() -> None:
    """Multiline and prompt naming alone must not invent a positive role."""

    prompt = _field("note", "prompt", title="Prompt", label="Prompt")
    graph = PromptSemanticGraph(
        nodes={"note": _node("note", title="Prompt", fields=(prompt,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert result.detections == ()
    assert result.ambiguities == ()


def test_authored_polarity_and_multiline_can_resolve_without_topology() -> None:
    """A clearly authored prompt field should retain existing title inference."""

    prompt = _field("node", "text", title="Positive Prompt")
    graph = PromptSemanticGraph(
        nodes={"node": _node("node", title="Positive Prompt", fields=(prompt,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert _roles(result) == {PromptFieldLocator("node", "text"): PromptRole.POSITIVE}


def test_authored_positive_name_can_resolve_without_prompt_word() -> None:
    """A concise authored polarity name should suffice with multiline text."""

    prompt = _field("node", "text", title="Positive")
    graph = PromptSemanticGraph(
        nodes={"node": _node("node", title="Positive", fields=(prompt,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert _roles(result) == {PromptFieldLocator("node", "text"): PromptRole.POSITIVE}


def test_unconnected_multiline_filename_is_not_a_prompt() -> None:
    """Ordinary multiline strings must remain standard fields."""

    filename = _field("save", "filename", title="Save Metadata")
    graph = PromptSemanticGraph(
        nodes={"save": _node("save", title="Save Metadata", fields=(filename,))}
    )

    result = PromptGraphAnalyzer().analyze(graph)

    assert result.detections == ()
    assert result.ambiguities == ()
