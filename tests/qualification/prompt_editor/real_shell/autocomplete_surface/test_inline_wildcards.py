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

"""Verify inline wildcard authoring through the production prompt editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.real_shell.models import PromptFieldHandle
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)

_SCENE_PROMPT = "**scene1\n1girl, , black dress, smug, narrowed eyes\n**scene2\n"


class _HairWildcardCatalog:
    """Return one deterministic wildcard while recording production requests."""

    def __init__(self) -> None:
        """Initialize the request ledger."""

        self.search_calls: list[tuple[str, int]] = []

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return the matching wildcard row for the typed prefix."""

        self.search_calls.append((prefix, limit))
        return (
            PromptAutocompleteSuggestion(
                "hairstyle",
                source_label="TXT wildcard",
                source_kind="wildcard",
            ),
        )

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return existing resolutions for syntax diagnostics."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=True,
            )
            for reference in references
        )


def test_unclosed_inline_wildcard_presents_and_accepts_without_eating_suffix(
    tmp_path: Path,
) -> None:
    """Complete an unfinished wildcard between ordinary scene prompt tags."""

    catalog = _HairWildcardCatalog()
    scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_wildcard_catalog_gateway=catalog,
    )
    try:
        field = _mount_inline_scene_prompt(scenario)

        scenario.input.type_text(field, "{hair")
        _wait_for_wildcard_results(scenario, field)

        presented = scenario.snapshots.capture(field, label="inline-unclosed")
        assert presented.source_text == _SCENE_PROMPT.replace(", ,", ", {hair,")
        assert presented.cursor_position == _inline_insertion_position() + len("{hair")
        assert presented.autocomplete_session_mode == "wildcard"
        assert presented.autocomplete_session_suggestions == ("hairstyle",)
        assert ("hair", 10) in catalog.search_calls

        scenario.input.press_key(field, Qt.Key.Key_Tab, text="\t")

        accepted = scenario.snapshots.capture(field, label="inline-unclosed-accepted")
        assert accepted.source_text == _SCENE_PROMPT.replace(", ,", ", {hairstyle},")
    finally:
        scenario.close()


def test_completed_inline_wildcard_keeps_one_caret_and_undoable_acceptance(
    tmp_path: Path,
) -> None:
    """Keep source, projection, and autocomplete aligned inside an existing closer."""

    catalog = _HairWildcardCatalog()
    scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_wildcard_catalog_gateway=catalog,
    )
    try:
        field = _mount_inline_scene_prompt(scenario)
        scenario.input.type_text(field, "{}")
        scenario.input.press_key(field, Qt.Key.Key_Left)

        scenario.input.type_text(field, "hair")
        _wait_for_wildcard_results(scenario, field)

        presented = scenario.snapshots.capture(field, label="inline-completed")
        expected_typed = _SCENE_PROMPT.replace(", ,", ", {hair},")
        assert presented.source_text == expected_typed
        assert presented.cursor_position == expected_typed.index("}")
        assert presented.autocomplete_session_mode == "wildcard"
        assert presented.autocomplete_session_suggestions == ("hairstyle",)
        assert ("hair", 10) in catalog.search_calls

        scenario.input.press_key(field, Qt.Key.Key_Tab, text="\t")
        expected_accepted = _SCENE_PROMPT.replace(", ,", ", {hairstyle},")
        assert field.editor.toPlainText() == expected_accepted

        scenario.input.undo(field)
        assert field.editor.toPlainText() == expected_typed
        assert field.editor.textCursor().position() == expected_typed.index("}")

        scenario.input.press_key(field, Qt.Key.Key_Backspace)
        expected_deleted = _SCENE_PROMPT.replace(", ,", ", {hai},")
        assert field.editor.toPlainText() == expected_deleted
        assert field.editor.textCursor().position() == expected_deleted.index("}")

        scenario.input.undo(field)
        scenario.input.redo(field)
        assert field.editor.toPlainText() == expected_deleted
    finally:
        scenario.close()


def test_mouse_expanded_wildcard_uses_exact_source_caret_for_autocomplete(
    tmp_path: Path,
) -> None:
    """A pointer-expanded wildcard must publish its exact inner source caret."""

    catalog = _HairWildcardCatalog()
    scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_wildcard_catalog_gateway=catalog,
    )
    try:
        source = _SCENE_PROMPT.replace(", ,", ", {hair},")
        field = scenario.workflows.add_prompt_workflow(initial_text=source)
        surface = field.editor._surface  # noqa: SLF001
        token = next(
            token
            for token in surface.projection_document().tokens
            if token.kind is PromptProjectionTokenKind.WILDCARD
        )
        token_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
            token,
            scroll_offset=float(field.editor.verticalScrollBar().value()),
        )
        assert token_rect is not None

        QTest.mouseDClick(
            field.editor.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            token_rect.center().toPoint(),
        )
        scenario.wait_for_queued_delivery()
        inner_cursor = source.index("}")
        scenario.input.click_projected_source_position(field, inner_cursor)

        assert field.editor.textCursor().position() == inner_cursor
        scenario.input.type_text(field, "x")
        _wait_for_wildcard_results(scenario, field)

        expected = _SCENE_PROMPT.replace(", ,", ", {hairx},")
        assert field.editor.toPlainText() == expected
        assert field.editor.textCursor().position() == expected.index("}")
        assert ("hairx", 10) in catalog.search_calls
    finally:
        scenario.close()


def _mount_inline_scene_prompt(
    scenario: PromptEditorRealShellScenario,
) -> PromptFieldHandle:
    """Mount the scene prompt and place its source caret at the empty inline slot."""

    field = scenario.workflows.add_prompt_workflow(initial_text=_SCENE_PROMPT)
    scenario.input.set_source_cursor_position(field, _inline_insertion_position())
    return field


def _inline_insertion_position() -> int:
    """Return the empty tag position in the shared scene prompt fixture."""

    return _SCENE_PROMPT.index(", ,") + 2


def _wait_for_wildcard_results(
    scenario: PromptEditorRealShellScenario,
    field: PromptFieldHandle,
) -> None:
    """Wait until the asynchronous wildcard request owns visible suggestions."""

    scenario.wait_until(
        lambda: (
            scenario.snapshots.capture(
                field,
                label="wildcard-result-poll",
                settle=False,
            ).autocomplete_session_mode
            == "wildcard"
        ),
        description="inline wildcard autocomplete presentation",
    )
