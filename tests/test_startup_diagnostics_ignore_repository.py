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

"""Tests for persisted startup diagnostics ignore fingerprints."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.infrastructure.persistence.file_startup_diagnostics_ignore_repository import (
    FileStartupDiagnosticsIgnoreRepository,
)


def test_missing_ignore_file_returns_empty_set(tmp_path: Path) -> None:
    """Missing ignore storage should mean no startup incidents are ignored."""

    repository = FileStartupDiagnosticsIgnoreRepository(tmp_path / "state")

    assert repository.load_ignored_fingerprints() == frozenset()


def test_valid_ignore_file_loads_fingerprints(tmp_path: Path) -> None:
    """Repository should load current and legacy fingerprint entry shapes."""

    repository = FileStartupDiagnosticsIgnoreRepository(tmp_path / "state")
    repository.path.parent.mkdir(parents=True)
    repository.path.write_text(
        json.dumps(
            {
                "version": 1,
                "ignored_fingerprints": [
                    {
                        "fingerprint": "abc",
                        "label": "Broken custom node",
                        "kind": "custom_node_import_failed",
                        "future": "ignored",
                    },
                    "legacy",
                    {"fingerprint": ""},
                    {"missing": "fingerprint"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert repository.load_ignored_fingerprints() == frozenset({"abc", "legacy"})


def test_save_writes_deterministic_json(tmp_path: Path) -> None:
    """Saving ignores should create state storage and sort fingerprint entries."""

    repository = FileStartupDiagnosticsIgnoreRepository(tmp_path / "state")

    repository.save_ignored_fingerprints(frozenset({"b", "a", ""}))

    payload = json.loads(repository.path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert [entry["fingerprint"] for entry in payload["ignored_fingerprints"]] == [
        "a",
        "b",
    ]
    assert all("ignored_at" in entry for entry in payload["ignored_fingerprints"])


def test_corrupt_ignore_file_logs_and_returns_empty_set(tmp_path: Path) -> None:
    """Damaged ignore JSON should fail open without deleting the file."""

    repository = FileStartupDiagnosticsIgnoreRepository(tmp_path / "state")
    repository.path.parent.mkdir(parents=True)
    repository.path.write_text("{", encoding="utf-8")

    assert repository.load_ignored_fingerprints() == frozenset()
    assert repository.path.read_text(encoding="utf-8") == "{"


def test_non_object_ignore_file_returns_empty_set(tmp_path: Path) -> None:
    """Unsupported JSON roots should be treated as no ignored incidents."""

    repository = FileStartupDiagnosticsIgnoreRepository(tmp_path / "state")
    repository.path.parent.mkdir(parents=True)
    repository.path.write_text("[]", encoding="utf-8")

    assert repository.load_ignored_fingerprints() == frozenset()
