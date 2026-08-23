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

"""Verify diagnostics command action behavior."""

from __future__ import annotations

from . import support


def test_controller_replace_spelling_diagnostic_routes_command() -> None:
    """Suggestion replacement should route through the diagnostic command boundary."""

    diagnostic = support._spelling_diagnostic(4, 8, "typo")
    editor = support._FakeEditor("one typo")
    controller = support._diagnostics_controller(
        editor,
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )

    controller.presentation.replace_spelling_diagnostic(diagnostic, "type")

    assert editor.toPlainText() == "one type"
    assert editor.focused is True


def test_wildcard_diagnostics_add_context_menu_explainer() -> None:
    """Wildcard diagnostics should add one disabled context-menu explanation."""

    diagnostic = support._wildcard_diagnostic(0, 9, "missing")
    controller = support._diagnostics_controller(
        support._FakeEditor("{missing}"),
        support._FakeSurface(),
        support._FakeService(diagnostic),
    )

    actions = controller.presentation.actions_for_diagnostic(diagnostic)

    assert len(actions) == 1
    assert actions[0].label == "Wildcard not found"
    assert actions[0].callback is None
    assert actions[0].enabled is False
