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

"""Verify diagnostics visibility publication behavior."""

from __future__ import annotations

from . import support


def test_controller_filters_active_word_before_updating_surface() -> None:
    """Controller should keep full snapshot but display only policy-visible diagnostics."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("beut", cursor_position=4)
    controller = support._diagnostics_controller(editor, surface, service)

    controller.refresh_now()

    assert service.snapshot_calls == ["beut"]
    assert not surface.diagnostics
    assert surface.clear_count == 1
    assert controller.presentation.visible_diagnostic_at_source_position(2) is None


def test_controller_refreshes_visible_diagnostics_on_cursor_move_without_backend_refresh() -> (
    None
):
    """Caret movement should update visibility from the cached snapshot."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("beut", cursor_position=4)
    controller = support._diagnostics_controller(editor, surface, service)
    controller.refresh_now()
    assert not surface.diagnostics

    editor.set_cursor_position(0)
    controller.refresh_visible_diagnostics()

    assert service.snapshot_calls == ["beut"]
    assert surface.diagnostics == (diagnostic,)


def test_controller_skips_unchanged_visible_diagnostic_surface_update() -> None:
    """Repeated visibility refreshes should not repush unchanged diagnostics."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("beut", cursor_position=0)
    controller = support._diagnostics_controller(editor, surface, service)
    controller.refresh_now()
    assert surface.diagnostics == (diagnostic,)
    assert surface.set_count == 1

    controller.refresh_visible_diagnostics()

    assert surface.diagnostics == (diagnostic,)
    assert surface.set_count == 1


def test_controller_context_lookup_uses_full_snapshot_for_active_word() -> None:
    """Context lookup should include hidden active-word diagnostics for actions."""

    diagnostic = support._spelling_diagnostic(0, 4, "beut")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("beut", cursor_position=4)
    controller = support._diagnostics_controller(editor, surface, service)

    controller.refresh_now()

    assert not surface.diagnostics
    assert service.snapshot_calls == ["beut"]
    assert (
        controller.presentation.context_diagnostic_at_source_position(2) == diagnostic
    )
    assert controller.presentation.context_diagnostic_at_source_position(4) is None


def test_controller_filters_active_wildcard_diagnostic_while_editing() -> None:
    """Missing wildcard diagnostics should stay hidden while the placeholder is active."""

    diagnostic = support._wildcard_diagnostic(0, 9, "missing")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("{missing}", cursor_position=9)
    controller = support._diagnostics_controller(editor, surface, service)

    controller.refresh_now()

    assert not surface.diagnostics
    assert (
        controller.presentation.context_diagnostic_at_source_position(2) == diagnostic
    )

    editor.set_text("{missing}, suffix")
    service._diagnostic = support._wildcard_diagnostic(0, 9, "missing")  # noqa: SLF001
    controller.refresh_now()

    assert surface.diagnostics == (diagnostic,)
