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

"""Verify detached repair request validation and path confinement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    PreparedRepairRequest,
    PreparedRepairRequestError,
    RepairScope,
)


def test_request_round_trip_preserves_detached_process_behavior(tmp_path: Path) -> None:
    """A valid request should survive atomic persistence without losing intent."""

    root = (tmp_path / "install").resolve()
    staging = root / ".repair" / "staging" / "1.2.3"
    request = PreparedRepairRequest(
        install_root=root,
        scope=RepairScope.APPLICATION,
        version="1.2.3",
        channel="stable",
        target_key="windows_x64",
        staged_app_dir=staging / "app",
        staged_launcher_dir=staging / "launcher",
        staged_app_sha256="a" * 64,
        staged_launcher_sha256="b" * 64,
        wait_pid=42,
        wait_process_created_at=1234.5,
        relaunch=True,
    )
    path = root / ".repair" / "prepared.json"

    request.save(path)

    assert PreparedRepairRequest.load(path) == request


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("staged_app_dir", "{external}"),
        ("staged_launcher_dir", "{root}\\.repair\\staging\\1.2.4\\launcher"),
        ("version", "..\\hostile"),
    ],
)
def test_request_rejects_hostile_or_cross_version_staging_paths(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    """Detached execution must reject attacker-controlled staging locations."""

    root = (tmp_path / "install").resolve()
    staging = root / ".repair" / "staging" / "1.2.3"
    payload: dict[str, object] = {
        "schema_version": 1,
        "install_root": str(root),
        "scope": "application",
        "version": "1.2.3",
        "channel": "stable",
        "target_key": "windows_x64",
        "staged_app_dir": str(staging / "app"),
        "staged_launcher_dir": str(staging / "launcher"),
        "staged_app_sha256": "a" * 64,
        "staged_launcher_sha256": "b" * 64,
        "wait_pid": None,
        "wait_process_created_at": None,
        "relaunch": False,
    }
    payload[field] = value.format(root=root, external=tmp_path / "external")
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PreparedRepairRequestError):
        PreparedRepairRequest.load(path)
