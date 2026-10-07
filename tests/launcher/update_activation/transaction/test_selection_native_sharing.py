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

"""Prove that native sharing failures cannot silently change launcher selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from .native_file_sharing import exclusive_read
from .support import _write_bundle_tree, _write_installed_layout

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize(
    "locked_part", ["selection", "metadata", "payload", "contract"]
)
def test_locked_selected_bundle_preserves_authoritative_identity(
    tmp_path: Path, locked_part: str
) -> None:
    """Fail observably during a sharing conflict and recover the same generation."""
    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher" / "updates" / "candidate"
    _write_bundle_tree(staged, marker="selected-compatible")
    assets = staged / "launcher-bin" / "launcher_assets"
    assets.mkdir()
    (assets / "launcher-contract.json").write_text(
        '{"schema_version":1,"delegation_protocol":1}', encoding="utf-8"
    )
    selection = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)
    candidate = selection.publish(staged, version="0.27.1")
    selection.activate(candidate)
    paths = {
        "selection": root / "launcher" / "bundles" / "active.json",
        "metadata": candidate.root.parent / "bundle.json",
        "payload": candidate.root / "SugarSubstitute.exe",
        "contract": candidate.root
        / "launcher-bin"
        / "launcher_assets"
        / "launcher-contract.json",
    }
    from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths

    paths["selection"] = LauncherBundlePaths(root).selection
    with exclusive_read(paths[locked_part]):
        with pytest.raises(OSError):
            selection.resolve()
    assert selection.resolve() == candidate
    assert not (candidate.root.parent / "rejected.json").exists()
