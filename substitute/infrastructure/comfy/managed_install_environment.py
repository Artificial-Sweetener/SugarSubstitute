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

"""Build path-safe subprocess environments for managed installation."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path


def build_managed_install_environment(
    scratch_root: Path,
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a managed-install environment rooted in materialized scratch paths."""

    temp_dir = scratch_root / "temp"
    pip_cache_dir = scratch_root / "pip-cache"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pip_cache_dir.mkdir(parents=True, exist_ok=True)
    result = dict(os.environ if env is None else env)
    result["TEMP"] = str(temp_dir)
    result["TMP"] = str(temp_dir)
    result["TMPDIR"] = str(temp_dir)
    result["PIP_CACHE_DIR"] = str(pip_cache_dir)
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    result["PYTHONUTF8"] = "1"
    result["PYTHONIOENCODING"] = "utf-8:replace"
    return result


__all__ = ["build_managed_install_environment"]
