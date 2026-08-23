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

"""Verify scene-marker editing through the production prompt-editor shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_typed_scene_marker_projects_on_first_title_character(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Scene syntax should project synchronously once a marker has a title."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")

    timeline = real_shell_scenario.projection_probes.typed_scene(field)

    initial_sample = timeline[0]
    first_title_sample = next(
        sample for sample in timeline if sample.label == "character-2:S"
    )
    first_asterisk_sample = next(
        sample for sample in timeline if sample.label == "character-0:*"
    )
    second_asterisk_sample = next(
        sample for sample in timeline if sample.label == "character-1:*"
    )
    settled_sample = timeline[-1]
    assert first_asterisk_sample.source_text == "*"
    assert first_asterisk_sample.scene_titles == ()
    assert second_asterisk_sample.source_text == "**"
    assert second_asterisk_sample.scene_titles == ()
    assert first_title_sample.source_text == "**S"
    assert first_title_sample.scene_titles == ("S",)
    assert first_title_sample.projection_text == "S"
    assert all(
        sample.projection_text != "**Scene"
        for sample in timeline
        if sample.source_text == "**Scene"
    )
    assert settled_sample.document_view_source_text == "**Scene"
    assert settled_sample.scene_titles == ("Scene",)
    assert settled_sample.projection_has_pending_update is False
    assert settled_sample.semantic_refresh_pending is False
    assert settled_sample.semantic_refresh_active is False
    assert settled_sample.cursor_position == len("**Scene")
    assert settled_sample.focus_active is initial_sample.focus_active


def test_real_shell_typed_scene_marker_projects_after_existing_prompt_line(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Rapid scene typing should project at a multiline prompt boundary."""

    initial_text = "quality\n"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial_text)
    real_shell_scenario.input.set_source_cursor_position(field, len(initial_text))

    timeline = real_shell_scenario.projection_probes.typed_scene(field)

    initial_sample = timeline[0]
    first_title_sample = next(
        sample for sample in timeline if sample.label == "character-2:S"
    )
    settled_sample = timeline[-1]
    assert first_title_sample.source_text == "quality\n**S"
    assert first_title_sample.scene_titles == ("S",)
    assert "**S" not in first_title_sample.projection_text
    assert settled_sample.source_text == "quality\n**Scene"
    assert settled_sample.scene_titles == ("Scene",)
    assert settled_sample.projection_has_pending_update is False
    assert settled_sample.semantic_refresh_pending is False
    assert settled_sample.semantic_refresh_active is False
    assert settled_sample.cursor_position == len(settled_sample.source_text)
    assert settled_sample.focus_active is initial_sample.focus_active


def test_real_shell_scene_marker_typing_preserves_unmapped_source_caret(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Syntax formation must not move the logical caret behind typed marker text."""

    initial_text = "quality\n**Landscape\nfield"
    marker_start = initial_text.index("**Landscape")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial_text)
    real_shell_scenario.input.set_source_cursor_position(field, marker_start)
    target = real_shell_scenario.input.focus_editor(field)

    QTest.keyClick(target, Qt.Key.Key_Return)
    expected_text = "quality\n\n**Landscape\nfield"
    expected_cursor = marker_start + 1
    assert field.editor.toPlainText() == expected_text
    assert field.editor.textCursor().position() == expected_cursor

    for character in "**Burst Scene":
        expected_text = (
            expected_text[:expected_cursor]
            + character
            + expected_text[expected_cursor:]
        )
        expected_cursor += 1
        QTest.keyClicks(target, character)

        assert field.editor.toPlainText() == expected_text
        assert field.editor.textCursor().position() == expected_cursor
        snapshot = real_shell_scenario.snapshots.capture(
            field,
            label=f"scene-marker-prefix-{expected_cursor}",
        )
        assert snapshot.caret_state_source_position == expected_cursor
        assert snapshot.caret_rect_has_area

    QTest.keyClick(target, Qt.Key.Key_Return)
    expected_text = (
        expected_text[:expected_cursor] + "\n" + expected_text[expected_cursor:]
    )
    real_shell_scenario.wait_for_queued_delivery()

    assert field.editor.toPlainText() == expected_text
    assert tuple(
        token.display_text
        for token in field.editor._surface.projection_document().tokens  # noqa: SLF001
        if token.kind.value == "scene"
    ) == ("Burst Scene", "Landscape")


def test_real_shell_enter_after_scene_title_enters_editable_scene_body(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Enter after a scene title must move every caret owner into its body."""

    title = "**Scene"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=title)
    real_shell_scenario.input.set_source_cursor_position(field, len(title))

    enter_route = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Return, text="\n"
    )
    entered = real_shell_scenario.snapshots.capture(field, label="entered-scene-body")

    assert enter_route.source_after == f"{title}\n"
    assert enter_route.cursor_after == len(title) + 1
    assert entered.cursor_position == len(title) + 1
    assert entered.editing_session_cursor_position == len(title) + 1
    assert entered.editing_session_anchor_position == len(title) + 1
    assert entered.caret_state_source_position == len(title) + 1
    assert entered.anchor_state_source_position == len(title) + 1
    assert entered.caret_map_source_length == len(title) + 1
    assert entered.layout_line_count == 2
    assert entered.caret_rect_intersects_viewport

    real_shell_scenario.input.type_text(field, "x")
    typed = real_shell_scenario.snapshots.capture(field, label="typed-scene-body")

    assert typed.source_text == f"{title}\nx"
    assert typed.cursor_position == len(title) + 2
    assert typed.editing_session_cursor_position == len(title) + 2
    assert typed.caret_state_source_position == len(title) + 2
    assert typed.layout_line_count == 2
    assert typed.caret_rect_intersects_viewport

    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(
        field, label="undone-scene-body-text"
    )
    assert undone.source_text == f"{title}\n"
    assert undone.cursor_position == len(title) + 1
    assert undone.caret_state_source_position == len(title) + 1


