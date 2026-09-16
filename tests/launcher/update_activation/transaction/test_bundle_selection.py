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

"""Verify immutable launcher publication, atomic activation and retained fallback."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord

from .support import _write_bundle_tree, _write_installed_layout


def _installation(tmp_path: Path) -> tuple[Path, Path, LauncherBundleSelection]:
    """Create the baseline and a distinct complete staged candidate."""
    root = _write_installed_layout(tmp_path / "installation")
    candidate = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(candidate, marker="candidate")
    return root, candidate, LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)


def test_publication_does_not_activate_until_record_commit(tmp_path: Path) -> None:
    """Keep the baseline selected while a complete new payload is published."""
    root, candidate, selection = _installation(tmp_path)
    published = selection.publish(candidate, version="1.2.3")
    assert selection.resolve().root == root
    assert (root / "SugarSubstitute.exe").read_text() == "old launcher"
    selection.activate(published)
    assert selection.resolve() == published
    assert (published.root / "SugarSubstitute.exe").read_text() == "candidate"
    assert (root / "launcher-bin" / "Repair.exe").read_text() == "old repair"


def test_prepared_selection_preserves_current_until_transaction_promotion(
    tmp_path: Path,
) -> None:
    """Prepare the same current/fallback transition without changing active state."""
    root, candidate, selection = _installation(tmp_path)
    previous = selection.publish(candidate, version="1")
    selection.activate(previous)
    updated = selection.publish(candidate, version="2")
    staged = root / ".repair" / "staging" / "attempt" / "selection.json"
    selection.stage_activation(updated, staged)
    assert selection.resolve() == previous
    assert json.loads(staged.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "current": updated.generation,
        "previous": previous.generation,
    }
    staged.replace(root / "launcher" / "bundles" / "active.json")
    assert selection.resolve() == updated


def test_prepared_selection_rejects_destination_outside_repair_staging(
    tmp_path: Path,
) -> None:
    """Prevent staging from overwriting user state or directly activating a bundle."""
    root, candidate, selection = _installation(tmp_path)
    updated = selection.publish(candidate, version="2")
    destination = root / "launcher" / "bundles" / "active.json"
    with pytest.raises(ValueError, match="repair staging"):
        selection.stage_activation(updated, destination)
    assert selection.resolve().root == root
    assert not destination.exists()


def test_failed_activation_preserves_previous_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail atomic replacement without consuming the current runnable generation."""
    root, candidate, selection = _installation(tmp_path)
    first = selection.publish(candidate, version="1")
    selection.activate(first)
    second = selection.publish(candidate, version="2")
    replace = Path.replace

    def fail_selection(path: Path, target: str | Path) -> Path:
        """Refuse only the selection commit at the filesystem boundary."""
        if Path(target).name == "active.json":
            raise PermissionError("selection is temporarily locked")
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_selection)
    with pytest.raises(PermissionError):
        selection.activate(second)
    assert selection.resolve() == first
    assert (root / "launcher-bin" / "Repair.exe").is_file()


def test_incomplete_current_generation_falls_back_to_previous(tmp_path: Path) -> None:
    """Use the retained complete payload when current dependencies are unavailable."""
    _root, candidate, selection = _installation(tmp_path)
    first = selection.publish(candidate, version="1")
    selection.activate(first)
    second = selection.publish(candidate, version="2")
    selection.activate(second)
    (second.root / "launcher-bin" / "runtime.txt").unlink()
    assert selection.resolve() == first


@pytest.mark.parametrize(
    "record",
    [
        "not-json",
        '{"schema_version": 99}',
        '{"schema_version": 1, "current": "../../outside"}',
    ],
)
def test_invalid_selection_uses_baseline(tmp_path: Path, record: str) -> None:
    """Reject unreadable and escaping records without selecting unknown folders."""
    root, _candidate, selection = _installation(tmp_path)
    path = root / "launcher" / "bundles" / "active.json"
    path.parent.mkdir(parents=True)
    path.write_text(record, encoding="utf-8")
    assert selection.resolve().root == root


