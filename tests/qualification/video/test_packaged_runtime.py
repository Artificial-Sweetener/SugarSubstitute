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

"""Prove synthetic fixtures and packaged Windows playback end to end."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile

import pytest

from tools.release_assets.payload import build_app_payload_zip, inspect_payload_zip


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ROOT = _REPOSITORY_ROOT / "tests" / "fixtures" / "video"


def test_synthetic_video_fixture_manifest_is_complete_and_exact() -> None:
    """Every committed video fixture should have explicit ownership and checksum."""

    manifest = tomllib.loads(
        (_FIXTURE_ROOT / "manifest.toml").read_text(encoding="utf-8")
    )
    assert manifest["license"] == "GPL-3.0-or-later"
    records = manifest["fixture"]
    declared = {str(record["path"]) for record in records}
    committed = {
        path.name for path in _FIXTURE_ROOT.iterdir() if path.name != "manifest.toml"
    }
    assert declared == committed
    for record in records:
        path = _FIXTURE_ROOT / str(record["path"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        assert str(record["purpose"]).strip()


@pytest.mark.platforms("windows")
def test_windows_payload_runs_real_video_acceptance_without_ambient_path(
    tmp_path: Path,
) -> None:
    """Extract the release payload and drive its bundled runtime from hostile paths."""

    payload = tmp_path / "SugarSubstitute app payload.zip"
    build_app_payload_zip(repo_root=_REPOSITORY_ROOT, output_path=payload)
    archive_names = inspect_payload_zip(payload)
    runtime_relative = "third_party/bin/mpv/windows-x64/libmpv-2.dll"
    assert runtime_relative in archive_names

    application_root = tmp_path / "installed app üñîçødé with spaces"
    with zipfile.ZipFile(payload) as archive:
        archive.extractall(application_root)
    evidence_dir = tmp_path / "qualification evidence üñîçødé"
    environment = os.environ.copy()
    environment["PATH"] = ""
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(_REPOSITORY_ROOT / "tools" / "qualify_packaged_video_runtime.py"),
            "--application-root",
            str(application_root),
            "--fixture-root",
            str(_FIXTURE_ROOT),
            "--evidence-dir",
            str(evidence_dir),
        ],
        cwd=application_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    evidence = json.loads(
        (evidence_dir / "packaged-video-runtime.json").read_text(encoding="utf-8")
    )
    assert Path(evidence["application_root"]) == application_root
    assert Path(evidence["runtime_path"]) == application_root / runtime_relative
    assert evidence["ambient_path"] == ""
    assert evidence["probe"]["truncated_rejected"] is True
    assert len(evidence["playback"]["vfr_step"]["distinct_deltas"]) >= 2
    assert (
        evidence["playback"]["bframe_step"]["after_previous"]
        < evidence["playback"]["bframe_step"]["after_next"]
    )
    assert evidence["playback"]["loop"]["default_enabled"] is True
    assert evidence["playback"]["audio_visibility"] == {
        "effectively_muted": True,
        "paused": True,
        "user_muted": False,
        "volume": 37,
    }
