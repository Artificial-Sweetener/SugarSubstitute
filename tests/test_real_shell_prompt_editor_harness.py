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

"""Exercise prompt editor mounting through the real shell harness."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
import os
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
import pytest

from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor import PromptDiagnosticKind
from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import UserPreset
from substitute.presentation.editor.catalog.snapshots import CatalogSnapshotReadiness
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from tests.real_shell_prompt_editor_harness import (
    _cached_scheduled_loras,
    PromptEditorVisibleLayoutRow,
    PromptEditorVisibleTextFragment,
    PromptEditorTrace,
    RealShellPromptEditorHarness,
)
from tests.prompt_projection_surface_test_helpers import (
    RecordingThumbnailAssetRepository,
    StaticPromptLoraCatalog,
    delay_projection_update_scheduler,
    lora_catalog_item_with_banner,
)
from tools.prompt_editor_abuse.models import PromptAbuseAction, PromptAbuseScenario
from tools.prompt_editor_abuse.real_shell_driver import run_real_shell_scenario

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real prompt editor shell harness requires non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture
def harness() -> Iterator[RealShellPromptEditorHarness]:
    """Create and close a real-shell prompt editor harness."""

    shell_harness = RealShellPromptEditorHarness()
    try:
        yield shell_harness
    finally:
        shell_harness.close()


def test_real_shell_harness_mounts_prompt_editor_through_editor_panel(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Mount a real PromptEditor from EditorPanel.load_all_cubes."""

    field = harness.add_prompt_workflow(initial_text="masterpiece")
    panel = harness.shell.editor_panels[field.workflow.workflow_id]

    assert isinstance(panel, EditorPanel)
    assert isinstance(field.editor, PromptEditor)
    registry = getattr(panel, "input_widgets_by_field_key")
    assert (
        registry[(field.workflow.cube_alias, field.node_name, field.field_key)]
        is field.editor
    )
    assert _is_descendant(field.editor, panel)
    assert field.editor.property("input_metadata")["cube_alias"] == (
        field.workflow.cube_alias
    )
    harness.focus_editor(field)
    assert field.editor.isVisible()


