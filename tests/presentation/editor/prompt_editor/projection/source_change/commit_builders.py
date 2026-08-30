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

"""Provide source-change commit and application builders."""

from __future__ import annotations

from typing import Any, cast


from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptEditApplicationState,
)
from substitute.presentation.editor.prompt_editor.core.editing.commands import (
    PromptReplaceDocumentEdit,
    PromptReplaceRangeEdit,
)
from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
)
from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_commands import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.core.editing.transactions import (
    PromptUndoSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.source_commit_application import (
    PromptProjectionSourceCommitApplication,
)
from substitute.presentation.editor.prompt_editor.projection.source_change_transaction import (
    PromptProjectionSourceChangeTransaction,
)
from substitute.presentation.editor.prompt_editor.projection.semantic_remap import (
    PromptProjectionSemanticRemapper,
)
from substitute.presentation.editor.prompt_editor.projection.source_range_commit_application import (
    PromptSourceRangeCommitApplication,
)
from substitute.presentation.editor.prompt_editor.projection.source_history_commit_application import (
    PromptSourceHistoryCommitApplication,
)
from substitute.presentation.editor.prompt_editor.projection.source_projection_application import (
    PromptSourceProjectionApplication,
)
from substitute.presentation.editor.prompt_editor.projection.source_document_commit_application import (
    PromptSourceDocumentCommitApplication,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_facts import (
    PromptSourceEditProjectionFactContext,
    PromptSourceEditProjectionFactResolver,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.projection.undo_payload import (
    PromptProjectionUndoPayload,
)

from .source_change_host import _SourceChangeHost

_ProjectionPayload = PromptProjectionUndoPayload


def _source_change_applier(
    host: _SourceChangeHost,
) -> PromptProjectionSourceCommitApplication[_ProjectionPayload]:
    """Compose the production fact resolver with the source-change owner."""

    projection_facts = PromptSourceEditProjectionFactResolver(
        cast(PromptSourceEditProjectionFactContext, host),
        applicator=cast(Any, host._projection_applicator),
        editor_state=cast(Any, host._editor_state),
        freshness=cast(Any, host._projection_freshness_controller),
        layout=host._layout,
        overlays=host._transient_edit_overlays,
    )
    semantic_remapper = PromptProjectionSemanticRemapper()
    projection_application = PromptSourceProjectionApplication(
        cast(Any, host),
        cast(Any, host),
        editor_state=cast(Any, host._editor_state),
        freshness=cast(Any, host._projection_freshness_controller),
        pipeline=cast(Any, host._edit_pipeline),
        overlays=host._transient_edit_overlays,
    )
    transaction = PromptProjectionSourceChangeTransaction[_ProjectionPayload](
        cast(Any, host),
        host._mouse_handler,
        editor_state=cast(Any, host._editor_state),
        freshness=cast(Any, host._projection_freshness_controller),
        projection_application=projection_application,
        semantic_remapper=semantic_remapper,
        session=cast(Any, host._session),
        source_document=cast(Any, host._source_document_adapter),
    )
    range_application = PromptSourceRangeCommitApplication[_ProjectionPayload](
        cast(Any, host),
        editor_state=cast(Any, host._editor_state),
        projection_facts=projection_facts,
        semantic_remapper=semantic_remapper,
        session=cast(Any, host._session),
        transaction=transaction,
    )
    history_application = PromptSourceHistoryCommitApplication[_ProjectionPayload](
        cast(Any, host),
        cast(Any, host),
        editor_state=cast(Any, host._editor_state),
        freshness=cast(Any, host._projection_freshness_controller),
        projection_application=projection_application,
        session=cast(Any, host._session),
        source_document=cast(Any, host._source_document_adapter),
    )
    document_application = PromptSourceDocumentCommitApplication[_ProjectionPayload](
        cast(Any, host),
        cast(Any, host),
        transaction=transaction,
    )
    return PromptProjectionSourceCommitApplication[_ProjectionPayload](
        document=document_application,
        history=history_application,
        range_edit=range_application,
    )


def _session(source_text: str) -> PromptEditingSession[str]:
    """Return one editing session for projection contract tests."""

    cursor_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(source_text: str) -> PromptUndoSnapshot[str]:
    """Return one passive undo snapshot for projection contract tests."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=source_text,
    )


def _projection_payload(source_text: str) -> _ProjectionPayload:
    """Return one projection restore payload for applier owner tests."""

    cursor_position = len(source_text)
    return _ProjectionPayload(
        cursor_state=PromptProjectionCaretState(source_position=cursor_position),
        anchor_state=PromptProjectionCaretState(source_position=cursor_position),
        expanded_source_range=(0, len(source_text)),
        document_view=PromptDocumentView(
            source_text=source_text,
            segments=(),
            emphasis_spans=(),
            wildcard_spans=(),
            lora_spans=(),
            syntax_spans=(),
            region_structure=PromptRegionStructureView.empty(len(source_text)),
            has_trailing_comma=False,
        ),
        render_plan=PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        ),
        layout_checkpoint=None,
    )


def _projection_session(source_text: str) -> PromptEditingSession[_ProjectionPayload]:
    """Return one editing session with projection restore payloads."""

    cursor_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _projection_undo_snapshot(
    source_text: str,
) -> PromptUndoSnapshot[_ProjectionPayload]:
    """Return one undo snapshot carrying projection restore payload state."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=_projection_payload(source_text),
    )


def _range_commit(
    session: PromptEditingSession[_ProjectionPayload],
    *,
    start: int,
    end: int,
    replacement_text: str,
    exact_source: bool = True,
    record_undo: bool = True,
) -> PromptEditCommit[_ProjectionPayload]:
    """Commit one bounded edit through the editing-session command boundary."""

    return session.execute(
        PromptReplaceRangeEdit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            normalizer=PromptSourceNormalizationService(),
            origin=PromptSourceEditOrigin.TYPED,
            exact_source=exact_source,
            record_undo=record_undo,
            undo_snapshot=_projection_undo_snapshot(session.source_text),
        )
    )


def _document_commit(
    session: PromptEditingSession[_ProjectionPayload],
    *,
    text: str,
    application_state: PromptEditApplicationState | None = None,
) -> PromptEditCommit[_ProjectionPayload]:
    """Commit one complete-source replacement with optional viewport intent."""

    commit = session.execute(
        PromptReplaceDocumentEdit(
            text=text,
            cursor_position=len(text),
            anchor_position=len(text),
            normalizer=PromptSourceNormalizationService(),
            exact_source=True,
            record_undo=True,
            clear_history=False,
            undo_snapshot=_projection_undo_snapshot(session.source_text),
        )
    )
    return (
        commit
        if application_state is None
        else commit.with_prepared_state(application_state)
    )
