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

"""Verify the sole edit execution and commit-publication boundary."""

from __future__ import annotations

from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.presentation.editor.prompt_editor.commands.execution import (
    PromptEditExecution,
)
from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
    PromptEditScope,
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


class _PayloadProvider:
    """Record passive undo payload reads."""

    def __init__(self) -> None:
        """Create empty payload-read counters."""

        self.comparison_reads = 0
        self.restoration_reads = 0

    def undo_comparison_payload(self) -> str:
        """Return one stable comparison value."""

        self.comparison_reads += 1
        return "comparison"

    def undo_restoration_payload(self) -> str:
        """Return one stable restoration value."""

        self.restoration_reads += 1
        return "restoration"


class _AvailabilitySink:
    """Record published undo and redo availability transitions."""

    def __init__(self) -> None:
        """Create empty transition logs."""

        self.undo_values: list[bool] = []
        self.redo_values: list[bool] = []

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record one undo transition."""

        self.undo_values.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record one redo transition."""

        self.redo_values.append(available)


class _CommitSink:
    """Record each edit commit delivered to projection."""

    def __init__(self) -> None:
        """Create an empty commit log."""

        self.commits: list[PromptEditCommit[str]] = []

    def apply_edit_commit(self, commit: PromptEditCommit[str]) -> None:
        """Record one authoritative edit result."""

        self.commits.append(commit)


def _execution(
    source_text: str,
) -> tuple[
    PromptEditExecution[str],
    _PayloadProvider,
    _AvailabilitySink,
    _CommitSink,
]:
    """Return one real editing owner with observable boundary fakes."""

    session = PromptEditingSession[str](
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(len(source_text), len(source_text)),
        max_undo_states=8,
        max_redo_states=8,
    )
    payloads = _PayloadProvider()
    availability = _AvailabilitySink()
    commits = _CommitSink()
    return (
        PromptEditExecution(
            session=session,
            undo_payload_provider=payloads,
            availability_signal_sink=availability,
            commit_sink=commits,
        ),
        payloads,
        availability,
        commits,
    )


def test_range_replacement_publishes_one_commit_and_one_snapshot_read() -> None:
    """One source transaction should cross the projection boundary once."""

    execution, payloads, availability, commits = _execution("alpha")

    commit = execution.replace_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
    )

    assert execution.session.source_text == "alpha beta"
    assert commits.commits == [commit]
    assert commit.previous_snapshot.source_text == "alpha"
    assert commit.next_snapshot.source_text == "alpha beta"
    assert commit.scope is PromptEditScope.RANGE
    assert payloads.comparison_reads == 1
    assert payloads.restoration_reads == 1
    assert availability.undo_values == [True]
    assert availability.redo_values == []


def test_noop_still_publishes_one_cursor_commit_without_undo_signal() -> None:
    """A no-op remains one observable commit without inventing history."""

    execution, _, availability, commits = _execution("alpha")

    commit = execution.replace_range(
        start=1,
        end=2,
        replacement_text="l",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.PROGRAMMATIC,
        exact_source=True,
    )

    assert not commit.source_changed
    assert commits.commits == [commit]
    assert availability.undo_values == []
    assert availability.redo_values == []


def test_undo_and_redo_each_publish_one_history_commit() -> None:
    """History restoration should use the same single-commit boundary."""

    execution, _, _, commits = _execution("alpha")
    execution.replace_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
    )
    commits.commits.clear()

    undo_commit = execution.undo()
    redo_commit = execution.redo()

    assert undo_commit is not None
    assert redo_commit is not None
    assert undo_commit.scope is PromptEditScope.HISTORY
    assert redo_commit.scope is PromptEditScope.HISTORY
    assert commits.commits == [undo_commit, redo_commit]
    assert execution.session.source_text == "alpha beta"
