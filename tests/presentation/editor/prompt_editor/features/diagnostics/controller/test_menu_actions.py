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

"""Verify prepared diagnostics context-menu actions."""

from __future__ import annotations

from . import support
from .spellcheck_support import _FakeSpellcheckService


def test_controller_prepares_spelling_menu_actions_before_menu_read() -> None:
    """Prepared diagnostic menu reads should not load spelling suggestions."""

    diagnostic = support._spelling_diagnostic(4, 8, "typo")
    spellcheck = _FakeSpellcheckService()
    editor = support._FakeEditor("one typo", cursor_position=0)
    controller = support._diagnostics_controller(
        editor,
        support._FakeSurface(),
        support._FakeService(diagnostic),
        spellcheck_service=spellcheck,
    )

    controller.refresh_now()
    assert spellcheck.suggestion_words == ["typo"]
    spellcheck.suggestion_words.clear()
    editor.read_count = 0

    snapshot = controller.presentation.prepared_menu_actions_for_source_position(5)

    assert snapshot.ready is True
    assert snapshot.diagnostic_id == diagnostic.diagnostic_id
    assert [action.label for action in snapshot.actions] == [
        "type",
        "Ignore spelling",
        "Add to dictionary",
    ]
    assert spellcheck.suggestion_words == []
    assert editor.read_count == 0


def test_controller_prepared_menu_actions_include_hidden_active_word() -> None:
    """Menu action snapshots should include active-word diagnostics hidden in paint."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    controller = support._diagnostics_controller(
        support._FakeEditor("beut", cursor_position=4),
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )

    controller.refresh_now()
    snapshot = controller.presentation.prepared_menu_actions_for_source_position(2)

    assert snapshot.ready is True
    assert snapshot.diagnostic_id == diagnostic.diagnostic_id
    assert snapshot.actions


def test_controller_prepared_menu_actions_report_no_diagnostic_without_derivation() -> (
    None
):
    """Positions outside diagnostics should return ready empty action snapshots."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    editor = support._FakeEditor("beut", cursor_position=0)
    controller = support._diagnostics_controller(
        editor,
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )
    controller.refresh_now()
    editor.read_count = 0

    snapshot = controller.presentation.prepared_menu_actions_for_source_position(4)

    assert snapshot.ready is True
    assert snapshot.diagnostic_id is None
    assert snapshot.actions == ()
    assert editor.read_count == 0


def test_controller_prepared_menu_actions_report_stale_source_identity() -> None:
    """Prepared diagnostic menu reads should fail closed on stale source identity."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    editor = support._FakeEditor("beut", cursor_position=0)
    controller = support._diagnostics_controller(
        editor,
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )
    controller.refresh_now()
    editor.set_text("beautiful")
    editor.read_count = 0

    snapshot = controller.presentation.prepared_menu_actions_for_source_position(2)

    assert snapshot.ready is False
    assert snapshot.stale is True
    assert snapshot.actions == ()
    assert snapshot.unavailable_reason == "stale_diagnostics_snapshot"
    assert editor.read_count == 0


def test_controller_context_lookup_ignores_stale_snapshot_ranges() -> None:
    """Context lookup should not offer actions from stale source text snapshots."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    editor = support._FakeEditor("beut", cursor_position=0)
    controller = support._diagnostics_controller(
        editor,
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )
    controller.refresh_now()

    editor.set_text("beautiful")

    assert controller.presentation.context_diagnostic_at_source_position(2) is None


def test_controller_prepares_wildcard_menu_action_explainer() -> None:
    """Wildcard diagnostic explainers should be prepared before menu open."""

    diagnostic = support._wildcard_diagnostic(0, 9, "missing")
    controller = support._diagnostics_controller(
        support._FakeEditor("{missing}"),
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )

    controller.refresh_now()
    snapshot = controller.presentation.prepared_menu_actions_for_source_position(2)

    assert len(snapshot.actions) == 1
    assert snapshot.actions[0].label == "Wildcard not found"
    assert snapshot.actions[0].callback is None
    assert snapshot.actions[0].enabled is False


def test_controller_prepares_duplicate_menu_actions() -> None:
    """Duplicate diagnostics should prepare their context actions before menu open."""

    diagnostic = support._duplicate_diagnostic(
        normalized_segment="beta",
        first_start=7,
        first_end=11,
        duplicate_start=13,
        duplicate_end=17,
    )
    controller = support._diagnostics_controller(
        support._FakeEditor("alpha, beta, beta"),
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )

    controller.refresh_now()
    snapshot = controller.presentation.prepared_menu_actions_for_source_position(14)

    assert [action.label for action in snapshot.actions] == [
        "Remove duplicate",
        "Emphasize first",
        "Ignore duplicate",
    ]
