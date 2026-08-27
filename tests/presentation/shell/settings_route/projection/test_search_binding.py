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

"""Test settings-route search binding contracts."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.settings_route_controller import (
    SettingsRouteController,
)

from .support import (
    _SettingsPanel,
    _SettingsToolbarSearchBox,
)


def test_settings_toolbar_search_wires_to_panel_query_state() -> None:
    """Toolbar Settings search should mirror and update panel-owned query state."""

    search_box = _SettingsToolbarSearchBox()
    panel = _SettingsPanel("credential")
    view = SimpleNamespace(
        settingsToolbarSearchBox=search_box,
        settings_workspace_panel=panel,
    )

    SettingsRouteController(
        view, error_presenter=None
    ).connect_settings_toolbar_search()

    assert search_box.search_text_calls == ["credential"]

    search_box.searchQueryChanged.emit("thumbnail")
    panel.searchQueryChanged.emit("server")

    assert panel.query_calls == ["thumbnail"]
    assert search_box.search_text_calls == ["credential", "server"]
