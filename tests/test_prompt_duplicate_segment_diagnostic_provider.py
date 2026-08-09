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

"""Contract tests for duplicate prompt-segment diagnostics."""

from __future__ import annotations

from substitute.application.prompt_editor.diagnostics.duplicate_segments import (
    PromptDuplicateSegmentDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDuplicateSegmentDiagnosticPayload,
)
from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContext,
    PromptConditioningMode,
)
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.domain.node_behavior.models import PromptRole


def test_duplicate_provider_flags_second_segment_occurrence() -> None:
    """Repeated prompt segments should flag the second occurrence only."""

    diagnostics = _diagnostics_for("yellow hat, masterpiece, yellow hat")

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.kind is PromptDiagnosticKind.DUPLICATE_SEGMENT
    assert diagnostic.source_start == 25
    assert diagnostic.source_end == 35
    assert isinstance(diagnostic.payload, PromptDuplicateSegmentDiagnosticPayload)
    assert diagnostic.payload.normalized_segment == "yellow hat"
    assert diagnostic.payload.first_source_start == 0
    assert diagnostic.payload.first_source_end == 10


def test_duplicate_provider_flags_second_and_third_occurrences() -> None:
    """Every occurrence after the first should receive its own diagnostic."""

    diagnostics = _diagnostics_for("yellow hat, yellow hat, yellow hat")

    assert [diagnostic.source_start for diagnostic in diagnostics] == [12, 24]


def test_duplicate_provider_flags_repro_prompt_duplicates() -> None:
    """The duplicate provider should flag repeated comma segments in plain prompts."""

    diagnostics = _diagnostics_for("from side, from side\n\nfrom side, from side,")

    assert [diagnostic.source_start for diagnostic in diagnostics] == [11, 22, 33]
    assert {
        diagnostic.payload.normalized_segment
        for diagnostic in diagnostics
        if isinstance(diagnostic.payload, PromptDuplicateSegmentDiagnosticPayload)
    } == {"from side"}


def test_duplicate_provider_does_not_match_subsegments() -> None:
    """Duplicate segment diagnostics should compare whole normalized segments."""

    assert _diagnostics_for("big yellow hat, yellow hat") == ()
    assert _diagnostics_for("yellow hat with ribbon, yellow hat") == ()


def test_duplicate_provider_matches_emphasized_and_plain_segments() -> None:
    """Emphasis wrappers should not change the duplicate key."""

    diagnostics = _diagnostics_for("(yellow hat:1.10), yellow hat, ((yellow hat))")

    assert [diagnostic.source_start for diagnostic in diagnostics] == [19, 31]
    assert all(
        isinstance(diagnostic.payload, PromptDuplicateSegmentDiagnosticPayload)
        and diagnostic.payload.normalized_segment == "yellow hat"
        for diagnostic in diagnostics
    )


def test_duplicate_provider_normalizes_underscores_case_and_whitespace() -> None:
    """Equivalent segment spelling styles should share one duplicate key."""

    diagnostics = _diagnostics_for("YELLOW   HAT, yellow_hat")

    assert len(diagnostics) == 1
    assert diagnostics[0].source_start == 14


def test_duplicate_provider_matches_weighted_duplicate_segment() -> None:
    """A weighted later segment should compare by its unwrapped content."""

    diagnostics = _diagnostics_for("yellow hat, (yellow_hat:1.20)")

    assert len(diagnostics) == 1
    assert diagnostics[0].source_start == 12


def test_duplicate_provider_skips_loras_and_wildcards() -> None:
    """Syntax segments should not be treated as duplicate prompt segments."""

    diagnostics = _diagnostics_for(
        "<lora:yellow_hat:1.0>, <lora:yellow_hat:1.0>, {yellow hat}, {yellow hat}"
    )

    assert diagnostics == ()


