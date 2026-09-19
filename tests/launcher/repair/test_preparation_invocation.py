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

"""Validate inert preparation inputs independently of release acquisition."""

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from launcher.sugarsubstitute_launcher.repair_preparation_invocation import (
    RepairPreparationInvocation,
)
from launcher.sugarsubstitute_launcher.repair_preparation_source import (
    RepairPreparationSource,
)


def test_invocation_round_trip_preserves_selected_install_and_source(
    tmp_path: Path,
) -> None:
    """Pass target and scope explicitly without reading a manifest or creating an install."""
    invocation = RepairPreparationInvocation(
        InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64),
        RepairPreparationSource.capture(LocalFolderReleaseSource(tmp_path / "release")),
        RepairScope.APPLICATION,
    )
    path = tmp_path / "control.json"
    invocation.save(path)
    restored = RepairPreparationInvocation.load(path)
    assert restored.layout.root == invocation.layout.root
    assert restored.layout.target == WINDOWS_X64
    assert restored.source == invocation.source
    assert restored.scope == invocation.scope
    assert not invocation.layout.root.exists()
    assert not (tmp_path / "release").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("install_root", "relative"),
        ("install_root", ""),
        ("install_root", None),
        ("target", "unknown"),
        ("target", True),
        ("scope", "unknown"),
        ("scope", None),
        ("source", {"kind": "unsupported"}),
    ],
)
def test_invocation_rejects_invalid_boundaries(
    tmp_path: Path, field: str, value: object
) -> None:
    """Reject invalid process input before reaching any preparation service."""
    payload: dict[str, object] = {
        "install_root": str(tmp_path / "install"),
        "target": WINDOWS_X64.key,
        "scope": RepairScope.APPLICATION.value,
        "source": {"kind": "local", "root": str(tmp_path / "release")},
    }
    payload[field] = value
    path = tmp_path / "control.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        RepairPreparationInvocation.load(path)
    assert not (tmp_path / "install").exists()


@pytest.mark.parametrize(
    "contents",
    ["[]", "{", " " * (64 * 1024 + 1)],
    ids=["non-object", "invalid-json", "oversized"],
)
def test_invocation_rejects_invalid_or_oversized_documents(
    tmp_path: Path, contents: str
) -> None:
    """Bound worker input parsing even when the private document is damaged."""
    path = tmp_path / "control.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        RepairPreparationInvocation.load(path)
