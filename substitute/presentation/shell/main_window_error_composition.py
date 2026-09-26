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

"""Compose and retain the main-window error presentation owner."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.errors import ErrorPresenter


def error_presenter_for_shell(shell: Any) -> ErrorPresenter:
    """Return the shell-owned error presenter, creating it before consumers."""

    existing = getattr(shell, "_error_presenter", None)
    if existing is not None:
        return cast(ErrorPresenter, existing)
    error_presenter = ErrorPresenter(
        parent=shell,
        open_console=(
            lambda: shell.comfy_runtime_actions.set_comfy_output_panel_visible(True)
        ),
    )
    shell._error_presenter = error_presenter
    return error_presenter


__all__ = ["error_presenter_for_shell"]