def test_real_shell_harness_edits_update_cube_buffer_through_field_wiring(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Persist typed prompt edits through production editor-panel field wiring."""

    field = harness.add_prompt_workflow(initial_text="old prompt")

    harness.replace_text_with_keys(field, "updated prompt")
    harness.wait_until(lambda: field.editor.toPlainText() == "updated prompt")

    nodes = cast(dict[str, dict[str, Any]], field.workflow.cube_state.buffer["nodes"])
    node = nodes[field.node_name]
    assert node["inputs"][field.field_key] == "updated prompt"
    assert field.workflow.cube_state.dirty is True


def test_real_shell_typed_selection_replacement_preserves_exact_keys(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A closing parenthesis must replace selected text without rewriting context."""

    source_text = "open (, alpha, {lighting/day}, omega"
    selection_start = source_text.index(",", source_text.index("{"))
    field = harness.add_prompt_workflow(initial_text=source_text)
    cursor = field.editor.textCursor()
    cursor.setPosition(selection_start)
    cursor.setPosition(selection_start + 2, QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)
    target = harness.focus_editor(field)

    QTest.keyClicks(target, ") ")

    assert field.editor.toPlainText() == ("open (, alpha, {lighting/day}) omega")
    assert field.editor.textCursor().position() == selection_start + 2


def test_real_shell_typed_scene_marker_projects_on_first_title_character(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Scene syntax should project synchronously once a marker has a title."""

    field = harness.add_prompt_workflow(initial_text="")

    timeline = harness.probe_typed_scene_projection(field)

    first_title_sample = next(
        sample for sample in timeline if sample.label == "character-2:S"
    )
    first_asterisk_sample = timeline[0]
    second_asterisk_sample = timeline[1]
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
    assert settled_sample.focus_active is True


def test_real_shell_typed_scene_marker_projects_after_existing_prompt_line(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Rapid scene typing should project at a multiline prompt boundary."""

    initial_text = "quality\n"
    field = harness.add_prompt_workflow(initial_text=initial_text)
    harness.set_source_cursor_position(field, len(initial_text))

    timeline = harness.probe_typed_scene_projection(field)

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
    assert settled_sample.focus_active is True


def test_real_shell_scene_marker_typing_preserves_unmapped_source_caret(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Syntax formation must not move the logical caret behind typed marker text."""

    initial_text = "quality\n**Landscape\nfield"
    marker_start = initial_text.index("**Landscape")
    field = harness.add_prompt_workflow(initial_text=initial_text)
    harness.set_source_cursor_position(field, marker_start)
    target = harness.focus_editor(field)

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

    QTest.keyClick(target, Qt.Key.Key_Return)
    expected_text = (
        expected_text[:expected_cursor] + "\n" + expected_text[expected_cursor:]
    )
    harness.process_events(cycles=8)

    assert field.editor.toPlainText() == expected_text
    assert tuple(
        token.display_text
        for token in field.editor._surface.projection_document().tokens  # noqa: SLF001
        if token.kind.value == "scene"
    ) == ("Burst Scene", "Landscape")


def test_real_shell_enter_after_scene_title_enters_editable_scene_body(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Enter after a scene title must move every caret owner into its body."""

    title = "**Scene"
    field = harness.add_prompt_workflow(initial_text=title)
    harness.set_source_cursor_position(field, len(title))

    enter_route = harness.press_key(field, Qt.Key.Key_Return, text="\n")
    entered = harness.capture_state_snapshot(field, label="entered-scene-body")

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

    harness.type_text(field, "x")
    typed = harness.capture_state_snapshot(field, label="typed-scene-body")

    assert typed.source_text == f"{title}\nx"
    assert typed.cursor_position == len(title) + 2
    assert typed.editing_session_cursor_position == len(title) + 2
    assert typed.caret_state_source_position == len(title) + 2
    assert typed.layout_line_count == 2
    assert typed.caret_rect_intersects_viewport

    harness.undo(field)
    undone = harness.capture_state_snapshot(field, label="undone-scene-body-text")
    assert undone.source_text == f"{title}\n"
    assert undone.cursor_position == len(title) + 1
    assert undone.caret_state_source_position == len(title) + 1


def test_real_shell_scene_line_break_toggle_preserves_decorated_row_metrics(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Enter and Backspace at a scene boundary must retain decorated row ownership."""

    source = "**scene\nbody, (sharp eyes:1.25), <lora:detail_booster:1.00>"
    scene_title_end = len("**scene")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, scene_title_end)

    entered = harness.press_key(field, Qt.Key.Key_Return, text="\n")
    assert (
        entered.source_after
        == f"{source[:scene_title_end]}\n{source[scene_title_end:]}"
    )
    assert entered.cursor_after == scene_title_end + 1

    restored = harness.press_key(field, Qt.Key.Key_Backspace)
    snapshot = harness.capture_state_snapshot(field, label="scene-break-restored")

    assert restored.source_after == source
    assert restored.cursor_after == scene_title_end
    assert not harness.invariant_violations(snapshot)


def test_real_shell_scene_title_space_advances_visible_caret(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A trailing title space must immediately own a distinct visible caret stop."""

    title = "**scene"
    field = harness.add_prompt_workflow(initial_text=title)
    harness.set_source_cursor_position(field, len(title))
    target = harness.focus_editor(field)
    before = harness.capture_state_snapshot(field, label="before-title-space")

    QTest.keyClicks(target, " ")
    after = harness.capture_state_snapshot(field, label="after-title-space")

    assert after.source_text == f"{title} "
    assert after.cursor_position == len(title) + 1
    assert after.caret_state_source_position == len(title) + 1
    assert after.projection_text == "scene "
    assert before.caret_rect is not None
    assert after.caret_rect is not None
    assert after.caret_rect[0] > before.caret_rect[0]


def test_real_shell_scene_title_resize_never_discards_uncommitted_typing(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A shell relayout must retain transient scene text until projection catches up."""

    title = "**scene with a deliberately long title and many spaced words"
    field = harness.add_prompt_workflow(initial_text="**scene ")
    field.editor.resize(430, 260)
    harness.set_source_cursor_position(field, len("**scene "))
    harness.type_text(field, title[len("**scene ") :])

    field.editor.resize(429, 260)
    QApplication.processEvents()
    QApplication.processEvents()
    snapshot = harness.capture_state_snapshot(field, label="scene-title-after-resize")

    assert snapshot.source_text == title
    assert snapshot.cursor_position == len(title)
    assert (
        snapshot.projection_document_source_text == title
        or snapshot.transient_insertion_overlay_valid
    )
    assert snapshot.caret_rect_intersects_viewport


def test_real_shell_routine_typing_around_scenes_never_rebuilds_projection(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Existing scene geometry should remap locally for ordinary source edits."""

    cases = (
        ("before-scene", "quality\n**Portrait\nstudio", 0),
        ("scene-title-end", "**Portrait\nstudio", len("**Portrait")),
        (
            "scene-title-next-word",
            "**Portrait\nstudio",
            len("**Portrait"),
        ),
        (
            "before-later-scene",
            "**Portrait\nstudio\n**Landscape\nfield",
            len("**Portrait\nstudio"),
        ),
        (
            "long-prompt-before-scene",
            f"{'quality, ' * 400}\n**Portrait\nstudio",
            0,
        ),
    )
    for label, initial_text, cursor_position in cases:
        field = harness.add_prompt_workflow(
            alias=f"scene-path-{label}",
            initial_text=initial_text,
        )
        harness.set_source_cursor_position(field, cursor_position)

        typed_text = " abc" if label == "scene-title-next-word" else "abc"
        probe = harness.probe_typed_projection_paths(field, typed_text)

        assert probe.canonical_rebuild_count == 0, (
            label,
            probe.apply_paths,
            probe.incremental_rejection_reasons,
            probe.layout_rejection_reasons,
        )
        assert "full_rebuild" not in probe.apply_paths, (label, probe)
        assert probe.source_text == (
            initial_text[:cursor_position] + typed_text + initial_text[cursor_position:]
        )
        if label == "long-prompt-before-scene":
            assert probe.elapsed_ms < 750.0


def test_real_shell_scene_marker_formation_rebuilds_and_projects_immediately(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A genuine scene-topology transition should take the canonical path."""

    field = harness.add_prompt_workflow(initial_text="")

    probe = harness.probe_typed_projection_paths(field, "**S")

    assert probe.canonical_rebuild_count >= 1
    assert "full_rebuild" in probe.apply_paths
    assert probe.scene_titles == ("S",)
    assert probe.projection_text == "S"


def test_real_shell_scene_typing_coalesces_against_live_previous_source(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Deferred scene-document typing must not compare against stale projection text."""

    initial_text = "quality\n**Portrait\nstudio"
    field = harness.add_prompt_workflow(initial_text=initial_text)
    surface = cast(Any, field.editor)._surface
    delay_projection_update_scheduler(surface)
    harness.set_source_cursor_position(field, 0)

    probe = harness.probe_typed_projection_paths(field, "abc")

    assert probe.canonical_rebuild_count == 0
    assert "full_rebuild" not in probe.apply_paths
    assert probe.source_text == f"abc{initial_text}"
    assert surface.projection_document().source_text == f"abc{initial_text}"


def test_real_shell_scene_deletion_uses_local_path_until_topology_changes(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Scene text deletion should stay local except when it removes the marker."""

    title_field = harness.add_prompt_workflow(
        alias="scene-title-delete",
        initial_text="**Scene\nbody",
    )
    harness.set_source_cursor_position(title_field, len("**Scene"))

    title_probe = harness.probe_projection_key_path(
        title_field,
        key=Qt.Key.Key_Backspace,
        label="backspace",
    )

    assert title_probe.canonical_rebuild_count == 0
    assert title_probe.scene_titles == ("Scen",)
    assert "full_rebuild" not in title_probe.apply_paths

    topology_field = harness.add_prompt_workflow(
        alias="scene-topology-delete",
        initial_text="**S\nbody",
    )
    harness.set_source_cursor_position(topology_field, len("**S"))

    topology_probe = harness.probe_projection_key_path(
        topology_field,
        key=Qt.Key.Key_Backspace,
        label="backspace",
    )

    assert topology_probe.canonical_rebuild_count >= 1
    assert "full_rebuild" in topology_probe.apply_paths
    assert topology_probe.scene_titles == ()
    assert topology_probe.projection_text == "**\nbody"


def test_real_shell_decorated_middle_paste_uses_bounded_canonical_reflow(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A syntax-bearing paste should rebuild semantics without relaying all layout."""

    initial_text = "alpha, (beta:1.20), gamma, delta"
    pasted_text = "pasted, (weighted:1.30), <lora:model:0.80>, "
    cursor_position = initial_text.index("gamma")
    field = harness.add_prompt_workflow(
        alias="decorated-middle-paste",
        initial_text=initial_text,
    )
    harness.set_source_cursor_position(field, cursor_position)

    probe = harness.probe_paste_projection_paths(field, pasted_text)

    expected_text = (
        initial_text[:cursor_position] + pasted_text + initial_text[cursor_position:]
    )
    assert probe.source_text == expected_text
    assert probe.canonical_rebuild_count == 0
    assert probe.apply_paths == ("reflow",)
    assert probe.projection_text

    undo_probe = harness.probe_undo_projection_paths(field)

    assert undo_probe.source_text == initial_text
    assert undo_probe.canonical_rebuild_count == 0
    assert undo_probe.apply_paths == ("checkpoint_restore",)

    redo_probe = harness.probe_redo_projection_paths(field)

    assert redo_probe.source_text == expected_text
    assert redo_probe.canonical_rebuild_count == 0
    assert redo_probe.apply_paths == ("checkpoint_restore",)


def test_real_shell_harness_uses_real_prompt_editor_composition(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Verify the target editor owns normal composed prompt-editor collaborators."""

    field = harness.add_prompt_workflow(initial_text="")
    editor = field.editor

    assert isinstance(getattr(editor, "_surface", None), QWidget)
    assert getattr(editor, "_autocomplete", None) is not None
    assert getattr(editor, "_interaction_controller", None) is not None

    harness.type_text(field, "re")
    harness.wait_until(lambda: bool(harness.autocomplete_gateway.calls))

    assert harness.autocomplete_gateway.calls[-1][0] == "re"
    assert getattr(editor, "_autocomplete_panel", None) is not None


def test_real_shell_same_source_semantics_switch_rebuilds_scene_state(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A same-text semantics switch should remove scenes and publish marker errors."""

    source = "**portrait\n{missing}"
    field = harness.add_prompt_workflow(initial_text=source)
    editor = cast(Any, field.editor)
    harness.wait_until(
        lambda: any(
            token.kind.value == "scene"
            for token in editor._surface.projection_document().tokens
        )
    )

    editor.replaceBaselineSourceDocument(source, WildcardTextDocumentSemantics())
    editor._diagnostics_feature_controller.refresh_now()
    harness.wait_until(
        lambda: all(
            token.kind.value != "scene"
            for token in editor._surface.projection_document().tokens
        )
    )
    harness.wait_until(
        lambda: any(
            diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER
            for diagnostic in editor._diagnostics_feature_controller.snapshot.diagnostics
        )
    )

    assert editor.toPlainText() == source
    assert editor._scene_feature_controller.scene_key_for_source_position(0) is None
    assert (
        editor._document_service.scene_autocomplete_query_at_cursor(
            text=source,
            cursor_position=2,
            has_selection=False,
        )
        is None
    )


def test_real_shell_select_all_highlights_blank_rows_between_projected_paragraphs(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Select-all should paint blank rows created by consecutive hard line breaks."""

    prompt = (
        "alpha,\n\n(small:1.20) breasts, flat chest,\n\n(pale skin:1.20), pointy ears"
    )
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.shell.resize(760, 520)
    harness.focus_editor(field)
    cursor = cast(Any, field.editor).textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len(prompt), QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    selected = harness.capture_state_snapshot(
        field,
        label="select-all-projected-paragraph-breaks",
    )

    expected_blank_ranges = _blank_line_break_ranges(prompt)
    blank_rows = {
        (row.source_start, row.source_end): row
        for row in selected.visible_layout_rows
        if (row.source_start, row.source_end) in expected_blank_ranges
    }

    assert selected.selection_range == (0, len(prompt))
    assert set(blank_rows) == set(expected_blank_ranges)
    for row in blank_rows.values():
        assert row.text == "\n"
        assert _row_has_selection_rect(row, selected.selection_rects)


def test_real_shell_harness_traces_lora_trigger_context_menu() -> None:
    """Trace a real right-click LoRA trigger action through the mounted editor."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess", "twili helmet"),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        trace_before_prepare = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
        )
        assert trace_before_prepare.cached_scheduled_lora_count_before == 1
        assert trace_before_prepare.trigger_action_full_labels == (
            "Trigger words: Midna",
        )
        assert trace_before_prepare.trigger_action_texts == ("Midna",)
        assert "Midna" not in trace_before_prepare.menu_rows
        assert trace_before_prepare.submenu_rows == (
            ("Insert trigger words", ("Midna",)),
        )

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
        assert trace.triggered_action_text == "Midna"
        assert "imp princess, twili helmet" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_trigger_submenu_keeps_all_loras_when_words_exist() -> None:
    """Existing prompt words must not hide scheduled LoRAs or flatten the submenu."""

    control_name = (
        "Illustrious\\Concept\\[Malebolgia] CONTROL BANANA Experiment Illustrious"
    )
    peoples_name = "Anima\\style\\People'sWorks_v10_Animabasev1.0_test3-000008"
    items = (
        replace(
            lora_catalog_item_with_banner(prompt_name=control_name),
            display_name="CONTROL BANANA Experiment Illustrious",
            display_subtitle=None,
            trained_words=("controlbananas",),
        ),
        replace(
            lora_catalog_item_with_banner(prompt_name=peoples_name),
            display_name="People's Works: Anima",
            display_subtitle="v10 Animabase",
            trained_words=("ppw",),
        ),
    )
    prompt = (
        "best quality, controlbananas, ppw, masterpiece\n\n"
        f"<lora:{control_name}:1.00>\n\n<lora:{peoples_name}:1.00>"
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(initial_text=prompt)
        shell_harness.wait_until(
            lambda: (
                _cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="masterpiece",
        )

        assert trace.cached_scheduled_lora_count_before == 2
        assert trace.trigger_action_full_labels == (
            "Trigger words: CONTROL BANANA Experiment Illustrious",
            "Trigger words: People's Works: Anima - v10 Animabase",
        )
        assert len(trace.trigger_action_texts) == 2
        assert trace.submenu_rows == (
            ("Insert trigger words", trace.trigger_action_texts),
        )
        assert not set(trace.trigger_action_texts).intersection(trace.menu_rows)

        inserted = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="masterpiece",
            trigger_lora_action_label=(
                "Trigger words: CONTROL BANANA Experiment Illustrious"
            ),
        )
        assert inserted.source_after.count("controlbananas") == 2
        shell_harness.wait_until(
            lambda: (
                _cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )
        reopened = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="masterpiece",
        )
        assert reopened.trigger_action_full_labels == trace.trigger_action_full_labels
        assert reopened.submenu_rows == (
            ("Insert trigger words", reopened.trigger_action_texts),
        )
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_survives_unrelated_prompt_edit() -> None:
    """Trigger actions should follow the current source after ordinary typing."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        shell_harness.move_cursor_to_end(field)
        shell_harness.type_text(field, ", dramatic lighting")
        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
        )

        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
        assert trace.cached_scheduled_lora_count_before == 1
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_survives_repeated_menu_openings() -> None:
    """Opening and cancelling the menu repeatedly should preserve trigger actions."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        traces = tuple(
            shell_harness.trace_prompt_context_menu(
                field,
                clicked_text="portrait",
            )
            for _index in range(10)
        )

        assert all(
            trace.trigger_action_full_labels == ("Trigger words: Midna",)
            for trace in traces
        )
        assert all(trace.source_after == trace.source_before for trace in traces)
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_selects_last_of_many_actions() -> None:
    """A named action should remain usable at the end of a populated submenu."""

    item_count = 24
    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=f"lora_{index}"),
            display_name=f"LoRA {index}",
            trained_words=(f"trigger {index}",),
        )
        for index in range(item_count)
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text=(
                "portrait, "
                + ", ".join(f"<lora:lora_{index}:1>" for index in range(item_count))
            )
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_lora_action_label=f"Trigger words: LoRA {item_count - 1}",
        )

        assert trace.captured_action_count == item_count
        assert trace.triggered_action_text == f"LoRA {item_count - 1}"
        assert f"trigger {item_count - 1}" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_follows_direct_source_replacement() -> None:
    """Trigger actions should follow source replaced through the public editor API."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        editor.setPlainText("<lora:zelda:1>, landscape")
        shell_harness.process_events(cycles=12)
        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="landscape",
        )

        assert trace.trigger_action_full_labels == ("Trigger words: Zelda",)
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_can_insert_two_scheduled_loras_in_sequence() -> (
    None
):
    """Inserting one LoRA's words should leave the other LoRA action usable."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, <lora:zelda:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        first = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_lora_action_label="Trigger words: Midna",
        )
        second = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="port",
            trigger_lora_action_label="Trigger words: Zelda",
        )

        assert first.triggered_action_text == "Midna"
        assert second.triggered_action_text == "Zelda"
        assert "imp princess" in second.source_after
        assert "wise princess" in second.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_does_not_split_clicked_prompt_word() -> None:
    """Trigger insertion should preserve the prompt token used to open the menu."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        assert "portrait" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_rejects_action_after_source_changes() -> None:
    """An action captured for an old source revision should not mutate new source."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        replacement = "unrelated replacement prompt"
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
            before_trigger_lora_action=lambda: editor.setPlainText(replacement),
        )

        assert trace.source_after == replacement
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_recovers_after_explicit_rewarm() -> None:
    """Explicitly warming changed source should restore remaining LoRA actions."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, <lora:zelda:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_lora_action_label="Trigger words: Midna",
        )

        cast(
            Any,
            editor,
        )._lora_trigger_word_controller.prewarm_current_source()
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="port",
            trigger_lora_action_label="Trigger words: Zelda",
        )

        assert trace.triggered_action_text == "Zelda"
        assert "wise princess" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_recovers_remaining_action_after_workflow_switch() -> (
    None
):
    """Switching away and back should restore actions after a trigger insertion."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, <lora:zelda:1>, portrait"
        )
        shell_harness.wait_until(
            lambda: (
                _cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )
        first = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_lora_action_label="Trigger words: Midna",
        )

        returned_field = shell_harness.workflow_round_trip(field)
        trace = shell_harness.trace_prompt_context_menu(
            returned_field,
            clicked_text="port",
            trigger_lora_action_label="Trigger words: Zelda",
        )

        assert first.triggered_action_text == "Midna"
        assert trace.triggered_action_text == "Zelda"
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_survives_workflow_round_trip() -> None:
    """Prepared trigger actions should survive switching away and back."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        shell_harness.wait_until(
            lambda: (
                _cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )

        returned_field = shell_harness.workflow_round_trip(field)
        trace = shell_harness.trace_prompt_context_menu(
            returned_field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        assert trace.triggered_action_text == "Midna"
        assert "imp princess" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_keeps_workflow_contexts_isolated() -> None:
    """Each workflow should expose actions for its own scheduled LoRA."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        midna_field = shell_harness.add_prompt_workflow(
            "midna-workflow",
            initial_text="<lora:midna:1>, portrait",
        )
        zelda_field = shell_harness.add_prompt_workflow(
            "zelda-workflow",
            initial_text="<lora:zelda:1>, landscape",
        )
        shell_harness.wait_until(
            lambda: (
                _cached_scheduled_loras(
                    zelda_field.editor,
                    zelda_field.editor.toPlainText(),
                )
                is not None
            )
        )

        zelda_trace = shell_harness.trace_prompt_context_menu(
            zelda_field,
            clicked_text="landscape",
        )
        shell_harness.activate_workflow("midna-workflow")
        midna_field = shell_harness.prompt_field("midna-workflow")
        shell_harness.wait_until(
            lambda: (
                _cached_scheduled_loras(
                    midna_field.editor,
                    midna_field.editor.toPlainText(),
                )
                is not None
            )
        )
        midna_trace = shell_harness.trace_prompt_context_menu(
            midna_field,
            clicked_text="portrait",
        )

        assert zelda_trace.trigger_action_full_labels == ("Trigger words: Zelda",)
        assert midna_trace.trigger_action_full_labels == ("Trigger words: Midna",)
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_returns_after_undo() -> None:
    """Undoing trigger insertion should make the trigger action available again."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        original_text = editor.toPlainText()
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        editor.undo()
        shell_harness.process_events(cycles=10)
        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
        )

        assert editor.toPlainText() == original_text
        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
    finally:
        shell_harness.close()


def test_real_shell_inline_lora_trigger_probe_exposes_prepared_action() -> None:
    """Right-clicking an inline LoRA token should expose its trigger action."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,))
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.probe_inline_lora_context_menu(field)

        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
    finally:
        shell_harness.close()


