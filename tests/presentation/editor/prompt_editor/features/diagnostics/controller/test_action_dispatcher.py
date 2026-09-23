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

"""Verify diagnostic action dispatch and provider side effects."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.features.diagnostic_action_dispatcher import (
    PromptDiagnosticActionDispatcher,
    PromptDiagnosticSpellcheckProvider,
)

from . import support
from .spellcheck_support import _FakeSpellcheckService


@dataclass(slots=True)
class _Providers:
    """Expose the active spellcheck provider to the dispatcher."""

    spellcheck_provider: PromptDiagnosticSpellcheckProvider | None


@dataclass(slots=True)
class _RefreshRequester:
    """Record diagnostics refresh requests after provider mutations."""

    refresh_count: int = 0

    def refresh_now(self) -> None:
        """Record one immediate refresh request."""

        self.refresh_count += 1


def _dispatcher(
    editor: support._FakeEditor,
    *,
    spellcheck: PromptDiagnosticSpellcheckProvider | None = None,
    refresh: _RefreshRequester | None = None,
) -> PromptDiagnosticActionDispatcher:
    """Return a dispatcher backed by deterministic diagnostic collaborators."""

    return PromptDiagnosticActionDispatcher(
        host=editor,
        providers=_Providers(spellcheck),
        refresh_requester=refresh or _RefreshRequester(),
    )


def test_dispatcher_replaces_spelling_and_restores_editor_focus() -> None:
    """Accepted spelling replacements should mutate source and restore focus."""

    diagnostic = support._spelling_diagnostic(4, 8, "typo")
    editor = support._FakeEditor("one typo")

    _dispatcher(editor).replace_spelling_diagnostic(diagnostic, "type")

    assert editor.toPlainText() == "one type"
    assert editor.focused is True


def test_dispatcher_applies_validated_spellcheck_provider_actions() -> None:
    """Validated ignores and dictionary additions should refresh diagnostics."""

    diagnostic = support._spelling_diagnostic(4, 8, "typo")
    editor = support._FakeEditor("one typo")
    spellcheck = _FakeSpellcheckService()
    refresh = _RefreshRequester()
    dispatcher = _dispatcher(editor, spellcheck=spellcheck, refresh=refresh)

    dispatcher.ignore_spelling_diagnostic_for_session(diagnostic)
    dispatcher.add_spelling_diagnostic_to_dictionary(diagnostic)

    assert spellcheck.ignored_words == ["typo"]
    assert spellcheck.added_words == ["typo"]
    assert refresh.refresh_count == 2
    assert dispatcher.dictionary_add_supported() is True


def test_dispatcher_rejects_stale_spellcheck_provider_actions() -> None:
    """Stale prepared actions should not mutate provider state or request refresh."""

    diagnostic = support._spelling_diagnostic(4, 8, "typo")
    editor = support._FakeEditor("one typo")
    prepared_identity = editor.prompt_command_source_identity()
    editor.set_text("one type")
    spellcheck = _FakeSpellcheckService()
    refresh = _RefreshRequester()
    dispatcher = _dispatcher(editor, spellcheck=spellcheck, refresh=refresh)

    dispatcher.ignore_spelling_diagnostic_for_session(
        diagnostic,
        source_identity=prepared_identity,
    )
    dispatcher.add_spelling_diagnostic_to_dictionary(
        diagnostic,
        source_identity=prepared_identity,
    )

    assert spellcheck.ignored_words == []
    assert spellcheck.added_words == []
    assert refresh.refresh_count == 0


def test_dispatcher_returns_validated_duplicate_ignore_identity() -> None:
    """Duplicate ignores should return only command-validated diagnostic identity."""

    diagnostic = support._duplicate_diagnostic(
        normalized_segment="beta",
        first_start=7,
        first_end=11,
        duplicate_start=13,
        duplicate_end=17,
    )
    editor = support._FakeEditor("alpha, beta, beta")
    dispatcher = _dispatcher(editor)

    ignored_id = dispatcher.ignore_duplicate_diagnostic(diagnostic)

    assert ignored_id == diagnostic.diagnostic_id


def test_dispatcher_reports_unsupported_dictionary_without_provider() -> None:
    """Missing spellcheck providers should disable persistent dictionary actions."""

    dispatcher = _dispatcher(support._FakeEditor("text"))

    assert dispatcher.dictionary_add_supported() is False
