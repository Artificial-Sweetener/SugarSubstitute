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

"""Share the installed-application runtime-mode handoff contract."""

from __future__ import annotations

from collections.abc import Mapping


APPLICATION_RUNTIME_MODE_ENV = "SUBSTITUTE_RUNTIME_MODE"
PACKAGED_APPLICATION_RUNTIME_MODE = "release"


def packaged_application_environment(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Return an app-child environment with release policy enabled."""

    child_environment = dict(environment)
    child_environment[APPLICATION_RUNTIME_MODE_ENV] = PACKAGED_APPLICATION_RUNTIME_MODE
    return child_environment


__all__ = [
    "APPLICATION_RUNTIME_MODE_ENV",
    "PACKAGED_APPLICATION_RUNTIME_MODE",
    "packaged_application_environment",
]
