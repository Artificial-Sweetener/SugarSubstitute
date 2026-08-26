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

"""Qualify verified uv archive extraction and rejection behavior."""

from __future__ import annotations

import io
import re
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from launcher.sugarsubstitute_launcher.platforms import LINUX_X64, WINDOWS_X64
from launcher.sugarsubstitute_launcher.runtime import UvManagedRuntimeInstaller
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningError
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider

from tests.infrastructure.launcher.runtime.support import (
    RecordingRuntimeRunner,
    sha256,
    write_file,
    write_posix_uv_archive,
    write_uv_archive,
)


def test_runtime_provisioner_requires_requirements_file(tmp_path: Path) -> None:
    """Runtime provisioning fails clearly before running uv without requirements."""

    layout = InstallLayout.from_root(tmp_path / "install")
    bundled_uv = tmp_path / "uv.exe"
    bundled_uv.write_bytes(b"uv")

    with pytest.raises(RuntimeProvisioningError, match="Requirements file is missing"):
        UvManagedRuntimeInstaller(
            uv_provider=VerifiedUvExecutableProvider(bundled_uv_path=bundled_uv)
        ).provision(layout=layout)


def test_runtime_provisioner_requires_verified_uv_source(tmp_path: Path) -> None:
    """Missing uv fails closed unless a bundled or checksummed source exists."""

    layout = InstallLayout.from_root(tmp_path / "install")
    write_file(layout.app_dir / "requirements.txt", "PySide6\n")

    expected_message = re.escape(f"{layout.target.uv_executable_name} is missing")
    with pytest.raises(RuntimeProvisioningError, match=expected_message):
        UvManagedRuntimeInstaller(runner=RecordingRuntimeRunner()).provision(
            layout=layout
        )


def test_runtime_provisioner_extracts_checksummed_uv_archive(tmp_path: Path) -> None:
    """A configured uv archive is verified before extraction."""

    layout = InstallLayout.from_root(tmp_path / "install")
    archive_path = write_uv_archive(
        tmp_path / "uv.zip",
        executable_name=layout.target.uv_executable_name,
    )
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    uv_executable = VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(
        layout=layout
    )

    assert uv_executable == layout.uv_executable
    assert uv_executable.read_bytes() == b"uv"
    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_extracts_posix_uv_archive_as_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified POSIX uv tarball produces an executable managed tool."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)
    archive_path = write_posix_uv_archive(tmp_path / "uv.tar.gz")
    chmod_calls: list[tuple[Path, int]] = []
    original_chmod = Path.chmod

    def record_chmod(path: Path, mode: int) -> None:
        """Record permission changes while retaining host filesystem behavior."""

        chmod_calls.append((path, mode))
        original_chmod(path, mode)

    monkeypatch.setattr(Path, "chmod", record_chmod)
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    uv_executable = VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(
        layout=layout
    )

    assert uv_executable == layout.runtime_dir / "uv" / "uv"
    assert uv_executable.read_bytes() == b"uv"
    assert any(path == uv_executable and mode & 0o111 for path, mode in chmod_calls)
    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_rejects_uv_zip_symlink(tmp_path: Path) -> None:
    """The uv ZIP policy rejects links even when their target is contained."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    archive_path = tmp_path / "uv.zip"
    symlink = zipfile.ZipInfo("uv-test-target/uv.exe")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(symlink, "real-uv.exe")
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(RuntimeProvisioningError, match="must not be a symlink"):
        VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)

    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_rejects_uv_tar_path_traversal(tmp_path: Path) -> None:
    """The uv TAR policy validates every path before writing any member."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)
    archive_path = tmp_path / "uv.tar.gz"
    payload = b"escape"
    member = tarfile.TarInfo("../escaped")
    member.size = len(payload)
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(payload))
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(RuntimeProvisioningError, match="unsafe path"):
        VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)

    assert not (tmp_path / "escaped").exists()
    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_rejects_uv_tar_links(tmp_path: Path) -> None:
    """The uv TAR policy rejects links before extracting archive content."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)
    archive_path = tmp_path / "uv.tar.gz"
    member = tarfile.TarInfo("uv-x86_64-unknown-linux-gnu/uv")
    member.type = tarfile.SYMTYPE
    member.linkname = "real-uv"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.addfile(member)
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(RuntimeProvisioningError, match="unsupported type"):
        VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)

    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_rejects_bad_uv_archive_checksum(tmp_path: Path) -> None:
    """A configured uv archive with a mismatched checksum is not extracted."""

    layout = InstallLayout.from_root(tmp_path / "install")
    archive_path = write_uv_archive(tmp_path / "uv.zip")
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256="0" * 64,
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(RuntimeProvisioningError, match="SHA256 mismatch"):
        VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)


def test_runtime_provisioner_rejects_archive_without_target_uv_executable(
    tmp_path: Path,
) -> None:
    """A verified archive without the target executable should fail explicitly."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    archive_path = write_uv_archive(
        tmp_path / "uv.zip",
        executable_name="not-uv.exe",
    )
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    expected_message = re.escape(
        f"Downloaded uv archive does not contain {layout.target.uv_executable_name}"
    )
    with pytest.raises(RuntimeProvisioningError, match=expected_message):
        VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)
    assert not (layout.runtime_dir / "uv_extract").exists()
