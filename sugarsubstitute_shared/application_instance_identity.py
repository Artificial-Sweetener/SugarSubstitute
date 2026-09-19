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

"""Bind application ownership to an installation and kernel account identity."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

from sugarsubstitute_shared.windows_long_paths import operational_path


def instance_identity(install_root: Path) -> str:
    """Use one election namespace across launch environments and desktop sessions."""
    normalized_root = os.path.normcase(str(operational_path(install_root).resolve()))
    payload = f"{normalized_root}\0{_account_identity()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _account_identity() -> str:
    """Read account authority from the OS rather than mutable environment labels."""
    if sys.platform == "win32":
        from sugarsubstitute_shared.windows_process_security import process_user_sid

        return process_user_sid(None)
    return str(os.getuid())
