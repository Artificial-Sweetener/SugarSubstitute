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
from zipfile import ZipFile

import pytest

from tools import prepare_mpv_runtime
from tools.prepare_mpv_runtime import (
    _extract_archive,
    _require_embeddable_runtime,
    _require_sha256,
    _require_windows_x64,
    _stage_runtime,
)


def test_runtime_stage_replaces_owned_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote every verified runtime DLL without disturbing sibling content."""

    source = tmp_path / "source"
    source.mkdir()
    runtime_files = {
        "libmpv-2.dll": b"new-runtime",
        "avcodec-60.dll": b"codec-runtime",
    }
    monkeypatch.setattr(
        prepare_mpv_runtime,
        "WINDOWS_RUNTIME_SHA256",
        {
            name: hashlib.sha256(content).hexdigest()
            for name, content in runtime_files.items()
        },
    )
    for name, content in runtime_files.items():
        (source / name).write_bytes(content)
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
    assert (destination_dir / "avcodec-60.dll").read_bytes() == b"codec-runtime"
    assert sibling.read_text(encoding="utf-8") == "keep"
    assert not destination.with_suffix(".dll.partial").exists()


def test_runtime_rejects_scripting_enabled_windows_build(tmp_path: Path) -> None:
    """Exclude LuaJIT and JavaScript from the embedded Windows renderer."""

    runtime = tmp_path / "libmpv-2.dll"
    runtime.write_bytes(b"-Dlua=disabled\0-Djavascript=disabled\0safe")
    _require_embeddable_runtime(runtime)

    runtime.write_bytes(b"-Dlua=enabled\0-Djavascript=disabled\0LuaJIT 2.1")
    with pytest.raises(RuntimeError, match="unsafe"):
        _require_embeddable_runtime(runtime)


def test_archive_extraction_rejects_path_traversal(tmp_path: Path) -> None:
    """Keep a malformed release archive inside the extraction workspace."""

    archive = tmp_path / "runtime.zip"
    with ZipFile(archive, mode="w") as bundle:
        bundle.writestr("../escape.dll", b"unsafe")

    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="unsafe path"):
        _extract_archive(archive=archive, destination=destination)
    assert not (tmp_path / "escape.dll").exists()


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