def test_real_shell_saved_segment_menu_refreshes_after_diffusion_model_projection() -> (
    None
):
    """A prompt built before its diffusion model should receive current save scopes."""

    model = _model_item(
        kind="diffusion_models",
        backend_value="Anima/hassakuAnima_v11.safetensors",
        display_name="Hassaku (Anima)",
        display_subtitle="v1.1",
        base_model="Anima",
    )
    catalog = _ModelCatalog(
        {"diffusion_models": (model,)},
        memory_cold=True,
    )
    shell_harness = RealShellPromptEditorHarness(
        user_preset_service=UserPresetService(_MemoryPresetRepository()),
        model_catalog_service=catalog,
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text="portrait, detailed lighting",
            model_node_type="SimpleSyrup.SimpleLoadAnima",
            model_field_key="diffusion_model",
            model_value="Anima\\hassakuAnima_v11.safetensors",
        )
        panel = shell_harness.shell.editor_panels[field.workflow.workflow_id]
        shell_harness.wait_until(
            lambda: (
                panel.active_model_snapshot_controller.snapshot.status.readiness
                is CatalogSnapshotReadiness.WARM
            )
        )
        target = shell_harness.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.SelectAll)
        shell_harness.process_events(cycles=8)

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
        )
        segment_snapshot = cast(Any, field.editor)._segment_preset_controller.snapshot

        assert "Save segment as..." in trace.menu_rows
        assert segment_snapshot.save_state.ready
        assert [
            render_application_text(scope.title)
            for scope in segment_snapshot.save_state.save_scopes
        ] == [
            "Global",
            "Anima",
            "Diffusion model",
        ]
        assert [
            render_application_text(scope.full_label)
            for scope in segment_snapshot.save_state.save_scopes
        ] == [
            "Global",
            "Base model: Anima",
            "Diffusion model: Hassaku (Anima) - v1.1",
        ]
        assert catalog.durable_requests == ["diffusion_models"]
    finally:
        shell_harness.close()


