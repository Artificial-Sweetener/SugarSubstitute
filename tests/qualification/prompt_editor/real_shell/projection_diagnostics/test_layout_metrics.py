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

"""Verify projection layout and metric transition diagnostics."""

from __future__ import annotations

from dataclasses import replace

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorStateSnapshot,
    PromptEditorVisibleLayoutRow,
    PromptEditorVisibleTextFragment,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_detects_stable_space_content_height_shift(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Detect same-line-count content height changes after one space edit."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alphabeta\ngamma\ndelta"
    )
    snapshot = real_shell_scenario.snapshots.capture(field, label="height-baseline")
    rows = (
        _visible_row(0, document_top=0.0, viewport_top=0.0, text="alpha"),
        _visible_row(1, document_top=16.0, viewport_top=16.0, text="gamma"),
        _visible_row(2, document_top=32.0, viewport_top=32.0, text="delta"),
    )
    before = replace(
        snapshot,
        source_text="alphabeta\ngamma\ndelta",
        layout_line_count=3,
        layout_content_height=48.0,
        visible_layout_rows=rows,
    )
    stable_after = replace(before, source_text="alpha beta\ngamma\ndelta")
    shifted_after = replace(
        stable_after,
        layout_content_height=50.0,
        visible_layout_rows=(
            replace(rows[0], height=18.0),
            replace(rows[1], document_top=18.0, viewport_top=18.0),
            replace(rows[2], document_top=34.0, viewport_top=34.0),
        ),
    )

    stable_violations = _space_violations(before, stable_after)
    shifted_violations = _space_violations(before, shifted_after)

    assert not any(
        violation.startswith("stable_single_character_content_height_shift")
        for violation in stable_violations
    )
    assert any(
        violation.startswith("stable_single_character_content_height_shift")
        for violation in shifted_violations
    )


def test_real_shell_detects_non_uniform_visible_fragment_shift(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Detect uneven text-fragment movement after a stable space edit."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alphabeta\ngamma\ndelta"
    )
    snapshot = real_shell_scenario.snapshots.capture(field, label="fragment-baseline")
    rows = (
        _visible_row(0, document_top=0.0, viewport_top=0.0, text="alphabeta"),
        _visible_row(1, document_top=16.0, viewport_top=16.0, text="gamma"),
        _visible_row(2, document_top=32.0, viewport_top=32.0, text="delta"),
    )
    before = replace(
        snapshot,
        source_text="alphabeta\ngamma\ndelta",
        layout_line_count=3,
        layout_content_width=240.0,
        layout_content_height=48.0,
        visible_layout_rows=rows,
        visible_text_fragments=(
            _visible_text_fragment(0, 0, 5, baseline=12.0, text="alpha"),
            _visible_text_fragment(1, 5, 9, baseline=12.0, text="beta"),
            _visible_text_fragment(2, 10, 15, baseline=28.0, text="gamma"),
            _visible_text_fragment(3, 16, 21, baseline=44.0, text="delta"),
        ),
    )
    stable_after = replace(
        before,
        source_text="alpha beta\ngamma\ndelta",
        visible_layout_rows=(
            replace(rows[0], source_end=10, text="alpha beta"),
            replace(rows[1], source_start=11, source_end=16),
            replace(rows[2], source_start=21, source_end=26),
        ),
        visible_text_fragments=(
            _visible_text_fragment(0, 0, 5, baseline=12.0, text="alpha"),
            _visible_text_fragment(1, 6, 10, baseline=12.0, text="beta"),
            _visible_text_fragment(2, 11, 16, baseline=28.0, text="gamma"),
            _visible_text_fragment(3, 17, 22, baseline=44.0, text="delta"),
        ),
    )
    mixed_after = replace(
        stable_after,
        visible_text_fragments=(
            _visible_text_fragment(0, 0, 5, baseline=12.0, text="alpha"),
            _visible_text_fragment(1, 6, 10, baseline=14.0, text="beta"),
            _visible_text_fragment(2, 11, 16, baseline=28.0, text="gamma"),
            _visible_text_fragment(3, 17, 22, baseline=44.0, text="delta"),
        ),
    )

    stable_violations = _space_violations(before, stable_after)
    mixed_violations = _space_violations(before, mixed_after)

    assert not any(
        violation.startswith("non_uniform_visible_fragment_shift")
        for violation in stable_violations
    )
    assert any(
        violation.startswith("non_uniform_visible_fragment_shift")
        for violation in mixed_violations
    )


