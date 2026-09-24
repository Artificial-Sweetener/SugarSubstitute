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

"""Verify pinned libmpv runtime preparation safety and provenance."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.prepare_mpv_runtime import (
    _require_sha256,
    _require_windows_x64,
    _stage_runtime,
)


def test_runtime_stage_replaces_only_owned_library(tmp_path: Path) -> None:
    """Promote a verified library without disturbing sibling content."""

    source = tmp_path / "source" / "libmpv-2.dll"
    source.parent.mkdir()
    source.write_bytes(b"new-runtime")
    output_root = tmp_path / "output"
    destination_dir = output_root / "windows-x64"
    destination_dir.mkdir(parents=True)
    destination = destination_dir / "libmpv-2.dll"
    destination.write_bytes(b"old-runtime")
    sibling = destination_dir / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")

    staged = _stage_runtime(source=source, output_root=output_root)

    assert staged == destination
    assert staged.read_bytes() == b"new-runtime"
    assert sibling.read_text(encoding="utf-8") == "keep"
    assert not destination.with_suffix(".dll.partial").exists()


def test_runtime_checksum_rejects_drift(tmp_path: Path) -> None:
    """Fail closed when the downloaded archive or binary changes."""

    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"expected")
    expected = hashlib.sha256(b"expected").hexdigest()
    _require_sha256(artifact, expected, label="test artifact")

    artifact.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="SHA-256"):
        _require_sha256(artifact, expected, label="test artifact")


def test_prebuilt_runtime_accepts_only_audited_host() -> None:
    """Prevent the Windows build from being mislabeled for another target."""

    _require_windows_x64(platform_name="win32", machine="AMD64")
    with pytest.raises(RuntimeError, match="Windows x64 only"):
        _require_windows_x64(platform_name="linux", machine="x86_64")