def test_real_shell_empty_entry_reprojection_preserves_anima_segment_scopes() -> None:
    """Startup reuse with empty entries must retain cube-state model context."""

    model = _model_item(
        kind="diffusion_models",
        backend_value="Anima/hassakuAnima_v11.safetensors",
        display_name="Hassaku (Anima)",
        display_subtitle="v1.1",
        base_model="Anima",
    )
    catalog = _ModelCatalog(
        {"diffusion_models": (model,)},
        memory_cold=True,
    )
    shell_harness = RealShellPromptEditorHarness(
        user_preset_service=UserPresetService(_MemoryPresetRepository()),
        model_catalog_service=catalog,
    )
    try:
        field = shell_harness.add_anima_prompt_workflow(
            initial_text="portrait, detailed lighting",
            model_value="Anima\\hassakuAnima_v11.safetensors",
        )
        panel = shell_harness.shell.editor_panels[field.workflow.workflow_id]
        shell_harness.wait_until(
            lambda: (
                shell_harness.probe_prompt_segment_scopes(
                    field
                ).active_snapshot_readiness
                == "warm"
            )
        )
        workflow = shell_harness.shell.workflow_session_service.get_workflow(
            field.workflow.workflow_id
        )
        assert workflow is not None

        panel.load_all_cubes(
            [],
            cube_states=workflow.cubes,
            stack_order=workflow.stack_order,
        )
        shell_harness.process_events(cycles=20)

        probe = shell_harness.probe_prompt_segment_scopes(field)
        assert probe.candidate_kind == "diffusion_models"
        assert probe.candidate_value == "Anima/hassakuAnima_v11.safetensors"
        assert probe.active_snapshot_readiness == "warm"
        assert probe.active_snapshot_item_value is not None
        assert probe.active_snapshot_item_value.replace("\\", "/") == (
            "Anima/hassakuAnima_v11.safetensors"
        )
        assert probe.editor_scope_titles == (
            "Global",
            "Anima",
            "Diffusion model",
        )
        dialog_probe = shell_harness.probe_prompt_segment_dialog(
            field,
            selected_text="portrait, detailed lighting",
        )
        assert dialog_probe.title == "Save segment"
        assert dialog_probe.scope_full_labels == (
            "Global",
            "Base model: Anima",
            "Diffusion model: Hassaku (Anima) - v1.1",
        )
    finally:
        shell_harness.close()


def test_real_shell_saved_segment_menu_allows_global_save_without_model() -> None:
    """Selected prompt text should remain globally saveable without model context."""

    shell_harness = RealShellPromptEditorHarness(
        user_preset_service=UserPresetService(_MemoryPresetRepository()),
    )
    try:
        field = shell_harness.add_prompt_workflow(initial_text="portrait")
        target = shell_harness.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.SelectAll)
        shell_harness.process_events(cycles=8)

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
        )
        segment_snapshot = cast(Any, field.editor)._segment_preset_controller.snapshot

        assert "Save segment as..." in trace.menu_rows
        assert segment_snapshot.save_state.ready
        assert [scope.title for scope in segment_snapshot.save_state.save_scopes] == [
            "Global"
        ]
    finally:
        shell_harness.close()


