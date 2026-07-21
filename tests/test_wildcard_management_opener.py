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

"""Tests for wildcard management modal wrapper and opener."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import PromptEditorFeature
from substitute.application.prompt_editor import PromptDiagnosticKind
from substitute.application.managed_text_assets.wildcard_csv_document_parser import (
    parse_wildcard_csv_document,
)
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.domain.prompt import PromptWheelAdjustmentMode
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository
from substitute.presentation.managed_text_assets import (
    WildcardManagementModal,
    WildcardManagementOpener,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
)
from tests.execution_test_helpers import immediate_editor_panel_execution_factories
from tests.real_shell_prompt_editor_harness import RealShellPromptEditorHarness
from tests.prompt_reorder_pointer_test_helpers import (
    PromptReorderPointerTarget,
    drag_prompt_reorder_target_to_global,
    prompt_reorder_pointer_target,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "wildcard management modal Qt tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_wildcard_management_opener_constructs_modal_with_caller_parent(
    tmp_path: Path,
) -> None:
    """The opener should parent the modal mask to the caller's top-level window."""

    app = ensure_qapp()
    parent = QWidget()
    child = QWidget(parent)
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
        prompt_wheel_adjustment_mode=lambda: PromptWheelAdjustmentMode.FOCUS_REQUIRED,
    )

    modal = opener.create_modal(child)

    assert app is not None
    assert isinstance(modal, WildcardManagementModal)
    assert modal.parent() is parent
    editor = cast(Any, modal._editor.editor())
    assert (
        editor._autocomplete._result_controller._prompt_autocomplete_gateway.__class__
        is (EmptyPromptAutocompleteGateway)
    )
    assert (
        cast(Any, modal._editor)._wheel_intent_controller._wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )


def test_wildcard_management_modal_uses_full_prompt_feature_profile(
    tmp_path: Path,
) -> None:
    """Wildcard modal prompt editor should expose every normal prompt feature."""

    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    )

    modal = opener.create_modal(None)
    profile = cast(Any, modal._editor.editor())._feature_profile_controller.profile

    assert all(profile.supports(feature) for feature in PromptEditorFeature)


def test_wildcard_management_modal_rejects_scene_markers_without_projecting_scenes(
    tmp_path: Path,
) -> None:
    """The production wildcard editor should keep markers literal and explain errors."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    service.create_text_file("characters", "**portrait\nstudio portrait")
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    )

    modal = opener.create_modal(None)
    editor = cast(Any, modal._editor.editor())
    process_events(app)
    diagnostics = editor._diagnostics_feature_controller
    diagnostics.refresh_now()
    process_events(app)

    projection = editor._surface.projection_document()
    assert projection.projection_text.startswith("**portrait")
    assert all(token.kind.value != "scene" for token in projection.tokens)
    marker = next(
        diagnostic
        for diagnostic in diagnostics.snapshot.diagnostics
        if diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER
    )
    assert (marker.source_start, marker.source_end) == (0, 2)
    actions = diagnostics.prepared_menu_actions_for_source_position(0).actions
    assert tuple(action.label for action in actions) == (
        "Scenes aren’t supported in wildcard values.",
    )
    assert actions[0].enabled is False
    scene_controller = editor._scene_feature_controller
    scene_controller.set_scene_autocomplete_titles(("Portrait",))
    scene_controller.set_queueable_scene_keys(frozenset({"portrait"}))
    assert scene_controller.snapshot.autocomplete.ready is False
    assert scene_controller.snapshot.autocomplete.titles == ()
    assert scene_controller.snapshot.queue_action.action_ready is False
    assert scene_controller.scene_key_for_source_position(0) is None
    assert scene_controller.queueable_scene_key_for_source_position(0) is None
    document_view = editor._document_service.build_document_view(editor.toPlainText())
    assert (
        editor._document_service.scene_autocomplete_query_at_cursor(
            text=editor.toPlainText(),
            cursor_position=2,
            has_selection=False,
        )
        is None
    )
    assert document_view.source_text == editor.toPlainText()

    modal._editor.setPlainText("**portrait\nstudio portrait **detail")
    modal._save_current()
    assert service.read_file("characters.txt") == (
        "**portrait\nstudio portrait **detail"
    )


def test_wildcard_modal_rejects_scene_markers_only_inside_csv_values(
    tmp_path: Path,
) -> None:
    """Production CSV diagnostics should ignore headers and map value markers exactly."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    source = '**Header\n"  **portrait, studio"'
    service.create_csv_file("characters", source)
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    process_events(app)
    diagnostics = editor._diagnostics_feature_controller

    diagnostics.refresh_now()
    process_events(app)
    markers = tuple(
        diagnostic
        for diagnostic in diagnostics.snapshot.diagnostics
        if diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER
    )

    assert len(markers) == 1
    assert source[markers[0].source_start : markers[0].source_end] == "**"
    assert markers[0].source_start == source.rindex("**")
    modal._save_current()
    assert service.read_file("characters.csv") == source


