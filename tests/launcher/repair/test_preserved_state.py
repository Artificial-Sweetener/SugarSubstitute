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

"""Verify authoritative data survives replacement of its containing package."""

from pathlib import Path
import os
import shutil
import stat
import subprocess
from types import SimpleNamespace

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
    RepairReplacement,
)
from launcher.sugarsubstitute_launcher.application.repair.plan_service import (
    RepairPlanError,
    RepairPlanService,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.repair_errors import RepairTransactionError
from launcher.sugarsubstitute_launcher.repair_transaction import (
    RepairTransaction,
)


@pytest.mark.parametrize("staged_package", [False, True])
@pytest.mark.parametrize("validation_fails", [False, True])
def test_owned_package_repair_preserves_the_complete_cube_library(
    tmp_path: Path, staged_package: bool, validation_fails: bool
) -> None:
    """Keep user-authored Cubes available before validation and after rollback."""
    layout = InstallLayout.from_root(tmp_path / "install")
    workspace = layout.root / "comfyui"
    package = workspace / "custom_nodes" / "SugarCubes"
    library = package / ".sugarcubes"
    library.mkdir(parents=True)
    (library / "authored.cube").write_bytes(b"user-authored-cube")
    (library / "tracked_repos.json").write_bytes(b"user-repository-selection")
    (package / "version.txt").write_text("old", encoding="utf-8")
    ownership = ManagedComfyOwnership("managed_local", workspace, True)
    plan = RepairPlanService().build_owned_nodes_plan(
        layout=layout, comfy_ownership=ownership
    )
    candidate = tmp_path / "candidate"

    def install_package(destination: Path) -> None:
        """Model a package installer creating its own default state."""
        generated_library = destination / ".sugarcubes"
        generated_library.mkdir(parents=True)
        (destination / "version.txt").write_text("new", encoding="utf-8")
        (generated_library / "tracked_repos.json").write_bytes(b"defaults")
        (generated_library / "generated-only.json").write_bytes(b"generated")

    if staged_package:
        install_package(candidate)

    def apply_repair() -> None:
        """Exercise both staged promotion and post-promotion package installation."""
        if not staged_package:
            install_package(package)

    def validate_repair() -> None:
        """Validate against preserved user state, never regenerated defaults."""
        assert (library / "authored.cube").read_bytes() == b"user-authored-cube"
        assert (
            library / "tracked_repos.json"
        ).read_bytes() == b"user-repository-selection"
        assert not (library / "generated-only.json").exists()
        if validation_fails:
            raise ValueError("candidate rejected after state preservation")

    def execute() -> Path:
        """Run the real plan and transaction with deterministic package installation."""
        return RepairTransaction().execute(
            plan=plan,
            replacements=(RepairReplacement(package, candidate),)
            if staged_package
            else (),
            apply_repair=apply_repair,
            validate_repair=validate_repair,
        )

    if validation_fails:
        with pytest.raises(RepairTransactionError, match="rolled back") as caught:
            execute()
        assert isinstance(caught.value.__cause__, ValueError)
        assert (package / "version.txt").read_text(encoding="utf-8") == "old"
    else:
        quarantine = execute()
        assert (package / "version.txt").read_text(encoding="utf-8") == "new"
        assert (
            quarantine / library.relative_to(layout.root) / "authored.cube"
        ).read_bytes() == b"user-authored-cube"
    assert (library / "authored.cube").read_bytes() == b"user-authored-cube"
    assert (library / "tracked_repos.json").read_bytes() == b"user-repository-selection"
    assert not (layout.root / ".repair" / "pending.json").exists()


def test_full_comfy_repair_preserves_model_selection_but_refreshes_environment_state(
    tmp_path: Path,
) -> None:
    """Retain model-root configuration independently of environment hydration state."""
    layout = InstallLayout.from_root(tmp_path / "install")
    workspace = layout.root / "comfyui"
    state = workspace / ".substitute"
    state.mkdir(parents=True)
    (state / "model_root.json").write_bytes(b"authoritative-model-root")
    (state / "standalone-hydration.json").write_bytes(b"old-environment")
    candidate = tmp_path / "state-candidate"
    candidate.mkdir()
    (candidate / "standalone-hydration.json").write_bytes(b"new-environment")
    plan = RepairPlanService().build_full_managed_comfy_plan(
        layout=layout,
        comfy_ownership=ManagedComfyOwnership("managed_local", workspace, True),
        replacement_names=frozenset({".substitute"}),
    )

    RepairTransaction().execute(
        plan=plan, replacements=(RepairReplacement(state, candidate),)
    )

    assert (state / "model_root.json").read_bytes() == b"authoritative-model-root"
    assert (state / "standalone-hydration.json").read_bytes() == b"new-environment"


def test_partial_library_copy_rolls_back_the_entire_original_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retain complete original data when restoring the candidate fails halfway."""
    layout = InstallLayout.from_root(tmp_path / "install")
    workspace = layout.root / "comfyui"
    package = workspace / "custom_nodes" / "SugarCubes"
    library = package / ".sugarcubes"
    library.mkdir(parents=True)
    (library / "first.cube").write_bytes(b"first-original")
    (library / "second.cube").write_bytes(b"second-original")
    (package / "version.txt").write_bytes(b"old-package")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "version.txt").write_bytes(b"new-package")
    plan = RepairPlanService().build_owned_nodes_plan(
        layout=layout,
        comfy_ownership=ManagedComfyOwnership("managed_local", workspace, True),
    )

    def fail_partial_copy(source: Path, destination: Path) -> None:
        """Model a filesystem copy that fails after writing one candidate file."""
        destination.mkdir()
        (destination / "first.cube").write_bytes((source / "first.cube").read_bytes())
        raise OSError("copy interrupted")

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.repair_preserved_state.shutil",
        SimpleNamespace(copytree=fail_partial_copy, copy2=shutil.copy2),
    )
    with pytest.raises(RepairTransactionError, match="rolled back") as caught:
        RepairTransaction().execute(
            plan=plan, replacements=(RepairReplacement(package, candidate),)
        )

    assert isinstance(caught.value.__cause__, OSError)
    assert (package / "version.txt").read_bytes() == b"old-package"
    assert (library / "first.cube").read_bytes() == b"first-original"
    assert (library / "second.cube").read_bytes() == b"second-original"
    assert not (layout.root / ".repair" / "pending.json").exists()


def test_new_package_without_existing_library_keeps_its_defaults(
    tmp_path: Path,
) -> None:
    """Preservation must not remove defaults when no prior authoritative state exists."""
    layout = InstallLayout.from_root(tmp_path / "install")
    workspace = layout.root / "comfyui"
    package = workspace / "custom_nodes" / "SugarCubes"
    candidate = tmp_path / "candidate"
    (candidate / ".sugarcubes").mkdir(parents=True)
    (candidate / ".sugarcubes" / "tracked_repos.json").write_bytes(b"defaults")
    plan = RepairPlanService().build_owned_nodes_plan(
        layout=layout,
        comfy_ownership=ManagedComfyOwnership("managed_local", workspace, True),
    )

    RepairTransaction().execute(
        plan=plan, replacements=(RepairReplacement(package, candidate),)
    )

    assert (package / ".sugarcubes" / "tracked_repos.json").read_bytes() == b"defaults"


def test_read_only_candidate_data_cannot_prevent_restoring_the_original(
    tmp_path: Path,
) -> None:
    """Roll back packages containing read-only Git objects or authored data."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.app_dir.mkdir(parents=True)
    (layout.app_dir / "version.txt").write_bytes(b"original")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "readonly.txt").write_bytes(b"candidate")
    plan = RepairPlanService().build_application_plan(layout=layout)

    def reject_candidate() -> None:
        """Reject a candidate after observing its real filesystem attributes."""
        (layout.app_dir / "readonly.txt").chmod(stat.S_IRUSR)
        raise ValueError("candidate invalid")

    try:
        with pytest.raises(RepairTransactionError, match="was rolled back"):
            RepairTransaction().execute(
                plan=plan,
                replacements=(RepairReplacement(layout.app_dir, candidate),),
                validate_repair=reject_candidate,
            )
        assert (layout.app_dir / "version.txt").read_bytes() == b"original"
        assert not (layout.root / ".repair" / "pending.json").exists()
    finally:
        for path in layout.root.rglob("readonly.txt"):
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)