def test_real_shell_harness_times_lora_trigger_context_menu_open() -> None:
    """Bound prompt context-menu CPU work while many trigger rows are populated."""

    item_count = 50
    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=f"midna_{index}"),
            display_name=f"Midna {index}",
            trained_words=(f"imp princess {index}",),
        )
        for index in range(item_count)
    )
    shell_harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items)
    )
    try:
        field = shell_harness.add_prompt_workflow(
            initial_text=(
                "portrait, "
                + ", ".join(f"<lora:midna_{index}:1>" for index in range(item_count))
            )
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: _cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.trace_prompt_context_menu(
            field,
            clicked_text="portrait",
            populate_lazy_submenus=False,
        )

        assert trace.captured_action_count == 0
        assert trace.captured_submenu_row_count == 0
        assert ("Insert trigger words", ()) in trace.submenu_rows
        assert trace.cached_scheduled_lora_count_before == item_count
        assert trace.event_dispatch_elapsed_ms < 80.0
        assert trace.event_dispatch_elapsed_ms > 0.0
        assert trace.menu_population_elapsed_ms >= 0.0
        assert trace.menu_exec_elapsed_ms >= 0.0
    finally:
        shell_harness.close()


def test_real_shell_harness_captures_headless_editor_and_popup_state(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Capture shell/editor/popup diagnostics without screenshot dependencies."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    snapshot = harness.capture_state_snapshot(field, label="after-re")

    assert snapshot.geometries["shell"] is not None
    assert snapshot.geometries["editor"] is not None
    assert snapshot.popup_widget_exists
    assert snapshot.popup_state_visible
    assert snapshot.popup_visual_visible
    assert snapshot.autocomplete_gateway_calls


def test_real_shell_harness_can_disable_hot_path_owner_tracing() -> None:
    """Primary performance probes should avoid deep per-owner trace overhead."""

    harness = RealShellPromptEditorHarness(observe_owner_calls=False)
    try:
        field = harness.add_prompt_workflow(initial_text="")
        harness.type_text(field, "fast exact input")
        snapshot = harness.capture_state_snapshot(field, label="untraced")

        assert snapshot.source_text == "fast exact input"
        assert snapshot.recent_observed_events == ()
        assert snapshot.observed_event_end_index == 0
        assert not harness.invariant_violations(snapshot)
    finally:
        harness.close()


def test_real_shell_abuse_driver_measures_exact_untraced_input(tmp_path: Path) -> None:
    """The low-overhead driver should measure the production-mounted key route."""

    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "driver-smoke",
            "alpha, ",
            (
                PromptAbuseAction(
                    "type",
                    value="xyz",
                    expected_source="alpha, xyz",
                    expected_cursor_position=len("alpha, xyz"),
                ),
            ),
            "alpha, xyz",
            cursor_position=len("alpha, "),
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert len(result.dispatch_samples) == 3
    assert all(sample.source_exact for sample in result.dispatch_samples)
    assert all(
        sample.visible_source_current_after_dispatch is True
        for sample in result.dispatch_samples
    )
    assert all(
        sample.visible_caret_current_after_dispatch is True
        for sample in result.dispatch_samples
    )
    assert result.latency.maximum_ms > 0.0
    assert result.deep_trace_enabled is False


def test_real_shell_abuse_driver_measures_each_lifecycle_transition(
    tmp_path: Path,
) -> None:
    """Round-trip torture should budget each visible switch as one operation."""

    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "lifecycle-step-timing",
            "alpha",
            (
                PromptAbuseAction(
                    "workflow_round_trip",
                    expected_source="alpha",
                    expected_cursor_position=0,
                ),
                PromptAbuseAction(
                    "canvas_round_trip",
                    expected_source="alpha",
                    expected_cursor_position=0,
                ),
            ),
            "alpha",
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert [sample.label for sample in result.dispatch_samples] == [
        "workflow:switch-away",
        "workflow:return",
        "canvas:switch-away",
        "canvas:return",
    ]
    assert all(sample.dispatch_ms > 0.0 for sample in result.dispatch_samples)


def test_real_shell_abuse_driver_checks_projection_ownership_after_each_action(
    tmp_path: Path,
) -> None:
    """A single mode switch should immediately retain canonical owner agreement."""

    source = "(cat:1.05), suffix"
    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "single-raw-mode-owner-check",
            source,
            (
                PromptAbuseAction(
                    "display_mode",
                    value="raw",
                    expected_source=source,
                    expected_cursor_position=len(source),
                ),
            ),
            source,
            cursor_position=len(source),
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert len(result.dispatch_samples) == 1
    sample = result.dispatch_samples[0]
    assert sample.active_projection_ownership_valid is True
    assert sample.layout_projection_ownership_valid is True


def test_real_shell_abuse_driver_keeps_every_wrapping_keystroke_visible(
    tmp_path: Path,
) -> None:
    """A wrap transition must never leave live source without a visual owner."""

    typed_text = "sfhjaklfhj jasfklaj flaosjufioewjflafiws"
    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "wrapping-visual-owner",
            "",
            (
                PromptAbuseAction(
                    "type",
                    value=typed_text,
                    expected_source=typed_text,
                    expected_cursor_position=len(typed_text),
                ),
            ),
            typed_text,
            cursor_position=0,
            viewport_size=(120, 240),
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert all(
        sample.visible_source_current_after_dispatch is True
        for sample in result.dispatch_samples
    )
    assert all(
        sample.visible_caret_current_after_dispatch is True
        for sample in result.dispatch_samples
    )


def test_real_shell_harness_reports_stale_visible_ghost_owner_state(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect paint-visible ghost state even when autocomplete owners are cleared."""

    field = harness.add_prompt_workflow(initial_text="backpack")
    harness.move_cursor_to_end(field)
    editor = field.editor
    surface = cast(Any, getattr(editor, "_surface"))
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("backpack"),
            suffix_text=" basket",
        )
    )
    stale_preview_document = cast(Any, surface)._layout.projection_document

    surface.set_autocomplete_preview_state(None)
    cast(Any, surface)._layout.set_projection(
        stale_preview_document,
        prompt_document_view=cast(Any, surface)._document_view,
    )
    snapshot = harness.capture_state_snapshot(
        field,
        label="forced-stale-visible-ghost-owner-state",
    )

    violations = harness.invariant_violations(snapshot)

    assert snapshot.autocomplete_preview_active is False
    assert snapshot.autocomplete_ghost_paint_visible_by_owner_state is True
    assert "backpack basket" in snapshot.layout_projection_text
    assert "autocomplete_ghost_paint_visible_without_preview_state" in violations
    assert "layout_projection_preview_leaked_without_preview_state" in violations
    assert "layout_not_restored_to_base_projection_document" in violations


def test_real_shell_harness_reports_headless_editor_common_sense_violations(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Prove broad headless editor invariants fail on deliberately bad owner state."""

    field = harness.add_prompt_workflow(initial_text="alpha\nbeta")
    cursor = cast(Any, field.editor).textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    snapshot = harness.capture_state_snapshot(
        field,
        label="common-sense-invariant-baseline",
    )

    selected_text_mismatch = harness.invariant_violations(
        replace(snapshot, selected_text="wrong")
    )
    empty_selection_with_rects = harness.invariant_violations(
        replace(
            snapshot, selection_range=(0, 0), selection_rects=((0.0, 0.0, 8.0, 16.0),)
        )
    )
    nonempty_selection_without_rects = harness.invariant_violations(
        replace(snapshot, selection_rects=())
    )
    invalid_selection_rect = harness.invariant_violations(
        replace(snapshot, selection_rects=((0.0, 0.0, -1.0, 16.0),))
    )
    out_of_bounds_selection_rect = harness.invariant_violations(
        replace(
            snapshot,
            selection_rects=(
                (
                    snapshot.layout_text_width + 999.0,
                    0.0,
                    8.0,
                    16.0,
                ),
            ),
        )
    )
    caret_outside_viewport_snapshot = replace(
        snapshot,
        selected_text="",
        selected_source_text="",
        selection_range=(snapshot.cursor_position, snapshot.cursor_position),
        selection_rects=(),
        caret_rect=(99999.0, 99999.0, 1.0, 16.0),
        caret_rect_intersects_viewport=False,
    )
    caret_outside_viewport = harness.transition_invariant_violations(
        action_name="caret",
        before=snapshot,
        after=caret_outside_viewport_snapshot,
    )
    scroll_out_of_range = harness.invariant_violations(
        replace(
            snapshot,
            scroll_values={**snapshot.scroll_values, "editor_vertical": 99999},
        )
    )
    empty_selection_snapshot = replace(snapshot, selection_range=(0, 0))
    cache_document_mismatch = harness.invariant_violations(
        replace(
            empty_selection_snapshot,
            paint_cache_key_present=True,
            paint_cache_projection_document_identity_matches_layout=False,
        )
    )
    selected_cache_document_mismatch = harness.invariant_violations(
        replace(
            snapshot,
            paint_cache_key_present=True,
            paint_cache_projection_document_identity_matches_layout=False,
        )
    )
    cache_source_revision_mismatch = harness.invariant_violations(
        replace(
            empty_selection_snapshot,
            paint_cache_key_present=True,
            paint_cache_source_revision=-1,
        )
    )
    stale_insertion_overlay = harness.invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_present=True,
            transient_insertion_overlay_valid=False,
        )
    )
    insertion_overlay_range = harness.invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_source_range=(0, len(snapshot.source_text) + 1),
        )
    )
    missing_insertion_repaint_rect = harness.invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_present=True,
            transient_insertion_overlay_valid=True,
            transient_insertion_overlay_viewport_rect=(0.0, 0.0, 12.0, 18.0),
            transient_insertion_overlay_repaint_rect=None,
        )
    )
    invalid_insertion_repaint_rect = harness.invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_repaint_rect=(0.0, 0.0, float("nan"), 18.0),
        )
    )
    broad_insertion_repaint_rect = harness.invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_repaint_rect=(0.0, 0.0, 99999.0, 18.0),
        )
    )
    missing_deletion_erase_rects = harness.invariant_violations(
        replace(
            snapshot,
            transient_deletion_overlay_present=True,
            transient_deletion_overlay_valid=True,
            transient_deletion_overlay_viewport_rects=((0.0, 0.0, 12.0, 18.0),),
            transient_deletion_overlay_erase_rects=(),
            transient_deletion_overlay_repaint_rect=(0.0, 0.0, 12.0, 18.0),
        )
    )
    invalid_deletion_erase_rect = harness.invariant_violations(
        replace(
            snapshot,
            transient_deletion_overlay_erase_rects=((0.0, 0.0, -1.0, 18.0),),
        )
    )
    broad_deletion_repaint_rect = harness.invariant_violations(
        replace(
            snapshot,
            transient_deletion_overlay_repaint_rect=(0.0, 0.0, 12.0, 99999.0),
        )
    )
    undo_depth_mismatch = harness.invariant_violations(
        replace(
            snapshot,
            undo_available=True,
            undo_depth=0,
        )
    )
    redo_depth_mismatch = harness.invariant_violations(
        replace(
            snapshot,
            redo_available=True,
            redo_depth=0,
        )
    )
    undo_group_conflict = harness.invariant_violations(
        replace(
            snapshot,
            undo_typing_group_active=True,
            undo_delete_group_active=True,
        )
    )
    undo_depth_exceeds_max = harness.invariant_violations(
        replace(snapshot, undo_depth=snapshot.undo_max_depth + 1)
    )
    redo_depth_exceeds_max = harness.invariant_violations(
        replace(snapshot, redo_depth=snapshot.redo_max_depth + 1)
    )
    dangling_pending_undo = harness.invariant_violations(
        replace(
            snapshot,
            undo_pending_state_present=True,
            undo_edit_block_depth=0,
        )
    )
    typing_group_without_cursor = harness.invariant_violations(
        replace(
            snapshot,
            undo_typing_group_active=True,
            undo_edit_block_depth=1,
            undo_pending_state_present=True,
            undo_typing_group_last_cursor_position=None,
        )
    )
    typing_group_cursor_out_of_bounds = harness.invariant_violations(
        replace(
            snapshot,
            undo_typing_group_active=True,
            undo_edit_block_depth=1,
            undo_pending_state_present=True,
            undo_typing_group_last_cursor_position=len(snapshot.source_text) + 1,
        )
    )
    stale_typing_group_cursor = harness.invariant_violations(
        replace(
            snapshot,
            undo_typing_group_active=False,
            undo_typing_group_last_cursor_position=1,
        )
    )
    delete_group_without_key = harness.invariant_violations(
        replace(
            snapshot,
            undo_delete_group_active=True,
            undo_edit_block_depth=1,
            undo_pending_state_present=True,
            undo_delete_group_key=None,
        )
    )
    stale_delete_group_key = harness.invariant_violations(
        replace(
            snapshot,
            undo_delete_group_active=False,
            undo_delete_group_key=1,
        )
    )
    invalid_layout_width = harness.invariant_violations(
        replace(snapshot, layout_content_width=float("nan"))
    )
    invalid_layout_height = harness.invariant_violations(
        replace(snapshot, layout_content_height=-1.0)
    )
    unresolved_caret_token = harness.invariant_violations(
        replace(
            snapshot,
            caret_token_id="missing-token",
            caret_token_id_resolves=False,
        )
    )
    missing_caret_stops = harness.invariant_violations(
        replace(snapshot, caret_map_stop_count=0)
    )
    invalid_preferred_x = harness.invariant_violations(
        replace(snapshot, caret_preferred_x=float("inf"))
    )
    oversized_preferred_x = harness.invariant_violations(
        replace(snapshot, caret_preferred_x=snapshot.layout_text_width + 999.0)
    )
    invalid_caret_rect_override = harness.invariant_violations(
        replace(snapshot, caret_rect_override=(0.0, 0.0, -1.0, 16.0))
    )
    out_of_bounds_caret_rect_override = harness.invariant_violations(
        replace(
            snapshot,
            caret_rect_override=(
                snapshot.layout_text_width + 999.0,
                0.0,
                1.0,
                16.0,
            ),
        )
    )
    autocomplete_selected_index_out_of_bounds = harness.invariant_violations(
        replace(
            snapshot,
            autocomplete_has_active_session=True,
            autocomplete_presenter_panel_visible=True,
            popup_state_visible=True,
            popup_global_rect=(10, 10, 100, 100),
            autocomplete_session_lifecycle="active",
            autocomplete_session_mode="tag",
            autocomplete_session_selected_index=99,
            autocomplete_session_suggestions=("alpha",),
            autocomplete_session_word_start=0,
            autocomplete_session_word_end=snapshot.cursor_position,
        )
    )
    autocomplete_word_range_out_of_bounds = harness.invariant_violations(
        replace(
            snapshot,
            autocomplete_has_active_session=True,
            autocomplete_presenter_panel_visible=True,
            autocomplete_session_lifecycle="active",
            autocomplete_session_mode="tag",
            autocomplete_session_selected_index=0,
            autocomplete_session_suggestions=("alpha",),
            autocomplete_session_word_start=0,
            autocomplete_session_word_end=len(snapshot.source_text) + 1,
        )
    )
    autocomplete_word_end_mismatch = harness.invariant_violations(
        replace(
            snapshot,
            autocomplete_has_active_session=True,
            autocomplete_presenter_panel_visible=True,
            autocomplete_session_lifecycle="active",
            autocomplete_session_mode="tag",
            autocomplete_session_selected_index=0,
            autocomplete_session_suggestions=("alpha",),
            autocomplete_session_word_start=0,
            autocomplete_session_word_end=0,
            cursor_position=len(snapshot.source_text),
        )
    )
    autocomplete_popup_missing_rect = harness.invariant_violations(
        replace(
            snapshot,
            autocomplete_has_active_session=True,
            autocomplete_presenter_panel_visible=True,
            popup_state_visible=True,
            popup_global_rect=None,
            autocomplete_session_lifecycle="active",
            autocomplete_session_mode="tag",
            autocomplete_session_selected_index=0,
            autocomplete_session_suggestions=("alpha",),
            autocomplete_session_word_start=0,
            autocomplete_session_word_end=snapshot.cursor_position,
        )
    )
    autocomplete_popup_unanchored = harness.invariant_violations(
        replace(
            snapshot,
            autocomplete_has_active_session=True,
            autocomplete_presenter_panel_visible=True,
            popup_state_visible=True,
            popup_global_rect=(99999, 99999, 100, 100),
            autocomplete_session_lifecycle="active",
            autocomplete_session_mode="tag",
            autocomplete_session_selected_index=0,
            autocomplete_session_suggestions=("alpha",),
            autocomplete_session_word_start=0,
            autocomplete_session_word_end=snapshot.cursor_position,
        )
    )
    assert "selected_text_source_slice_mismatch" in selected_text_mismatch
    assert "selection_rects_present_for_empty_selection" in empty_selection_with_rects
    assert (
        "selection_rects_missing_for_nonempty_selection"
        in nonempty_selection_without_rects
    )
    assert any(
        violation.startswith("selection_rect_invalid")
        for violation in invalid_selection_rect
    )
    assert any(
        violation.startswith("selection_rect_outside_layout")
        for violation in out_of_bounds_selection_rect
    )
    assert "caret_rect_outside_viewport_after_settle" in caret_outside_viewport
    assert any(
        violation.startswith("vertical_scroll_value_out_of_range")
        for violation in scroll_out_of_range
    )
    assert (
        "paint_cache_projection_document_identity_mismatch" in cache_document_mismatch
    )
    assert (
        "paint_cache_projection_document_identity_mismatch"
        not in selected_cache_document_mismatch
    )
    assert any(
        violation.startswith("paint_cache_source_revision_mismatch")
        for violation in cache_source_revision_mismatch
    )
    assert "stale_transient_insertion_overlay" in stale_insertion_overlay
    assert any(
        violation.startswith("transient_insertion_overlay_range_out_of_bounds")
        for violation in insertion_overlay_range
    )
    assert (
        "transient_insertion_overlay_repaint_rect_missing"
        in missing_insertion_repaint_rect
    )
    assert any(
        violation.startswith("transient_insertion_overlay_repaint_rect_invalid")
        for violation in invalid_insertion_repaint_rect
    )
    assert any(
        violation.startswith("transient_insertion_overlay_repaint_rect_too_broad")
        for violation in broad_insertion_repaint_rect
    )
    assert (
        "transient_deletion_overlay_erase_rects_missing" in missing_deletion_erase_rects
    )
    assert any(
        violation.startswith("transient_deletion_overlay_erase_rect_invalid")
        for violation in invalid_deletion_erase_rect
    )
    assert any(
        violation.startswith("transient_deletion_overlay_repaint_rect_too_broad")
        for violation in broad_deletion_repaint_rect
    )
    assert any(
        violation.startswith("undo_availability_depth_mismatch")
        for violation in undo_depth_mismatch
    )
    assert any(
        violation.startswith("redo_availability_depth_mismatch")
        for violation in redo_depth_mismatch
    )
    assert "undo_typing_and_delete_groups_both_active" in undo_group_conflict
    assert any(
        violation.startswith("undo_depth_exceeds_max")
        for violation in undo_depth_exceeds_max
    )
    assert any(
        violation.startswith("redo_depth_exceeds_max")
        for violation in redo_depth_exceeds_max
    )
    assert any(
        violation.startswith("undo_pending_state_edit_block_mismatch")
        for violation in dangling_pending_undo
    )
    assert "undo_typing_group_missing_last_cursor" in typing_group_without_cursor
    assert any(
        violation.startswith("undo_typing_group_last_cursor_out_of_bounds")
        for violation in typing_group_cursor_out_of_bounds
    )
    assert (
        "undo_typing_group_last_cursor_without_active_group"
        in stale_typing_group_cursor
    )
    assert "undo_delete_group_missing_key" in delete_group_without_key
    assert "undo_delete_group_key_without_active_group" in stale_delete_group_key
    assert any(
        violation.startswith("layout_content_width_invalid")
        for violation in invalid_layout_width
    )
    assert "layout_content_height_invalid:-1.0" in invalid_layout_height
    assert "caret_token_id_unresolved:missing-token" in unresolved_caret_token
    assert "caret_map_has_no_stops" in missing_caret_stops
    assert any(
        violation.startswith("caret_preferred_x_not_finite")
        for violation in invalid_preferred_x
    )
    assert any(
        violation.startswith("caret_preferred_x_outside_layout_width")
        for violation in oversized_preferred_x
    )
    assert any(
        violation.startswith("caret_rect_override_invalid")
        for violation in invalid_caret_rect_override
    )
    assert any(
        violation.startswith("caret_rect_override_outside_layout")
        for violation in out_of_bounds_caret_rect_override
    )
    assert any(
        violation.startswith("autocomplete_selected_index_out_of_bounds")
        for violation in autocomplete_selected_index_out_of_bounds
    )
    assert any(
        violation.startswith("autocomplete_session_word_range_out_of_bounds")
        for violation in autocomplete_word_range_out_of_bounds
    )
    assert any(
        violation.startswith("autocomplete_session_word_end_not_at_cursor")
        for violation in autocomplete_word_end_mismatch
    )
    assert "visible_popup_missing_global_rect" in autocomplete_popup_missing_rect
    assert any(
        violation.startswith("visible_popup_not_anchored_to_editor")
        for violation in autocomplete_popup_unanchored
    )


