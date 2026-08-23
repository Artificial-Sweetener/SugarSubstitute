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

"""Contract tests for speculative prompt projection incremental edits."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
)
from substitute.presentation.editor.prompt_editor.projection.plain_text_document_editor import (
    PromptPlainTextDocumentEditor,
)
from tests.support.prompt_editor.projection_invariants import (
    validate_prompt_projection_document,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.plain_edit_caret_sequence import (
    MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


from .support import (
    _CountingCaretStopSequence,
    _plain_text_caret_stops,
    _plain_text_projection_document,
)


def test_repeated_incremental_delete_rebuilds_canonical_caret_stops() -> None:
    """Repeated deletes should leave concrete stops for every source boundary."""

    text = "alpha ABCDEFGHIJKL beta gamma"
    editor = PromptPlainTextDocumentEditor()
    document = _plain_text_projection_document(text)
    cursor_position = text.index("L") + 1

    for _ in range(8):
        next_text = text[: cursor_position - 1] + text[cursor_position:]
        result = editor.try_build_plain_text_edit(
            PromptProjectionIncrementalEdit(
                start=cursor_position - 1,
                end=cursor_position,
                replacement_text="",
                previous_source_text=text,
                next_source_text=next_text,
            ),
            previous_document=document,
            document_view=PromptDocumentService().build_document_view(next_text),
            render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            session=PromptProjectionSession(),
            active_span_range=None,
            decoration_accent_ranges=(),
            scene_error_keys=frozenset(),
        )
        assert result is not None
        document = result.projection_document
        text = next_text
        cursor_position -= 1

    validate_prompt_projection_document(document)
    assert getattr(document.caret_map.stops, "lazy_depth", None) is None
    assert tuple(stop.visual_index for stop in document.caret_map.stops) == tuple(
        range(len(text) + 1)
    )
    assert tuple(
        stop.state.source_position for stop in document.caret_map.stops
    ) == tuple(range(len(text) + 1))

    previous_state = document.caret_map.previous_state(
        PromptProjectionCaretState(
            source_position=cursor_position,
            placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
            run_id="run-1",
        )
    )
    next_state = document.caret_map.next_state(previous_state)

    assert previous_state.source_position == cursor_position - 1
    assert next_state.source_position == cursor_position


def test_noncontiguous_edits_keep_caret_transform_depth_bounded() -> None:
    """Hostile cursor relocation must never create recursive caret-map growth."""

    text = "x" * 240
    editor = PromptPlainTextDocumentEditor()
    document = _plain_text_projection_document(text)
    observed_depth = 0

    for edit_index in range(80):
        position = len(text) // (3 if edit_index % 2 == 0 else 2)
        next_text = text[:position] + text[position + 1 :]
        result = editor.try_build_plain_text_edit(
            PromptProjectionIncrementalEdit(
                start=position,
                end=position + 1,
                replacement_text="",
                previous_source_text=text,
                next_source_text=next_text,
            ),
            previous_document=document,
            document_view=PromptDocumentService().build_document_view(next_text),
            render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            session=PromptProjectionSession(),
            active_span_range=None,
            decoration_accent_ranges=(),
            scene_error_keys=frozenset(),
        )
        assert result is not None, f"edit {edit_index} was rejected"
        document = result.projection_document
        text = next_text
        observed_depth = max(
            observed_depth,
            int(getattr(document.caret_map.stops, "transform_depth", 0)),
        )
        resolved = document.caret_map.resolve_state(
            PromptProjectionCaretState(position)
        )
        assert resolved.source_position == position

    validate_prompt_projection_document(document)
    assert observed_depth <= MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH


def test_caret_map_clamps_to_the_only_available_nearest_boundary() -> None:
    """A sparse transient map must resolve an edge with no opposite-side stop."""

    origin = PromptProjectionCaretState(0)
    caret_map = PromptProjectionCaretMap(
        stops=(
            PromptProjectionCaretStop(
                visual_index=0,
                projection_position=0,
                state=origin,
            ),
        ),
        tokens=(),
        source_length=4,
        projection_length=4,
    )

    assert caret_map.state_for_source_position(4) == origin
    assert caret_map.state_for_source_position(4, prefer_after=True) == origin
    assert caret_map.state_for_projection_position(4) == origin
    assert caret_map.state_for_projection_position(4, prefer_after=True) == origin


def test_long_repeated_incremental_inserts_rebuild_canonical_caret_stops() -> None:
    """Long typing runs should leave concrete stops for every source boundary."""

    text = "alpha beta gamma"
    editor = PromptPlainTextDocumentEditor()
    document = _plain_text_projection_document(text)
    cursor_position = text.index(" beta") + 1

    for index, character in enumerate("abcdefghijklmnopqrst"):
        next_text = text[:cursor_position] + character + text[cursor_position:]
        result = editor.try_build_plain_text_edit(
            PromptProjectionIncrementalEdit(
                start=cursor_position,
                end=cursor_position,
                replacement_text=character,
                previous_source_text=text,
                next_source_text=next_text,
            ),
            previous_document=document,
            document_view=PromptDocumentService().build_document_view(next_text),
            render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            session=PromptProjectionSession(),
            active_span_range=None,
            decoration_accent_ranges=(),
            scene_error_keys=frozenset(),
        )
        assert result is not None, f"insert {index} was rejected"
        document = result.projection_document
        text = next_text
        cursor_position += 1

    validate_prompt_projection_document(document)
    assert getattr(document.caret_map.stops, "lazy_depth", None) is None

    states = tuple(stop.state for stop in document.caret_map.stops)
    assert tuple(state.source_position for state in states) == tuple(
        range(len(text) + 1)
    )
    assert document.caret_map.previous_state(
        states[cursor_position]
    ).source_position == (cursor_position - 1)
    assert document.caret_map.next_state(states[cursor_position]).source_position == (
        cursor_position + 1
    )


def test_canonical_caret_stop_adjacent_lookup_does_not_read_base_stops() -> None:
    """Adjacent lookup should not depend on the previous caret-stop sequence."""

    first_text = "alpha XYZbeta gamma"
    second_text = "alpha XYbeta gamma"
    third_text = "alpha Xbeta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(first_text, run_id="run-1"))
    )
    editor = PromptPlainTextDocumentEditor()

    first_result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=8,
            end=9,
            replacement_text="",
            previous_source_text=first_text,
            next_source_text=second_text,
        ),
        previous_document=_plain_text_projection_document(
            first_text,
            stops=base_stops,
        ),
        document_view=PromptDocumentService().build_document_view(second_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )
    assert first_result is not None

    second_result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=7,
            end=8,
            replacement_text="",
            previous_source_text=second_text,
            next_source_text=third_text,
        ),
        previous_document=first_result.projection_document,
        document_view=PromptDocumentService().build_document_view(third_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )
    assert second_result is not None

    base_stops.reset_counts()
    caret_map = second_result.projection_document.caret_map
    current_state = PromptProjectionCaretState(
        source_position=7,
        placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
        run_id="run-1",
    )

    assert caret_map.previous_state(current_state).source_position == 6
    assert caret_map.next_state(current_state).source_position == 8
    assert base_stops.item_access_count == 0


def test_incremental_same_length_replacement_rebuilds_canonical_caret_stops() -> None:
    """Plain one-character replacement should rebuild canonical caret stops."""

    previous_text = "alpha beta gamma"
    next_text = "alpha zeta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(previous_text, run_id="run-1"))
    )
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=7,
            replacement_text="z",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_plain_text_projection_document(
            previous_text,
            stops=base_stops,
        ),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    assert result.projection_document.projection_text == next_text
    validate_prompt_projection_document(result.projection_document)
    assert result.projection_document.caret_map.stops is not base_stops
    assert tuple(
        stop.state.source_position
        for stop in result.projection_document.caret_map.stops
    ) == tuple(range(len(next_text) + 1))
    assert base_stops.item_access_count == 0
    assert result.projection_document.caret_map.state_for_source_position(6)
    assert result.projection_document.caret_map.state_for_projection_position(6)


def test_incremental_plain_selection_delete_remaps_caret_stops_lazily() -> None:
    """Same-run plain selection delete should avoid rebuilding the full document."""

    previous_text = "alpha removable beta gamma"
    next_text = "alpha beta gamma"
    delete_start = previous_text.index("removable ")
    delete_end = delete_start + len("removable ")
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(previous_text, run_id="run-1"))
    )
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=delete_start,
            end=delete_end,
            replacement_text="",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_plain_text_projection_document(
            previous_text,
            stops=base_stops,
        ),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    base_stops.reset_counts()
    caret_map = result.projection_document.caret_map

    assert result.projection_document.projection_text == next_text
    assert len(caret_map.stops) == len(next_text) + 1
    assert caret_map.has_projection_position(delete_start)
    assert caret_map.has_projection_position(len(next_text))
    assert caret_map.state_for_source_position(delete_start).source_position == (
        delete_start
    )
    assert base_stops.item_access_count == 0