def test_wildcard_modal_isolates_only_duplicate_diagnostics_by_value(
    tmp_path: Path,
) -> None:
    """Production diagnostics should ignore cross-value repeats only."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    source = "red hair, blue eyes\nred hair, red hair"
    service.create_text_file("characters", source)
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    process_events(app)

    diagnostics = editor._diagnostics_feature_controller
    diagnostics.refresh_now()
    process_events(app)
    duplicates = tuple(
        diagnostic
        for diagnostic in diagnostics.snapshot.diagnostics
        if diagnostic.kind is PromptDiagnosticKind.DUPLICATE_SEGMENT
    )

    assert len(duplicates) == 1
    duplicate = duplicates[0]
    assert source[duplicate.source_start : duplicate.source_end] == "red hair"
    assert duplicate.source_start == source.rindex("red hair")


def test_wildcard_asset_switch_changes_semantics_and_resets_undo_baseline(
    tmp_path: Path,
) -> None:
    """TXT/CSV switches should atomically replace semantics and editor history."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    service.create_text_file("characters", "one\n")
    service.create_csv_file("poses", "value\nportrait\n")
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    )
    modal = opener.create_modal(None)
    editor = cast(Any, modal._editor.editor())
    process_events(app)

    assert editor._document_semantics.identity == "wildcard-txt-v1"
    modal._editor.setPlainText("edited")
    csv_asset_id = next(
        asset_id for asset_id in modal._assets if asset_id.endswith(".csv")
    )
    modal._select_asset(csv_asset_id)
    process_events(app)

    assert editor._document_semantics.identity == "wildcard-csv-v1"
    assert modal._editor.toPlainText() == "value\nportrait\n"
    modal._editor.undo()
    assert modal._editor.toPlainText() == "value\nportrait\n"