def test_real_shell_harness_detects_non_uniform_visible_row_shift(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect mixed row movement without treating uniform scroll as a paint bug."""

    field = harness.add_prompt_workflow(initial_text="alpha\nbeta\ngamma")
    snapshot = harness.capture_state_snapshot(field, label="row-shift-baseline")
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

    uniform_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=uniform_after,
    )
    mixed_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=mixed_after,
    )

    assert not any(
        violation.startswith("non_uniform_visible_row_shift")
        for violation in uniform_violations
    )
    assert any(
        violation.startswith("non_uniform_visible_row_shift")
        for violation in mixed_violations
    )


def test_real_shell_harness_detects_stable_space_geometry_shift(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect editor chrome movement when a stable space edit preserves layout."""

    field = harness.add_prompt_workflow(initial_text="alpha\nbeta")
    snapshot = harness.capture_state_snapshot(field, label="geometry-baseline")
    before = replace(
        snapshot,
        source_text="alphabeta",
        layout_line_count=2,
        layout_content_width=240.0,
        layout_content_height=32.0,
        geometries={
            **snapshot.geometries,
            "editor": (10, 8, 360, 120),
            "viewport": (0, 0, 347, 114),
        },
    )
    stable_after = replace(
        before,
        source_text="alpha beta",
    )
    shifted_after = replace(
        stable_after,
        geometries={
            **before.geometries,
            "editor": (10, 8, 360, 122),
            "viewport": (0, 0, 347, 116),
        },
    )

    stable_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=stable_after,
    )
    shifted_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=shifted_after,
    )

    assert not any(
        violation.startswith("stable_single_character_geometry_shift")
        for violation in stable_violations
    )
    assert any(
        violation.startswith("stable_single_character_geometry_shift")
        for violation in shifted_violations
    )


