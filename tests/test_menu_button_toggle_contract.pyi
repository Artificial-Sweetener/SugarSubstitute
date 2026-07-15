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

"""Type stubs for wrapper contract tests."""

from __future__ import annotations

def _install_widget_stubs(monkeypatch: object) -> None: ...
def _import_module(monkeypatch: object) -> object: ...
def test_toggle_transparent_dropdown_button_closes_same_menu_on_second_click(
    monkeypatch: object,
) -> None: ...
def test_toggle_split_tool_button_rewires_drop_arrow_to_toggle_flyout(
    monkeypatch: object,
) -> None: ...
def test_toggle_primary_split_button_preserves_primary_action(
    monkeypatch: object,
) -> None: ...
def test_external_popup_close_clears_tracked_open_state(
    monkeypatch: object,
) -> None: ...
def test_same_click_close_does_not_reopen_popup_on_release(
    monkeypatch: object,
) -> None: ...
