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

"""Verify diagnostics for non-uniform visible-row movement."""

from __future__ import annotations

from dataclasses import replace

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.models import PromptEditorVisibleLayoutRow
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_detects_non_uniform_visible_row_shift(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Detect mixed row movement without treating uniform scrolling as a paint bug."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha\nbeta\ngamma"
    )
    snapshot = real_shell_scenario.snapshots.capture(field, label="row-shift-baseline")
    rows = (
        _visible_row(0, document_top=0.0, viewport_top=0.0, text="alpha"),
        _visible_row(1, document_top=16.0, viewport_top=16.0, text="beta"),
        _visible_row(2, document_top=32.0, viewport_top=32.0, text="gamma"),
    )
    before = replace(
        snapshot,
        layout_line_count=3,
        layout_content_height=48.0,
        visible_layout_rows=rows,
    )
    uniform_after = replace(
        before,
        visible_layout_rows=tuple(
            replace(row, viewport_top=row.viewport_top - 2.0) for row in rows
        ),
        scroll_values={**before.scroll_values, "editor_vertical": 2},
    )
    mixed_after = replace(
        before,
        visible_layout_rows=(
            replace(rows[0], viewport_top=0.0),
            replace(rows[1], viewport_top=14.0),
            replace(rows[2], viewport_top=32.0),
        ),
    )

    uniform_violations = transition_violations(
        action_name="space",
        before=before,
        after=uniform_after,
        snapshot_violations=snapshot_invariant_violations,
    )
    mixed_violations = transition_violations(
        action_name="space",
        before=before,
        after=mixed_after,
        snapshot_violations=snapshot_invariant_violations,
    )

    assert not any(
        violation.startswith("non_uniform_visible_row_shift")
        for violation in uniform_violations
    )
    assert any(
        violation.startswith("non_uniform_visible_row_shift")
        for violation in mixed_violations
    )


def _visible_row(
    row_index: int,
    *,
    document_top: float,
    viewport_top: float,
    text: str,
) -> PromptEditorVisibleLayoutRow:
    """Build one visible layout row with stable test-only geometry."""

    return PromptEditorVisibleLayoutRow(
        row_index=row_index,
        document_top=document_top,
        viewport_top=viewport_top,
        height=16.0,
        source_start=row_index * 10,
        source_end=(row_index * 10) + len(text),
        text=text,
    )
