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

"""Verify keyboard-driven real prompt-editor segment reordering."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


class _EmptyPromptAutocompleteGateway:
    """Return deterministic empty autocomplete results for reorder tests."""

    @staticmethod
    def search(
        _prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions for the supplied prefix."""

        _ = limit
        return ()


class _EmptyPromptWildcardCatalogGateway:
    """Return deterministic missing wildcard rows for reorder keyboard tests."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return missing rows for the supplied wildcard references."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


def ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder keyboard tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


@pytest.fixture()
def hosts() -> Iterator[list[QWidget]]:
    """Own and destroy each real prompt-editor host after one test."""

    created: list[QWidget] = []
    yield created
    for host in reversed(created):
        destroy_qt_object(host)


def _create_editor(
    hosts: list[QWidget],
    *,
    width: int,
    height: int,
    text: str,
) -> PromptEditor:
    """Create one visible prompt editor inside an owned host widget."""

    host = QWidget()
    host.resize(width, height)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=_EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=PromptSyntaxProfileService().default_profile(),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    layout.addWidget(editor)
    editor.setPlainText(text)
    hosts.append(host)
    host.show()
    editor.show()
    wait_for_qt_condition(lambda: editor.isVisible() and editor.width() > 0)
    wait_for_queued_qt_turn()
    return editor


def _set_editor_caret_inside_text(editor: PromptEditor, text: str) -> None:
    """Place the editor caret inside the first matching text fragment."""

    cursor = editor.textCursor()
    cursor.setPosition(editor.toPlainText().index(text) + 1)
    editor.setTextCursor(cursor)


def _press_alt_arrow_sequence(
    editor: PromptEditor,
    keys: tuple[Qt.Key, ...],
) -> None:
    """Drive the real PromptEditor Alt+Arrow reorder key path."""

    editor.setFocus()
    wait_for_qt_condition(editor.hasFocus)
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    for key in keys:
        QTest.keyPress(editor, key, Qt.KeyboardModifier.AltModifier)
    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    wait_for_queued_qt_turn()


def test_prompt_editor_alt_arrow_round_trip_preserves_space_separator(
    hosts: list[QWidget],
) -> None:
    """Avoid inventing comma separators after an Alt+Arrow round trip."""

    editor = _create_editor(
        hosts,
        width=430,
        height=220,
        text="<lora:a:1.0> <lora:b:1.0>",
    )
    _set_editor_caret_inside_text(editor, "b")
    expected_text = editor.toPlainText()

    _press_alt_arrow_sequence(
        editor,
        (Qt.Key.Key_Left, Qt.Key.Key_Right),
    )

    assert editor.toPlainText() == expected_text


def test_prompt_editor_alt_right_skips_soft_wrap_duplicate_drop_target(
    hosts: list[QWidget],
) -> None:
    """Step by logical targets rather than duplicate soft-wrap seams."""

    editor = _create_editor(
        hosts,
        width=750,
        height=280,
        text=(
            "glowing red eyes, long white hair, swept bangs, "
            "elegant seductive pose, twintails, pink hair ribbon, "
            "white eyebrows, see-through dress, iridescent belt, "
            "spaghetti strap, short white oni horns,  "
        ),
    )
    _set_editor_caret_inside_text(editor, "pink hair ribbon")

    _press_alt_arrow_sequence(
        editor,
        (Qt.Key.Key_Right, Qt.Key.Key_Right),
    )

    expected = (
        "glowing red eyes, long white hair, swept bangs, "
        "elegant seductive pose, twintails, white eyebrows, "
        "see-through dress, pink hair ribbon, iridescent belt, "
        "spaghetti strap, short white oni horns, "
    )
    wait_for_qt_condition(lambda: editor.toPlainText() == expected)
    assert editor.toPlainText() == expected


def test_prompt_editor_alt_up_moves_final_row_across_blank_line_without_space(
    hosts: list[QWidget],
) -> None:
    """Move a final-row chip without adding trailing spaces."""

    editor = _create_editor(
        hosts,
        width=430,
        height=260,
        text="alpha,\n\nbeta,",
    )
    _set_editor_caret_inside_text(editor, "beta")

    _press_alt_arrow_sequence(editor, (Qt.Key.Key_Up,))

    expected = "alpha,\nbeta,"
    wait_for_qt_condition(lambda: editor.toPlainText() == expected)
    assert editor.toPlainText() == expected


def test_prompt_editor_alt_up_moves_last_row_in_multiline_prompt(
    hosts: list[QWidget],
) -> None:
    """Address a final row hidden by keyboard base-drag layout."""

    editor = _create_editor(
        hosts,
        width=430,
        height=280,
        text="alpha,\n\nbeta,\n\ngamma",
    )
    _set_editor_caret_inside_text(editor, "gamma")

    _press_alt_arrow_sequence(editor, (Qt.Key.Key_Up,))

    expected = "alpha,\n\nbeta,\ngamma"
    wait_for_qt_condition(lambda: editor.toPlainText() == expected)
    assert editor.toPlainText() == expected
