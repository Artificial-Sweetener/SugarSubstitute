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

"""Verify journaled repair promotion, rollback, and recovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    RepairPlanService,
    RepairReplacement,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.repair_transaction import (
    RepairTransaction,
    RepairTransactionError,
    recover_interrupted_repair,
)


def _write_tree(path: Path, value: str) -> None:
    """Write a representative versioned directory."""

    path.mkdir(parents=True)
    (path / "version.txt").write_text(value, encoding="utf-8")


def test_transaction_promotes_staged_content_and_retains_quarantine(
    tmp_path: Path,
) -> None:
    """Successful repair should promote clean artifacts and retain the prior version."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    _write_tree(layout.app_dir, "old")
    staged = tmp_path / "staged-app"
    _write_tree(staged, "new")
    plan = RepairPlanService().build_application_plan(layout=layout)

    quarantine = RepairTransaction().execute(
        plan=plan,
        replacements=(RepairReplacement(layout.app_dir, staged),),
        transaction_id="test-transaction",
    )

    assert (layout.app_dir / "version.txt").read_text(encoding="utf-8") == "new"
    assert (quarantine / "app" / "version.txt").read_text(encoding="utf-8") == "old"
    assert not (layout.root / ".repair" / "pending.json").exists()


def test_transaction_rolls_back_runtime_created_by_repair_callback(
    tmp_path: Path,
) -> None:
    """Provisioning and validation failures must restore the previous runtime."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    _write_tree(layout.app_dir, "old-app")
    _write_tree(layout.runtime_dir, "old-runtime")
    staged_app = tmp_path / "staged-app"
    _write_tree(staged_app, "new-app")
    plan = RepairPlanService().build_application_plan(layout=layout)

    def provision_runtime() -> None:
        """Create a candidate runtime in the journaled active slot."""

        _write_tree(layout.runtime_dir, "new-runtime")

    def reject_runtime() -> None:
        """Simulate post-provision validation failure."""

        raise RuntimeError("runtime imports failed")

    with pytest.raises(RepairTransactionError, match="rolled back"):
        RepairTransaction().execute(
            plan=plan,
            replacements=(RepairReplacement(layout.app_dir, staged_app),),
            transaction_id="runtime-validation-failure",
            apply_repair=provision_runtime,
            validate_repair=reject_runtime,
        )

    assert (layout.app_dir / "version.txt").read_text(encoding="utf-8") == "old-app"
    assert (layout.runtime_dir / "version.txt").read_text(
        encoding="utf-8"
    ) == "old-runtime"


def test_transaction_quarantines_replaceable_state_without_deleting_it(
    tmp_path: Path,
) -> None:
    """Repair should clear planned state by moving it into recoverable quarantine."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    _write_tree(layout.appdata_dir / "cache", "cached")
    _write_tree(layout.appdata_dir / "session", "recovery")
    staged = tmp_path / "staged-app"
    _write_tree(staged, "new")
    plan = RepairPlanService().build_application_plan(layout=layout)

    quarantine = RepairTransaction().execute(
        plan=plan,
        replacements=(RepairReplacement(layout.app_dir, staged),),
        transaction_id="state-quarantine",
    )

    assert not (layout.appdata_dir / "cache").exists()
    assert (layout.appdata_dir / "session" / "version.txt").exists()
    assert (quarantine / "appdata" / "cache" / "version.txt").read_text(
        encoding="utf-8"
    ) == "cached"


def test_transaction_fault_rolls_back_every_already_moved_destination(
    tmp_path: Path,
) -> None:
    """A later promotion fault should restore all earlier paths exactly."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    _write_tree(layout.app_dir, "old-app")
    _write_tree(layout.runtime_dir, "old-runtime")
    staged_app = tmp_path / "staged-app"
    staged_runtime = tmp_path / "staged-runtime"
    _write_tree(staged_app, "new-app")
    _write_tree(staged_runtime, "new-runtime")
    plan = RepairPlanService().build_application_plan(layout=layout)
    moves = 0

    def fail_after_third_move(_source: Path, _destination: Path) -> None:
        """Inject a fault after app promotion and runtime quarantine."""

        nonlocal moves
        moves += 1
        if moves == 3:
            raise OSError("injected move failure")

    with pytest.raises(RepairTransactionError, match="rolled back"):
        RepairTransaction(after_move=fail_after_third_move).execute(
            plan=plan,
            replacements=(
                RepairReplacement(layout.app_dir, staged_app),
                RepairReplacement(layout.runtime_dir, staged_runtime),
            ),
            transaction_id="faulted-transaction",
        )

    assert (layout.app_dir / "version.txt").read_text(encoding="utf-8") == "old-app"
    assert (layout.runtime_dir / "version.txt").read_text(
        encoding="utf-8"
    ) == "old-runtime"
    assert not (layout.root / ".repair" / "pending.json").exists()


def test_recovery_rejects_journal_path_traversal_without_mutation(
    tmp_path: Path,
) -> None:
    """Corrupt recovery data must fail closed before it touches external paths."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    external = tmp_path / "external"
    _write_tree(external, "safe")
    journal = layout.root / ".repair" / "pending.json"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "quarantine_root": ".repair/quarantine/test",
                "records": [
                    {
                        "destination": "../external",
                        "disposition": "replace",
                        "had_destination": True,
                        "relocated": True,
                        "promoted": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RepairTransactionError, match="unsafe"):
        recover_interrupted_repair(layout.root)

    assert (external / "version.txt").read_text(encoding="utf-8") == "safe"
