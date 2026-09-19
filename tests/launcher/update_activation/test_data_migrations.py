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

"""Tests for restart-safe launcher-owned data migration coordination."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.data_migrations import DataMigrationRunner
from sugarsubstitute_shared.update_compatibility import DataMigrationStep


_STEP = DataMigrationStep("adopt-epoch-1", 0, 1)


def test_migration_records_completion_without_mutating_user_data(
    tmp_path: Path,
) -> None:
    """Legacy adoption should preserve user state and advance its durable epoch."""

    install_root = tmp_path / "SugarSubstitute"
    user_file = install_root / "user" / "project.json"
    user_file.parent.mkdir(parents=True)
    user_file.write_text('{"owned":"user"}', encoding="utf-8")

    DataMigrationRunner(steps=(_STEP,)).migrate(
        install_root=install_root, target_epoch=1
    )

    assert user_file.read_text(encoding="utf-8") == '{"owned":"user"}'
    ledger = json.loads(
        (install_root / "launcher" / "data-migrations.json").read_text(encoding="utf-8")
    )
    assert ledger == {
        "active": None,
        "completed": ["adopt-epoch-1"],
        "current_epoch": 1,
        "schema_version": 1,
    }


def test_interrupted_migration_replays_the_same_idempotent_step(
    tmp_path: Path,
) -> None:
    """A crash after intent publication should replay instead of skipping work."""

    install_root = tmp_path / "SugarSubstitute"
    calls = 0

    def fail_once(_root: Path) -> None:
        """Fail once after durable migration intent exists."""

        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected interruption")

    runner = DataMigrationRunner(
        steps=(_STEP,), operations={_STEP.identifier: fail_once}
    )
    with pytest.raises(RuntimeError, match="injected interruption"):
        runner.migrate(install_root=install_root, target_epoch=1)

    runner.migrate(install_root=install_root, target_epoch=1)

    assert calls == 2


def test_migration_rejects_unknown_epoch_gap(tmp_path: Path) -> None:
    """Missing migration ownership must fail closed."""

    with pytest.raises(ValueError, match="No declared data migration"):
        DataMigrationRunner(steps=(_STEP,)).migrate(
            install_root=tmp_path / "SugarSubstitute", target_epoch=2
        )
