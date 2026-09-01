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

"""Verify repair-specific owned-node orchestration and exact validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.app.maintenance.owned_nodes import (
    OwnedNodeMaintenanceError,
    OwnedNodeMaintenanceService,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS


def test_repair_refreshes_every_owned_nodepack(tmp_path: Path) -> None:
    """Repair should request both authoritative nodepack identifiers together."""

    workspace = tmp_path / "comfyui"
    workspace.mkdir()
    calls: list[tuple[Path, frozenset[CoreNodepackId]]] = []

    def refresh(
        selected_workspace: Path,
        *,
        nodepacks: frozenset[CoreNodepackId],
    ) -> None:
        """Record the repair reconciliation request."""

        calls.append((selected_workspace, nodepacks))

    OwnedNodeMaintenanceService(refresher=refresh).repair(workspace)

    assert calls == [(workspace.resolve(), frozenset(CoreNodepackId))]


def test_validation_requires_exact_versions_and_sentinels(tmp_path: Path) -> None:
    """A merely present node folder must not satisfy repair validation."""

    workspace = tmp_path / "comfyui"
    for nodepack in CORE_COMFY_NODEPACKS:
        root = workspace / nodepack.expected_folder
        root.mkdir(parents=True)
        for sentinel in nodepack.sentinel_files:
            path = root / sentinel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("sentinel", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            "[project]\n"
            f'name = "{nodepack.registry_id}"\n'
            f'version = "{nodepack.required_version}"\n',
            encoding="utf-8",
        )
        (root / ".tracking").write_text("{}", encoding="utf-8")

    service = OwnedNodeMaintenanceService()
    service.validate(workspace)
    first = CORE_COMFY_NODEPACKS[0]
    (workspace / first.expected_folder / "pyproject.toml").write_text(
        f'[project]\nname = "{first.registry_id}"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )

    with pytest.raises(OwnedNodeMaintenanceError, match=first.required_version):
        service.validate(workspace)