def test_changed_staging_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject a candidate that changes between validation and complete publication."""
    root, candidate, selection = _installation(tmp_path)
    copytree = shutil.copytree

    def change_before_copy(source: Path, destination: Path, *, symlinks: bool) -> Path:
        """Change staged content at the copy boundary while retaining real copying."""
        (source / "SugarSubstitute.exe").write_text("changed", encoding="utf-8")
        monkeypatch.setattr(shutil, "copytree", copytree)
        return copytree(source, destination, symlinks=symlinks)

    monkeypatch.setattr(shutil, "copytree", change_before_copy)
    with pytest.raises(ValueError, match="changed"):
        selection.publish(candidate, version="1")
    assert selection.resolve().root == root
    assert not (root / "launcher" / "bundles" / "active.json").exists()


def test_generation_from_other_installation_cannot_be_activated(tmp_path: Path) -> None:
    """Constrain selection to verified generations owned by the installation."""
    _root, candidate, selection = _installation(tmp_path / "first")
    foreign = selection.publish(candidate, version="1")
    root, _candidate, other = _installation(tmp_path / "second")
    with pytest.raises((ValueError, OSError)):
        other.activate(foreign)
    assert other.resolve().root == root


def test_selection_retains_previous_identity(tmp_path: Path) -> None:
    """Commit current and fallback together in the same authoritative record."""
    root, candidate, selection = _installation(tmp_path)
    first = selection.publish(candidate, version="1")
    selection.activate(first)
    second = selection.publish(candidate, version="2")
    selection.activate(second)
    record = json.loads((root / "launcher" / "bundles" / "active.json").read_text())
    assert record["current"] == second.generation
    assert record["previous"] == first.generation


def test_modified_current_and_previous_payloads_use_baseline(tmp_path: Path) -> None:
    """Reject modified payload bytes even when required files still exist."""
    root, candidate, selection = _installation(tmp_path)
    first = selection.publish(candidate, version="1")
    selection.activate(first)
    second = selection.publish(candidate, version="2")
    selection.activate(second)
    for bundle in (first, second):
        (bundle.root / "launcher-bin" / "runtime.txt").write_text(
            "damaged", encoding="utf-8"
        )
    assert selection.resolve().root == root


def test_unsealed_directory_is_not_selected(tmp_path: Path) -> None:
    """Ignore incomplete publication instead of inferring authority from a folder."""
    root, _candidate, selection = _installation(tmp_path)
    unsealed = root / "launcher" / "bundles" / ("a" * 32)
    _write_bundle_tree(unsealed / "payload", marker="unsealed")
    active = unsealed.parent / "active.json"
    active.write_text(
        json.dumps({"schema_version": 1, "current": unsealed.name}), encoding="utf-8"
    )
    assert selection.resolve().root == root


def test_active_version_tracks_selected_payload_and_retains_baseline_version(
    tmp_path: Path,
) -> None:
    """Report the code selected for launch, including a fallback to the baseline."""
    root, candidate, selection = _installation(tmp_path)
    baseline = LauncherInstallationRecord(version="0.1", target_key="windows_x64")
    path = root / "launcher" / "installation.json"
    baseline.save(path)
    assert selection.installed_record() == baseline
    published = selection.publish(candidate, version="1.0")
    selection.activate(published)
    assert selection.installed_record() == LauncherInstallationRecord(
        version="1.0", target_key="windows_x64"
    )
    assert LauncherInstallationRecord.load(path) == baseline
    (published.root / "SugarSubstitute.exe").unlink()
    assert selection.installed_record() == baseline


@pytest.mark.parametrize("replacement_activated", [False, True])
def test_rejection_retires_only_the_failed_identity(
    tmp_path: Path, replacement_activated: bool
) -> None:
    """Keep a newer activation while retiring the failed process generation."""
    root, staged, selection = _installation(tmp_path)
    first = selection.publish(staged, version="1")
    selection.activate(first)
    second = selection.publish(staged, version="2")
    if replacement_activated:
        selection.activate(second)
    selection.reject(first)
    selection.reject(first)
    assert selection.resolve().root == (second.root if replacement_activated else root)
    with pytest.raises(ValueError, match="retired"):
        selection.activate(first)
    if replacement_activated:
        selection.reject(second)
        assert selection.resolve().root == root
