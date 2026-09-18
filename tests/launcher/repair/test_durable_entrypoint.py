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

"""Require application repair to retain its launch and recovery bootstrap."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairReplacement,
)
from launcher.sugarsubstitute_launcher.application.repair.plan_service import (
    RepairPlanService,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction


def test_application_repair_keeps_bootstrap_available_at_every_move(
    tmp_path: Path,
) -> None:
    """Keep normal launch and independent recovery reachable even between promotions.

    The transaction observer runs after real filesystem moves. A missing bootstrap
    at any observed boundary would remain missing after abrupt process death;
    exception rollback cannot establish the required continuous availability.
    """
    root = tmp_path / "installation"
    layout = InstallLayout.from_root(
        root, target=launcher_target_for_key("windows_x64")
    )
    baseline = {
        Path("SugarSubstitute.exe"): b"baseline entrypoint",
        Path("launcher-bin/LauncherUi.exe"): b"baseline presentation",
        Path("launcher-bin/Repair.exe"): b"baseline recovery",
        Path("launcher-bin/runtime.txt"): b"baseline dependencies",
    }
    for relative, content in baseline.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    layout.app_dir.mkdir()
    (layout.app_dir / "version.txt").write_text("old", encoding="utf-8")
    staged = root / ".repair" / "staging" / "candidate-app"
    staged.mkdir(parents=True)
    (staged / "version.txt").write_text("new", encoding="utf-8")
    observed_moves: list[tuple[Path, Path]] = []

    def assert_bootstrap() -> None:
        """Verify all bootstrap roles and their dependencies without executing them."""
        for relative, expected in baseline.items():
            path = root / relative
            assert path.is_file(), f"Repair removed bootstrap file: {relative}"
            assert path.read_bytes() == expected, (
                f"Repair changed bootstrap: {relative}"
            )

    def observe_move(source: Path, destination: Path) -> None:
        """Check the crash-visible state before the next transaction operation."""
        observed_moves.append((source, destination))
        assert_bootstrap()

    plan = RepairPlanService().build_application_plan(layout=layout)
    RepairTransaction(after_move=observe_move).execute(
        plan=plan,
        replacements=(RepairReplacement(layout.app_dir, staged),),
    )

    assert observed_moves
    assert_bootstrap()
    assert (layout.app_dir / "version.txt").read_text(encoding="utf-8") == "new"
