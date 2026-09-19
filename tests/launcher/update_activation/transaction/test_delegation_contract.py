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

"""Verify packaged delegation declarations across supported bundle layouts."""

from pathlib import Path
import shutil

import pytest

from sugarsubstitute_shared.launcher_update.delegation_contract import (
    supports_launcher_delegation,
)
from sugarsubstitute_shared.launcher_update.targets import (
    WINDOWS_X64_BUNDLE,
    LINUX_X64_BUNDLE,
    MACOS_ARM64_BUNDLE,
    LauncherBundleTarget,
)


@pytest.mark.parametrize(
    "target", [WINDOWS_X64_BUNDLE, LINUX_X64_BUNDLE, MACOS_ARM64_BUNDLE]
)
def test_packaged_contract_matches_supported_owner_protocol(
    tmp_path: Path, target: LauncherBundleTarget
) -> None:
    """Admit the actual shipped contract from each platform's runtime data root."""
    source = Path(__file__).resolve().parents[4] / "launcher" / "launcher-contract.json"
    destination = (
        tmp_path / target.support_relative_path / "launcher_assets" / source.name
    )
    destination.parent.mkdir(parents=True)
    shutil.copyfile(source, destination)
    assert supports_launcher_delegation(tmp_path, target)


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "[]",
        '{"schema_version": true, "delegation_protocol": 1}',
        '{"schema_version": 1, "delegation_protocol": true}',
    ],
)
def test_invalid_contract_does_not_authorize_shared_ownership(
    tmp_path: Path, payload: str
) -> None:
    """Reject JSON values whose shapes or primitive types cannot prove compatibility."""
    destination = (
        tmp_path
        / WINDOWS_X64_BUNDLE.support_relative_path
        / "launcher_assets"
        / "launcher-contract.json"
    )
    destination.parent.mkdir(parents=True)
    destination.write_text(payload)
    assert not supports_launcher_delegation(tmp_path, WINDOWS_X64_BUNDLE)
