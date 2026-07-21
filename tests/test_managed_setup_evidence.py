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

"""Tests for durable managed-setup evidence ownership."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from substitute.infrastructure.comfy import managed_setup_evidence


def test_atomic_write_replaces_complete_prior_evidence(tmp_path: Path) -> None:
    """A successful commit should expose only the complete new payload."""

    path = tmp_path / "managed_setup_freshness.json"
    path.write_text('{"generation": 1}', encoding="utf-8")

    managed_setup_evidence.write_json_object_atomic(path, {"generation": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"generation": 2}
    assert tuple(tmp_path.glob("*.tmp")) == ()


def test_atomic_write_failure_preserves_prior_evidence_and_cleans_temporary_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An interrupted commit should preserve retryable prior success evidence."""

    path = tmp_path / "managed_setup_freshness.json"
    original = '{"generation": 1}'
    path.write_text(original, encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        """Simulate failure at the atomic commit boundary."""

        _ = source, destination
        raise OSError("simulated replacement interruption")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replacement interruption"):
        managed_setup_evidence.write_json_object_atomic(path, {"generation": 2})

    assert path.read_text(encoding="utf-8") == original
    assert tuple(tmp_path.glob("*.tmp")) == ()


def test_content_signature_ignores_timestamp_only_changes(tmp_path: Path) -> None:
    """Contract freshness should change only when authoritative content changes."""

    path = tmp_path / "requirements.txt"
    path.write_text("package==1\n", encoding="utf-8")
    original = managed_setup_evidence.content_signature(path)
    path.touch()

    assert managed_setup_evidence.content_signature(path) == original

    path.write_text("package==2\n", encoding="utf-8")
    assert managed_setup_evidence.content_signature(path) != original
