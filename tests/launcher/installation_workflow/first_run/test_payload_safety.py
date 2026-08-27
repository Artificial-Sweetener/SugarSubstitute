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

"""Verify payload integrity and safe archive extraction."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.payload import (
    AppPayloadInstaller,
    PayloadInstallError,
    extract_app_payload_archive,
)
from tests.launcher.installation_workflow.first_run.support import (
    write_valid_payload_zip,
)


def test_app_payload_installer_rejects_checksum_mismatch(tmp_path: Path) -> None:
    """Payload installation fails closed when manifest checksum is wrong."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest = ReleaseManifest(
        schema_version=1,
        channel="stable",
        version="0.4.0",
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename=app_zip.name,
            url=app_zip.as_uri(),
            sha256="0" * 64,
            size_bytes=app_zip.stat().st_size,
        ),
        launchers={},
        installers={},
    )

    with pytest.raises(PayloadInstallError, match="SHA256 mismatch"):
        AppPayloadInstaller().install(
            layout=InstallLayout.from_root(tmp_path / "install"), manifest=manifest
        )


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    """Archive extraction rejects entries that escape the destination."""

    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(PayloadInstallError, match="unsafe path"):
        extract_app_payload_archive(
            zip_path=zip_path,
            destination_dir=tmp_path / "extract",
        )


def test_safe_extract_rejects_symlink_entries(tmp_path: Path) -> None:
    """Archive extraction rejects symlink-like zip entries."""

    zip_path = tmp_path / "symlink.zip"
    symlink_info = zipfile.ZipInfo("link")
    symlink_info.external_attr = 0o120777 << 16
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(symlink_info, "target")

    with pytest.raises(PayloadInstallError, match="symlink"):
        extract_app_payload_archive(
            zip_path=zip_path,
            destination_dir=tmp_path / "extract",
        )


def test_app_payload_validates_members_before_one_filesystem_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Large payloads must not canonicalize every member through the filesystem."""

    zip_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for index in range(250):
            archive.writestr(f"package/module_{index}.py", "VALUE = 1\n")
    original_resolve = Path.resolve
    resolution_count = 0

    def bounded_resolve(path: Path, strict: bool = False) -> Path:
        """Reject the former per-member filesystem canonicalization strategy."""

        nonlocal resolution_count
        resolution_count += 1
        if resolution_count > 1:
            raise AssertionError("Archive extraction resolved more than its root.")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", bounded_resolve)
    destination = tmp_path / "extract"

    extract_app_payload_archive(zip_path=zip_path, destination_dir=destination)

    assert resolution_count == 1
    assert len(tuple((destination / "package").iterdir())) == 250
