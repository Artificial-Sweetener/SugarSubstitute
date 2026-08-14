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

"""Verify transparent macOS historical-release reconstitution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from tools.ci.local_release_server import LOCAL_RELEASE_BASE_URL
from tools.ci.reconstitute_historical_macos_release import (
    reconstitute_historical_macos_release,
)


def test_reconstitution_retains_only_released_app_bundle(tmp_path: Path) -> None:
    """Qualification may remove only the reviewed PyInstaller sibling root."""

    source_root = tmp_path / "source"
    output_root = tmp_path / "output"
    app_path = _write_asset(source_root / "app.zip", b"historical app")
    launcher_path = source_root / "launcher.zip"
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(launcher_path, "w") as archive:
        archive.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            b"app launcher",
        )
        archive.writestr(
            "SugarSubstitute.app/Contents/Frameworks/Python",
            b"framework",
        )
        archive.writestr("SugarSubstitute/SugarSubstitute", b"sibling launcher")
        archive.writestr("SugarSubstitute/launcher-bin/Python", b"sibling runtime")
    manifest = {
        "schema_version": 2,
        "version": "0.20.1",
        "app": _asset_metadata(app_path),
        "launchers": {"macos_arm64": _asset_metadata(launcher_path)},
    }
    (source_root / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    manifest_path = reconstitute_historical_macos_release(
        source_root=source_root,
        output_root=output_root,
    )

    rewritten = json.loads(manifest_path.read_text(encoding="utf-8"))
    with zipfile.ZipFile(output_root / "launcher.zip") as archive:
        roots = {name.split("/", maxsplit=1)[0] for name in archive.namelist()}
    evidence = json.loads(
        (output_root / "historical-reconstitution.json").read_text(encoding="utf-8")
    )
    assert roots == {"SugarSubstitute.app"}
    assert rewritten["app"]["sha256"] == _sha256(app_path)
    assert rewritten["app"]["url"] == f"{LOCAL_RELEASE_BASE_URL}/app.zip"
    assert rewritten["launchers"]["macos_arm64"]["sha256"] == _sha256(
        output_root / "launcher.zip"
    )
    assert evidence["removed_roots"] == ["SugarSubstitute"]
    assert evidence["retained_root"] == "SugarSubstitute.app"


def test_reconstitution_rejects_unreviewed_archive_roots(tmp_path: Path) -> None:
    """A changed historical defect shape must stop qualification visibly."""

    source_root = tmp_path / "source"
    app_path = _write_asset(source_root / "app.zip", b"historical app")
    launcher_path = source_root / "launcher.zip"
    with zipfile.ZipFile(launcher_path, "w") as archive:
        archive.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            b"app launcher",
        )
        archive.writestr(
            "SugarSubstitute.app/Contents/Frameworks/Python",
            b"framework",
        )
        archive.writestr("unreviewed/file", b"unexpected")
    (source_root / "manifest.json").write_text(
        json.dumps(
            {
                "version": "0.20.1",
                "app": _asset_metadata(app_path),
                "launchers": {"macos_arm64": _asset_metadata(launcher_path)},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="differ from the reviewed defect"):
        reconstitute_historical_macos_release(
            source_root=source_root,
            output_root=tmp_path / "output",
        )


def _write_asset(path: Path, content: bytes) -> Path:
    """Write one fixture release asset."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _asset_metadata(path: Path) -> dict[str, object]:
    """Return manifest metadata for one fixture release asset."""

    return {
        "filename": path.name,
        "url": f"https://example.test/{path.name}",
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _sha256(path: Path) -> str:
    """Return one fixture SHA256 digest."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
