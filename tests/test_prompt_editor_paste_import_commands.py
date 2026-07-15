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

"""Tests for Phase 3.7 prompt editor paste/import commands."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
    PromptPasteImportCommandResult,
    PromptPreparedDanbooruImportRequest,
    build_prepared_danbooru_import_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)


def _session(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
) -> PromptEditingSession[str]:
    """Return one editing session for paste/import command tests."""

    default_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=(
                default_position if cursor_position is None else cursor_position
            ),
            anchor_position=default_position
            if anchor_position is None
            else anchor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Return the current session state as a passive undo snapshot."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        restoration_payload=session.source_text,
    )


def _source_identity(session: PromptEditingSession[str]) -> PromptCommandSourceIdentity:
    """Return the current source identity for stale-command tests."""

    return PromptCommandSourceIdentity(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    )


def _seed_literal_url_paste(
    session: PromptEditingSession[str],
    url: str,
) -> PromptUndoSnapshot[str]:
    """Apply the literal URL paste state that precedes async import completion."""

    paste_start = len(session.source_text)
    session.replace_source_range(
        start=paste_start,
        end=paste_start,
        replacement_text=url,
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.PASTE,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    return _undo_snapshot(session)


def _execute_import_request(
    session: PromptEditingSession[str],
    request: PromptPreparedDanbooruImportRequest[str],
) -> PromptPasteImportCommandResult[str]:
    """Execute one prepared import command through the real dispatcher."""

    command = build_prepared_danbooru_import_command(
        request,
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    return cast(
        PromptPasteImportCommandResult[str],
        PromptCommandDispatcher(session).execute(command),
    )


def test_prepared_danbooru_import_replaces_matching_pasted_range() -> None:
    """Prepared imports should replace only the original pasted URL slice."""

    source_prefix = "alpha, "
    url = "https://danbooru.donmai.us/posts/12345"
    session = _session(source_prefix)
    pasted_snapshot = _seed_literal_url_paste(session, url)

    result = _execute_import_request(
        session,
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(
                len(source_prefix), len(session.source_text)
            ),
            expected_pasted_text=url,
            import_text="1girl, long hair, smile",
            pasted_undo_snapshot=pasted_snapshot,
            source_identity=_source_identity(session),
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "alpha, 1girl, long hair, smile"
    assert result.cursor_state == PromptCursorState(
        cursor_position=len("alpha, 1girl, long hair, smile"),
        anchor_position=len("alpha, 1girl, long hair, smile"),
    )
    assert result.discarded_intermediate_undo_state


def test_prepared_danbooru_import_normalizes_import_text() -> None:
    """Prepared import insertion should use source normalization like paste."""

    source_prefix = "alpha, "
    url = "https://danbooru.donmai.us/posts/12345"
    session = _session(source_prefix)
    pasted_snapshot = _seed_literal_url_paste(session, url)

    result = _execute_import_request(
        session,
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(
                len(source_prefix), len(session.source_text)
            ),
            expected_pasted_text=url,
            import_text="(smile)",
            pasted_undo_snapshot=pasted_snapshot,
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "alpha, (smile:1.10)"


def test_prepared_danbooru_import_rejects_stale_source_identity() -> None:
    """Prepared imports should fail closed when an explicit identity is stale."""

    source_prefix = "alpha, "
    url = "https://danbooru.donmai.us/posts/12345"
    session = _session(source_prefix)
    pasted_snapshot = _seed_literal_url_paste(session, url)

    result = _execute_import_request(
        session,
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(
                len(source_prefix), len(session.source_text)
            ),
            expected_pasted_text=url,
            import_text="1girl",
            pasted_undo_snapshot=pasted_snapshot,
            source_identity=PromptCommandSourceIdentity(
                source_revision=session.source_revision + 1,
                source_length=len(session.source_text),
            ),
        ),
    )

    assert result.status == "rejected"
    assert result.reason == "stale_source"
    assert session.source_text == source_prefix + url


def test_prepared_danbooru_import_rejects_changed_pasted_text() -> None:
    """Later edits inside the pasted range should prevent import replacement."""

    source_prefix = "alpha, "
    url = "https://danbooru.donmai.us/posts/12345"
    session = _session(source_prefix + url)
    pasted_snapshot = _undo_snapshot(session)

    result = _execute_import_request(
        session,
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(
                len(source_prefix), len(session.source_text)
            ),
            expected_pasted_text="https://danbooru.donmai.us/posts/99999",
            import_text="1girl",
            pasted_undo_snapshot=pasted_snapshot,
        ),
    )

    assert result.status == "rejected"
    assert result.reason == "pasted_text_changed"
    assert session.source_text == source_prefix + url


def test_prepared_danbooru_import_rejects_out_of_bounds_range() -> None:
    """Prepared imports should not clamp ranges that no longer fit the source."""

    session = _session("alpha")

    result = _execute_import_request(
        session,
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(0, len(session.source_text) + 1),
            expected_pasted_text="alpha",
            import_text="1girl",
            pasted_undo_snapshot=_undo_snapshot(session),
        ),
    )

    assert result.status == "rejected"
    assert result.reason == "range_out_of_bounds"
    assert session.source_text == "alpha"


def test_prepared_danbooru_import_undo_skips_intermediate_url() -> None:
    """Undo after prepared import replacement should restore the pre-paste source."""

    source_prefix = "alpha, "
    url = "https://danbooru.donmai.us/posts/12345"
    session = _session(source_prefix)
    pasted_snapshot = _seed_literal_url_paste(session, url)

    result = _execute_import_request(
        session,
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(
                len(source_prefix), len(session.source_text)
            ),
            expected_pasted_text=url,
            import_text="1girl, smile",
            pasted_undo_snapshot=pasted_snapshot,
        ),
    )
    restore_result = session.undo(_undo_snapshot(session))

    assert result.status == "applied"
    assert restore_result is not None
    assert session.source_text == source_prefix
