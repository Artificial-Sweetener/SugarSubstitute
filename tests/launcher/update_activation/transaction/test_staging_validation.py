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

"""Verify launcher archive staging and trusted ownership boundaries."""

from __future__ import annotations

from pathlib import Path
import stat
import zipfile

import pytest

from sugarsubstitute_shared.launcher_update.archive import SecureArchiveError
from sugarsubstitute_shared.launcher_update.models import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    MACOS_ARM64_BUNDLE,
    WINDOWS_X64_BUNDLE,
)
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
    LauncherUpdateTransactionError,
)

from .support import (
    _asset,
    _write_bundle,
    _write_bundle_tree,
    _write_installed_layout,
)


def test_stager_verifies_and_persists_complete_bundle(tmp_path: Path) -> None:
    """A checksum-pinned target bundle should become one pending request."""

    install_root = tmp_path / "SugarSubstitute"
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new")

    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(archive),
    )

    request = LauncherUpdateRequest.load(request_path)
    assert request.install_root == install_root.resolve()
    assert request.version == "0.11.0"
    assert (request.staged_bundle_dir / "SugarSubstitute.exe").read_text() == "new"
    assert (request.staged_bundle_dir / "launcher-bin" / "runtime.txt").is_file()


def test_stager_rejects_archive_path_traversal(tmp_path: Path) -> None:
    """A launcher archive must never write outside its staging directory."""

    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escaped.txt", "bad")

    with pytest.raises(SecureArchiveError):
        LauncherBundleStager().stage(
            install_root=tmp_path / "SugarSubstitute",
            version="0.11.0",
            target=WINDOWS_X64_BUNDLE,
            asset=_asset(archive),
        )

    assert not (tmp_path / "escaped.txt").exists()


def test_stager_rejects_symlink_target_that_escapes_bundle(tmp_path: Path) -> None:
    """A launcher symlink may never resolve outside its staged bundle."""

    archive = tmp_path / "unsafe-link.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        link = zipfile.ZipInfo("SugarSubstitute.app/Contents/Frameworks/Python")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "../../../../outside")

    with pytest.raises(SecureArchiveError, match="target escapes"):
        LauncherBundleStager().stage(
            install_root=tmp_path / "SugarSubstitute",
            version="0.11.0",
            target=MACOS_ARM64_BUNDLE,
            asset=_asset(archive),
        )

    assert not (tmp_path / "outside").exists()


def test_transaction_rejects_staging_outside_install_root(tmp_path: Path) -> None:
    """A forged request cannot promote arbitrary filesystem content."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    staged = tmp_path / "outside"
    _write_bundle_tree(staged, marker="malicious")
    request_path = install_root / "launcher" / "updates" / "pending.json"
    LauncherUpdateRequest(
        install_root=install_root,
        version="0.11.0",
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(request_path)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )
