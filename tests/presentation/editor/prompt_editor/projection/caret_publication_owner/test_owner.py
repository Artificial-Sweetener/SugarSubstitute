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

"""Test complete caret-state publication and its ordered presentation effects."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.projection.caret_publication_owner import (
    PromptCaretPublicationEditorState,
    PromptProjectionCaretPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.caret_state_owner import (
    PromptProjectionCaretStateOwner,
)
from substitute.presentation.editor.prompt_editor.projection.undo_payload import (
    PromptProjectionUndoPayload,
)


def _state(position: int) -> PromptProjectionCaretState:
    """Build one canonical plain-text caret state."""

    return PromptProjectionCaretState(source_position=position)


def _caret_map(*positions: int) -> PromptProjectionCaretMap:
    """Build a sparse current projection map for stale-state resolution tests."""

    return PromptProjectionCaretMap(
        stops=tuple(
            PromptProjectionCaretStop(
                visual_index=index,
                projection_position=position,
                state=_state(position),
            )
            for index, position in enumerate(positions)
        ),
        tokens=(),
        source_length=6,
        projection_length=6,
    )


def _editing_session() -> PromptEditingSession[PromptProjectionUndoPayload]:
    """Build source cursor ownership for one publication contract test."""

    return PromptEditingSession(
        source_text="abcdef",
        source_revision=0,
        cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
        max_undo_states=10,
        max_redo_states=10,
    )


def _owner(
    *,
    state: PromptProjectionCaretStateOwner,
    editing_session: PromptEditingSession[PromptProjectionUndoPayload],
    caret_map: PromptProjectionCaretMap,
    events: list[str],
) -> PromptProjectionCaretPublicationOwner:
    """Build one publication owner with fully observable presentation effects."""

    editor_state = cast(
        PromptCaretPublicationEditorState,
        SimpleNamespace(
            projection=SimpleNamespace(
                document=SimpleNamespace(caret_map=caret_map),
            )
        ),
    )

    def selection() -> PromptProjectionSelection:
        """Derive selection from the authoritative caret states."""

        return PromptProjectionSelection(
            anchor_position=state.anchor_state.source_position,
            cursor_position=state.cursor_state.source_position,
        )

    return PromptProjectionCaretPublicationOwner(
        state=state,
        editor_state=editor_state,
        editing_session=editing_session,
        selection=selection,
        current_caret_rect=lambda: QRectF(1.0, 2.0, 1.0, 12.0),
        clear_transient_geometry=lambda: events.append("clear_transient"),
        expanded_source_range_present=lambda: True,
        collapse_expanded_token=lambda: events.append("collapse_token"),
        reconcile_autocomplete=(
            lambda cursor_position, selection_is_empty: events.append(
                f"autocomplete:{cursor_position}:{selection_is_empty}"
            )
        ),
        refresh_active_projection=lambda: events.append("active_projection"),
        ensure_caret_visible=lambda: events.append("visibility"),
        refresh_caret_layers=lambda: events.append("caret_layers"),
        refresh_deferred_caret_layers=lambda: events.append("deferred_layers"),
        restart_caret_blink=lambda: events.append("blink"),
        request_viewport_update=lambda: events.append("viewport"),
        update_caret_paint=lambda _rect: events.append("caret_paint"),
        emit_cursor_position_changed=lambda: events.append("signal"),
        surface_state=dict,
    )


def test_publish_resolves_stale_state_and_orders_complete_effects() -> None:
    """Interactive publication should resolve once and publish every effect in order."""

    events: list[str] = []
    state = PromptProjectionCaretStateOwner(_state(0))
    editing_session = _editing_session()
    owner = _owner(
        state=state,
        editing_session=editing_session,
        caret_map=_caret_map(0, 2, 4, 6),
        events=events,
    )
    stale_cursor = PromptProjectionCaretState(
        source_position=4,
        placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
        token_id="removed-token",
        token_slot=2,
    )

    owner.publish(cursor_state=stale_cursor, anchor_state=_state(2))

    assert state.cursor_state == _state(4)
    assert state.anchor_state == _state(2)
    assert editing_session.cursor_state == PromptCursorState(
        cursor_position=4,
        anchor_position=2,
    )
    assert events == [
        "clear_transient",
        "collapse_token",
        "autocomplete:4:False",
        "active_projection",
        "visibility",
        "caret_layers",
        "blink",
        "viewport",
        "caret_paint",
        "signal",
    ]


def test_unchanged_publish_only_repairs_visibility_and_caret_paint() -> None:
    """A no-op publication should avoid signals and unrelated layer invalidation."""

    events: list[str] = []
    state = PromptProjectionCaretStateOwner(_state(0))
    editing_session = _editing_session()
    owner = _owner(
        state=state,
        editing_session=editing_session,
        caret_map=_caret_map(0, 6),
        events=events,
    )

    owner.publish(cursor_state=_state(0), anchor_state=_state(0))

    assert events == ["visibility", "caret_paint"]


def test_deferred_publish_preserves_raw_source_positions_and_deferred_layers() -> None:
    """Pending reflow should retain unmapped source positions without normal layers."""

    events: list[str] = []
    state = PromptProjectionCaretStateOwner(_state(0))
    editing_session = _editing_session()
    owner = _owner(
        state=state,
        editing_session=editing_session,
        caret_map=_caret_map(0, 6),
        events=events,
    )

    owner.publish_deferred(cursor_state=_state(5), anchor_state=_state(3))

    assert state.cursor_state == _state(5)
    assert state.anchor_state == _state(3)
    assert editing_session.cursor_state == PromptCursorState(
        cursor_position=5,
        anchor_position=3,
    )
    assert events == [
        "visibility",
        "deferred_layers",
        "blink",
        "viewport",
        "caret_paint",
        "signal",
    ]
