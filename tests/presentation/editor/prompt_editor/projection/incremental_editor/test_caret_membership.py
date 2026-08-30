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
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


from .support import (
    _CountingCaretStopSequence,
    _plain_text_caret_stops,
    _plain_text_projection_document,
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
    editor = PromptPlainTextDocumentEditor()

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
    editor = PromptPlainTextDocumentEditor()

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
    editor = PromptPlainTextDocumentEditor()

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
    editor = PromptPlainTextDocumentEditor()

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
    editor = PromptPlainTextDocumentEditor()

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