def test_real_shell_harness_detects_stable_space_content_height_shift(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect same-line-count content height changes after one space edit."""

    field = harness.add_prompt_workflow(initial_text="alphabeta\ngamma\ndelta")
    snapshot = harness.capture_state_snapshot(field, label="height-baseline")
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
    stable_after = replace(
        before,
        source_text="alpha beta\ngamma\ndelta",
    )
    shifted_after = replace(
        stable_after,
        layout_content_height=50.0,
        visible_layout_rows=(
            replace(rows[0], height=18.0),
            replace(rows[1], document_top=18.0, viewport_top=18.0),
            replace(rows[2], document_top=34.0, viewport_top=34.0),
        ),
    )

    stable_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=stable_after,
    )
    shifted_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=shifted_after,
    )

    assert not any(
        violation.startswith("stable_single_character_content_height_shift")
        for violation in stable_violations
    )
    assert any(
        violation.startswith("stable_single_character_content_height_shift")
        for violation in shifted_violations
    )


def test_real_shell_harness_detects_non_uniform_visible_fragment_shift(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect uneven visible text-fragment movement after a stable space edit."""

    field = harness.add_prompt_workflow(initial_text="alphabeta\ngamma\ndelta")
    snapshot = harness.capture_state_snapshot(field, label="fragment-baseline")
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

    stable_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=stable_after,
    )
    mixed_violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=mixed_after,
    )

    assert not any(
        violation.startswith("non_uniform_visible_fragment_shift")
        for violation in stable_violations
    )
    assert any(
        violation.startswith("non_uniform_visible_fragment_shift")
        for violation in mixed_violations
    )


