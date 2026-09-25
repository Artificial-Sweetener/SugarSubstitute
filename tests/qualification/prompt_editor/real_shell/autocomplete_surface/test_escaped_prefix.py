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

"""Verify storage-only parenthesis escapes never trigger tag suggestions."""

from __future__ import annotations

from pathlib import Path

from substitute.application.ports import PromptAutocompleteSuggestion
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_escaped_parenthesis_does_not_query_emoticon_tag_prefix(
    tmp_path: Path,
) -> None:
    """Use visible prefix text while preserving the raw source caret position."""

    source_text = r"(casshern \series\):1.25)"
    scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        autocomplete_results={
            r"\(": (PromptAutocompleteSuggestion(r"\(^o^)/", 121),),
        },
    )
    try:
        field = scenario.workflows.add_prompt_workflow(initial_text=source_text)
        cursor_position = source_text.index("\\") + 1
        scenario.input.set_source_cursor_position(field, cursor_position)
        scenario.input.type_text(field, "(")
        snapshot = scenario.snapshots.capture(field, label="after-escaped-parenthesis")

        queried_prefixes = tuple(
            prefix for prefix, _limit in scenario.autocomplete_gateway.calls
        )
        assert "casshern (" in queried_prefixes
        assert r"\(" not in queried_prefixes
        assert snapshot.source_text == r"(casshern \(series\):1.25)"
        assert snapshot.cursor_position == cursor_position + 1
        assert not snapshot.autocomplete_session_suggestions
        assert not snapshot.popup_state_visible
    finally:
        scenario.close()


def test_visible_text_after_escaped_parenthesis_still_suggests(
    tmp_path: Path,
) -> None:
    """Continue matching valid tag text after a storage-only escape."""

    source_text = r"(casshern \(se\):1.25)"
    scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        autocomplete_results={
            "(ser": (PromptAutocompleteSuggestion("(series)", 121),),
        },
    )
    try:
        field = scenario.workflows.add_prompt_workflow(initial_text=source_text)
        scenario.input.set_source_cursor_position(
            field, source_text.index("se") + len("se")
        )
        scenario.input.type_text_and_wait_for_autocomplete(field, "r")
        presented = scenario.snapshots.capture(field, label="escaped-prefix-presented")

        assert "(ser" in (
            prefix for prefix, _limit in scenario.autocomplete_gateway.calls
        )
        assert presented.autocomplete_session_prefix == "(ser"
        assert presented.autocomplete_session_suggestions == ("(series)",)
        assert presented.popup_state_visible
    finally:
        scenario.close()
