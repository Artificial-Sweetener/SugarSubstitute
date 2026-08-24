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

"""Run bounded randomized real-shell prompt-editor abuse campaigns."""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import random
from typing import Any, Protocol, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tests.support.prompt_editor.real_shell.artifacts import (
    PromptEditorArtifactStore,
    group_abuse_findings,
    owner_hypothesis_for_violation,
    safe_artifact_name,
)
from tests.support.prompt_editor.real_shell.input_driver import PromptEditorInputDriver
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorAbuseFinding,
    PromptEditorAbuseReport,
    PromptEditorStateSnapshot,
    PromptFieldHandle,
)
from tests.support.prompt_editor.real_shell.session import PromptEditorRealShell
from tests.support.prompt_editor.real_shell.workflows import PromptWorkflowMounts
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


class PromptEditorStateSnapshotCapture(Protocol):
    """Describe the state-capture contract required by an abuse campaign."""

    def __call__(
        self,
        field: PromptFieldHandle,
        *,
        label: str,
        settle: bool = True,
    ) -> PromptEditorStateSnapshot:
        """Capture the real-shell editor state for one abuse boundary."""


class PromptEditorTransitionInvariantEvaluator(Protocol):
    """Describe the transition-invariant contract required by abuse finding triage."""

    def __call__(
        self,
        *,
        action_name: str,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
    ) -> tuple[str, ...]:
        """Return observable invariant violations for one completed transition."""


