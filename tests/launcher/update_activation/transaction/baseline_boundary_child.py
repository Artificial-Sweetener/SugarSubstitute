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

"""Expose real baseline publication and cleanup boundaries to a process parent."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Mapping

import pytest

from sugarsubstitute_shared.launcher_update import baseline_transaction as transaction
from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest


def _pause(boundary: str) -> None:
    """Announce an observed durable boundary and await the parent's terminal action."""
    print(boundary, flush=True)
    sys.stdin.buffer.read(1)


def main() -> None:
    """Install barriers at real filesystem boundaries without replacing their behavior."""
    request_path = Path(sys.argv[1])
    request = LauncherUpdateRequest.load(request_path)
    root = request.install_root.resolve()
    mode = sys.argv[2] if len(sys.argv) > 2 else "record"
    original_save = LauncherInstallationRecord.save
    original_copy = transaction._copy_path
    original_replace = Path.replace
    original_write = write_json_atomic
    original_remove = transaction._remove_path

    def publish_and_pause(self: LauncherInstallationRecord, path: Path) -> None:
        """Publish the actual installation record before exposing its boundary."""
        original_save(self, path)
        if mode == "record":
            _pause("installation-record-published")

    def copy_and_pause(*, source: Path, destination: Path) -> None:
        """Copy the actual executable before exposing its atomic publication."""
        original_copy(source=source, destination=destination)
        if mode == "executable" and destination == root / "SugarSubstitute.exe":
            _pause(mode)

    def replace_and_pause(self: Path, target: str | Path) -> Path:
        """Expose the exact point after the old runtime was moved to its backup."""
        result = original_replace(self, target)
        if mode == "support-detached" and self == root / "launcher-bin":
            _pause(mode)
        return result

    def write_and_pause(path: Path, payload: Mapping[str, object]) -> None:
        """Persist the real journal before exposing a publication boundary."""
        original_write(path, payload)
        if mode in {"promoted", "committed"} and payload.get("phase") == mode:
            _pause(mode)

    def remove_and_pause(path: Path) -> None:
        """Complete actual backup disposal before exposing its cleanup boundary."""
        original_remove(path)
        if (
            mode == "cleanup"
            and path == root / "launcher" / "updates" / "backup"
            and (root / "launcher" / "updates" / "transaction.json").is_file()
            and '"committed"'
            in (root / "launcher" / "updates" / "transaction.json").read_text(
                encoding="utf-8"
            )
        ):
            _pause(mode)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(LauncherInstallationRecord, "save", publish_and_pause)
        monkeypatch.setattr(transaction, "_copy_path", copy_and_pause)
        monkeypatch.setattr(Path, "replace", replace_and_pause)
        monkeypatch.setattr(transaction, "write_json_atomic", write_and_pause)
        monkeypatch.setattr(transaction, "_remove_path", remove_and_pause)
        transaction.LauncherBaselineTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )


if __name__ == "__main__":
    main()
