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

"""Qualify launcher replacement beyond legacy Windows path limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.filesystem import remove_app_owned_path
from sugarsubstitute_shared.launcher_update.models import (
    LauncherInstallationRecord,
    LauncherUpdateRequest,
)
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
)
from sugarsubstitute_shared.windows_long_paths import operational_path


@pytest.mark.platforms("windows")
def test_transaction_promotes_launcher_inside_long_install_root(
    tmp_path: Path,
) -> None:
    """Persisted update paths should retain extended filesystem transport."""

    cleanup_root = operational_path(tmp_path / "long-launcher-update")
    install_root = cleanup_root / "SugarSubstitute"
    while len(str(install_root)) < 285:
        install_root /= "deep-install-segment"
    staged_root = install_root / "launcher" / "updates" / "staging" / "0.20.0"
    request_path = install_root / "launcher" / "updates" / "pending.json"
    try:
        (install_root / "SugarSubstitute.exe").parent.mkdir(parents=True)
        (install_root / "SugarSubstitute.exe").write_text(
            "old launcher",
            encoding="utf-8",
        )
        (install_root / "launcher-bin").mkdir()
        (install_root / "launcher-bin" / "runtime.txt").write_text(
            "old runtime",
            encoding="utf-8",
        )
        staged_root.mkdir(parents=True)
        (staged_root / "SugarSubstitute.exe").write_text(
            "new launcher",
            encoding="utf-8",
        )
        (staged_root / "launcher-bin").mkdir()
        (staged_root / "launcher-bin" / "runtime.txt").write_text(
            "new runtime",
            encoding="utf-8",
        )
        LauncherUpdateRequest(
            install_root=install_root,
            version="0.20.0",
            target_key="windows_x64",
            staged_bundle_dir=staged_root,
            relaunch=False,
        ).save(request_path)

        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

        assert (install_root / "SugarSubstitute.exe").read_text(
            encoding="utf-8"
        ) == "new launcher"
        assert (install_root / "launcher-bin" / "runtime.txt").read_text(
            encoding="utf-8"
        ) == "new runtime"
        assert LauncherInstallationRecord.load(
            install_root / "launcher" / "installation.json"
        ) == LauncherInstallationRecord(version="0.20.0", target_key="windows_x64")
        assert not request_path.exists()
    finally:
        remove_app_owned_path(cleanup_root)
