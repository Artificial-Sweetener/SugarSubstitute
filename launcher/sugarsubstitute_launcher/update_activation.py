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

"""Own durable activation, commit, recovery, and rollback for app updates."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shutil
import secrets

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_rollback_reporting import (
    discard_update_rollback_report,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState


_LOGGER = logging.getLogger(__name__)
_JOURNAL_SCHEMA_VERSION = 1
_JOURNAL_NAME = "pending-app-update.json"
_PREPARING_PHASE = "preparing"
_COMMITTED_PHASE = "committed"


class UpdateRecoveryError(RuntimeError):
    """Report pending update state that cannot be recovered safely."""


@dataclass(frozen=True, slots=True)
class _UpdateActivationJournal:
    """Describe the pre-update directories required for crash recovery."""

    had_app: bool
    had_runtime: bool
    phase: str
    successful_state: LauncherUpdateState

    def to_json(self) -> dict[str, object]:
        """Return the stable persisted journal representation."""

        return {
            "had_app": self.had_app,
            "had_runtime": self.had_runtime,
            "phase": self.phase,
            "schema_version": _JOURNAL_SCHEMA_VERSION,
            "successful_state": self.successful_state.to_json(),
        }


class PendingUpdateActivation:
    """Hold a prepared update until its first visible launch is proven."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        journal: _UpdateActivationJournal,
        successful_state: LauncherUpdateState,
    ) -> None:
        """Store the durable rollback record and state to commit."""

        self._layout = layout
        self._journal = journal
        self._successful_state = successful_state
        self._finished = False

    @classmethod
    def begin(
        cls,
        *,
        layout: InstallLayout,
        successful_state: LauncherUpdateState,
    ) -> PendingUpdateActivation:
        """Persist recovery intent before any installed directory is replaced."""

        journal = _UpdateActivationJournal(
            had_app=layout.app_dir.exists(),
            had_runtime=layout.runtime_dir.exists(),
            phase=_PREPARING_PHASE,
            successful_state=successful_state,
        )
        _write_json_atomic(_journal_path(layout), journal.to_json())
        return cls(
            layout=layout,
            journal=journal,
            successful_state=successful_state,
        )

    def prepare_runtime(self) -> None:
        """Preserve the prior runtime and create a clean candidate runtime."""

        previous_runtime = _previous_runtime_dir(self._layout)
        _remove_directory(previous_runtime)
        if self._layout.runtime_dir.exists():
            self._layout.runtime_dir.replace(previous_runtime)
        self._layout.runtime_dir.mkdir(parents=True, exist_ok=True)

    def commit(self) -> None:
        """Record the proven version and retire rollback directories."""

        if self._finished:
            return
        committed_journal = _UpdateActivationJournal(
            had_app=self._journal.had_app,
            had_runtime=self._journal.had_runtime,
            phase=_COMMITTED_PHASE,
            successful_state=self._successful_state,
        )
        _write_json_atomic(
            _journal_path(self._layout),
            committed_journal.to_json(),
        )
        self._successful_state.save(self._layout.state_path)
        discard_update_rollback_report(self._layout.root)
        for path in (
            _previous_app_dir(self._layout),
            _previous_runtime_dir(self._layout),
        ):
            try:
                _remove_directory(path)
            except OSError:
                _LOGGER.warning(
                    "Failed to remove committed update backup | path=%s",
                    path,
                    exc_info=True,
                )
        _remove_journal(self._layout)
        self._finished = True

    def rollback(self) -> None:
        """Restore the exact app and runtime that preceded the candidate."""

        if self._finished:
            return
        _restore_directory(
            active=self._layout.runtime_dir,
            previous=_previous_runtime_dir(self._layout),
            existed_before=self._journal.had_runtime,
        )
        _restore_directory(
            active=self._layout.app_dir,
            previous=_previous_app_dir(self._layout),
            existed_before=self._journal.had_app,
        )
        _remove_directory(self._layout.root / "app_next")
        _remove_journal(self._layout)
        self._finished = True


def recover_interrupted_update(layout: InstallLayout) -> bool:
    """Rollback a journaled update left incomplete by process termination."""

    journal = _load_journal(layout)
    if journal is None:
        return False
    if journal.phase == _COMMITTED_PHASE:
        journal.successful_state.save(layout.state_path)
        _remove_directory(_previous_app_dir(layout))
        _remove_directory(_previous_runtime_dir(layout))
        _remove_journal(layout)
        _LOGGER.warning("Completed an interrupted proven app update.")
        return True
    _restore_directory(
        active=layout.runtime_dir,
        previous=_previous_runtime_dir(layout),
        existed_before=journal.had_runtime,
    )
    _restore_directory(
        active=layout.app_dir,
        previous=_previous_app_dir(layout),
        existed_before=journal.had_app,
    )
    _remove_directory(layout.root / "app_next")
    _remove_journal(layout)
    _LOGGER.warning("Recovered an interrupted app update before launch.")
    return True


def _load_journal(layout: InstallLayout) -> _UpdateActivationJournal | None:
    """Load one valid pending-update journal or fail closed on corruption."""

    path = _journal_path(layout)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise UpdateRecoveryError(
            f"Pending update journal is unreadable: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise UpdateRecoveryError(f"Pending update journal is invalid: {path}")
    if payload.get("schema_version") != _JOURNAL_SCHEMA_VERSION:
        raise UpdateRecoveryError(
            f"Pending update journal has an unsupported schema: {path}"
        )
    had_app = payload.get("had_app")
    had_runtime = payload.get("had_runtime")
    phase = payload.get("phase")
    successful_state = payload.get("successful_state")
    if (
        not isinstance(had_app, bool)
        or not isinstance(had_runtime, bool)
        or phase not in {_PREPARING_PHASE, _COMMITTED_PHASE}
        or not isinstance(successful_state, dict)
    ):
        raise UpdateRecoveryError(f"Pending update journal is invalid: {path}")
    try:
        parsed_state = LauncherUpdateState.from_json(successful_state)
    except (TypeError, ValueError) as error:
        raise UpdateRecoveryError(
            f"Pending update journal contains invalid state: {path}"
        ) from error
    return _UpdateActivationJournal(
        had_app=had_app,
        had_runtime=had_runtime,
        phase=phase,
        successful_state=parsed_state,
    )


def _restore_directory(*, active: Path, previous: Path, existed_before: bool) -> None:
    """Restore one preserved directory or remove a newly introduced directory."""

    if previous.exists():
        _remove_directory(active)
        previous.replace(active)
        return
    if not existed_before:
        _remove_directory(active)


def _journal_path(layout: InstallLayout) -> Path:
    """Return the single durable pending-update journal path."""

    return layout.launcher_dir / _JOURNAL_NAME


def _previous_app_dir(layout: InstallLayout) -> Path:
    """Return the app rollback directory used by payload promotion."""

    return layout.root / "app_previous"


def _previous_runtime_dir(layout: InstallLayout) -> Path:
    """Return the runtime rollback directory used during activation."""

    return layout.root / "runtime_previous"


def _remove_journal(layout: InstallLayout) -> None:
    """Remove the pending-update journal after a terminal transition."""

    try:
        _journal_path(layout).unlink()
    except FileNotFoundError:
        pass


def _remove_directory(path: Path) -> None:
    """Remove one launcher-owned update directory when present."""

    if path.exists():
        shutil.rmtree(path)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist a stable JSON object in launcher-owned state."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


__all__ = [
    "PendingUpdateActivation",
    "UpdateRecoveryError",
    "recover_interrupted_update",
]
