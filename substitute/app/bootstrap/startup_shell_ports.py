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

"""Create concrete shell composition startup port bundles."""

from __future__ import annotations

from typing import Any

from substitute.app.bootstrap.startup_ports import StartupShellCompositionPorts


def create_startup_shell_composition_ports() -> StartupShellCompositionPorts:
    """Create concrete shell composition ports for startup orchestration."""

    composition = _load_composition_module()
    return StartupShellCompositionPorts(
        build_main_window=composition.build_main_window,
        show_main_window=composition.show_main_window,
        show_built_main_window=composition.show_built_main_window,
        main_window_for_shell=composition.main_window_widget,
        build_model_metadata_refresh_service=(
            composition.build_model_metadata_refresh_service
        ),
        is_comfy_http_ready=composition.is_comfy_http_ready,
    )


def _load_composition_module() -> Any:
    """Import composition only when shell composition ports are needed."""

    from substitute.app.bootstrap import composition

    return composition


__all__ = ["create_startup_shell_composition_ports"]
