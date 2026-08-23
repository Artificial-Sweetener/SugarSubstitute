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

"""Test wildcard management modal diagnostics and asset semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


from substitute.application.prompt_editor.diagnostics.models import PromptDiagnosticKind
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository
from substitute.presentation.managed_text_assets import (
    WildcardManagementOpener,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
)

from tests.presentation.managed_text_assets.wildcards.support import (
    _prompt_runtime_services,
)


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
    app.processEvents()
    diagnostics = editor._diagnostics_feature_controller
    diagnostics.refresh_now()
    app.processEvents()

    projection = editor._surface.projection_document()
    assert projection.projection_text.startswith("**portrait")
    assert all(token.kind.value != "scene" for token in projection.tokens)
    marker = next(
        diagnostic
        for diagnostic in diagnostics.presentation.snapshot.diagnostics
        if diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER
    )
    assert (marker.source_start, marker.source_end) == (0, 2)
    actions = diagnostics.presentation.prepared_menu_actions_for_source_position(
        0
    ).actions
    assert tuple(action.label for action in actions) == (
        "Scenes aren’t supported in wildcard values.",
    )
    assert actions[0].enabled is False
    scene_publication = editor._scene_context_publication
    scene_preparation = editor._scene_position_preparation
    scene_publication.set_scene_autocomplete_titles(("Portrait",))
    scene_publication.set_queueable_scene_keys(frozenset({"portrait"}))
    assert scene_publication.snapshot.autocomplete.ready is False
    assert scene_publication.snapshot.autocomplete.titles == ()
    assert scene_publication.snapshot.queue_action.action_ready is False
    prepared_scene = scene_preparation.prepare_position_context(
        0,
        reason="unsupported_scene_marker_assertion",
    )
    assert prepared_scene.context is not None
    assert prepared_scene.context.scene_key is None
    assert prepared_scene.context.queueable_scene_key is None
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
    app.processEvents()
    diagnostics = editor._diagnostics_feature_controller

    diagnostics.refresh_now()
    app.processEvents()
    markers = tuple(
        diagnostic
        for diagnostic in diagnostics.presentation.snapshot.diagnostics
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
    app.processEvents()

    diagnostics = editor._diagnostics_feature_controller
    diagnostics.refresh_now()
    app.processEvents()
    duplicates = tuple(
        diagnostic
        for diagnostic in diagnostics.presentation.snapshot.diagnostics
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
    app.processEvents()

    assert editor._document_semantics.identity == "wildcard-txt-v1"
    modal._editor.setPlainText("edited")
    csv_asset_id = next(
        asset_id for asset_id in modal._assets if asset_id.endswith(".csv")
    )
    modal._select_asset(csv_asset_id)
    app.processEvents()

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
    app.processEvents()
    diagnostics = editor._diagnostics_feature_controller
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)

    diagnostics.refresh_now()
    app.processEvents()
    assert (
        sum(
            token.kind.value == "wildcard"
            for token in editor._surface.projection_document().tokens
        )
        == 1
    )
    assert any(
        diagnostic.kind is PromptDiagnosticKind.WILDCARD
        for diagnostic in diagnostics.presentation.snapshot.diagnostics
    )

    csv_asset_id = next(
        asset_id for asset_id in modal._assets if asset_id.endswith(".csv")
    )
    modal._select_asset(csv_asset_id)
    app.processEvents()
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    diagnostics.refresh_now()
    app.processEvents()
    assert all(
        token.kind.value != "wildcard"
        for token in editor._surface.projection_document().tokens
    )
    assert all(
        diagnostic.kind is not PromptDiagnosticKind.WILDCARD
        for diagnostic in diagnostics.presentation.snapshot.diagnostics
    )

    txt_asset_id = next(
        asset_id for asset_id in modal._assets if asset_id.endswith(".txt")
    )
    modal._select_asset(txt_asset_id)
    app.processEvents()
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    diagnostics.refresh_now()
    app.processEvents()
    assert (
        sum(
            token.kind.value == "wildcard"
            for token in editor._surface.projection_document().tokens
        )
        == 1
    )
    assert any(
        diagnostic.kind is PromptDiagnosticKind.WILDCARD
        for diagnostic in diagnostics.presentation.snapshot.diagnostics
    )
