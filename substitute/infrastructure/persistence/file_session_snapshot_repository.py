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

"""Persist mutable session snapshots as atomic JSON files."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from substitute.domain.session import (
    SessionSnapshot,
    session_snapshot_from_json,
    session_snapshot_to_json,
)
from substitute.domain.workspace_snapshot import SnapshotCodecError
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_warning,
)

_LOGGER = get_logger("infrastructure.persistence.file_session_snapshot_repository")


class FileSessionSnapshotRepository:
    """Load and save session snapshots beneath the app session directory."""

    def __init__(self, session_dir: Path) -> None:
        """Create a repository rooted at the Substitute session directory."""

        self._session_dir = Path(session_dir)
        self._session_path = self._session_dir / "session.json"
        self._backup_path = self._session_dir / "session.json.bak"
        self._temp_path = self._session_dir / "session.json.tmp"

    def load(self) -> SessionSnapshot | None:
        """Load the primary snapshot, falling back to backup when possible."""

        primary = self._load_path(self._session_path, label="primary")
        if primary is not None:
            return primary
        if not self._session_path.exists():
            return self._load_path(self._backup_path, label="backup")
        backup = self._load_path(self._backup_path, label="backup")
        if backup is not None:
            log_warning(
                _LOGGER,
                "Recovered session snapshot from backup",
                session_path=str(self._session_path),
                backup_path=str(self._backup_path),
            )
        return backup

    def save(self, snapshot: SessionSnapshot) -> None:
        """Persist one snapshot using temp-write and atomic replacement."""

        self._session_dir.mkdir(parents=True, exist_ok=True)
        payload = session_snapshot_to_json(snapshot)
        shell_layout = snapshot.workspace.shell_layout
        log_debug(
            _LOGGER,
            "file session repository saving shell layout",
            session_path=str(self._session_path),
            active_route=snapshot.workspace.active_route,
            active_workflow_id=snapshot.workspace.active_workflow_id,
            shell_layout_present=shell_layout is not None,
            saved_main_splitter_sizes=tuple(shell_layout.main_splitter_sizes)
            if shell_layout is not None
            else (),
            saved_editor_output_splitter_sizes=tuple(
                shell_layout.editor_output_splitter_sizes
            )
            if shell_layout is not None
            else (),
            saved_cube_stack_compact=shell_layout.cube_stack_compact
            if shell_layout is not None
            else None,
            saved_cube_stack_width=shell_layout.cube_stack_width
            if shell_layout is not None
            else None,
            saved_editor_panel_width=shell_layout.editor_panel_width
            if shell_layout is not None
            else None,
            saved_canvas_panel_width=shell_layout.canvas_panel_width
            if shell_layout is not None
            else None,
        )
        log_debug(
            _LOGGER,
            "file session repository save payload",
            session_path=str(self._session_path),
            active_route=snapshot.workspace.active_route,
            active_workflow_id=snapshot.workspace.active_workflow_id,
            tab_order=snapshot.workspace.tab_order,
            workflow_count=len(snapshot.workspace.workflows),
        )
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        self._temp_path.write_text(serialized, encoding="utf-8")
        if self._session_path.exists():
            shutil.copy2(self._session_path, self._backup_path)
        os.replace(self._temp_path, self._session_path)
        log_debug(
            _LOGGER,
            "Saved session snapshot",
            session_path=str(self._session_path),
            captured_at=snapshot.captured_at.isoformat(),
            workflow_count=len(snapshot.workspace.workflows),
        )

    def _load_path(self, path: Path, *, label: str) -> SessionSnapshot | None:
        """Load one snapshot file and log recoverable failures."""

        if not path.exists():
            return None
        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(decoded, Mapping):
                raise SnapshotCodecError("Session snapshot root must be an object")
            snapshot = session_snapshot_from_json(decoded)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to load session snapshot",
                session_path=str(path),
                session_snapshot_label=label,
                error=error,
            )
            return None
        log_debug(
            _LOGGER,
            "file session repository loaded payload",
            session_path=str(path),
            session_snapshot_label=label,
            active_route=snapshot.workspace.active_route,
            active_workflow_id=snapshot.workspace.active_workflow_id,
            tab_order=snapshot.workspace.tab_order,
            workflow_count=len(snapshot.workspace.workflows),
        )
        shell_layout = snapshot.workspace.shell_layout
        log_debug(
            _LOGGER,
            "file session repository loaded shell layout",
            session_path=str(path),
            session_snapshot_label=label,
            active_route=snapshot.workspace.active_route,
            active_workflow_id=snapshot.workspace.active_workflow_id,
            shell_layout_present=shell_layout is not None,
            loaded_main_splitter_sizes=tuple(shell_layout.main_splitter_sizes)
            if shell_layout is not None
            else (),
            loaded_editor_output_splitter_sizes=tuple(
                shell_layout.editor_output_splitter_sizes
            )
            if shell_layout is not None
            else (),
            loaded_cube_stack_compact=shell_layout.cube_stack_compact
            if shell_layout is not None
            else None,
            loaded_cube_stack_width=shell_layout.cube_stack_width
            if shell_layout is not None
            else None,
            loaded_editor_panel_width=shell_layout.editor_panel_width
            if shell_layout is not None
            else None,
            loaded_canvas_panel_width=shell_layout.canvas_panel_width
            if shell_layout is not None
            else None,
        )
        log_debug(
            _LOGGER,
            "Loaded session snapshot",
            session_path=str(path),
            session_snapshot_label=label,
            captured_at=snapshot.captured_at.isoformat(),
            workflow_count=len(snapshot.workspace.workflows),
        )
        return snapshot


__all__ = ["FileSessionSnapshotRepository"]