def test_real_shell_scene_line_break_toggle_preserves_decorated_row_metrics(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Enter and Backspace at a scene boundary must retain decorated row ownership."""

    source = "**scene\nbody, (sharp eyes:1.25), <lora:detail_booster:1.00>"
    scene_title_end = len("**scene")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, scene_title_end)

    entered = real_shell_scenario.input.press_key(field, Qt.Key.Key_Return, text="\n")
    assert (
        entered.source_after
        == f"{source[:scene_title_end]}\n{source[scene_title_end:]}"
    )
    assert entered.cursor_after == scene_title_end + 1

    restored = real_shell_scenario.input.press_key(field, Qt.Key.Key_Backspace)
    snapshot = real_shell_scenario.snapshots.capture(
        field, label="scene-break-restored"
    )

    assert restored.source_after == source
    assert restored.cursor_after == scene_title_end
    assert not snapshot_invariant_violations(snapshot)


def test_real_shell_scene_title_space_advances_visible_caret(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """A trailing title space must immediately own a distinct visible caret stop."""

    title = "**scene"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=title)
    real_shell_scenario.input.set_source_cursor_position(field, len(title))
    target = real_shell_scenario.input.focus_editor(field)
    before = real_shell_scenario.snapshots.capture(field, label="before-title-space")

    QTest.keyClicks(target, " ")
    after = real_shell_scenario.snapshots.capture(field, label="after-title-space")

    assert after.source_text == f"{title} "
    assert after.cursor_position == len(title) + 1
    assert after.caret_state_source_position == len(title) + 1
    assert after.projection_text == "scene "
    assert before.caret_rect is not None
    assert after.caret_rect is not None
    assert after.caret_rect[0] > before.caret_rect[0]


def test_real_shell_scene_title_resize_never_discards_uncommitted_typing(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """A shell relayout must retain transient scene text until projection catches up."""

    title = "**scene with a deliberately long title and many spaced words"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="**scene ")
    field.editor.resize(430, 260)
    real_shell_scenario.input.set_source_cursor_position(field, len("**scene "))
    real_shell_scenario.input.type_text(field, title[len("**scene ") :])

    field.editor.resize(429, 260)
    QApplication.processEvents()
    QApplication.processEvents()
    snapshot = real_shell_scenario.snapshots.capture(
        field, label="scene-title-after-resize"
    )

    assert snapshot.source_text == title
    assert snapshot.cursor_position == len(title)
    assert (
        snapshot.projection_document_source_text == title
        or snapshot.transient_insertion_overlay_valid
    )
    assert snapshot.caret_rect_intersects_viewport


def test_real_shell_scene_title_typing_keeps_every_character_visually_owned(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Each title character must remain visible while a deferred wrap catches up."""

    title = "**scene with a deliberately long title and many spaced words"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    field.editor.resize(430, 260)
    target = real_shell_scenario.input.focus_editor(field)

    for character in title:
        QTest.keyClicks(target, character)
        snapshot = real_shell_scenario.snapshots.capture(
            field,
            label=f"scene-title-character-{len(field.editor.toPlainText())}",
        )

        assert snapshot.source_text == field.editor.toPlainText()
        assert (
            snapshot.projection_document_source_text == snapshot.source_text
            or snapshot.transient_insertion_overlay_valid
        )
        assert snapshot.caret_rect_intersects_viewport
