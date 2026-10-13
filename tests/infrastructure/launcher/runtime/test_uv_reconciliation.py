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

"""Prove trusted uv sources reconcile tools retained across runtime updates."""

from pathlib import Path
import shutil

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningError
from launcher.sugarsubstitute_launcher.runtime_generation_copy import (
    copy_reusable_runtime,
)
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider
from tests.infrastructure.launcher.runtime.support import sha256, write_uv_archive


def test_bundled_uv_replaces_a_retained_runtime_tool(tmp_path: Path) -> None:
    """Runtime updates must use their bundled tool before installing requirements."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")
    bundle = tmp_path / "bundled-uv"
    bundle.write_bytes(b"fixed uv")

    result = VerifiedUvExecutableProvider(bundled_uv_path=bundle).ensure(layout=layout)

    assert result == layout.uv_executable
    assert result.read_bytes() == b"fixed uv"
    assert list(result.parent.iterdir()) == [result]


def test_matching_bundled_uv_reuses_the_existing_file(tmp_path: Path) -> None:
    """A matching tool keeps its identity and avoids unnecessary replacement."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"fixed uv")
    original = layout.uv_executable.stat()
    bundle = tmp_path / "bundled-uv"
    bundle.write_bytes(b"fixed uv")

    result = VerifiedUvExecutableProvider(bundled_uv_path=bundle).ensure(layout=layout)

    assert result.stat().st_ino == original.st_ino
    assert result.stat().st_mtime_ns == original.st_mtime_ns


def test_missing_configured_bundle_never_falls_back_to_retained_uv(
    tmp_path: Path,
) -> None:
    """A missing trusted source stops provisioning rather than running stale uv."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")

    with pytest.raises(
        RuntimeProvisioningError, match="Bundled uv executable is missing"
    ):
        VerifiedUvExecutableProvider(bundled_uv_path=tmp_path / "missing").ensure(
            layout=layout
        )

    assert layout.uv_executable.read_bytes() == b"old uv"


def test_interrupted_uv_copy_preserves_the_retained_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial source copies never become the executable used by provisioning."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")
    bundle = tmp_path / "bundled-uv"
    bundle.write_bytes(b"fixed uv")

    def interrupt_copy(source: Path, destination: Path) -> None:
        """Fail after writing partial bytes at the external filesystem boundary."""
        destination.write_bytes(b"partial")
        raise OSError("copy interrupted")

    monkeypatch.setattr(shutil, "copy2", interrupt_copy)

    with pytest.raises(RuntimeProvisioningError, match="install uv") as failure:
        VerifiedUvExecutableProvider(bundled_uv_path=bundle).ensure(layout=layout)

    assert isinstance(failure.value.__cause__, OSError)
    assert layout.uv_executable.read_bytes() == b"old uv"
    assert list(layout.uv_executable.parent.iterdir()) == [layout.uv_executable]


def test_failed_uv_publication_preserves_the_retained_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A locked destination aborts refresh without damaging installed bytes."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")
    bundle = tmp_path / "bundled-uv"
    bundle.write_bytes(b"fixed uv")

    def reject_replacement(source: Path, destination: Path) -> Path:
        """Reject publication at the filesystem boundary."""
        raise PermissionError("destination locked")

    monkeypatch.setattr(Path, "replace", reject_replacement)

    with pytest.raises(RuntimeProvisioningError, match="install uv") as failure:
        VerifiedUvExecutableProvider(bundled_uv_path=bundle).ensure(layout=layout)

    assert isinstance(failure.value.__cause__, PermissionError)
    assert layout.uv_executable.read_bytes() == b"old uv"
    assert list(layout.uv_executable.parent.iterdir()) == [layout.uv_executable]


def test_corrupted_uv_copy_never_replaces_the_retained_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The published executable must match the verified source snapshot."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")
    bundle = tmp_path / "bundled-uv"
    bundle.write_bytes(b"fixed uv")

    def corrupt_copy(source: Path, destination: Path) -> None:
        """Return corrupted bytes from the external filesystem copy boundary."""
        destination.write_bytes(b"corrupted")

    monkeypatch.setattr(shutil, "copy2", corrupt_copy)

    with pytest.raises(RuntimeProvisioningError, match="SHA256 mismatch"):
        VerifiedUvExecutableProvider(bundled_uv_path=bundle).ensure(layout=layout)

    assert layout.uv_executable.read_bytes() == b"old uv"
    assert list(layout.uv_executable.parent.iterdir()) == [layout.uv_executable]


def test_copied_runtime_generation_reconciles_to_the_current_bundle(
    tmp_path: Path,
) -> None:
    """Reused generation assets cannot retain a different tool at provisioning."""
    previous = InstallLayout.from_root(tmp_path / "previous")
    previous.uv_executable.parent.mkdir(parents=True)
    previous.uv_executable.write_bytes(b"old uv")
    candidate = InstallLayout.from_root(tmp_path / "candidate")
    copy_reusable_runtime(
        source=previous.runtime_dir, destination=candidate.runtime_dir
    )
    bundle = tmp_path / "bundled-uv"
    bundle.write_bytes(b"fixed uv")

    result = VerifiedUvExecutableProvider(bundled_uv_path=bundle).ensure(
        layout=candidate
    )

    assert result.read_bytes() == b"fixed uv"
    assert previous.uv_executable.read_bytes() == b"old uv"


def test_verified_archive_replaces_a_retained_runtime_tool(tmp_path: Path) -> None:
    """A configured archive remains authoritative when an older tool exists."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")
    archive = write_uv_archive(
        tmp_path / "uv.zip", executable_name=layout.target.uv_executable_name
    )
    asset = ReleaseAsset(
        filename=archive.name,
        url=archive.as_uri(),
        sha256=sha256(archive),
        size_bytes=archive.stat().st_size,
    )

    result = VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)

    assert result.read_bytes() == b"uv"
    assert not (layout.runtime_dir / "uv_extract").exists()


def test_invalid_archive_preserves_the_retained_tool_and_stops_provisioning(
    tmp_path: Path,
) -> None:
    """Failed source verification cannot authorize a previously installed tool."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"old uv")
    archive = write_uv_archive(tmp_path / "uv.zip")
    asset = ReleaseAsset(
        filename=archive.name,
        url=archive.as_uri(),
        sha256="0" * 64,
        size_bytes=archive.stat().st_size,
    )

    with pytest.raises(RuntimeProvisioningError, match="SHA256 mismatch"):
        VerifiedUvExecutableProvider(uv_archive_asset=asset).ensure(layout=layout)

    assert layout.uv_executable.read_bytes() == b"old uv"


def test_preprovisioned_uv_without_a_configured_source_remains_usable(
    tmp_path: Path,
) -> None:
    """Hosts supplying their own managed tool retain the source-free contract."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.uv_executable.parent.mkdir(parents=True)
    layout.uv_executable.write_bytes(b"host tool")

    result = VerifiedUvExecutableProvider().ensure(layout=layout)

    assert result.read_bytes() == b"host tool"
