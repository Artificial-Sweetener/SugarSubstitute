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

"""Bind completed worker output to the preparation selected by its parent."""

from dataclasses import replace
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.paths import (
    RepairPreparationPaths,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.repair_preparation_result import (
    load_preparation_result,
)


def _request(root: Path) -> PreparedRepairRequest:
    """Create valid synthetic metadata without pretending that it verifies asset bytes."""
    paths = RepairPreparationPaths(root, "1.2.3", "a" * 32)
    return PreparedRepairRequest(
        install_root=root,
        scope=RepairScope.APPLICATION,
        version="1.2.3",
        channel="stable",
        target_key=WINDOWS_X64.key,
        staged_app_dir=paths.staging_root / "app",
        staged_launcher_dir=paths.staging_root / "launcher",
        staged_app_sha256="a" * 64,
        staged_launcher_sha256="b" * 64,
        preparation_id="a" * 32,
        helper_bundle_dir=root / ".repair" / "helper" / "1.2.3" / "session" / "bundle",
    )


def test_result_uses_canonical_request_for_the_selected_install(tmp_path: Path) -> None:
    """Read only the request derived from the parent's root and validated identity."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    request = _request(layout.root)
    request.save(request.request_path)
    result = load_preparation_result(
        {"kind": "succeeded", "version": "1.2.3", "preparation_id": "a" * 32},
        layout=layout,
        scope=RepairScope.APPLICATION,
    )
    assert result.request == request
    assert result.request_path == request.request_path


@pytest.mark.parametrize(
    "message",
    [
        {},
        {"kind": "failed", "version": "1.2.3", "preparation_id": "a" * 32},
        {"kind": "succeeded", "version": "../outside", "preparation_id": "a" * 32},
        {"kind": "succeeded", "version": "1.2.3", "preparation_id": "../outside"},
        {"kind": "succeeded", "version": "1.2.3", "preparation_id": None},
        {
            "kind": "succeeded",
            "version": "1.2.3",
            "preparation_id": "a" * 32,
            "request_path": "outside.json",
        },
    ],
)
def test_result_rejects_invalid_identity_before_reading_files(
    tmp_path: Path, message: dict[str, object]
) -> None:
    """Reject malformed result locations instead of following child-supplied paths."""
    with pytest.raises(ValueError):
        load_preparation_result(
            message,
            layout=InstallLayout.from_root(tmp_path, target=WINDOWS_X64),
            scope=RepairScope.APPLICATION,
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "mismatch",
    ["root", "target", "scope", "identity", "version", "helper", "wait", "relaunch"],
)
def test_result_rejects_valid_requests_with_different_parent_intent(
    tmp_path: Path, mismatch: str
) -> None:
    """Keep internally valid but unrelated metadata from authorizing the next repair."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    request = _request(layout.root)
    expected_path = request.request_path
    if mismatch == "root":
        request = _request(tmp_path / "other")
    elif mismatch == "target":
        request = replace(request, target_key="linux_x64")
    elif mismatch == "scope":
        request = replace(request, scope=RepairScope.FULL_MANAGED_COMFY)
    elif mismatch == "identity":
        paths = RepairPreparationPaths(layout.root, "1.2.3", "b" * 32)
        request = replace(
            request,
            preparation_id="b" * 32,
            staged_app_dir=paths.staging_root / "app",
            staged_launcher_dir=paths.staging_root / "launcher",
        )
    elif mismatch == "version":
        paths = RepairPreparationPaths(layout.root, "1.2.4", "a" * 32)
        request = replace(
            request,
            version="1.2.4",
            staged_app_dir=paths.staging_root / "app",
            staged_launcher_dir=paths.staging_root / "launcher",
            helper_bundle_dir=layout.root / ".repair/helper/1.2.4/session/bundle",
        )
    elif mismatch == "helper":
        request = replace(request, helper_bundle_dir=None)
    elif mismatch == "wait":
        request = replace(request, wait_pid=123, wait_process_created_at=1234.0)
    else:
        request = replace(request, relaunch=True)
    request.save(expected_path)
    with pytest.raises(ValueError, match="selected preparation"):
        load_preparation_result(
            {"kind": "succeeded", "version": "1.2.3", "preparation_id": "a" * 32},
            layout=layout,
            scope=RepairScope.APPLICATION,
        )
