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

"""Tests for Phase 21.3 prompt clipboard/history routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptReplaceSourceRangeCommand,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.editing_session.edit_controller import (
    PromptEditController,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptClipboardHistoryController,
)


@dataclass(slots=True)
class _PayloadProvider:
    """Provide passive undo payloads for controller tests."""

    def undo_restoration_payload(self) -> str:
        """Return a restoration payload."""

        return "payload"

    def undo_comparison_payload(self) -> str:
        """Return a comparison payload."""

        return "comparison"


@dataclass(slots=True)
class _AvailabilitySink:
    """Record availability emissions."""

    undo_values: list[bool] = field(default_factory=list)
    redo_values: list[bool] = field(default_factory=list)

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record undo availability."""

        self.undo_values.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record redo availability."""

        self.redo_values.append(available)


@dataclass(slots=True)
class _PendingFlusher:
    """Record pending-key flush requests."""

    reasons: list[str] = field(default_factory=list)

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Record a typing-only flush."""

        self.reasons.append(reason)

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Record a full pending-key flush."""

        self.reasons.append(reason)


@dataclass(slots=True)
class _Clipboard:
    """Store clipboard text in memory."""

    value: str = ""
    writes: list[str] = field(default_factory=list)

    def text(self) -> str:
        """Return stored clipboard text."""

        return self.value

    def set_text(self, text: str) -> None:
        """Store clipboard text and record the write."""

        self.value = text
        self.writes.append(text)


@dataclass(slots=True)
class _Sink:
    """Record clipboard/history sink operations."""

    cursor_states: list[PromptCursorState] = field(default_factory=list)
    restored_sources: list[str] = field(default_factory=list)

    def set_clipboard_history_cursor_state(
        self,
        cursor_state: PromptCursorState,
    ) -> None:
        """Record one cursor state."""

        self.cursor_states.append(cursor_state)

    def restore_clipboard_history_state(self, restore_result: object) -> None:
        """Record one restored source snapshot."""

        snapshot = getattr(restore_result, "snapshot")
        self.restored_sources.append(snapshot.source_text)


@dataclass(slots=True)
class _SourceReplacementExecutor:
    """Record source replacements requested by clipboard/history routing."""

    replacements: list[tuple[int, int, str, PromptSourceEditOrigin]] = field(
        default_factory=list
    )

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
    ) -> None:
        """Record one requested source replacement."""

        _ = command_name
        _ = record_undo
        self.replacements.append((start, end, replacement_text, origin))


@dataclass(slots=True)
class _DanbooruScheduler:
    """Record Danbooru paste scheduling attempts."""

    scheduled: bool = False
    texts: list[str] = field(default_factory=list)

    def try_schedule_clipboard_danbooru_paste(self, text: str) -> bool:
        """Record text and return the configured scheduling result."""

        self.texts.append(text)
        return self.scheduled


def _session(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
) -> PromptEditingSession[str]:
    """Return one editing session for clipboard/history tests."""

    default_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=(
                default_position if cursor_position is None else cursor_position
            ),
            anchor_position=(
                default_position if anchor_position is None else anchor_position
            ),
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


@dataclass(slots=True)
class _Harness:
    """Bundle controller collaborators for one test."""

    controller: PromptClipboardHistoryController[str]
    edit_controller: PromptEditController[str]
    clipboard: _Clipboard
    sink: _Sink
    source_replacement_executor: _SourceReplacementExecutor
    scheduler: _DanbooruScheduler
    flusher: _PendingFlusher
    paste_completions: list[str]


def _harness(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
    editing_enabled: bool = True,
    clipboard_text: str = "",
    danbooru_scheduled: bool = False,
) -> _Harness:
    """Return one controller harness."""

    session = _session(
        source_text,
        cursor_position=cursor_position,
        anchor_position=anchor_position,
    )
    flusher = _PendingFlusher()
    edit_controller = PromptEditController(
        session=session,
        undo_payload_provider=_PayloadProvider(),
        availability_signal_sink=_AvailabilitySink(),
        pending_key_flusher=flusher,
    )
    clipboard = _Clipboard(value=clipboard_text)
    sink = _Sink()
    source_replacement_executor = _SourceReplacementExecutor()
    scheduler = _DanbooruScheduler(scheduled=danbooru_scheduled)
    paste_completions: list[str] = []
    controller = PromptClipboardHistoryController(
        edit_controller=edit_controller,
        clipboard=clipboard,
        sink=sink,
        source_replacement_executor=source_replacement_executor,
        danbooru_paste_scheduler=scheduler,
        editing_enabled=lambda: editing_enabled,
        paste_completed=paste_completions.append,
    )
    return _Harness(
        controller=controller,
        edit_controller=edit_controller,
        clipboard=clipboard,
        sink=sink,
        source_replacement_executor=source_replacement_executor,
        scheduler=scheduler,
        flusher=flusher,
        paste_completions=paste_completions,
    )


def test_copy_writes_selected_source_text_without_mutation() -> None:
    """Copy should write selected raw source text and leave source unchanged."""

    harness = _harness("alpha beta", cursor_position=5, anchor_position=0)

    harness.controller.copy()

    assert harness.clipboard.writes == ["alpha"]
    assert harness.edit_controller.session.source_text == "alpha beta"
    assert harness.source_replacement_executor.replacements == []


def test_cut_flushes_before_selection_command_and_requests_deletion() -> None:
    """Cut should write clipboard text and request selected source deletion."""

    harness = _harness("alpha beta", cursor_position=5, anchor_position=0)

    harness.controller.cut()

    assert harness.flusher.reasons == ["cut"]
    assert harness.clipboard.writes == ["alpha"]
    assert harness.source_replacement_executor.replacements == [
        (0, 5, "", PromptSourceEditOrigin.TYPED)
    ]


def test_cut_disabled_or_empty_selection_does_not_write_clipboard() -> None:
    """Cut should not mutate clipboard when editing is disabled or selection empty."""

    disabled = _harness(
        "alpha",
        cursor_position=5,
        anchor_position=0,
        editing_enabled=False,
    )
    empty = _harness("alpha", cursor_position=2, anchor_position=2)

    disabled.controller.cut()
    empty.controller.cut()

    assert disabled.clipboard.writes == []
    assert disabled.flusher.reasons == []
    assert empty.clipboard.writes == []
    assert empty.flusher.reasons == ["cut"]


def test_paste_consults_danbooru_before_literal_replacement() -> None:
    """Paste should let Danbooru scheduling consume supported URLs."""

    harness = _harness(
        "alpha",
        clipboard_text="https://danbooru.donmai.us/posts/1",
        danbooru_scheduled=True,
    )

    harness.controller.paste()

    assert harness.flusher.reasons == ["paste"]
    assert harness.scheduler.texts == ["https://danbooru.donmai.us/posts/1"]
    assert harness.source_replacement_executor.replacements == []
    assert harness.paste_completions == ["paste"]


def test_literal_paste_requests_normalized_source_replacement() -> None:
    """Literal paste should request a normalized replacement through the sink."""

    harness = _harness(
        "alpha beta",
        cursor_position=10,
        anchor_position=6,
        clipboard_text="gamma",
    )

    harness.controller.paste()

    assert harness.flusher.reasons == ["paste"]
    assert harness.scheduler.texts == ["gamma"]
    assert harness.source_replacement_executor.replacements == [
        (6, 10, "gamma", PromptSourceEditOrigin.PASTE)
    ]
    assert harness.paste_completions == ["paste"]


def test_select_all_applies_command_cursor_state() -> None:
    """Select-all should apply the cursor state returned by the command."""

    harness = _harness("alpha")

    harness.controller.select_all()

    assert harness.flusher.reasons == ["select_all"]
    assert harness.sink.cursor_states == [
        PromptCursorState(cursor_position=5, anchor_position=0)
    ]


def test_undo_and_redo_restore_results_reach_sink() -> None:
    """Undo and redo should restore through the controller's sink."""

    harness = _harness("alpha")
    edit_controller = harness.edit_controller
    edit_controller.dispatch_command(
        PromptReplaceSourceRangeCommand(
            name="append",
            replacement=PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(start=5, end=5),
                replacement_text=" beta",
                origin=PromptSourceEditOrigin.PROGRAMMATIC,
                exact_source=True,
            ),
            normalizer=PromptSourceNormalizationService(),
            undo_snapshot=edit_controller.current_undo_snapshot(),
        )
    )

    harness.controller.undo()
    harness.controller.redo()

    assert harness.flusher.reasons == ["undo", "redo"]
    assert harness.sink.restored_sources == ["alpha", "alpha beta"]