def test_wildcard_asset_switch_rebinds_diagnostic_value_mapping(
    tmp_path: Path,
) -> None:
    """TXT/CSV switches should apply diagnostics through the live source format."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    service.create_text_file("characters", "{missing}\nplain")
    service.create_csv_file("poses", "{missing}\nplain")
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    process_events(app)
    diagnostics = editor._diagnostics_feature_controller
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)

    diagnostics.refresh_now()
    process_events(app)
    assert (
        sum(
            token.kind.value == "wildcard"
            for token in editor._surface.projection_document().tokens
        )
        == 1
    )
    assert any(
        diagnostic.kind is PromptDiagnosticKind.WILDCARD
        for diagnostic in diagnostics.snapshot.diagnostics
    )

    csv_asset_id = next(
        asset_id for asset_id in modal._assets if asset_id.endswith(".csv")
    )
    modal._select_asset(csv_asset_id)
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    diagnostics.refresh_now()
    process_events(app)
    assert all(
        token.kind.value != "wildcard"
        for token in editor._surface.projection_document().tokens
    )
    assert all(
        diagnostic.kind is not PromptDiagnosticKind.WILDCARD
        for diagnostic in diagnostics.snapshot.diagnostics
    )

    txt_asset_id = next(
        asset_id for asset_id in modal._assets if asset_id.endswith(".txt")
    )
    modal._select_asset(txt_asset_id)
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    diagnostics.refresh_now()
    process_events(app)
    assert (
        sum(
            token.kind.value == "wildcard"
            for token in editor._surface.projection_document().tokens
        )
        == 1
    )
    assert any(
        diagnostic.kind is PromptDiagnosticKind.WILDCARD
        for diagnostic in diagnostics.snapshot.diagnostics
    )


def test_wildcard_modal_alt_reorders_tags_within_and_across_values(
    tmp_path: Path,
) -> None:
    """Wildcard Alt reorder should retain normal cross-line tag behavior."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    source = "1girl, blonde hair, blue eyes\nsmile, red dress"
    service.create_text_file("characters", source)
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    owner = modal.parentWidget()
    assert owner is not None
    owner.show()
    modal.show()
    editor.setFocus()
    process_events(app)

    document_view = editor._document_service.build_document_view(editor.toPlainText())
    session = editor._document_service.build_reorder_session_view(document_view)

    assert tuple(chip.text for chip in session.chips) == (
        "1girl",
        "blonde hair",
        "blue eyes",
        "smile",
        "red dress",
    )

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    overlay = cast(QWidget, editor._segment_overlay)
    assert len(cast(Any, overlay).pointer_region_rects()) == 5
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)
    assert editor.toPlainText() == source

    cursor = editor.textCursor()
    cursor.setPosition(source.index("blue eyes") + 2)
    editor.setTextCursor(cursor)
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    QTest.keyPress(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    process_events(app)
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "1girl, blonde hair\nblue eyes, smile, red dress"
    modal.close()
    owner.close()


def test_wildcard_modal_alt_preview_preserves_rendered_zebra(
    tmp_path: Path,
) -> None:
    """Holding Alt should keep wildcard source-line zebra visible in preview."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    source = "1girl, blonde hair, blue eyes\nsmile, red dress\nhat, outdoors"
    service.create_text_file("characters", source)
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    owner = modal.parentWidget()
    assert owner is not None
    owner.show()
    modal.show()
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    editor.setFocus()
    process_events(app)

    before = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="before-alt",
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    held = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="alt-held-noop",
    )
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)
    after_noop = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="after-noop-release",
    )

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    QTest.keyPress(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    process_events(app)
    during = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="during-alt",
    )
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)
    after_commit = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="after-commit",
    )

    before_colors = dict(before.line_colors)
    held_colors = dict(held.line_colors)
    after_noop_colors = dict(after_noop.line_colors)
    during_colors = dict(during.line_colors)
    after_commit_colors = dict(after_commit.line_colors)
    assert before.reorder_overlay_active is False
    assert before.projection_preview_active is False
    assert held.reorder_overlay_active is True
    assert held.projection_preview_active is False
    assert after_noop.reorder_overlay_active is False
    assert after_noop.projection_preview_active is False
    assert during.reorder_overlay_active is True
    assert during.projection_preview_active is True
    assert after_commit.reorder_overlay_active is False
    assert after_commit.projection_preview_active is False
    assert before_colors[1] != before_colors[2]
    assert held_colors[1] == before_colors[1]
    assert held_colors[1] != held_colors[2]
    assert after_noop_colors[1] == before_colors[1]
    assert after_noop_colors[1] != after_noop_colors[2]
    assert during_colors[1] == before_colors[1]
    assert during_colors[1] != during_colors[2]
    assert after_commit_colors[1] != after_commit_colors[2]
    modal.close()
    owner.close()


def test_wildcard_modal_mouse_drag_preview_preserves_rendered_zebra(
    tmp_path: Path,
) -> None:
    """Mouse chip dragging should retain zebra through preview and commit."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    source = "1girl, blonde hair, blue eyes\nsmile, red dress\nhat, outdoors"
    service.create_text_file("characters", source)
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    owner = modal.parentWidget()
    assert owner is not None
    owner.show()
    modal.show()
    editor.setFocus()
    process_events(app)
    before = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="before-mouse-drag",
    )

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    overlay = cast(QWidget, editor._segment_overlay)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.leading_global_point(),
    )
    process_events(app)
    during = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="during-mouse-drag-preview",
    )
    assert editor.toPlainText() == source

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)
    after = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        editor,
        label="after-mouse-drag-commit",
    )

    before_colors = dict(before.line_colors)
    during_colors = dict(during.line_colors)
    after_colors = dict(after.line_colors)
    assert during.reorder_overlay_active is True
    assert during_colors[1] == before_colors[1]
    assert during_colors[1] != during_colors[2]
    assert after.reorder_overlay_active is False
    assert after.projection_preview_active is False
    assert after_colors[1] != after_colors[2]
    assert editor.toPlainText().startswith("blonde hair, 1girl, blue eyes")
    modal.close()
    owner.close()


