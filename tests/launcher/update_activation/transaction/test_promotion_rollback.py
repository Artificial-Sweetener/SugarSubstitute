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

"""Verify transactional launcher promotion, rollback, and recovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
    LauncherUpdateTransactionError,
)
import sugarsubstitute_shared.launcher_update.transaction as transaction_module

from .support import _asset, _write_bundle, _write_installed_layout


def test_transaction_replaces_only_launcher_and_preserves_install_data(
    tmp_path: Path,
) -> None:
    """Launcher promotion must preserve app, runtime, Comfy, and user content."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new launcher")
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(archive),
    )

    LauncherUpdateTransaction(wait_timeout_seconds=0).apply(request_path=request_path)

    assert (install_root / "SugarSubstitute.exe").read_text() == "new launcher"
    assert (install_root / "launcher-bin" / "runtime.txt").read_text() == "new"
    for relative_path in (
        "app/preserve.txt",
        "runtime/preserve.txt",
        "comfyui/preserve.txt",
        "user/preserve.txt",
        "appdata/preserve.txt",
    ):
        assert (install_root / relative_path).read_text() == "preserved"
    assert LauncherInstallationRecord.load(
        install_root / "launcher" / "installation.json"
    ) == LauncherInstallationRecord(version="0.11.0", target_key="windows_x64")
    assert not request_path.exists()


def test_transaction_rolls_back_both_bundle_roots_on_copy_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A partial two-root Windows promotion must restore the old bundle."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(_write_bundle(tmp_path / "launcher.zip", marker="new")),
    )
    original_copy = transaction_module._copy_path
    calls = 0

    def fail_second_copy(*, source: Path, destination: Path) -> None:
        """Fail after the executable has already been promoted."""

        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated lock")
        original_copy(source=source, destination=destination)

    monkeypatch.setattr(transaction_module, "_copy_path", fail_second_copy)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

    assert (install_root / "SugarSubstitute.exe").read_text() == "old launcher"
    assert (install_root / "launcher-bin" / "runtime.txt").read_text() == "old"


def test_transaction_recovers_interrupted_backup_before_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A later helper should recover the original bundle before another attempt."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(_write_bundle(tmp_path / "launcher.zip", marker="new")),
    )
    update_root = install_root / "launcher" / "updates"
    backup_root = update_root / "backup"
    backup_root.mkdir(parents=True)
    (install_root / "SugarSubstitute.exe").replace(backup_root / "SugarSubstitute.exe")
    (install_root / "launcher-bin").replace(backup_root / "launcher-bin")
    (install_root / "SugarSubstitute.exe").write_text(
        "interrupted partial", encoding="utf-8"
    )
    (install_root / "launcher-bin").mkdir()
    (install_root / "launcher-bin" / "runtime.txt").write_text(
        "interrupted partial", encoding="utf-8"
    )
    (update_root / "transaction.json").write_text(
        '{"phase":"promoting","target_key":"windows_x64"}\n',
        encoding="utf-8",
    )

    def fail_copy(*, source: Path, destination: Path) -> None:
        """Fail the retry so assertions expose the recovered rollback source."""

        _ = source
        _ = destination
        raise OSError("simulated retry failure")

    monkeypatch.setattr(transaction_module, "_copy_path", fail_copy)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

    assert (install_root / "SugarSubstitute.exe").read_text() == "old launcher"
    assert (install_root / "launcher-bin" / "runtime.txt").read_text() == "old"


def test_first_install_rollback_removes_targets_that_were_initially_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed first install must not leave half of a launcher bundle behind."""

    install_root = (tmp_path / "SugarSubstitute").resolve()
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(_write_bundle(tmp_path / "launcher.zip", marker="new")),
    )
    original_copy = transaction_module._copy_path
    calls = 0

    def fail_second_copy(*, source: Path, destination: Path) -> None:
        """Fail after placing the initially absent executable."""

        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated first-install failure")
        original_copy(source=source, destination=destination)

    monkeypatch.setattr(transaction_module, "_copy_path", fail_second_copy)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

    assert not (install_root / "SugarSubstitute.exe").exists()
    assert not (install_root / "launcher-bin").exists()