def test_real_shell_detects_projection_metrics_contract_violations(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Detect row, fragment, content, shell, and caret metric drift."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="alpha")
    snapshot = real_shell_scenario.snapshots.capture(field, label="metrics-baseline")
    before = replace(
        snapshot,
        layout_content_height=24.0,
        projection_metrics_text_line_height=16.0,
        projection_metrics_content_height=24.0,
        shell_document_vertical_padding=8,
        shell_outer_vertical_padding=4,
        shell_natural_height=28,
        visible_layout_rows=(
            replace(
                _visible_row(0, document_top=4.0, viewport_top=4.0, text="alpha"),
                expected_height=16.0,
                expected_text_baseline=16.0,
            ),
        ),
        visible_text_fragments=(
            replace(
                _visible_text_fragment(0, 0, 5, baseline=16.0, text="alpha"),
                expected_document_baseline=16.0,
                expected_viewport_baseline=16.0,
                expected_height=16.0,
            ),
        ),
        caret_rect=(0.0, 4.0, 1.0, 16.0),
    )
    shifted = replace(
        before,
        layout_content_height=26.0,
        projection_metrics_content_height=24.0,
        shell_natural_height=35,
        visible_layout_rows=(replace(before.visible_layout_rows[0], height=18.0),),
        visible_text_fragments=(
            replace(
                before.visible_text_fragments[0],
                viewport_rect=(0.0, 4.0, 40.0, 18.0),
                document_rect=(0.0, 4.0, 40.0, 18.0),
                document_baseline=17.0,
                viewport_baseline=17.0,
            ),
        ),
        caret_rect=(0.0, 4.0, 1.0, 12.0),
    )

    stable_violations = snapshot_invariant_violations(before)
    shifted_violations = snapshot_invariant_violations(shifted)

    assert not any("mismatch" in violation for violation in stable_violations)
    assert "text_only_row_height_mismatch" in shifted_violations
    assert "content_height_contract_mismatch:26.000:24.000" in shifted_violations
    assert any(
        violation.startswith("shell_height_contract_mismatch")
        for violation in shifted_violations
    )
    assert any(
        violation.startswith("text_fragment_height_mismatch")
        for violation in shifted_violations
    )
    assert any(
        violation.startswith("text_fragment_baseline_mismatch")
        for violation in shifted_violations
    )
    assert any(
        violation.startswith("caret_rect_height_mismatch")
        for violation in shifted_violations
    )


def test_real_shell_allows_newline_only_rows_without_text_fragments(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Allow hard-break-only layout rows without an ink baseline."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="alpha")
    snapshot = real_shell_scenario.snapshots.capture(field, label="blank-row-baseline")
    blank_row = replace(
        _visible_row(99, document_top=20.0, viewport_top=20.0, text="\n"),
        expected_height=16.0,
        expected_text_baseline=32.0,
    )
    with_blank_row = replace(
        snapshot,
        visible_layout_rows=snapshot.visible_layout_rows + (blank_row,),
    )

    violations = snapshot_invariant_violations(with_blank_row)

    assert "text_only_row_baseline_mismatch:99" not in violations


def _space_violations(
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Evaluate one synthetic stable-space transition through production invariants."""

    return transition_violations(
        action_name="space",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )


def _visible_row(
    row_index: int,
    *,
    document_top: float,
    viewport_top: float,
    text: str,
) -> PromptEditorVisibleLayoutRow:
    """Create one synthetic visible row for projection invariant tests."""

    source_start = row_index * 10
    return PromptEditorVisibleLayoutRow(
        row_index=row_index,
        source_start=source_start,
        source_end=source_start + len(text),
        document_top=document_top,
        viewport_top=viewport_top,
        height=16.0,
        text=text,
    )


def _visible_text_fragment(
    fragment_index: int,
    source_start: int,
    source_end: int,
    *,
    baseline: float,
    text: str,
) -> PromptEditorVisibleTextFragment:
    """Return one synthetic visible fragment for projection invariant tests."""

    fragment_rect = (0.0, baseline - 12.0, 40.0, 16.0)
    return PromptEditorVisibleTextFragment(
        fragment_index=fragment_index,
        source_start=source_start,
        source_end=source_end,
        document_rect=fragment_rect,
        viewport_rect=fragment_rect,
        document_baseline=baseline,
        viewport_baseline=baseline,
        text=text,
    )
