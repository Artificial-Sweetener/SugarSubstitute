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

"""Resolve immutable application launch context shared across process owners."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def application_launch_install_root(
    argv: Sequence[str],
    *,
    app_root: Path,
) -> Path:
    """Resolve the installation root before application bootstrap starts."""

    prefix = "--install-root="
    for raw_argument in argv:
        if raw_argument.startswith(prefix):
            raw_path = raw_argument[len(prefix) :].strip()
            if raw_path:
                return Path(raw_path).expanduser().resolve()
    return app_root.resolve()


__all__ = ["application_launch_install_root"]
