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

from collections.abc import Sequence
from typing import overload

import pytest

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection import incremental_editor
from substitute.presentation.editor.prompt_editor.projection.incremental_editor import (
    PromptProjectionIncrementalEdit,
    PromptProjectionIncrementalEditor,
)
from tests.prompt_projection_invariants import (
    validate_prompt_projection_document,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


def test_incremental_plain_text_edit_rejects_invalid_projection_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid speculative incremental documents should fall back to full rebuild."""

    previous_text = "abc"
    next_text = "aXbc"
    run = PromptProjectionRun(
        run_id="run-1",
        kind=PromptProjectionRunKind.TEXT,
        source_start=0,
        source_end=len(previous_text),
        display_text=previous_text,
        source_positions=range(0, len(previous_text) + 1),
        projection_start=0,
        projection_end=len(previous_text),
    )
    previous_document = PromptProjectionDocument(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        source_text=previous_text,
        projection_text=previous_text,
        runs=(run,),
        tokens=(),
        mapping=PromptProjectionMapping(
            runs=(run,),
            source_length=len(previous_text),
            projection_length=len(previous_text),
        ),
        caret_map=PromptProjectionCaretMap(
            stops=tuple(
                PromptProjectionCaretStop(
                    visual_index=index,
                    projection_position=index,
                    state=PromptProjectionCaretState(
                        source_position=index,
                        placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                        run_id=run.run_id,
                    ),
                )
                for index in range(len(previous_text) + 1)
            ),
            tokens=(),
            source_length=len(previous_text),
            projection_length=len(previous_text),
        ),
    )

    def fail_incremental_apply(
        *args: object, **kwargs: object
    ) -> PromptProjectionDocument:
        """Simulate a speculative document invariant failure."""

        raise ValueError("invalid source boundary count")

    monkeypatch.setattr(
        incremental_editor,
        "_apply_plain_text_document_edit",
        fail_incremental_apply,
    )
    editor = PromptProjectionIncrementalEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=1,
            end=1,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is None
    assert editor.last_rejection_reason == "invalid_incremental_projection_document"


def test_incremental_plain_text_insert_preserves_caret_navigation() -> None:
    """Plain insert remaps caret stops without changing navigation semantics."""

    previous_text = "alpha beta"
    next_text = "alpha Xbeta"
    previous_document = _plain_text_projection_document(previous_text)
    editor = PromptProjectionIncrementalEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=6,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    caret_map = result.projection_document.caret_map
    assert tuple(stop.state.source_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert tuple(stop.projection_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert (
        caret_map.next_state(
            PromptProjectionCaretState(
                source_position=6,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id="run-1",
            )
        ).source_position
        == 7
    )


def test_incremental_plain_text_delete_preserves_caret_navigation() -> None:
    """Plain delete remaps caret stops without changing navigation semantics."""

    previous_text = "alpha Xbeta"
    next_text = "alpha beta"
    previous_document = _plain_text_projection_document(previous_text)
    editor = PromptProjectionIncrementalEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=7,
            replacement_text="",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    caret_map = result.projection_document.caret_map
    assert tuple(stop.state.source_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert tuple(stop.projection_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert (
        caret_map.previous_state(
            PromptProjectionCaretState(
                source_position=7,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id="run-1",
            )
        ).source_position
        == 6
    )


def test_incremental_insert_membership_does_not_read_previous_caret_stops() -> None:
    """Caret membership after insert should use the canonical rebuilt caret map."""

    previous_text = "alpha beta gamma"
    next_text = "alpha Xbeta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(previous_text, run_id="run-1"))
    )
    previous_document = _plain_text_projection_document(
        previous_text,
        stops=base_stops,
    )
    editor = PromptProjectionIncrementalEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=6,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
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

    assert caret_map.has_projection_position(0)
    assert caret_map.has_projection_position(7)
    assert caret_map.has_projection_position(len(next_text))
    assert not caret_map.has_projection_position(len(next_text) + 1)
    assert base_stops.item_access_count == 0


def test_repeated_incremental_insert_membership_uses_canonical_caret_map() -> None:
    """Repeated inserts should not depend on the previous caret-stop sequence."""

    first_text = "alpha beta gamma"
    second_text = "alpha Xbeta gamma"
    third_text = "alpha XYbeta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(first_text, run_id="run-1"))
    )
    editor = PromptProjectionIncrementalEditor()

    first_result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=6,
            replacement_text="X",
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
            end=7,
            replacement_text="Y",
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

    assert caret_map.has_projection_position(0)
    assert caret_map.has_projection_position(8)
    assert caret_map.has_projection_position(len(third_text))
    assert not caret_map.has_projection_position(len(third_text) + 1)
    assert base_stops.item_access_count == 0


def test_repeated_incremental_insert_caret_sync_uses_canonical_caret_map() -> None:
    """Repeated insert caret sync should use canonical caret-stop positions."""

    first_text = "alpha beta gamma"
    second_text = "alpha Xbeta gamma"
    third_text = "alpha XYbeta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(first_text, run_id="run-1"))
    )
    editor = PromptProjectionIncrementalEditor()

    first_result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=6,
            replacement_text="X",
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
            end=7,
            replacement_text="Y",
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

    resolved_state = caret_map.resolve_state(PromptProjectionCaretState(8))
    assert resolved_state.source_position == 8
    assert caret_map.projection_position_for_state(resolved_state) == 8
    assert caret_map.state_for_source_position(8).source_position == 8
    assert caret_map.state_for_projection_position(8).source_position == 8
    assert base_stops.item_access_count == 0


def test_incremental_delete_membership_does_not_read_previous_caret_stops() -> None:
    """Caret membership after delete should use the canonical rebuilt caret map."""

    previous_text = "alpha Xbeta gamma"
    next_text = "alpha beta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(previous_text, run_id="run-1"))
    )
    previous_document = _plain_text_projection_document(
        previous_text,
        stops=base_stops,
    )
    editor = PromptProjectionIncrementalEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=7,
            replacement_text="",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
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

    assert caret_map.has_projection_position(0)
    assert caret_map.has_projection_position(6)
    assert caret_map.has_projection_position(len(next_text))
    assert not caret_map.has_projection_position(len(next_text) + 1)
    assert base_stops.item_access_count == 0


def test_incremental_delete_build_does_not_read_previous_caret_stops() -> None:
    """Delete construction should not read the previous caret-stop sequence."""

    previous_text = "alpha Xbeta gamma"
    next_text = "alpha beta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(previous_text, run_id="run-1"))
    )
    editor = PromptProjectionIncrementalEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=7,
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
    assert base_stops.item_access_count == 0


def test_repeated_incremental_delete_caret_sync_uses_canonical_caret_map() -> None:
    """Repeated delete caret sync should use canonical caret-stop positions."""

    first_text = "alpha XYZbeta gamma"
    second_text = "alpha XYbeta gamma"
    third_text = "alpha Xbeta gamma"
    base_stops = _CountingCaretStopSequence(
        tuple(_plain_text_caret_stops(first_text, run_id="run-1"))
    )
    editor = PromptProjectionIncrementalEditor()

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

    base_stops.reset_counts()
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
    assert base_stops.item_access_count == 0

    caret_map = second_result.projection_document.caret_map
    resolved_state = caret_map.resolve_state(PromptProjectionCaretState(7))
    assert resolved_state.source_position == 7
    assert caret_map.projection_position_for_state(resolved_state) == 7
    assert caret_map.state_for_source_position(7).source_position == 7
    assert caret_map.state_for_projection_position(7).source_position == 7
    assert base_stops.item_access_count == 0

    materialized_stops = tuple(caret_map.stops)
    assert tuple(stop.visual_index for stop in materialized_stops) == tuple(
        range(len(third_text) + 1)
    )
    assert tuple(stop.projection_position for stop in materialized_stops) == tuple(
        range(len(third_text) + 1)
    )
    assert tuple(stop.state.source_position for stop in materialized_stops) == tuple(
        range(len(third_text) + 1)
    )


def test_repeated_incremental_delete_rebuilds_canonical_caret_stops() -> None:
    """Repeated deletes should leave concrete stops for every source boundary."""

    text = "alpha ABCDEFGHIJKL beta gamma"
    editor = PromptProjectionIncrementalEditor()
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


def test_long_repeated_incremental_inserts_rebuild_canonical_caret_stops() -> None:
    """Long typing runs should leave concrete stops for every source boundary."""

    text = "alpha beta gamma"
    editor = PromptProjectionIncrementalEditor()
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
    editor = PromptProjectionIncrementalEditor()

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
    editor = PromptProjectionIncrementalEditor()

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
    editor = PromptProjectionIncrementalEditor()

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


def _plain_text_projection_document(
    text: str,
    *,
    stops: Sequence[PromptProjectionCaretStop] | None = None,
) -> PromptProjectionDocument:
    """Return a simple projected document containing one source-backed text run."""

    run = PromptProjectionRun(
        run_id="run-1",
        kind=PromptProjectionRunKind.TEXT,
        source_start=0,
        source_end=len(text),
        display_text=text,
        source_positions=range(0, len(text) + 1),
        projection_start=0,
        projection_end=len(text),
    )
    return _plain_text_projection_document_with_run(text, run=run, stops=stops)


def _plain_text_projection_document_with_run(
    text: str,
    *,
    run: PromptProjectionRun,
    stops: Sequence[PromptProjectionCaretStop] | None = None,
) -> PromptProjectionDocument:
    """Return a projected document for one supplied text run."""

    caret_stops = stops
    if caret_stops is None:
        caret_stops = tuple(_plain_text_caret_stops(text, run_id=run.run_id))
    return PromptProjectionDocument(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        source_text=text,
        projection_text=text,
        runs=(run,),
        tokens=(),
        mapping=PromptProjectionMapping(
            runs=(run,),
            source_length=len(text),
            projection_length=len(text),
        ),
        caret_map=PromptProjectionCaretMap(
            stops=caret_stops,
            tokens=(),
            source_length=len(text),
            projection_length=len(text),
        ),
    )


def _plain_text_caret_stops(
    text: str,
    *,
    run_id: str,
) -> tuple[PromptProjectionCaretStop, ...]:
    """Return plain text caret stops for each source boundary."""

    return tuple(
        PromptProjectionCaretStop(
            visual_index=index,
            projection_position=index,
            state=PromptProjectionCaretState(
                source_position=index,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id=run_id,
            ),
        )
        for index in range(len(text) + 1)
    )


class _CountingCaretStopSequence(Sequence[PromptProjectionCaretStop]):
    """Count item access while providing optimized projection membership."""

    def __init__(self, stops: tuple[PromptProjectionCaretStop, ...]) -> None:
        """Store base stops and precompute cheap membership."""

        self._stops = stops
        self._projection_positions = frozenset(
            stop.projection_position for stop in stops
        )
        self._projection_position_by_state = {
            stop.state: stop.projection_position for stop in stops
        }
        self._first_state_by_projection_position: dict[
            int,
            PromptProjectionCaretState,
        ] = {}
        self._last_state_by_projection_position: dict[
            int,
            PromptProjectionCaretState,
        ] = {}
        self._first_state_by_source_position: dict[int, PromptProjectionCaretState] = {}
        self._last_state_by_source_position: dict[int, PromptProjectionCaretState] = {}
        for stop in stops:
            self._first_state_by_projection_position.setdefault(
                stop.projection_position,
                stop.state,
            )
            self._last_state_by_projection_position[stop.projection_position] = (
                stop.state
            )
            self._first_state_by_source_position.setdefault(
                stop.state.source_position,
                stop.state,
            )
            self._last_state_by_source_position[stop.state.source_position] = stop.state
        self.item_access_count = 0

    def __len__(self) -> int:
        """Return the base stop count."""

        return len(self._stops)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionCaretStop: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionCaretStop, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionCaretStop | tuple[PromptProjectionCaretStop, ...]:
        """Return base stops while counting materializing access."""

        self.item_access_count += 1
        return self._stops[index]

    def has_projection_position(self, projection_position: int) -> bool:
        """Return membership without item access."""

        return projection_position in self._projection_positions

    def projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return a state projection boundary without item access."""

        return self._projection_position_by_state.get(state)

    def index_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return visual index for a state without item access."""

        projection_position = self.projection_position_for_state(state)
        return projection_position

    def state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return a projection-position state without item access."""

        if prefer_after:
            return self._last_state_by_projection_position.get(projection_position)
        return self._first_state_by_projection_position.get(projection_position)

    def state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return a source-position state without item access."""

        if prefer_after:
            return self._last_state_by_source_position.get(source_position)
        return self._first_state_by_source_position.get(source_position)

    def resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Resolve a caret state without item access."""

        if state in self._projection_position_by_state:
            return state
        return self.state_for_source_position(
            state.source_position,
            prefer_after=state.placement
            is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
        )

    def reset_counts(self) -> None:
        """Reset materialization counters."""

        self.item_access_count = 0