def test_real_shell_harness_detects_projection_metrics_contract_violations(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect row, fragment, content, shell, and caret metric drift."""

    field = harness.add_prompt_workflow(initial_text="alpha")
    snapshot = harness.capture_state_snapshot(field, label="metrics-baseline")
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

    stable_violations = harness.invariant_violations(before)
    shifted_violations = harness.invariant_violations(shifted)

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


def test_real_shell_harness_allows_newline_only_rows_without_text_fragments(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Treat hard-break-only layout rows as valid without an ink baseline."""

    field = harness.add_prompt_workflow(initial_text="alpha")
    snapshot = harness.capture_state_snapshot(field, label="blank-row-baseline")
    blank_row = replace(
        _visible_row(99, document_top=20.0, viewport_top=20.0, text="\n"),
        expected_height=16.0,
        expected_text_baseline=32.0,
    )
    with_blank_row = replace(
        snapshot,
        visible_layout_rows=snapshot.visible_layout_rows + (blank_row,),
    )

    violations = harness.invariant_violations(with_blank_row)

    assert "text_only_row_baseline_mismatch:99" not in violations


def test_real_shell_harness_detects_transient_deletion_overerase(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect deletion erase rects that overlap text outside the deleted range."""

    field = harness.add_prompt_workflow(initial_text="alphabeta")
    snapshot = harness.capture_state_snapshot(field, label="deletion-baseline")
    overerased = replace(
        snapshot,
        transient_deletion_overlay_valid=True,
        transient_deletion_overlay_source_range=(5, 6),
        transient_deletion_overlay_erase_rects=((0.0, 0.0, 50.0, 16.0),),
        visible_text_fragments=(
            _visible_text_fragment(
                0,
                0,
                5,
                baseline=12.0,
                text="alpha",
                rect=(0.0, 0.0, 38.0, 16.0),
            ),
            _visible_text_fragment(
                1,
                5,
                6,
                baseline=12.0,
                text="b",
                rect=(40.0, 0.0, 8.0, 16.0),
            ),
        ),
    )

    violations = harness.invariant_violations(overerased)

    assert any(
        violation.startswith("transient_deletion_overerase_left")
        for violation in violations
    )
    assert "transient_deletion_overerase_neighbor:0" in violations


def test_real_shell_harness_keeps_pale_skin_space_edit_layout_stable() -> None:
    """Keep the reported narrow prompt space edit from moving stable rows."""

    prompt_name = r"Anima\style\People'sWorks_v10_Animabasev1.0_test3-000008"
    prompt = "\n".join(
        (
            "best quality, score_7, ppw, masterpiece, very aesthetic, "
            "character portrait, faux figurine, garden,",
            "1girl, (mature female:1.10), floating, parted lips, contrapposto, "
            "holding helix spear, planted spear, skinny,",
            "(small:1.20) breasts, flat chest, sparkling blue sash, "
            "sparkling blue bralette,",
            "(pale skin:1.20),",
            "backpack basket, pointy ears, sharp teeth, too many rabbits, "
            "backlighting,",
            "empty eyes, sharp teeth, too many rabbits, backlighting,",
            "white dress, wrathful, pink bridal garter, sparkling dress,",
            "glowing red eyes, long white hair, swept bangs, elegant seductive pose, "
            "twintails, white eyebrows, pink hair ribbon, see-through dress, "
            "iridescent belt, spaghetti strap, short white oni horns,",
            "convenient censoring, barefoot, cloudy sky, blue sky, golden hour, "
            "night sky, column, black and white roses, halo behind head,",
            f"<lora:{prompt_name}:1.00>",
        )
    )
    thumbnail_repository = RecordingThumbnailAssetRepository()
    harness = RealShellPromptEditorHarness(
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(prompt_name=prompt_name),)
        ),
        thumbnail_asset_repository=thumbnail_repository,
    )
    try:
        field = harness.add_prompt_workflow(initial_text=prompt)
        harness.shell.resize(412, 1300)
        panel = harness.shell.editor_panels[field.workflow.workflow_id]
        panel.setMinimumWidth(412)
        panel.resize(412, 1220)
        field.editor.setManualScrollHeight(1200)
        harness.process_events(cycles=40)
        insertion_position = prompt.index("(pale skin:1.20),") + len(
            "(pale skin:1.20),"
        )
        cursor = field.editor.textCursor()
        cursor.setPosition(insertion_position)
        field.editor.setTextCursor(cursor)
        harness.focus_editor(field)
        before = harness.capture_state_snapshot(field, label="before-pale-space")

        harness.press_key(field, Qt.Key.Key_Space)

        after = harness.capture_state_snapshot(field, label="after-pale-space")
        violations = harness.transition_invariant_violations(
            action_name="space",
            before=before,
            after=after,
        )
    finally:
        harness.close()

    assert thumbnail_repository.reads
    assert after.source_text[insertion_position : insertion_position + 2] == " \n"
    assert before.layout_line_count == after.layout_line_count
    assert before.layout_content_height == after.layout_content_height
    assert not [
        violation
        for violation in violations
        if "height_shift" in violation
        or "geometry_shift" in violation
        or "visible_row_shift" in violation
        or "visible_fragment_shift" in violation
    ]


def test_real_shell_trace_replay_uses_fresh_real_shell_path(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Replay a trace through a second real shell and prompt editor mount."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "replay")
    trace = harness.trace()

    replay_harness = RealShellPromptEditorHarness()
    try:
        replay_field = replay_harness.add_prompt_workflow(initial_text="")
        replay_harness.replay(replay_field, trace)
        snapshot = replay_harness.capture_state_snapshot(
            replay_field,
            label="after-replay",
        )
    finally:
        replay_harness.close()

    assert snapshot.source_text == "replay"
    assert "PromptProjectionSurface" in snapshot.target_event_widget_path
    assert "EditorPanel#workflow-prompt-harness-editor-panel" in (
        snapshot.target_event_widget_path
    )


def test_real_shell_minimization_preserves_real_replay_predicate(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Minimize actions only when a real-shell replay still satisfies the predicate."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "remove")
    harness.type_text(field, "keep")
    trace = harness.trace()

    def replays_keep_text(candidate: PromptEditorTrace) -> bool:
        """Return whether candidate still replays the target text in a real shell."""

        replay_harness = RealShellPromptEditorHarness()
        try:
            replay_field = replay_harness.add_prompt_workflow(initial_text="")
            replay_harness.replay(replay_field, candidate)
            return "keep" in replay_field.editor.toPlainText()
        finally:
            replay_harness.close()

    minimized = harness.minimized_trace(trace, replays_keep_text)

    assert len(minimized.actions) <= len(trace.actions)
    assert replays_keep_text(minimized)


def test_real_shell_seeded_abuse_campaign_writes_grouped_report(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Run a bounded seeded abuse pass through the production-mounted editor."""

    field = harness.add_prompt_workflow(initial_text="")

    report = harness.run_seeded_abuse_campaign(
        field,
        seed=7,
        sizes=((860, 560), (1040, 760), (1280, 820)),
        steps_per_size=2,
    )

    assert report.action_count == 6
    assert report.report_path.exists()
    assert isinstance(report.grouped_failures, dict)
    assert "literal-tab-in-source" not in report.grouped_failures
    assert "control-character-in-source" not in report.grouped_failures
    if report.findings:
        assert report.grouped_failures


class _MemoryPresetRepository:
    """Store user presets in memory for real-shell segment tests."""

    def __init__(self) -> None:
        """Initialize an empty preset collection."""

        self.presets: tuple[UserPreset, ...] = ()

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return stored presets."""

        return self.presets

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Replace stored presets."""

        self.presets = presets


class _ModelCatalog:
    """Return cached model rows without foreground loading."""

    def __init__(
        self,
        items_by_kind: dict[str, tuple[ModelCatalogItem, ...]],
        *,
        memory_cold: bool = False,
    ) -> None:
        """Store catalog rows by kind."""

        self.items_by_kind = items_by_kind
        self.memory_cold = memory_cold
        self.durable_requests: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Fail if the foreground context lists models."""

        raise AssertionError(f"unexpected model listing for {kind}")

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured rows for protocol completeness."""

        return self.items_by_kind.get(kind, ())

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return an immediately available catalog snapshot."""

        return self.cached_snapshot(kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached catalog snapshot."""

        if self.memory_cold:
            return None

        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=1,
        )

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached rows for legacy readers."""

        if self.memory_cold:
            return None
        return self.items_by_kind.get(kind, ())

    def load_durable_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return the configured authoritative durable snapshot."""

        self.durable_requests.append(kind)
        self.memory_cold = False
        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=2,
        )

    def cached_metadata_snapshot_for_kind(self, kind: str) -> ModelCatalogSnapshot:
        """Return configured rows as a local metadata fallback."""

        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=0,
        )

    def invalidate(self, kind: str | None = None) -> None:
        """Accept invalidation for protocol completeness."""

        _ = kind


def _model_item(
    *,
    kind: str,
    backend_value: str,
    display_name: str,
    base_model: str,
    display_subtitle: str | None = None,
) -> ModelCatalogItem:
    """Return one deterministic model catalog item."""

    basename = backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors")
    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=display_subtitle,
        backend_value=backend_value,
        relative_path=backend_value,
        folder="models",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=base_model,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=display_name.casefold(),
    )


def _is_descendant(widget: QWidget, ancestor: QWidget) -> bool:
    """Return whether widget has ancestor in its parent chain."""

    current: QWidget | None = widget
    while current is not None:
        if current is ancestor:
            return True
        current = current.parentWidget()
    return False


def _blank_line_break_ranges(prompt: str) -> tuple[tuple[int, int], ...]:
    """Return newline ranges that own visual blank rows in consecutive breaks."""

    return tuple(
        (index + 1, index + 2)
        for index in range(len(prompt) - 1)
        if prompt[index] == "\n" and prompt[index + 1] == "\n"
    )


def _row_has_selection_rect(
    row: PromptEditorVisibleLayoutRow,
    selection_rects: tuple[tuple[float, float, float, float], ...],
) -> bool:
    """Return whether a document-local selection rect intersects one row."""

    row_top = row.document_top
    row_bottom = row.document_top + row.height
    for _left, rect_top, _width, rect_height in selection_rects:
        rect_center_y = rect_top + rect_height / 2.0
        if row_top <= rect_center_y <= row_bottom:
            return True
    return False


def _visible_row(
    row_index: int,
    *,
    document_top: float,
    viewport_top: float,
    text: str,
) -> PromptEditorVisibleLayoutRow:
    """Create one synthetic visible row for transition invariant tests."""

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
    rect: tuple[float, float, float, float] | None = None,
) -> PromptEditorVisibleTextFragment:
    """Return one synthetic visible fragment for invariant tests."""

    fragment_rect = rect or (0.0, baseline - 12.0, 40.0, 16.0)
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
