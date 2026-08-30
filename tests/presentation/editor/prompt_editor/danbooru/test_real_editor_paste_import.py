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

"""Test real prompt-editor Danbooru paste/import behavior."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.danbooru import (
    DanbooruFailureReason,
    DanbooruImportedPrompt,
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlKind,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
)
from tests.presentation.editor.prompt_editor.danbooru.real_editor_support import (
    FailingDanbooruUrlImportService,
    ImmediateDanbooruImportDispatcher,
    StaticDanbooruUrlImportService,
    configure_danbooru_url_import,
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


def move_cursor_to_end(editor: PromptEditor) -> None:
    """Move the prompt-editor cursor to the document end."""

    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)


def test_prompt_editor_paste_supported_danbooru_url_imports_tags(
    widgets: list[QWidget],
) -> None:
    """Supported Danbooru URLs should be replaced with imported tag text."""

    app = ensure_qapp()
    service = StaticDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/12345",
            kind=DanbooruUrlKind.POST,
            lookup_value="12345",
        ),
        result=DanbooruPromptImportResult(
            imported_prompt=DanbooruImportedPrompt(
                display_text="1girl, long hair, smile",
                source_post_id=12345,
                included_tags=("1girl", "long_hair", "smile"),
                excluded_tags=("commentary",),
            )
        ),
    )
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    configure_danbooru_url_import(
        editor,
        service,
        dispatcher=ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://danbooru.donmai.us/posts/12345")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "1girl, long hair, smile"
    assert service.classify_calls == ["https://danbooru.donmai.us/posts/12345"]
    assert service.import_calls == ["https://danbooru.donmai.us/posts/12345"]


def test_prompt_editor_danbooru_url_import_undo_skips_intermediate_url(
    widgets: list[QWidget],
) -> None:
    """Undo after Danbooru expansion should jump back before the paste entirely."""

    app = ensure_qapp()
    service = StaticDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/12345",
            kind=DanbooruUrlKind.POST,
            lookup_value="12345",
        ),
        result=DanbooruPromptImportResult(
            imported_prompt=DanbooruImportedPrompt(
                display_text="1girl, long hair, smile",
                source_post_id=12345,
                included_tags=("1girl", "long_hair", "smile"),
                excluded_tags=("commentary",),
            )
        ),
    )
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    editor.setPlainText("alpha, ")
    move_cursor_to_end(editor)
    configure_danbooru_url_import(
        editor,
        service,
        dispatcher=ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://danbooru.donmai.us/posts/12345")

    editor.paste()
    process_events(app)
    assert editor.toPlainText() == "alpha, 1girl, long hair, smile"

    editor.undo()
    process_events(app)

    assert editor.toPlainText() == "alpha, "


def test_prompt_editor_paste_unsupported_danbooru_url_falls_back_to_literal_paste(
    widgets: list[QWidget],
) -> None:
    """Unsupported URLs should use the existing literal paste behavior."""

    app = ensure_qapp()
    service = StaticDanbooruUrlImportService(
        classification=None,
        result=DanbooruPromptImportResult(imported_prompt=None),
    )
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    configure_danbooru_url_import(
        editor,
        service,
        dispatcher=ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://example.com/posts/12345")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "https://example.com/posts/12345"
    assert service.classify_calls == ["https://example.com/posts/12345"]
    assert service.import_calls == []


def test_prompt_editor_paste_failed_danbooru_lookup_keeps_literal_url(
    widgets: list[QWidget],
) -> None:
    """Failed Danbooru lookups should leave the pasted URL in place."""

    app = ensure_qapp()
    service = StaticDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/777",
            kind=DanbooruUrlKind.POST,
            lookup_value="777",
        ),
        result=DanbooruPromptImportResult(
            imported_prompt=None,
            failure_reason=DanbooruFailureReason.NOT_FOUND,
        ),
    )
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    configure_danbooru_url_import(
        editor,
        service,
        dispatcher=ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://danbooru.donmai.us/posts/777")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "https://danbooru.donmai.us/posts/777"
    assert service.import_calls == ["https://danbooru.donmai.us/posts/777"]


def test_prompt_editor_paste_danbooru_exception_logs_prompt_safe_context(
    widgets: list[QWidget],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Danbooru import exceptions should not serialize pasted URL content."""

    app = ensure_qapp()
    service = FailingDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/888",
            kind=DanbooruUrlKind.POST,
            lookup_value="888",
        ),
    )
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    configure_danbooru_url_import(
        editor,
        service,
        dispatcher=ImmediateDanbooruImportDispatcher(),
    )
    caplog.set_level(
        logging.WARNING,
        logger="presentation.editor.prompt_editor.danbooru_paste_import",
    )
    pasted_url = "https://danbooru.donmai.us/posts/888"
    QApplication.clipboard().setText(pasted_url)

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == pasted_url
    assert service.import_calls == [pasted_url]
    assert "Prompt paste Danbooru import failed unexpectedly." in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert f"source_length={len(pasted_url)}" in caplog.text
    assert pasted_url not in caplog.text
