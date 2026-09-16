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

"""Exercise abrupt process exit at real repair filesystem boundaries."""

from __future__ import annotations

import os
import json
from pathlib import Path
import sys
from unittest.mock import patch

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairOperation,
    RepairPlan,
    RepairReplacement,
    RepairScope,
)
from sugarsubstitute_shared.repair_recovery.disposition import RepairDisposition
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction


def interrupt_transaction(root: Path, boundary: str) -> None:
    """Exit after an atomic move without running transaction exception cleanup."""
    destination = root / "app"
    staged = root / ".repair" / "staging" / "app"
    original_replace = Path.replace
    original_unlink = Path.unlink

    def replace(path: Path, target: Path | str) -> Path:
        """Complete the native move before terminating the selected boundary."""
        if boundary == "before_relocation" and path == destination:
            os._exit(74)
        result = original_replace(path, target)
        if boundary == "relocation" and path == destination:
            os._exit(71)
        if boundary == "rollback" and path == root / ".repair/quarantine/probe/runtime":
            os._exit(72)
        if boundary == "promotion" and path == staged:
            os._exit(75)
        if boundary == "rollback_candidate" and Path(target).parent.name.startswith(
            "rejected-"
        ):
            os._exit(76)
        return result

    def unlink(path: Path, missing_ok: bool = False) -> None:
        """Leave the durable commit marker present when the process exits."""
        if boundary == "commit" and path == root / ".repair/pending.json":
            os._exit(73)
        if boundary == "rollback_cleanup" and path == root / ".repair/pending.json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["phase"] == "rolling_back":
                os._exit(77)
        original_unlink(path, missing_ok=missing_ok)

    def validate() -> None:
        """Enter rollback through an ordinary rejected candidate."""
        if boundary in {"rollback", "rollback_candidate", "rollback_cleanup"}:
            raise RuntimeError("controlled validation rejection")

    plan = RepairPlan(
        RepairScope.APPLICATION,
        root,
        tuple(
            RepairOperation(root / name, RepairDisposition.REPLACE, "synthetic package")
            for name in ("app", "runtime")
        ),
    )
    with (
        patch.object(Path, "replace", autospec=True, side_effect=replace),
        patch.object(Path, "unlink", autospec=True, side_effect=unlink),
    ):
        RepairTransaction().execute(
            plan=plan,
            replacements=tuple(
                RepairReplacement(root / name, root / ".repair/staging" / name)
                for name in ("app", "runtime")
            ),
            transaction_id="probe",
            validate_repair=validate,
        )


if __name__ == "__main__":
    interrupt_transaction(Path(sys.argv[1]), sys.argv[2])