def test_wildcard_modal_alt_reorders_csv_tags_without_moving_headers(
    tmp_path: Path,
) -> None:
    """Production CSV Alt reorder should move tags and retain CSV containers."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    source = 'Prompt\n"1girl, blonde hair, blue eyes"\n"smile, red dress"'
    service.create_csv_file("characters", source)
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    owner = modal.parentWidget()
    assert owner is not None
    owner.show()
    modal.show()
    editor.setFocus()
    process_events(app)

    document_view = editor._document_service.build_document_view(source)
    session = editor._document_service.build_reorder_session_view(document_view)
    assert tuple(chip.text for chip in session.chips) == (
        "1girl",
        "blonde hair",
        "blue eyes",
        "smile",
        "red dress",
    )

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    overlay = cast(QWidget, editor._segment_overlay)
    assert len(cast(Any, overlay).pointer_region_rects()) == 5
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)
    assert editor.toPlainText() == source

    cursor = editor.textCursor()
    cursor.setPosition(source.index("blue eyes") + 2)
    editor.setTextCursor(cursor)
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    QTest.keyPress(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    process_events(app)
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == (
        'Prompt\n"1girl, blonde hair"\n"blue eyes, smile, red dress"'
    )
    assert parse_wildcard_csv_document(editor.toPlainText()).valid is True
    modal.close()
    owner.close()


def test_wildcard_modal_context_insert_preserves_csv_and_cursor(
    tmp_path: Path,
) -> None:
    """Saved prompt text inserts should quote CSV cells and retain the local caret."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    service.create_csv_file("characters", "value\nalpha\n")
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    cursor = editor.textCursor()
    cursor.setPosition(len("value\nalpha"))
    editor.setTextCursor(cursor)

    result = editor._command_adapter.insert_context_menu_text(', "detail"')
    process_events(app)

    assert result.status == "applied"
    assert editor.toPlainText() == 'value\n"alpha, ""detail"""\n'
    assert parse_wildcard_csv_document(editor.toPlainText()).valid is True
    assert editor.textCursor().position() == len(editor.toPlainText()) - 2
    editor.undo()
    assert editor.toPlainText() == "value\nalpha\n"


def test_wildcard_modal_projects_prompt_syntax_inside_quoted_csv_values(
    tmp_path: Path,
) -> None:
    """Production CSV values should render every supported prompt syntax token."""

    app = ensure_qapp()
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    service.create_csv_file(
        "characters",
        'value\n"(Portrait:1.1), {animal}, <lora:model:1>"\n',
    )
    modal = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    ).create_modal(None)
    editor = cast(Any, modal._editor.editor())
    process_events(app)

    token_kinds = {
        token.kind.value for token in editor._surface.projection_document().tokens
    }

    assert token_kinds == {"emphasis", "wildcard", "lora"}


def _prompt_runtime_services() -> PromptEditorRuntimeServices:
    """Return production-shaped prompt services for wildcard modal tests."""

    execution_factories = immediate_editor_panel_execution_factories()
    return PromptEditorRuntimeServices(
        autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_task_executor_factory=execution_factories.prompt_task_executor_factory,
        danbooru_lookup_dispatcher_factory=(
            execution_factories.danbooru_lookup_dispatcher_factory
        ),
    )


def _overlay_chip_by_segment_index(
    overlay: QWidget, segment_index: int
) -> PromptReorderPointerTarget:
    """Return one production logical pointer target by segment index."""

    return prompt_reorder_pointer_target(overlay, segment_index)


def _drag_reorder_chip_to_global(
    chip: PromptReorderPointerTarget,
    *,
    global_target: QPoint,
) -> None:
    """Drive one real mouse drag to the supplied global overlay position."""

    drag_prompt_reorder_target_to_global(chip, global_target=global_target)
