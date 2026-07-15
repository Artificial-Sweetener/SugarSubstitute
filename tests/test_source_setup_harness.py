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

"""Verify destructive-safety boundaries for the source setup harness."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
import pytest

from tools import run_source_setup_harness as harness


def test_source_setup_harness_rejects_every_non_allowlisted_root(
    tmp_path: Path,
) -> None:
    """No arbitrary path may pass the harness destructive cleanup guard."""

    with pytest.raises(harness.SourceSetupHarnessError, match="Refusing"):
        harness._require_exact_test_root(tmp_path / "SugarSubstitute-Test")


def test_source_setup_harness_cleans_only_its_exact_test_root(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The exact allowlisted disposable root should be removable in isolation."""

    test_root = tmp_path / "SugarSubstitute-Test"
    test_root.mkdir()
    (test_root / "owned.txt").write_text("owned", encoding="utf-8")
    neighbor = tmp_path / "SugarSubstitute"
    neighbor.mkdir()
    (neighbor / "keep.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(harness, "DEFAULT_INSTALL_ROOT", test_root)

    harness._clean_exact_test_root(test_root, log=lambda _line: None)

    assert not test_root.exists()
    assert (neighbor / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_harness_cache_copy_excludes_interrupted_partial_downloads(
    tmp_path: Path,
) -> None:
    """Only finalized artifacts should seed later fresh-install iterations."""

    source = tmp_path / "source"
    source.mkdir()
    (source / "complete.7z").write_bytes(b"complete")
    (source / "incomplete.7z.part").write_bytes(b"partial")
    destination = tmp_path / "destination"

    harness._copy_complete_cache(source_root=source, destination=destination)

    assert (destination / "complete.7z").read_bytes() == b"complete"
    assert not (destination / "incomplete.7z.part").exists()
