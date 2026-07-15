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

"""Tests for Phase 21.4 prompt undo coalescing ownership."""

from __future__ import annotations

from collections.abc import Callable
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
from substitute.presentation.editor.prompt_editor.editing_session.undo_coalescing import (
    PromptUndoCoalescingController,
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
    """Record undo/redo availability emissions."""

    undo_values: list[bool] = field(default_factory=list)
    redo_values: list[bool] = field(default_factory=list)

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record one undo availability transition."""

        self.undo_values.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record one redo availability transition."""

        self.redo_values.append(available)


@dataclass(slots=True)
class _Timer:
    """Record timer lifecycle and expose deterministic expiry."""

    starts: int = 0
    stops: int = 0
    timeout_handler: Callable[[], None] | None = None

    def set_timeout_handler(self, handler: Callable[[], None]) -> None:
        """Store the timer expiry handler."""

        self.timeout_handler = handler

    def start(self) -> None:
        """Record one timer start."""

        self.starts += 1

    def stop(self) -> None:
        """Record one timer stop."""

        self.stops += 1

    def expire(self) -> None:
        """Invoke the stored expiry handler."""

        if self.timeout_handler is not None:
            self.timeout_handler()


@dataclass(slots=True)
class _SelectionState:
    """Expose mutable selection emptiness to the coalescing controller."""

    empty: bool = True


@dataclass(slots=True)
class _Harness:
    """Group a coalescing controller with its deterministic collaborators."""

    controller: PromptUndoCoalescingController[str]
    edit_controller: PromptEditController[str]
    typing_timer: _Timer
    delete_timer: _Timer
    availability_sink: _AvailabilitySink
    selection_state: _SelectionState


def _session(source_text: str) -> PromptEditingSession[str]:
    """Return one source-backed editing session."""

    cursor_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _harness(source_text: str) -> _Harness:
    """Return one coalescing controller harness."""

    session = _session(source_text)
    availability_sink = _AvailabilitySink()
    edit_controller = PromptEditController(
        session=session,
        undo_payload_provider=_PayloadProvider(),
        availability_signal_sink=availability_sink,
    )
    typing_timer = _Timer()
    delete_timer = _Timer()
    selection_state = _SelectionState()
    controller = PromptUndoCoalescingController(
        edit_controller=edit_controller,
        typing_timer=typing_timer,
        delete_timer=delete_timer,
        cursor_position=lambda: edit_controller.session.cursor_position,
        selection_empty=lambda: selection_state.empty,
    )
    edit_controller.set_pending_key_flusher(controller)
    return _Harness(
        controller=controller,
        edit_controller=edit_controller,
        typing_timer=typing_timer,
        delete_timer=delete_timer,
        availability_sink=availability_sink,
        selection_state=selection_state,
    )


def _replace_range(
    edit_controller: PromptEditController[str],
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> None:
    """Apply one exact source replacement through the command boundary."""

    edit_controller.dispatch_command(
        PromptReplaceSourceRangeCommand(
            name="test_replace",
            replacement=PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(start=start, end=end),
                replacement_text=replacement_text,
                origin=PromptSourceEditOrigin.TYPED,
            ),
            normalizer=PromptSourceNormalizationService(),
            undo_snapshot=edit_controller.current_undo_snapshot(),
        )
    )


def _type_text(harness: _Harness, text: str) -> None:
    """Type text through coalescing and command dispatch."""

    for character in text:
        assert harness.controller.can_group_typed_text(character)
        harness.controller.begin_or_extend_typing_group(character)
        position = harness.edit_controller.session.cursor_position
        _replace_range(
            harness.edit_controller,
            start=position,
            end=position,
            replacement_text=character,
        )


def _backspace(harness: _Harness, *, key: int = 1) -> None:
    """Backspace one character through coalescing and command dispatch."""

    harness.controller.begin_delete_group(key=key, autorepeat=False)
    position = harness.edit_controller.session.cursor_position
    _replace_range(
        harness.edit_controller,
        start=position - 1,
        end=position,
        replacement_text="",
    )


def test_grouped_word_typing_undoes_as_one_step() -> None:
    """Contiguous word typing should finish as one undo transaction."""

    harness = _harness("alpha ")

    _type_text(harness, "beta")
    harness.controller.finish_pending_key_edit_blocks(reason="test")
    restore_result = harness.edit_controller.undo()

    assert harness.edit_controller.session.source_text == "alpha "
    assert restore_result is not None
    assert harness.typing_timer.starts == 4
    assert harness.typing_timer.stops == 4
    assert harness.availability_sink.undo_values == [True, False]
    assert harness.availability_sink.redo_values == [True]


def test_idle_typing_expiry_splits_undo_steps() -> None:
    """Typing idle expiry should commit the current typing group."""

    harness = _harness("a")

    _type_text(harness, "b")
    harness.typing_timer.expire()
    _type_text(harness, "c")
    harness.controller.finish_pending_key_edit_blocks(reason="test")
    harness.edit_controller.undo()

    assert harness.edit_controller.session.source_text == "ab"


def test_selection_and_prompt_boundaries_block_typing_grouping() -> None:
    """Non-word text and non-empty selection should not join typing groups."""

    harness = _harness("alpha")

    assert harness.controller.can_group_typed_text(",") is False
    harness.selection_state.empty = False
    assert harness.controller.can_group_typed_text("b") is False


def test_rapid_delete_coalesces_until_idle_expiry() -> None:
    """Rapid delete actions using one key should undo as one transaction."""

    harness = _harness("alpha")

    _backspace(harness, key=1)
    _backspace(harness, key=1)
    harness.delete_timer.expire()
    harness.edit_controller.undo()

    assert harness.edit_controller.session.source_text == "alpha"
    assert harness.delete_timer.starts == 2
    assert harness.delete_timer.stops == 2


def test_delete_key_change_splits_undo_steps() -> None:
    """Changing delete key identity should close the previous delete group."""

    harness = _harness("alpha")

    _backspace(harness, key=1)
    _backspace(harness, key=2)
    harness.controller.finish_pending_key_edit_blocks(reason="test")
    harness.edit_controller.undo()

    assert harness.edit_controller.session.source_text == "alph"


def test_explicit_flush_commits_typing_and_delete_groups() -> None:
    """Explicit pending-key flush should close both active group types."""

    harness = _harness("alpha ")

    _type_text(harness, "b")
    _backspace(harness, key=1)
    harness.controller.finish_pending_key_edit_blocks(reason="command")

    assert harness.edit_controller.session.typing_group_active is False
    assert harness.edit_controller.session.delete_group_active is False
    assert harness.typing_timer.stops == 1
    assert harness.delete_timer.stops == 1
