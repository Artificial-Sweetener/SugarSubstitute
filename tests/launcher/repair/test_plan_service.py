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

"""Verify fail-closed repair planning and preservation policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    ManagedComfyOwnership,
    RepairDisposition,
    RepairPlanError,
    RepairPlanService,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairPlan
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


def _touch_directory(path: Path) -> None:
    """Create one representative directory with content."""

    path.mkdir(parents=True)
    (path / "content.txt").write_text("keep or quarantine", encoding="utf-8")


def _managed_ownership(layout: InstallLayout) -> ManagedComfyOwnership:
    """Return valid ownership evidence for the layout's managed workspace."""

    return ManagedComfyOwnership(
        target_mode="managed_local",
        workspace_root=layout.root / "comfyui",
        install_owned=True,
    )


def _disposition(plan: RepairPlan, path: Path) -> RepairDisposition:
    """Return one planned disposition after proving the operation exists."""

    operation = plan.operation_for(path)
    assert operation is not None
    return operation.disposition


def test_application_repair_preserves_user_recovery_and_all_comfy_content(
    tmp_path: Path,
) -> None:
    """Application repair must not classify user, recovery, or Comfy data as disposable."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    for path in (
        layout.user_dir / "projects",
        layout.appdata_dir / "session",
        layout.appdata_dir / "cache",
        layout.root / "comfyui" / "models",
        layout.root / "comfyui" / "user",
    ):
        _touch_directory(path)

    plan = RepairPlanService().build_application_plan(layout=layout)

    assert (
        _disposition(plan, layout.user_dir / "projects" / "content.txt")
        is RepairDisposition.PRESERVE
    )
    assert (
        _disposition(plan, layout.appdata_dir / "session" / "content.txt")
        is RepairDisposition.PRESERVE
    )
    assert (
        _disposition(plan, layout.root / "comfyui" / "models" / "content.txt")
        is RepairDisposition.PRESERVE
    )
    assert (
        _disposition(plan, layout.appdata_dir / "cache") is RepairDisposition.QUARANTINE
    )
    assert _disposition(plan, layout.app_dir) is RepairDisposition.REPLACE
    assert _disposition(plan, layout.runtime_dir) is RepairDisposition.REPLACE


def test_application_repair_quarantines_unknown_root_content(tmp_path: Path) -> None:
    """Unknown installation content should be recoverable rather than silently deleted."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    _touch_directory(layout.root / "mystery-tool")

    plan = RepairPlanService().build_application_plan(layout=layout)

    operation = plan.operation_for(layout.root / "mystery-tool" / "content.txt")
    assert operation is not None
    assert operation.disposition is RepairDisposition.QUARANTINE


@pytest.mark.parametrize(
    "ownership",
    [
        ManagedComfyOwnership("attached_local", Path("comfyui"), True),
        ManagedComfyOwnership("remote", None, False),
        ManagedComfyOwnership("managed_local", Path("elsewhere"), True),
        ManagedComfyOwnership("managed_local", Path("comfyui"), False),
    ],
)
def test_comfy_repairs_fail_closed_without_exact_managed_ownership(
    tmp_path: Path,
    ownership: ManagedComfyOwnership,
) -> None:
    """Attached, remote, external, and unowned targets must never be mutated."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    with pytest.raises(RepairPlanError, match="proven installer-owned"):
        RepairPlanService().build_owned_nodes_plan(
            layout=layout,
            comfy_ownership=ownership,
        )


def test_owned_node_repair_targets_only_backend_and_sugarcubes(tmp_path: Path) -> None:
    """Owned-node repair must leave every third-party node outside its replacement set."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    custom_nodes = layout.root / "comfyui" / "custom_nodes"
    for name in ("substitute-backend", "SugarCubes", "third-party-node"):
        _touch_directory(custom_nodes / name)

    plan = RepairPlanService().build_owned_nodes_plan(
        layout=layout,
        comfy_ownership=_managed_ownership(layout),
    )

    replaced = {
        operation.path.name
        for operation in plan.operations
        if operation.disposition is RepairDisposition.REPLACE
    }
    assert replaced == {"substitute-backend", "SugarCubes"}
    assert plan.operation_for(custom_nodes / "third-party-node") is None


def test_full_comfy_repair_preserves_models_user_io_and_third_party_nodes(
    tmp_path: Path,
) -> None:
    """Explicit full repair should refresh core while retaining all protected data."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    comfy_root = layout.root / "comfyui"
    for path in (
        comfy_root / "models" / "checkpoints",
        comfy_root / "user" / "default",
        comfy_root / "input",
        comfy_root / "output",
        comfy_root / "custom_nodes" / "third-party-node",
        comfy_root / "custom_nodes" / "substitute-backend",
        comfy_root / "custom_nodes" / "SugarCubes",
        comfy_root / "comfy",
        comfy_root / ".venv",
    ):
        _touch_directory(path)

    plan = RepairPlanService().build_full_managed_comfy_plan(
        layout=layout,
        comfy_ownership=_managed_ownership(layout),
    )

    for protected in ("models", "user", "input", "output"):
        operation = plan.operation_for(comfy_root / protected / "content.txt")
        assert operation is not None
        assert operation.disposition is RepairDisposition.PRESERVE
    assert (
        _disposition(
            plan,
            comfy_root / "custom_nodes" / "third-party-node" / "content.txt",
        )
        is RepairDisposition.PRESERVE
    )
    assert (
        _disposition(plan, comfy_root / "custom_nodes" / "SugarCubes")
        is RepairDisposition.REPLACE
    )
    assert _disposition(plan, comfy_root / "comfy") is RepairDisposition.QUARANTINE
    assert _disposition(plan, comfy_root / ".venv") is RepairDisposition.QUARANTINE
