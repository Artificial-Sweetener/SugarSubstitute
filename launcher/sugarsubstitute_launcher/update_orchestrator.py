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

"""Run launcher-owned pre-launch app payload updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Protocol

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload import (
    AppPayloadInstallResult,
    AppPayloadInstaller,
)
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource
from launcher.sugarsubstitute_launcher.runtime_reconciliation import (
    RuntimeReconciler,
    UvRuntimeReconciler,
)
from launcher.sugarsubstitute_launcher.update_lock import (
    LauncherUpdateLock,
    LauncherUpdateLockError,
)
from launcher.sugarsubstitute_launcher.update_policy import (
    AppPayloadUpdateDecision,
    UpdateCheckDecision,
    decide_app_payload_update,
    decide_update_check,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState


_LOGGER = logging.getLogger(__name__)


class LauncherUpdateProgress(Protocol):
    """Receive user-visible launcher update progress."""

    def append_log(self, line: str) -> None:
        """Append one update progress line."""


class AppPayloadInstallerProtocol(Protocol):
    """Install one manifest app payload into an install layout."""

    def install(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Install the manifest app payload."""


@dataclass(frozen=True, slots=True)
class PreLaunchUpdateResult:
    """Describe one launcher pre-launch update attempt."""

    checked_manifest: bool
    installed_update: bool
    skipped_reason: str | None = None
    failure_reason: str | None = None


class NullLauncherUpdateProgress:
    """Ignore update progress when no splash or UI surface is available."""

    def append_log(self, line: str) -> None:
        """Discard one progress line."""

        _ = line


class LauncherUpdateOrchestrator:
    """Coordinate manifest checks, payload install, and update state writes."""

    def __init__(
        self,
        *,
        payload_installer: AppPayloadInstallerProtocol | None = None,
        runtime_reconciler: RuntimeReconciler | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Store update collaborators."""

        self._payload_installer = payload_installer or AppPayloadInstaller()
        self._runtime_reconciler = runtime_reconciler or UvRuntimeReconciler()
        self._now = _utc_now if now is None else now

    def run(
        self,
        *,
        layout: InstallLayout,
        config: LauncherConfig,
        release_source: ReleaseSource | None,
        no_update_check: bool,
        progress: LauncherUpdateProgress | None = None,
    ) -> PreLaunchUpdateResult:
        """Run a best-effort update before launching the installed app."""

        progress = progress or NullLauncherUpdateProgress()
        state = LauncherUpdateState.load(layout.state_path)
        check_policy = decide_update_check(
            config=config,
            state=state,
            now=self._now(),
            no_update_check=no_update_check,
        )
        if release_source is None:
            return PreLaunchUpdateResult(
                checked_manifest=False,
                installed_update=False,
                skipped_reason="release_source_unconfigured",
            )
        if check_policy.decision is UpdateCheckDecision.SKIP:
            return PreLaunchUpdateResult(
                checked_manifest=False,
                installed_update=False,
                skipped_reason=check_policy.reason,
            )

        progress.append_log("Checking for SugarSubstitute updates.")
        try:
            with LauncherUpdateLock.acquire(layout.locks_dir):
                return self._run_with_lock(
                    layout=layout,
                    config=config,
                    release_source=release_source,
                    progress=progress,
                )
        except LauncherUpdateLockError as error:
            _LOGGER.warning("Skipping update check because lock is held: %r", error)
            return PreLaunchUpdateResult(
                checked_manifest=False,
                installed_update=False,
                skipped_reason="update_lock_unavailable",
            )
        except Exception as error:
            _LOGGER.warning(
                "Pre-launch update failed; launching installed app.",
                exc_info=True,
            )
            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
                failure_reason=type(error).__name__,
            )

    def _run_with_lock(
        self,
        *,
        layout: InstallLayout,
        config: LauncherConfig,
        release_source: ReleaseSource,
        progress: LauncherUpdateProgress,
    ) -> PreLaunchUpdateResult:
        """Run the manifest and install sequence while holding the update lock."""

        state = LauncherUpdateState.load(layout.state_path)
        manifest = release_source.load_manifest()
        if manifest.channel != config.channel:
            state.with_update_check(
                channel=manifest.channel,
                checked_at=self._now(),
            ).save(layout.state_path)
            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
                skipped_reason="channel_mismatch",
            )

        update_policy = decide_app_payload_update(
            installed_version=state.installed_app_version,
            manifest_version=manifest.version,
        )
        if update_policy.decision is AppPayloadUpdateDecision.SKIP:
            state.with_update_check(
                channel=manifest.channel,
                checked_at=self._now(),
            ).save(layout.state_path)
            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
                skipped_reason=update_policy.reason,
            )

        progress.append_log(f"Installing SugarSubstitute {manifest.version}.")
        install_result = self._payload_installer.install(
            layout=layout,
            manifest=manifest,
        )
        progress.append_log("Preparing SugarSubstitute runtime.")
        self._runtime_reconciler.reconcile(layout=layout, progress=progress)
        state.with_successful_update(
            version=install_result.version,
            channel=manifest.channel,
            completed_at=self._now(),
        ).save(layout.state_path)
        progress.append_log(f"Installed SugarSubstitute {install_result.version}.")
        return PreLaunchUpdateResult(checked_manifest=True, installed_update=True)


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(UTC)