def test_duplicate_provider_skips_machine_text_segments() -> None:
    """Machine-looking segments should not be treated as prompt duplicates."""

    assert _diagnostics_for("https://example.test/a, https://example.test/a") == ()
    assert _diagnostics_for("models/yellow_hat, models/yellow_hat") == ()
    assert _diagnostics_for("yellow_hat.safetensors, yellow_hat.safetensors") == ()
    assert _diagnostics_for("abcdef123456, abcdef123456") == ()


def test_duplicate_provider_does_not_compare_independent_scenes() -> None:
    """The same segment in different scene-local blocks should not be duplicate."""

    diagnostics = _diagnostics_for("**portrait\nfrom side\n**cafe\nfrom side")

    assert diagnostics == ()


def test_duplicate_provider_compares_universal_text_inside_each_scene() -> None:
    """Universal prompt segments should be part of each scene-effective scope."""

    diagnostics = _diagnostics_for(
        "from side\n**portrait\nfrom side\n**cafe\nfrom side"
    )

    assert [diagnostic.source_start for diagnostic in diagnostics] == [21, 38]
    assert all(
        isinstance(diagnostic.payload, PromptDuplicateSegmentDiagnosticPayload)
        and diagnostic.payload.first_source_start == 0
        for diagnostic in diagnostics
    )


def test_duplicate_provider_flags_duplicates_within_one_scene_only() -> None:
    """Scene-local duplicates should not leak into later scenes."""

    diagnostics = _diagnostics_for(
        "**portrait\nfrom side, from side\n**cafe\nfrom side"
    )

    assert [diagnostic.source_start for diagnostic in diagnostics] == [22]


def test_detailer_sep_partitions_reset_duplicate_detection() -> None:
    """Independent conditioning batches should not compare across separators."""

    diagnostics = _diagnostics_for(
        "1girl, red hair\n[SEP]\n1girl, red hair",
        mode=PromptConditioningMode.INDEPENDENT,
    )

    assert diagnostics == ()


def test_detailer_duplicates_remain_visible_within_one_sep_partition() -> None:
    """A duplicate inside one independent condition should still be reported."""

    diagnostics = _diagnostics_for(
        "1girl, red hair, red hair\n[SEP]\n1girl, red hair",
        mode=PromptConditioningMode.INDEPENDENT,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].source_start == 17


def test_regional_global_segments_are_compared_with_each_region() -> None:
    """Each regional condition should inherit duplicate state from global source."""

    diagnostics = _diagnostics_for(
        "2girls, red hair\n[SEP]\n1girl, red hair\n[SEP]\n1girl, blue hair",
        mode=PromptConditioningMode.REGIONAL,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].source_start == 30
    assert isinstance(diagnostics[0].payload, PromptDuplicateSegmentDiagnosticPayload)
    assert diagnostics[0].payload.first_source_start == 8


def test_regional_sibling_regions_do_not_share_duplicate_state() -> None:
    """Repeated text in separate regional conditions should not be a duplicate."""

    diagnostics = _diagnostics_for(
        "2girls, twins\n[SEP]\n1girl, red hair\n[SEP]\n1girl, red hair",
        mode=PromptConditioningMode.REGIONAL,
    )

    assert diagnostics == ()


def test_regional_duplicate_within_one_region_remains_visible() -> None:
    """A region should compare its own segments after inheriting global state."""

    diagnostics = _diagnostics_for(
        "2girls, twins\n[SEP]\n1girl, red hair, red hair\n[SEP]\n1girl, blue hair",
        mode=PromptConditioningMode.REGIONAL,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].source_start == 37


def _diagnostics_for(
    text: str,
    *,
    mode: PromptConditioningMode = PromptConditioningMode.INDEPENDENT,
) -> tuple[PromptDiagnostic, ...]:
    """Return duplicate segment diagnostics for one prompt source string."""

    provider = PromptDuplicateSegmentDiagnosticProvider(
        conditioning_context=PromptConditioningContext(
            mode=mode,
            endpoint=PromptEndpoint(
                cube_alias="cube",
                role=PromptRole.POSITIVE,
                node_name="prompt",
                field_key="value",
            ),
        )
    )
    return provider.diagnostics_for_text(text).diagnostics
