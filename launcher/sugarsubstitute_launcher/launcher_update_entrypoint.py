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

"""Run launcher mutation inside the durable bootstrap instead of app code."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


_UPDATE_ARGUMENT = "--apply-launcher-update"


def run_launcher_update_invocation(arguments: Sequence[str]) -> int | None:
    """Apply an internal update request or leave ordinary startup untouched."""

    if not arguments or arguments[0] != _UPDATE_ARGUMENT:
        return None
    if len(arguments) != 2:
        raise ValueError(f"usage: {_UPDATE_ARGUMENT} REQUEST_PATH")
    from sugarsubstitute_shared.launcher_update.helper import (
        apply_launcher_update_request,
    )

    apply_launcher_update_request(Path(arguments[1]).expanduser().resolve())
    return 0


__all__ = ["run_launcher_update_invocation"]
