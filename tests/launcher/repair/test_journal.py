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

"""Verify persisted repair compatibility and validation before recovery mutates data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.repair_errors import RepairTransactionError
from launcher.sugarsubstitute_launcher.repair_recovery import recover_interrupted_repair


def _legacy_journal(root: Path, *, phase: str, relocated: bool) -> Path:
    """Persist the original released journal format around synthetic package data."""
    path = root / ".repair/pending.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "quarantine_root": ".repair/quarantine/legacy",
                "phase": phase,
                "records": [
                    {
                        "destination": "app",
                        "disposition": "replace",
                        "had_destination": True,
                        "relocated": relocated,
                        "promoted": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("relocated", [False, True])
def test_legacy_journal_restores_original_after_relocation(
    tmp_path: Path, relocated: bool
) -> None:
    """Recover old journals even when the old relocation flag missed the move."""
    _legacy_journal(tmp_path, phase="relocating", relocated=relocated)
    original = tmp_path / ".repair/quarantine/legacy/app"
    original.mkdir(parents=True)
    (original / "version.txt").write_text("original", encoding="utf-8")

    assert recover_interrupted_repair(tmp_path)
    assert (tmp_path / "app/version.txt").read_text(encoding="utf-8") == "original"
    assert not recover_interrupted_repair(tmp_path)


def test_legacy_committed_journal_keeps_candidate(tmp_path: Path) -> None:
    """Honor an already durable commit from the previous journal schema."""
    _legacy_journal(tmp_path, phase="committed", relocated=True)
    app = tmp_path / "app"
    app.mkdir()
    (app / "version.txt").write_text("candidate", encoding="utf-8")

    assert recover_interrupted_repair(tmp_path)
    assert (app / "version.txt").read_text(encoding="utf-8") == "candidate"


@pytest.mark.parametrize(
    "corruption", ["version", "phase", "overlap", "quarantine", "destination"]
)
def test_invalid_journal_preserves_all_data(tmp_path: Path, corruption: str) -> None:
    """Reject corrupt recovery authority before retaining or restoring any path."""
    journal = _legacy_journal(tmp_path, phase="relocating", relocated=True)
    app = tmp_path / "app"
    app.mkdir()
    (app / "version.txt").write_text("candidate", encoding="utf-8")
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if corruption == "version":
        payload["schema_version"] = []
    elif corruption == "phase":
        payload["phase"] = "unknown"
    elif corruption == "overlap":
        payload["records"].append(
            {**payload["records"][0], "destination": "app/nested"}
        )
    elif corruption == "quarantine":
        payload["quarantine_root"] = ".repair/quarantine"
    else:
        payload["records"][0]["destination"] = ".repair/pending.json"
    journal.write_text(json.dumps(payload), encoding="utf-8")
    before = journal.read_bytes()

    with pytest.raises(RepairTransactionError):
        recover_interrupted_repair(tmp_path)

    assert journal.read_bytes() == before
    assert (app / "version.txt").read_text(encoding="utf-8") == "candidate"


def test_missing_original_does_not_discard_recovery_journal(tmp_path: Path) -> None:
    """Keep recovery evidence when neither an original nor a valid completion exists."""
    journal = _legacy_journal(tmp_path, phase="validating", relocated=True)
    before = journal.read_bytes()

    with pytest.raises(RepairTransactionError, match="source is missing"):
        recover_interrupted_repair(tmp_path)

    assert journal.read_bytes() == before
