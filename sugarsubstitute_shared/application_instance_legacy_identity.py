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

"""Preserve the released environment-scoped native launch address."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def released_instance_identity(install_root: Path) -> str:
    """Reproduce the public rendezvous contract for previously packaged launchers."""
    root = os.path.normcase(str(install_root.expanduser().resolve()))
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if not user:
        getuid = getattr(os, "getuid", None)
        user = str(int(getuid()) if callable(getuid) else 0)
    payload = f"{root}\0{user}\0{_released_session_label()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _released_session_label() -> str:
    """Keep the former environment precedence solely for protocol compatibility."""
    for name in ("XDG_SESSION_ID", "WAYLAND_DISPLAY", "DISPLAY", "SESSIONNAME"):
        value = os.environ.get(name)
        if value:
            return value
    if os.name == "nt":
        from sugarsubstitute_shared.windows_process_security import process_session_id

        try:
            return str(process_session_id(os.getpid()))
        except OSError:
            _LOGGER.warning(
                "Could not resolve the released launch session label", exc_info=True
            )
    return "default"
