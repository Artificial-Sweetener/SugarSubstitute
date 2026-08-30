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

"""Verify real-shell caret traversal, viewport visibility, and resize layout."""

from __future__ import annotations

from PySide6.QtCore import Qt
import pytest

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_projected_token_navigation_keeps_caret_map_sane(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep caret and token state coherent while traversing projected tokens."""

    prompt = "alpha, (small:1.20), <lora:missing:1.00>, omega"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(
        field, label="before-token-navigation"
    )
    for _ in range(18):
        real_shell_scenario.input.press_key(field, Qt.Key.Key_Left)
    after_left = real_shell_scenario.snapshots.capture(field, label="after-token-left")
    for _ in range(18):
        real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
    after_right = real_shell_scenario.snapshots.capture(
        field, label="after-token-right"
    )
    _assert_transitions(
        real_shell_scenario,
        "projected-token-navigation-left-bad-editor-state",
        "Projected token navigation must keep caret-map state coherent.",
        (("caret", before, after_left), ("caret", after_left, after_right)),
    )
    assert after_left.source_text == prompt
    assert after_right.source_text == prompt


def test_real_shell_vertical_navigation_preferred_x_is_owned_and_reset(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Own preferred x for vertical movement and reset it after horizontal movement."""

    prompt = (
        "masterpiece, best quality, official art\n"
        "backpack basket, empty eyes, pointy ears, sharp teeth\n"
        "glowing red eyes, long white hair, swept bangs"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.shell.resize(560, 640)
    real_shell_scenario.wait_for_queued_delivery()
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(field, label="before-vertical-nav")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Up)
    after_up = real_shell_scenario.snapshots.capture(field, label="after-up-nav")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Down)
    after_down = real_shell_scenario.snapshots.capture(field, label="after-down-nav")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Left)
    after_left = real_shell_scenario.snapshots.capture(field, label="after-left-reset")
    _assert_transitions(
        real_shell_scenario,
        "vertical-navigation-left-bad-caret-owner-state",
        "Vertical caret navigation must own and reset preferred x.",
        (
            ("caret", before, after_up),
            ("caret", after_up, after_down),
            ("caret", after_down, after_left),
        ),
    )
    assert after_up.caret_preferred_x is not None
    assert after_down.caret_preferred_x is not None
    assert after_left.caret_preferred_x is None
    assert not after_left.skip_next_same_source_soft_wrap_move


def test_real_shell_long_document_home_end_keep_caret_visible(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Scroll same-position Home and End carets into the long-document viewport."""

    prompt = "\n".join(
        f"line {index:02d} backpack basket empty eyes pointy ears"
        for index in range(60)
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.shell.resize(520, 420)
    real_shell_scenario.wait_for_queued_delivery()
    before = real_shell_scenario.snapshots.capture(field, label="before-long-end")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_End)
    after_end = real_shell_scenario.snapshots.capture(field, label="after-long-end")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Home)
    after_home = real_shell_scenario.snapshots.capture(field, label="after-long-home")
    _assert_transitions(
        real_shell_scenario,
        "long-document-boundary-navigation-left-caret-hidden",
        "Home/End navigation must keep long-document carets visible.",
        (("caret", before, after_end), ("caret", after_end, after_home)),
    )
    assert before.vertical_scroll_maximum > 0
    assert after_end.cursor_position == len(prompt)
    assert after_end.caret_rect_intersects_viewport
    assert (
        after_end.scroll_values["editor_vertical"]
        > before.scroll_values["editor_vertical"]
    )
    assert after_home.cursor_position == 0
    assert after_home.caret_rect_intersects_viewport
    assert (
        after_home.scroll_values["editor_vertical"]
        <= after_end.scroll_values["editor_vertical"]
    )


def test_real_shell_resize_wrap_keeps_layout_and_caret_sane(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Preserve coherent layout and caret state across repeated width changes."""

    prompt = (
        "masterpiece, best quality, very aesthetic, official art, "
        "(small:1.20), backpack basket, empty eyes, pointy ears, sharp teeth, "
        "<lora:missing:1.00>, glowing red eyes, long white hair"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(field, label="before-resize-wrap")
    snapshots: list[PromptEditorStateSnapshot] = []
    for index, width in enumerate((460, 920, 560, 1180, 520)):
        real_shell_scenario.shell.resize(width, 640)
        real_shell_scenario.wait_for_queued_delivery()
        snapshots.append(
            real_shell_scenario.snapshots.capture(field, label=f"after-resize-{index}")
        )
    pairs = tuple(
        ("resize", earlier, later)
        for earlier, later in zip((before, *snapshots), snapshots)
    )
    _assert_transitions(
        real_shell_scenario,
        "resize-wrap-left-bad-editor-state",
        "Resize/wrap changes must keep layout and caret state coherent.",
        pairs,
    )
    assert all(snapshot.source_text == prompt for snapshot in snapshots)


def _assert_transitions(
    scenario: PromptEditorRealShellScenario,
    artifact_name: str,
    invariant: str,
    transitions: tuple[
        tuple[str, PromptEditorStateSnapshot, PromptEditorStateSnapshot], ...
    ],
) -> None:
    """Persist a failure artifact when one caret or resize transition violates owners."""

    violations = tuple(
        violation
        for action_name, before, after in transitions
        for violation in transition_violations(
            action_name=action_name,
            before=before,
            after=after,
            snapshot_violations=snapshot_invariant_violations,
        )
    )
    if violations:
        artifact = scenario.artifacts.save(
            artifact_name,
            before=transitions[0][1],
            after=transitions[-1][2],
            invariant=invariant,
            observed=f"violations={tuple(dict.fromkeys(violations))}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
