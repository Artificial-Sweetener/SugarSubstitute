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

"""Sanitize the host environment before CI launches a packaged application."""

from __future__ import annotations

_FROZEN_LAUNCH_OVERRIDE_VARIABLES = (
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_LIBRARY_PATH",
    "LD_LIBRARY_PATH_ORIG",
    "DYLD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH_ORIG",
    "DYLD_FALLBACK_LIBRARY_PATH",
    "DYLD_FRAMEWORK_PATH",
    "QT_PLUGIN_PATH",
    "QML2_IMPORT_PATH",
    "QML_IMPORT_PATH",
)


def external_frozen_launch_environment(
    environment: dict[str, str],
) -> dict[str, str]:
    """Remove host Python and frozen-runtime overrides from a packaged launch."""

    launch_environment = dict(environment)
    for variable_name in _FROZEN_LAUNCH_OVERRIDE_VARIABLES:
        launch_environment.pop(variable_name, None)
    for variable_name in tuple(launch_environment):
        if variable_name.startswith("_PYI_"):
            launch_environment.pop(variable_name, None)
    return launch_environment


__all__ = ["external_frozen_launch_environment"]