@pytest.mark.parametrize("nested", [False, True])
def test_redirected_library_is_rejected_before_any_package_moves(
    tmp_path: Path, nested: bool
) -> None:
    """Keep repair within its declared installation for native filesystem redirects."""
    layout = InstallLayout.from_root(tmp_path / "install")
    workspace = layout.root / "comfyui"
    package = workspace / "custom_nodes" / "SugarCubes"
    library = package / ".sugarcubes"
    package.mkdir(parents=True)
    (package / "version.txt").write_bytes(b"original-package")
    external = tmp_path / "outside-install"
    external.mkdir()
    (external / "keep.cube").write_bytes(b"outside-data")
    if nested:
        library.mkdir()
    link = library / "redirected" if nested else library
    if os.name == "nt":
        subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(external)],
            check=True,
            capture_output=True,
            timeout=10,
        )
    else:
        link.symlink_to(external, target_is_directory=True)
    try:
        with pytest.raises(
            (RepairPlanError, RepairTransactionError), match="redirected|escapes"
        ):
            plan = RepairPlanService().build_owned_nodes_plan(
                layout=layout,
                comfy_ownership=ManagedComfyOwnership("managed_local", workspace, True),
            )
            RepairTransaction().execute(plan=plan, replacements=())
        assert (package / "version.txt").read_bytes() == b"original-package"
        assert (external / "keep.cube").read_bytes() == b"outside-data"
        assert not (layout.root / ".repair" / "pending.json").exists()
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()
