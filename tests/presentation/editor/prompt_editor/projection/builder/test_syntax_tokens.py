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

"""Contracts for prompt projection syntax tokens and caret maps."""

from __future__ import annotations


from substitute.application.ports import PromptWildcardResolution
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.projection.caret_stop_sequence import (
    PromptProjectionCaretStopSequence,
)

from .support import _build_projection


def test_projection_builder_emits_projected_runs_for_emphasis_and_wildcard_tokens() -> (
    None
):
    """Projected mode should emit visible text runs plus inline-object runs."""

    projection = _build_projection(
        "(cat:1.05), {animal}",
        wildcard_resolutions={
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        },
    )

    assert projection.projection_text.count(OBJECT_REPLACEMENT_CHARACTER) == 3
    assert [token.kind for token in projection.tokens] == [
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.WILDCARD,
    ]
    assert [run.kind for run in projection.runs] == [
        PromptProjectionRunKind.INLINE_OBJECT,
        PromptProjectionRunKind.TEXT,
        PromptProjectionRunKind.INLINE_OBJECT,
        PromptProjectionRunKind.TEXT,
        PromptProjectionRunKind.INLINE_OBJECT,
    ]
    assert projection.runs[0].renderer_key == "emphasis_prefix"
    assert projection.runs[1].display_text == "cat"
    assert projection.runs[1].token_id == projection.tokens[0].token_id
    assert projection.runs[2].display_text == "1.05"
    assert projection.runs[2].renderer_key == "emphasis_suffix"
    assert projection.runs[4].display_text == "animal"
    assert projection.runs[4].renderer_key == "wildcard_chip"
    assert projection.tokens[0].display_text == "cat"
    assert projection.tokens[0].value_text == "1.05"
    assert projection.tokens[0].content_range == (1, 4)
    assert (
        projection.tokens[0].navigation_mode
        is PromptProjectionTokenNavigationMode.TEXT_CONTENT
    )
    assert projection.tokens[1].display_text == "animal"
    assert projection.tokens[1].status_text is None
    assert projection.tokens[1].wildcard_display_tag is None
    assert projection.tokens[1].wildcard_can_step_tag is False
    assert (
        projection.tokens[1].navigation_mode
        is PromptProjectionTokenNavigationMode.ATOMIC
    )


def test_projection_builder_projects_wildcard_group_tags_without_status_badges() -> (
    None
):
    """Projected wildcards should carry inline tag metadata without txt/csv labels."""

    projection = _build_projection("{animal}, {animal|2}, {animal|one}")

    wildcard_tokens = [
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.WILDCARD
    ]

    assert [
        (
            token.display_text,
            token.status_text,
            token.wildcard_display_tag,
            token.wildcard_tag_is_explicit,
            token.wildcard_can_step_tag,
        )
        for token in wildcard_tokens
    ] == [
        ("animal", None, "1", False, True),
        ("animal", None, "2", True, True),
        ("animal", None, "one", True, False),
    ]


def test_projection_builder_raw_mode_keeps_visible_runs_as_plain_source_text() -> None:
    """Raw mode should emit only text runs and preserve the source text verbatim."""

    projection = _build_projection(
        "(cat:1.05), {animal}",
        display_mode=PromptProjectionDisplayMode.RAW,
    )

    assert projection.display_mode is PromptProjectionDisplayMode.RAW
    assert projection.projection_text == "(cat:1.05), {animal}"
    assert len(projection.runs) == 1
    assert projection.runs[0].kind is PromptProjectionRunKind.TEXT
    assert projection.runs[0].display_text == "(cat:1.05), {animal}"


def test_projection_builder_plain_text_caret_map_exposes_all_source_boundaries() -> (
    None
):
    """Token-free single-run projections should keep exact plain caret stops."""

    projection = _build_projection("alpha beta")
    stops = projection.caret_map.stops

    assert projection.tokens == ()
    assert [stop.visual_index for stop in stops] == list(range(len(stops)))
    assert [stop.projection_position for stop in stops] == list(range(11))
    assert [stop.state.source_position for stop in stops] == list(range(11))
    assert {stop.state.placement for stop in stops} == {
        PromptProjectionCaretPlacement.PLAIN_TEXT
    }
    assert {stop.state.run_id for stop in stops} == {projection.runs[0].run_id}


def test_projection_builder_keeps_long_caret_maps_run_bounded() -> None:
    """Long decorated documents should not allocate one stored object per boundary."""

    projection = _build_projection("(alpha:1.10), beta, " * 120)
    stops = projection.caret_map.stops

    assert isinstance(stops, PromptProjectionCaretStopSequence)
    assert len(stops) > 1_000
    assert stops.span_count <= (len(projection.runs) * 3) + 1
    assert tuple(stop.visual_index for stop in stops[:4]) == (0, 1, 2, 3)
    assert stops[-1].visual_index == len(stops) - 1


def test_projection_builder_caret_map_builds_position_indexes_lazily() -> None:
    """Caret-map position dictionaries should be built only after lookup demand."""

    projection = _build_projection("alpha (cat:1.05) beta")
    caret_map = projection.caret_map

    assert caret_map._states_by_source_position is None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    assert caret_map.state_for_source_position(0).source_position == 0
    assert caret_map._states_by_source_position is None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    assert caret_map.state_for_projection_position(0).source_position == 0
    assert caret_map._states_by_source_position is None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    caret_map._source_position_states()  # noqa: SLF001
    assert caret_map._states_by_source_position is not None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    caret_map._projection_position_states()  # noqa: SLF001
    assert caret_map._states_by_projection_position is not None  # noqa: SLF001
