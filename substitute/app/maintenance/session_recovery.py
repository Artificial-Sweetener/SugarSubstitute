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

"""Preserve and migrate existing session files through the repaired app reader."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import secrets
import shutil

from substitute.domain.session import (
    session_snapshot_from_json,
    session_snapshot_to_json,
)
from sugarsubstitute_shared.session_recovery import (
    SessionRecoveryResult,
    SessionRecoveryState,
)

_PRIMARY_NAME = "session.json"
_BACKUP_NAME = "session.json.bak"


class SessionRecoveryService:
    """Retain original bytes, then publish only a reader-validated current snapshot."""

    def reconcile(
        self,
        *,
        session_dir: Path,
        recovery_root: Path,
        result_path: Path,
    ) -> SessionRecoveryResult:
        """Recover the primary or backup snapshot without risking either original."""

        session_dir = session_dir.resolve()
        recovery_root = recovery_root.resolve()
        result_path = result_path.resolve()
        if not result_path.is_relative_to(recovery_root):
            raise ValueError(
                "Session recovery result must stay below recovery storage."
            )
        if recovery_root.is_relative_to(session_dir):
            raise ValueError(
                "Session recovery storage cannot overlap the live session."
            )
        primary = session_dir / _PRIMARY_NAME
        backup = session_dir / _BACKUP_NAME
        existing = tuple(path for path in (primary, backup) if path.is_file())
        if not existing:
            result = SessionRecoveryResult(SessionRecoveryState.NO_SESSION)
            self._write_result(result_path, result)
            return result
        recovery_root.mkdir(parents=True, exist_ok=True)
        for path in existing:
            shutil.copy2(path, recovery_root / f"{path.name}.original")
        selected: tuple[Path, SessionRecoveryState] | None = None
        for path, state in (
            (primary, SessionRecoveryState.RESTORED_PRIMARY),
            (backup, SessionRecoveryState.RESTORED_BACKUP),
        ):
            if path.is_file() and self._load_current_payload(path) is not None:
                selected = (path, state)
                break
        if selected is None:
            result = SessionRecoveryResult(
                SessionRecoveryState.PRESERVED_NOT_RESTORED,
                recovery_root=recovery_root,
                detail="Neither the previous primary session nor its backup is compatible.",
            )
            self._write_result(result_path, result)
            return result
        selected_path, state = selected
        payload = self._load_current_payload(selected_path)
        assert payload is not None
        self._write_json_atomic(primary, payload)
        result = SessionRecoveryResult(state, recovery_root=recovery_root)
        self._write_result(result_path, result)
        return result

    @staticmethod
    def _load_current_payload(path: Path) -> dict[str, object] | None:
        """Decode and normalize one candidate through the current full codec."""

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, Mapping):
                return None
            snapshot = session_snapshot_from_json(raw)
            return session_snapshot_to_json(snapshot)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return None

    @staticmethod
    def _write_result(path: Path, result: SessionRecoveryResult) -> None:
        """Persist a result only after its referenced recovery copy exists."""

        SessionRecoveryService._write_json_atomic(path, result.to_json())

    @staticmethod
    def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
        """Replace one JSON file only after a complete sibling write."""

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


__all__ = ["SessionRecoveryService"]
