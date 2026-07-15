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

"""Discover development release channels for local installer testing."""

from __future__ import annotations

import os
import sys
from pathlib import Path


RELEASE_ROOT_ENV = "SUGARSUBSTITUTE_RELEASE_ROOT"
LOCAL_RELEASE_CHANNEL_DIR_NAME = ".local-release-channel"


def discover_local_release_root() -> Path:
    """Resolve a local release-channel root for development installs."""

    env_root = os.environ.get(RELEASE_ROOT_ENV)
    if env_root:
        return _validate_release_root(Path(env_root))

    executable_dir = Path(sys.executable).resolve().parent
    source_root = Path(__file__).resolve().parents[2]
    candidates = (
        Path.cwd() / LOCAL_RELEASE_CHANNEL_DIR_NAME,
        Path.cwd().parent / LOCAL_RELEASE_CHANNEL_DIR_NAME,
        executable_dir / LOCAL_RELEASE_CHANNEL_DIR_NAME,
        executable_dir.parent / LOCAL_RELEASE_CHANNEL_DIR_NAME,
        source_root / LOCAL_RELEASE_CHANNEL_DIR_NAME,
    )
    for candidate in candidates:
        if (candidate / "manifest.json").is_file():
            return candidate.resolve()
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"No local release manifest found. Searched: {searched}")


def _validate_release_root(release_root: Path) -> Path:
    """Return a release root after confirming it contains a manifest."""

    resolved_root = release_root.expanduser().resolve()
    manifest_path = resolved_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Local release manifest does not exist: {manifest_path}"
        )
    return resolved_root
