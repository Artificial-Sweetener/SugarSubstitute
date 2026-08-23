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

"""Verify real-shell trace replay and bounded abuse reporting."""

from __future__ import annotations

from pathlib import Path

from tests.support.prompt_editor.real_shell.models import PromptEditorTrace
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_trace_replay_uses_fresh_real_shell_path(
    real_shell_scenario: PromptEditorRealShellScenario,
    tmp_path: Path,
) -> None:
    """Replay a trace through a separately mounted production shell."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "replay")
    trace = real_shell_scenario.trace()

    replay_scenario = PromptEditorRealShellScenario(artifact_root=tmp_path)
    try:
        replay_field = replay_scenario.workflows.add_prompt_workflow(initial_text="")
        replay_scenario.trace_replay.replay(replay_field, trace)
        snapshot = replay_scenario.snapshots.capture(
            replay_field,
            label="after-replay",
        )
    finally:
        replay_scenario.close()

    assert snapshot.source_text == "replay"
    assert "PromptProjectionSurface" in snapshot.target_event_widget_path
    assert "EditorPanel#workflow-prompt-harness-editor-panel" in (
        snapshot.target_event_widget_path
    )


def test_real_shell_minimization_preserves_real_replay_predicate(
    real_shell_scenario: PromptEditorRealShellScenario,
    tmp_path: Path,
) -> None:
    """Minimize only actions preserving the real-shell replay predicate."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "remove")
    real_shell_scenario.input.type_text(field, "keep")
    trace = real_shell_scenario.trace()

    def replays_keep_text(candidate: PromptEditorTrace) -> bool:
        """Return whether candidate still replays target text in a production shell."""

        replay_scenario = PromptEditorRealShellScenario(artifact_root=tmp_path)
        try:
            replay_field = replay_scenario.workflows.add_prompt_workflow(
                initial_text=""
            )
            replay_scenario.trace_replay.replay(replay_field, candidate)
            return "keep" in replay_field.editor.toPlainText()
        finally:
            replay_scenario.close()

    minimized = real_shell_scenario.trace_replay.minimize(trace, replays_keep_text)

    assert len(minimized.actions) <= len(trace.actions)
    assert replays_keep_text(minimized)


def test_real_shell_seeded_abuse_campaign_writes_grouped_report(
    real_shell_scenario: PromptEditorRealShellScenario,
    tmp_path: Path,
) -> None:
    """Run a bounded seeded abuse pass through the production-mounted editor."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")

    report = real_shell_scenario.abuse_campaign.run(
        field,
        seed=7,
        sizes=((860, 560), (1040, 760), (1280, 820)),
        steps_per_size=2,
    )

    assert report.action_count == 6
    assert report.report_path.exists()
    assert report.report_path.is_relative_to(tmp_path)
    assert isinstance(report.grouped_failures, dict)
    assert "literal-tab-in-source" not in report.grouped_failures
    assert "control-character-in-source" not in report.grouped_failures
    if report.findings:
        assert report.grouped_failures
