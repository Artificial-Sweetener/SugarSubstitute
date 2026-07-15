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

"""Reset install-owned onboarding artifacts without touching user content."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat


_INSTALL_STATE_DIR_NAMES = ("config", "state", "runtime", "comfyui")


def reset_install_state(installation_root: Path) -> tuple[Path, ...]:
    """Remove install-owned directories and return the paths that were cleared."""

    removed: list[Path] = []
    for directory_name in _INSTALL_STATE_DIR_NAMES:
        target = installation_root / directory_name
        if target.exists():
            shutil.rmtree(target, onexc=_clear_readonly_and_retry)
            removed.append(target)
    return tuple(removed)


def _clear_readonly_and_retry(
    func: object,
    path: str,
    excinfo: BaseException,
) -> None:
    """Clear readonly attributes and retry the failing removal callback."""

    _ = excinfo
    os.chmod(path, stat.S_IWRITE)
    if callable(func):
        func(path)
