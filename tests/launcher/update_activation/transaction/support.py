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

"""Build deterministic filesystem fixtures for launcher update contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from sugarsubstitute_shared.launcher_update.models import (
    LauncherBundleAsset,
    LauncherUpdateRequest,
)


def _write_installed_layout(root: Path) -> Path:
    """Create an old Windows launcher plus unrelated preserved install content."""

    root.mkdir(parents=True)
    (root / "SugarSubstitute.exe").write_text("old launcher", encoding="utf-8")
    (root / "LauncherUi.exe").write_text("old launcher UI", encoding="utf-8")
    (root / "Repair.exe").write_text("old repair", encoding="utf-8")
    (root / "launcher-bin").mkdir()
    (root / "launcher-bin" / "runtime.txt").write_text("old", encoding="utf-8")
    for relative_path in (
        "app/preserve.txt",
        "runtime/preserve.txt",
        "comfyui/preserve.txt",
        "user/preserve.txt",
        "appdata/preserve.txt",
    ):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserved", encoding="utf-8")
    return root.resolve()


def _write_scheduled_update_request(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Write the minimum valid request needed to schedule an updater helper."""

    install_root = tmp_path / "SugarSubstitute"
    app_dir = install_root / "app"
    runtime_python = install_root / "runtime" / ".venv" / "bin" / "python"
    request_path = install_root / "launcher" / "updates" / "pending.json"
    staged_bundle = install_root / "launcher" / "updates" / "staged"
    app_dir.mkdir(parents=True)
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("python", encoding="utf-8")
    staged_bundle.mkdir(parents=True)
    LauncherUpdateRequest(
        install_root=install_root,
        version="9999.0.1",
        target_key="linux_x64",
        staged_bundle_dir=staged_bundle,
        relaunch=False,
    ).save(request_path)
    return request_path, runtime_python, app_dir


def _write_bundle(path: Path, *, marker: str) -> Path:
    """Write one valid Windows launcher bundle ZIP."""

    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("SugarSubstitute.exe", marker)
        bundle.writestr("LauncherUi.exe", f"{marker} UI")
        bundle.writestr("Repair.exe", f"{marker} repair")
        bundle.writestr("launcher-bin/runtime.txt", "new")
    return path


def _write_bundle_tree(path: Path, *, marker: str) -> None:
    """Write one extracted Windows launcher bundle."""

    path.mkdir(parents=True)
    (path / "SugarSubstitute.exe").write_text(marker, encoding="utf-8")
    (path / "LauncherUi.exe").write_text(f"{marker} UI", encoding="utf-8")
    (path / "Repair.exe").write_text(f"{marker} repair", encoding="utf-8")
    (path / "launcher-bin").mkdir()
    (path / "launcher-bin" / "runtime.txt").write_text("new", encoding="utf-8")


def _asset(path: Path) -> LauncherBundleAsset:
    """Create a manifest asset for one local test archive."""

    return LauncherBundleAsset(
        filename=path.name,
        url=path.resolve().as_uri(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
    )


def _manifest_payload(archive: Path) -> dict[str, object]:
    """Create the launcher portion of a production manifest."""

    asset = _asset(archive)
    return {
        "schema_version": 2,
        "channel": "stable",
        "version": "0.11.0",
        "minimum_launcher_version": "0.10.0",
        "launchers": {
            "windows_x64": {
                "filename": asset.filename,
                "url": asset.url,
                "sha256": asset.sha256,
                "size_bytes": asset.size_bytes,
            }
        },
    }


def _write_launcher_config(root: Path, *, runtime_python: Path) -> None:
    """Write the installed config fields consumed by the legacy bridge."""

    config_path = root / "launcher" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "install_root": str(root),
                "app_dir": str(root / "app"),
                "runtime_python": str(runtime_python),
                "channel": "stable",
                "update_check": {"enabled": True, "frequency": "daily"},
                "release_source": {
                    "kind": "github_release_manifest",
                    "manifest_url": "https://example.test/manifest.json",
                },
            }
        ),
        encoding="utf-8",
    )
