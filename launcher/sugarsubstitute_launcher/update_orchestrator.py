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
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher import __version__ as LAUNCHER_VERSION

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
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
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions


_LOGGER = logging.getLogger(__name__)


class LauncherMinimumVersionError(RuntimeError):
    """Report a required launcher update that cannot be completed safely."""


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


class LauncherBundleStagerProtocol(Protocol):
    """Stage a verified launcher bundle for detached replacement."""

    def stage(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
    ) -> Path:
        """Return the pending update request path."""


@dataclass(frozen=True, slots=True)
class PreLaunchUpdateResult:
    """Describe one launcher pre-launch update attempt."""

    checked_manifest: bool
    installed_update: bool
    skipped_reason: str | None = None
    failure_reason: str | None = None
    launcher_update_request_path: str | None = None


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
        launcher_bundle_stager: LauncherBundleStagerProtocol | None = None,
        launcher_version: str = LAUNCHER_VERSION,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Store update collaborators."""

        self._payload_installer = payload_installer or AppPayloadInstaller()
        self._runtime_reconciler = runtime_reconciler or UvRuntimeReconciler()
        self._launcher_bundle_stager = launcher_bundle_stager or LauncherBundleStager()
        self._launcher_version = launcher_version
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
        check_policy = decide_update_check(
            config=config,
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

        progress.append_log(launcher_text("Checking for SugarSubstitute updates."))
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
        except LauncherMinimumVersionError:
            raise
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
        installed_app_update = False
        if update_policy.decision is AppPayloadUpdateDecision.INSTALL:
            progress.append_log(
                launcher_text("Installing SugarSubstitute %1.", manifest.version)
            )
            install_result = self._payload_installer.install(
                layout=layout,
                manifest=manifest,
            )
            progress.append_log(launcher_text("Preparing SugarSubstitute runtime."))
            self._runtime_reconciler.reconcile(layout=layout, progress=progress)
            state = state.with_successful_update(
                version=install_result.version,
                channel=manifest.channel,
                completed_at=self._now(),
            )
            progress.append_log(
                launcher_text(
                    "Installed SugarSubstitute %1.",
                    install_result.version,
                )
            )
            installed_app_update = True
        else:
            state = state.with_update_check(
                channel=manifest.channel,
                checked_at=self._now(),
            )
        launcher_request = self._stage_launcher_update(
            layout=layout,
            manifest=manifest,
            progress=progress,
        )
        state.save(layout.state_path)
        return PreLaunchUpdateResult(
            checked_manifest=True,
            installed_update=installed_app_update,
            skipped_reason=(None if installed_app_update else update_policy.reason),
            launcher_update_request_path=(
                str(launcher_request) if launcher_request is not None else None
            ),
        )

    def _stage_launcher_update(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
        progress: LauncherUpdateProgress,
    ) -> Path | None:
        """Stage a newer launcher or enforce the manifest minimum version."""

        version_comparison = compare_release_versions(
            self._launcher_version,
            manifest.version,
        )
        minimum_comparison = compare_release_versions(
            self._launcher_version,
            manifest.minimum_launcher_version,
        )
        if minimum_comparison < 0 and version_comparison >= 0:
            raise LauncherMinimumVersionError(
                "The release manifest requires a launcher version newer than its "
                "published launcher bundle."
            )
        if version_comparison >= 0:
            return None
        release_asset = manifest.launcher_for(layout.target)
        if release_asset is None:
            if minimum_comparison < 0:
                raise LauncherMinimumVersionError(
                    "This release requires a newer launcher, but its launcher bundle "
                    f"is missing for {layout.target.key}."
                )
            return None
        if not layout.runtime_python.is_file():
            error_message = (
                "The managed app runtime is unavailable for launcher replacement."
            )
            if minimum_comparison < 0:
                raise LauncherMinimumVersionError(error_message)
            raise RuntimeError(error_message)
        progress.append_log(launcher_text("Preparing launcher %1.", manifest.version))
        try:
            request_path = self._launcher_bundle_stager.stage(
                install_root=layout.root,
                version=manifest.version,
                target=launcher_bundle_target_for_key(layout.target.key),
                asset=LauncherBundleAsset(
                    filename=release_asset.filename,
                    url=release_asset.url,
                    sha256=release_asset.sha256,
                    size_bytes=release_asset.size_bytes,
                ),
            )
        except Exception as error:
            if minimum_comparison < 0:
                raise LauncherMinimumVersionError(
                    "The required launcher update could not be staged."
                ) from error
            raise
        progress.append_log(
            launcher_text("The launcher will restart to finish updating.")
        )
        return request_path


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(UTC)
