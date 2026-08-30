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

"""Test wildcard management modal editing and rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


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

from tests.presentation.managed_text_assets.wildcards.support import (
    _prompt_runtime_services,
)


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

    result = editor._context_insertion.insert_context_menu_text(', "detail"')
    app.processEvents()

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
    app.processEvents()

    token_kinds = {
        token.kind.value for token in editor._surface.projection_document().tokens
    }

    assert token_kinds == {"emphasis", "wildcard", "lora"}
