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

"""Test wildcard management modal reorder interaction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.managed_text_assets.wildcard_csv_document_parser import (
    parse_wildcard_csv_document,
)
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository
from substitute.presentation.managed_text_assets import (
    WildcardManagementOpener,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
)
from tests.support.prompt_editor.real_shell.reorder_rendering import (
    capture_source_line_chrome,
)

from tests.presentation.managed_text_assets.wildcards.support import (
    _drag_reorder_chip_to_global,
    _overlay_chip_by_segment_index,
    _prompt_runtime_services,
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
    app.processEvents()

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
    app.processEvents()
    overlay = cast(QWidget, editor._segment_overlay)
    assert len(cast(Any, overlay).pointer_region_rects()) == 5
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()
    assert editor.toPlainText() == source

    cursor = editor.textCursor()
    cursor.setPosition(source.index("blue eyes") + 2)
    editor.setTextCursor(cursor)
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    QTest.keyPress(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    app.processEvents()
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()

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
    app.processEvents()

    before = capture_source_line_chrome(
        editor,
        label="before-alt",
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    app.processEvents()
    held = capture_source_line_chrome(
        editor,
        label="alt-held-noop",
    )
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()
    after_noop = capture_source_line_chrome(
        editor,
        label="after-noop-release",
    )

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    QTest.keyPress(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    app.processEvents()
    during = capture_source_line_chrome(
        editor,
        label="during-alt",
    )
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()
    after_commit = capture_source_line_chrome(
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
    app.processEvents()
    before = capture_source_line_chrome(
        editor,
        label="before-mouse-drag",
    )

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    app.processEvents()
    overlay = cast(QWidget, editor._segment_overlay)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.leading_global_point(),
    )
    app.processEvents()
    during = capture_source_line_chrome(
        editor,
        label="during-mouse-drag-preview",
    )
    assert editor.toPlainText() == source

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()
    after = capture_source_line_chrome(
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
    app.processEvents()

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
    app.processEvents()
    overlay = cast(QWidget, editor._segment_overlay)
    assert len(cast(Any, overlay).pointer_region_rects()) == 5
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()
    assert editor.toPlainText() == source

    cursor = editor.textCursor()
    cursor.setPosition(source.index("blue eyes") + 2)
    editor.setTextCursor(cursor)
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    QTest.keyPress(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    app.processEvents()
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    app.processEvents()

    assert editor.toPlainText() == (
        'Prompt\n"1girl, blonde hair"\n"blue eyes, smile, red dress"'
    )
    assert parse_wildcard_csv_document(editor.toPlainText()).valid is True
    modal.close()
    owner.close()
