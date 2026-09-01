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

"""Verify installer-side loading of persisted Comfy ownership evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    ManagedComfyOwnership,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.repair_ownership import (
    RepairOwnershipError,
    load_comfy_ownership,
)


def test_missing_target_configuration_provides_no_mutation_authority(
    tmp_path: Path,
) -> None:
    """Absence should remain distinct from a synthesized managed target."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    assert load_comfy_ownership(layout) is None


def test_loader_reads_exact_persisted_managed_workspace(tmp_path: Path) -> None:
    """The launcher should pass persisted facts to the fail-closed planner."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    path = layout.user_dir / "settings" / "comfy_target.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "mode": "managed_local",
                "workspace_path": str(layout.root / "comfyui"),
                "install_owned": True,
                "launch_owned": True,
            }
        ),
        encoding="utf-8",
    )

    assert load_comfy_ownership(layout) == ManagedComfyOwnership(
        target_mode="managed_local",
        workspace_root=layout.root / "comfyui",
        install_owned=True,
    )


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        json.dumps({"mode": "managed_local", "install_owned": "yes"}),
        json.dumps({"mode": 4, "install_owned": True}),
    ],
)
def test_invalid_target_configuration_fails_before_repair_planning(
    tmp_path: Path,
    payload: str,
) -> None:
    """Corrupt ownership evidence must never silently authorize Comfy mutation."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    path = layout.user_dir / "settings" / "comfy_target.json"
    path.parent.mkdir(parents=True)
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(RepairOwnershipError):
        load_comfy_ownership(layout)
