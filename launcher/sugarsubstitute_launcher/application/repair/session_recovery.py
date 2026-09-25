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

"""Invoke session reconciliation through code from the repaired application."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeCommandRunner
from sugarsubstitute_shared.session_recovery import (
    SessionRecoveryResult,
    SessionRecoveryState,
)
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path

_LOGGER = logging.getLogger(__name__)
_TIMEOUT_SECONDS = 120.0


class SessionRescuer(Protocol):
    """Reconcile session state through the promoted application reader."""

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        recovery_root: Path,
    ) -> SessionRecoveryResult:
        """Return restoration outcome while retaining incompatible originals."""


class SubprocessSessionRescuer:
    """Ask the promoted exact app to validate and migrate old session data."""

    def __init__(self, *, runner: RuntimeCommandRunner | None = None) -> None:
        """Store the bounded runtime command adapter."""

        self._runner = runner or SubprocessRuntimeCommandRunner(
            timeout_seconds=_TIMEOUT_SECONDS
        )

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        recovery_root: Path,
    ) -> SessionRecoveryResult:
        """Return restoration outcome without turning session loss into repair loss."""

        session_dir = layout.appdata_dir / "session"
        if not any(
            (session_dir / name).is_file()
            for name in ("session.json", "session.json.bak")
        ):
            return SessionRecoveryResult(SessionRecoveryState.NO_SESSION)
        result_path = recovery_root / "result.json"
        environment = clean_frozen_parent_environment()
        environment["PYTHONPATH"] = str(layout.app_dir)
        command = (
            subprocess_path(layout.runtime_python),
            "-m",
            "substitute.app.maintenance",
            "reconcile-session",
            "--session-dir",
            subprocess_path(session_dir),
            "--recovery-root",
            subprocess_path(recovery_root),
            "--result-path",
            subprocess_path(result_path),
        )
        try:
            self._runner.run(command, cwd=layout.app_dir, env=environment)
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            result = SessionRecoveryResult.from_json(payload)
        except Exception as error:
            _LOGGER.exception(
                "Session recovery could not restore prior state",
                extra={"session_recovery_root": str(recovery_root)},
            )
            return SessionRecoveryResult(
                SessionRecoveryState.PRESERVED_NOT_RESTORED,
                recovery_root=recovery_root if recovery_root.exists() else session_dir,
                detail=f"Session reconciliation failed: {type(error).__name__}",
            )
        if (
            result.recovery_root is not None
            and not result.recovery_root.resolve().is_relative_to(
                recovery_root.resolve()
            )
        ):
            return SessionRecoveryResult(
                SessionRecoveryState.PRESERVED_NOT_RESTORED,
                recovery_root=recovery_root,
                detail="Session recovery reported an invalid recovery path.",
            )
        return result


__all__ = ["SessionRescuer", "SubprocessSessionRescuer"]