class PromptEditorAbuseCampaign:
    """Own randomized interactions and finding artifacts for one mounted shell."""

    def __init__(
        self,
        *,
        shell: PromptEditorRealShell,
        artifact_root: Path,
        artifacts: PromptEditorArtifactStore,
        input_driver: PromptEditorInputDriver,
        workflows: PromptWorkflowMounts,
        snapshot_capture: PromptEditorStateSnapshotCapture,
        transition_invariants: PromptEditorTransitionInvariantEvaluator,
    ) -> None:
        """Bind the campaign to explicit real interaction and diagnostic owners."""

        self._shell = shell
        self._artifact_root = artifact_root
        self._artifacts = artifacts
        self._input = input_driver
        self._workflows = workflows
        self._snapshot_capture = snapshot_capture
        self._transition_invariants = transition_invariants

    def run(
        self,
        field: PromptFieldHandle,
        *,
        seed: int,
        sizes: Sequence[tuple[int, int]] = ((860, 560), (1040, 760), (1280, 820)),
        steps_per_size: int = 8,
    ) -> PromptEditorAbuseReport:
        """Run a bounded autocomplete-heavy campaign against the real editor."""

        rng = random.Random(seed)
        findings: list[PromptEditorAbuseFinding] = []
        suspicious_successes: list[str] = []
        action_index = 0
        for width, height in sizes:
            self._shell.resize(width, height)
            wait_for_queued_qt_turn()
            self._input.replace_text_with_keys(field, "")
            for _step in range(steps_per_size):
                before = self._snapshot_capture(
                    field,
                    label=f"abuse-before-{action_index}",
                )
                action_name = self._run_action(field, rng)
                after = self._snapshot_capture(
                    field,
                    label=f"abuse-after-{action_index}",
                )
                finding = self._finding_for_transition(
                    action_index=action_index,
                    action_name=action_name,
                    before=before,
                    after=after,
                )
                if finding is not None:
                    findings.append(finding)
                elif action_name in {"tab", "escape", "resize"}:
                    suspicious_successes.append(
                        self._suspicious_success(
                            action_index, action_name, before, after
                        )
                    )
                action_index += 1
        report_path = self._write_report(
            seed=seed,
            sizes=tuple(sizes),
            action_count=action_index,
            findings=tuple(findings),
            suspicious_successes=tuple(suspicious_successes),
        )
        return PromptEditorAbuseReport(
            seed=seed,
            sizes=tuple(sizes),
            action_count=action_index,
            findings=tuple(findings),
            suspicious_successes=tuple(suspicious_successes),
            grouped_failures=group_abuse_findings(findings),
            report_path=report_path,
        )

    def _run_action(self, field: PromptFieldHandle, rng: random.Random) -> str:
        """Run one randomized but bounded abuse interaction."""

        action = rng.choice(
            (
                "prefix",
                "space",
                "tab",
                "escape",
                "backspace",
                "delete",
                "cursor",
                "shift_selection",
                "selection_replace",
                "paste_multiline",
                "undo_redo",
                "projected_token_walk",
                "long_document_navigation",
                "multiline_backpack_up",
                "multiline_backpack_up",
                "scroll_editor",
                "workflow_round_trip",
                "resize",
                "click_away",
                "canvas",
            )
        )
        if action == "prefix":
            self._input.type_text(field, rng.choice(("re", "1g", "ha", "backpack")))
        elif action == "space":
            self._input.press_key(field, Qt.Key.Key_Space, text=" ")
        elif action == "tab":
            self._input.press_key(field, Qt.Key.Key_Tab, text="\t")
        elif action == "escape":
            self._input.press_key(field, Qt.Key.Key_Escape)
        elif action == "backspace":
            self._input.press_key(field, Qt.Key.Key_Backspace)
        elif action == "delete":
            self._input.press_key(field, Qt.Key.Key_Delete)
        elif action == "cursor":
            self._input.press_key(field, rng.choice(_CURSOR_KEYS))
        elif action == "shift_selection":
            self._input.press_key(
                field,
                rng.choice(_SELECTION_KEYS),
                modifiers=Qt.KeyboardModifier.ShiftModifier,
            )
            return "selection"
        elif action == "selection_replace":
            self._replace_selection(field, rng)
            return "selection_replace"
        elif action == "paste_multiline":
            self._paste_multiline(field, rng)
            return "paste"
        elif action == "undo_redo":
            self._undo_redo(field)
            return "undo_redo"
        elif action == "projected_token_walk":
            self._walk_projected_tokens(field, rng)
            return "caret"
        elif action == "long_document_navigation":
            self._navigate_long_document(field, rng)
            return "caret"
        elif action == "multiline_backpack_up":
            self._navigate_multiline_autocomplete(field)
            return "caret"
        elif action == "scroll_editor":
            self._scroll_editor(field, rng)
            return "scroll"
        elif action == "workflow_round_trip":
            self._workflows.workflow_round_trip(field)
            return "workflow"
        elif action == "resize":
            self._shell.resize(
                rng.choice((820, 960, 1180)), rng.choice((520, 700, 860))
            )
            wait_for_queued_qt_turn()
        elif action == "canvas":
            self._input.switch_canvas("Output")
            self._input.switch_canvas("Input")
        else:
            self._input.click_away_from_editor(field)
            self._input.focus_editor(field)
        return action

    def _replace_selection(self, field: PromptFieldHandle, rng: random.Random) -> None:
        """Replace a random source selection through the real input route."""

        source = field.editor.toPlainText()
        if source:
            start = rng.randrange(0, len(source))
            end = rng.randrange(start, len(source) + 1)
            cursor = cast(Any, field.editor).textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cast(Any, field.editor).setTextCursor(cursor)
            wait_for_queued_qt_turn()
        self._input.type_text(field, rng.choice(("alpha", "backpack", "1girl")))

    def _paste_multiline(self, field: PromptFieldHandle, rng: random.Random) -> None:
        """Paste one bounded multiline source through the platform shortcut."""

        QApplication.clipboard().setText(rng.choice(_MULTILINE_PASTES))
        QTest.keySequence(
            self._input.focus_editor(field),
            QKeySequence.StandardKey.Paste,
        )
        wait_for_queued_qt_turn()

    def _undo_redo(self, field: PromptFieldHandle) -> None:
        """Exercise the native undo and redo shortcuts once each."""

        target = self._input.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.Undo)
        wait_for_queued_qt_turn()
        QTest.keySequence(target, QKeySequence.StandardKey.Redo)
        wait_for_queued_qt_turn()

    def _walk_projected_tokens(
        self, field: PromptFieldHandle, rng: random.Random
    ) -> None:
        """Traverse tokenized source using real cursor key input."""

        self._input.replace_text_with_keys(
            field,
            "alpha, (small:1.20), <lora:missing:1.00>, omega",
        )
        self._input.move_cursor_to_end(field)
        for _ in range(rng.randint(2, 8)):
            self._input.press_key(field, Qt.Key.Key_Left)
        for _ in range(rng.randint(2, 8)):
            self._input.press_key(field, Qt.Key.Key_Right)

    def _navigate_long_document(
        self, field: PromptFieldHandle, rng: random.Random
    ) -> None:
        """Exercise page navigation after seeding a scrollable source document."""

        self._input.seed_text_directly(field, _long_prompt())
        self._input.press_key(field, Qt.Key.Key_End)
        self._input.press_key(
            field, rng.choice((Qt.Key.Key_PageUp, Qt.Key.Key_PageDown))
        )
        self._input.press_key(field, Qt.Key.Key_Home)

    def _navigate_multiline_autocomplete(self, field: PromptFieldHandle) -> None:
        """Exercise up-arrow navigation from a multiline autocomplete target."""

        self._input.replace_text_with_keys(
            field, "empty eyes, pointy ears, sharp teeth"
        )
        self._input.press_key(field, Qt.Key.Key_Return, text="\n")
        self._input.move_cursor_to_end(field)
        self._input.type_text(field, "backpack")
        self._input.press_key(field, Qt.Key.Key_Up)

    def _scroll_editor(self, field: PromptFieldHandle, rng: random.Random) -> None:
        """Exercise one bounded editor scroll position."""

        if field.editor.verticalScrollBar().maximum() <= 0:
            self._input.seed_text_directly(field, _long_prompt(line_count=24))
        self._input.scroll_editor(field, rng.choice(("top", "middle", "bottom")))

    def _finding_for_transition(
        self,
        *,
        action_index: int,
        action_name: str,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
    ) -> PromptEditorAbuseFinding | None:
        """Classify one completed abuse transition by its first invariant symptom."""

        violations = self._transition_invariants(
            action_name=action_name,
            before=before,
            after=after,
        )
        if not violations:
            return None
        symptom = violations[0]
        artifact = self._artifacts.save(
            f"abuse-{action_index}-{safe_artifact_name(symptom)}",
            before=before,
            after=after,
            invariant=symptom,
            observed=f"violations={violations}; {before.source_text!r}->{after.source_text!r}",
        )
        return PromptEditorAbuseFinding(
            symptom=symptom,
            owner_hypothesis=owner_hypothesis_for_violation(symptom),
            action_index=action_index,
            source_before=before.source_text,
            source_after=after.source_text,
            artifact_path=str(artifact),
        )

    def _write_report(
        self,
        *,
        seed: int,
        sizes: tuple[tuple[int, int], ...],
        action_count: int,
        findings: tuple[PromptEditorAbuseFinding, ...],
        suspicious_successes: tuple[str, ...],
    ) -> Path:
        """Write grouped campaign evidence for later failure triage."""

        directory = self._artifact_root / f"abuse-seed-{seed}"
        directory.mkdir(parents=True, exist_ok=True)
        report_path = directory / "report.json"
        report_path.write_text(
            json.dumps(
                {
                    "seed": seed,
                    "sizes": sizes,
                    "action_count": action_count,
                    "findings": [
                        {
                            "symptom": finding.symptom,
                            "owner_hypothesis": finding.owner_hypothesis,
                            "action_index": finding.action_index,
                            "source_before": finding.source_before,
                            "source_after": finding.source_after,
                            "artifact_path": finding.artifact_path,
                        }
                        for finding in findings
                    ],
                    "suspicious_successes": suspicious_successes,
                    "grouped_failures": group_abuse_findings(findings),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return report_path

    @staticmethod
    def _suspicious_success(
        action_index: int,
        action_name: str,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
    ) -> str:
        """Describe a stable high-risk action that did not violate an invariant."""

        return (
            f"{action_index}:{action_name}:{before.source_text!r}->{after.source_text!r}:"
            f"panel={after.autocomplete_presenter_panel_visible}:"
            f"preview={after.autocomplete_preview_active}:"
            f"session={after.autocomplete_has_active_session}"
        )


_CURSOR_KEYS = (
    Qt.Key.Key_Left,
    Qt.Key.Key_Right,
    Qt.Key.Key_Up,
    Qt.Key.Key_Down,
    Qt.Key.Key_Home,
    Qt.Key.Key_End,
    Qt.Key.Key_PageUp,
    Qt.Key.Key_PageDown,
)
_SELECTION_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End)
_MULTILINE_PASTES = (
    "alpha\nbeta",
    "backpack basket\nempty eyes",
    "(small:1.20),\nwhite dress",
)


def _long_prompt(*, line_count: int = 16) -> str:
    """Build the bounded scrollable source used by navigation actions."""

    return "\n".join(
        f"line {index:02d} backpack basket empty eyes pointy ears"
        for index in range(line_count)
    )
