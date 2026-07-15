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

"""Own managed-install scratch storage and its subprocess environment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import shutil
from uuid import uuid4

_INSTALLER_TEMP_ROOT_NAME = "installer-temp"
_WORKSPACE_TEMP_ROOT_NAME = ".substitute-installer-temp"


@dataclass(frozen=True, slots=True)
class ManagedInstallScratch:
    """Own one managed install scratch directory and subprocess environment."""

    root: Path

    @property
    def temp_dir(self) -> Path:
        """Return the Python temporary-file directory for this install run."""

        return self.root / "temp"

    @property
    def pip_cache_dir(self) -> Path:
        """Return the pip download/cache directory for this install run."""

        return self.root / "pip-cache"

    def create(self) -> None:
        """Create scratch directories before subprocesses inherit them."""

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.pip_cache_dir.mkdir(parents=True, exist_ok=True)

    def apply_to(self, env: Mapping[str, str] | None = None) -> dict[str, str]:
        """Return a subprocess environment that keeps setup scratch local."""

        result = dict(os.environ if env is None else env)
        result["TEMP"] = str(self.temp_dir)
        result["TMP"] = str(self.temp_dir)
        result["PIP_CACHE_DIR"] = str(self.pip_cache_dir)
        result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        result["PYTHONUTF8"] = "1"
        result["PYTHONIOENCODING"] = "utf-8:replace"
        return result

    def cleanup(self) -> None:
        """Remove scratch data after subprocesses have exited."""

        resolved_root = self.root.resolve()
        if not _is_safe_scratch_cleanup_root(resolved_root):
            raise RuntimeError(
                f"Refusing to clean unsafe scratch root: {resolved_root}"
            )
        if resolved_root.exists():
            shutil.rmtree(resolved_root)


def default_installer_temp_root(workspace: Path) -> Path:
    """Return a workspace-derived scratch root when no install root is supplied."""

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return (
        workspace.parent
        / _WORKSPACE_TEMP_ROOT_NAME
        / workspace.name
        / f"run-{timestamp}-{uuid4().hex[:8]}"
    )


def _is_safe_scratch_cleanup_root(path: Path) -> bool:
    """Return whether one scratch root is safe for recursive cleanup."""

    if path == Path(path.anchor):
        return False
    parts = set(path.parts)
    if (
        _INSTALLER_TEMP_ROOT_NAME not in parts
        and _WORKSPACE_TEMP_ROOT_NAME not in parts
    ):
        return False
    return bool(path.name)
