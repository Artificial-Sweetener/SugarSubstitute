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

from sugarsubstitute_shared.installation_mutation import InstallationMutationBusyError

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
from launcher.sugarsubstitute_launcher.data_migrations import (
    DataMigrationRunner,
    default_data_migration_runner,
)
from launcher.sugarsubstitute_launcher.payload import AppPayloadInstaller
from launcher.sugarsubstitute_launcher.payload_staging import AppPayloadStager
from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.payload_models import AppPayloadInstallResult
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource
from launcher.sugarsubstitute_launcher.runtime_reconciliation import (
    RuntimeReconciler,
    UvRuntimeReconciler,
)
from launcher.sugarsubstitute_launcher.update_activation import (
    PendingUpdateActivation,
)
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateRecoveryError,
)
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from launcher.sugarsubstitute_launcher.update_policy import (
    AppPayloadUpdateDecision,
    UpdateCheckDecision,
    decide_app_payload_update,
    decide_update_check,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.update_quarantine import UpdateQuarantine
from launcher.sugarsubstitute_launcher.trusted_metadata import TrustedMetadataState
from launcher.sugarsubstitute_launcher.update_progress import (
    LauncherUpdateProgress,
    ResilientLauncherUpdateProgress,
)
from launcher.sugarsubstitute_launcher.update_rollback_reporting import (
    record_update_rollback,
)
from launcher.sugarsubstitute_launcher.update_activity import (
    application_dependencies_activity,
    application_install_activity,
)
from launcher.sugarsubstitute_launcher.launcher_update_preparation import (
    LauncherBundleStagerProtocol,
    LauncherUpdatePreparation,
)
from sugarsubstitute_shared.update_rollback_report import UpdateRollbackStage
from sugarsubstitute_shared.startup_remote_access import is_startup_connectivity_failure


_LOGGER = logging.getLogger(__name__)


class AppPayloadInstallerProtocol(Protocol):
    """Install one manifest app payload into an install layout."""

    def install(
        self,
        *,
        activation: PendingUpdateActivation,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Install the manifest app payload."""


class UpdateRollbackReporter(Protocol):
    """Persist diagnostics after an update preparation rollback."""

    def __call__(
        self,
        *,
        install_root: Path,
        attempted_version: str,
        stage: UpdateRollbackStage,
        error: BaseException,
    ) -> None:
        """Record one successfully rolled-back update failure."""


@dataclass(frozen=True, slots=True)
class PreLaunchUpdateResult:
    """Describe one launcher pre-launch update attempt."""

    checked_manifest: bool
    installed_update: bool
    skipped_reason: str | None = None
    failure_reason: str | None = None
    launcher_update_request_path: str | None = None
    pending_activation: PendingUpdateActivation | None = None
    attempted_version: str | None = None
    connectivity_failure: bool = False

    @property
    def remote_failure_reason(self) -> str | None:
        """Degrade remote startup only when the update proved connectivity loss."""
        return self.failure_reason if self.connectivity_failure else None


class LauncherUpdateOrchestrator:
    """Coordinate manifest checks, payload install, and update state writes."""

    def __init__(
        self,
        *,
        payload_installer: AppPayloadInstallerProtocol | None = None,
        runtime_reconciler: RuntimeReconciler | None = None,
        launcher_bundle_stager: LauncherBundleStagerProtocol | None = None,
        rollback_reporter: UpdateRollbackReporter = record_update_rollback,
        data_migration_runner: DataMigrationRunner | None = None,
        launcher_version: str = LAUNCHER_VERSION,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Store update collaborators."""

        self._payload_installer = payload_installer
        self._runtime_reconciler = runtime_reconciler or UvRuntimeReconciler()
        self._launcher_update = LauncherUpdatePreparation(
            stager=launcher_bundle_stager, launcher_version=launcher_version
        )
        self._rollback_reporter = rollback_reporter
        self._data_migrations = data_migration_runner or default_data_migration_runner()
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

        progress = ResilientLauncherUpdateProgress(progress)
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
            return self._run_update(
                layout=layout,
                config=config,
                release_source=release_source,
                progress=progress,
            )
        except (
            UpdateRecoveryError,
            InstallationMutationBusyError,
        ):
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
                connectivity_failure=is_startup_connectivity_failure(error),
            )

    def _run_update(
        self,
        *,
        layout: InstallLayout,
        config: LauncherConfig,
        release_source: ReleaseSource,
        progress: LauncherUpdateProgress,
    ) -> PreLaunchUpdateResult:
        """Recover and run the supervisor-serialized update transaction."""

        InstallationRecovery(layout).recover()
        state = LauncherUpdateState.load(layout.state_path)
        manifest = release_source.load_manifest()
        if (
            manifest.signed_metadata_version is not None
            and manifest.signed_metadata_digest is not None
        ):
            TrustedMetadataState.admit(
                install_root=layout.root,
                metadata_version=manifest.signed_metadata_version,
                signed_digest=manifest.signed_metadata_digest,
            )
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

        launcher_request = self._launcher_update.stage(
            layout=layout,
            manifest=manifest,
            progress=progress,
        )
        if launcher_request is not None:
            state.with_update_check(
                channel=manifest.channel,
                checked_at=self._now(),
            ).save(layout.state_path)
            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
                skipped_reason="launcher_update_staged",
                launcher_update_request_path=str(launcher_request),
            )

        update_policy = decide_app_payload_update(
            installed_version=state.installed_app_version,
            manifest_version=manifest.version,
        )
        if update_policy.decision is AppPayloadUpdateDecision.INSTALL:
            if UpdateQuarantine(layout.root).contains(
                version=manifest.version,
                sha256=manifest.app.sha256,
            ):
                return PreLaunchUpdateResult(
                    checked_manifest=True,
                    installed_update=False,
                    skipped_reason="candidate_quarantined",
                    attempted_version=manifest.version,
                )
            successful_state = state.with_successful_update(
                version=manifest.version,
                channel=manifest.channel,
                completed_at=self._now(),
            )
            activation = PendingUpdateActivation.begin(
                layout=layout,
                successful_state=successful_state,
                generation_backed=True,
                candidate_sha256=manifest.app.sha256,
            )
            try:
                install_activity = application_install_activity(manifest.version)
                progress.append_log(install_activity.initial_text)
                progress.start_activity(install_activity)
                try:
                    payload_installer = self._payload_installer or AppPayloadInstaller(
                        stager=AppPayloadStager(
                            downloader=AssetDownloader(
                                progress_observer=lambda _transfer: (
                                    progress.record_activity()
                                )
                            ),
                            activity_observer=progress.record_activity,
                        )
                    )
                    install_result = payload_installer.install(
                        activation=activation,
                        manifest=manifest,
                    )
                    dependencies_activity = application_dependencies_activity()
                    progress.append_log(dependencies_activity.initial_text)
                    progress.start_activity(dependencies_activity)
                    activation.prepare_runtime()
                    self._runtime_reconciler.reconcile(
                        layout=activation.preparation_layout,
                        progress=progress,
                    )
                    self._data_migrations.migrate(
                        install_root=layout.root,
                        target_epoch=manifest.compatibility.data_schema_epoch,
                    )
                    activation.activate()
                except BaseException as error:
                    progress.clear_activity()
                    activation.reject(type(error).__name__)
                    self._rollback_reporter(
                        install_root=layout.root,
                        attempted_version=manifest.version,
                        stage=UpdateRollbackStage.PREPARATION,
                        error=error,
                    )
                    raise
                progress.clear_activity()
                progress.append_log(
                    launcher_text(
                        "Installed SugarSubstitute %1.",
                        install_result.version,
                    )
                )
                return PreLaunchUpdateResult(
                    checked_manifest=True,
                    installed_update=True,
                    pending_activation=activation,
                    attempted_version=manifest.version,
                )
            except BaseException:
                activation.rollback()
                raise

        state.with_update_check(
            channel=manifest.channel,
            checked_at=self._now(),
        ).save(layout.state_path)
        return PreLaunchUpdateResult(
            checked_manifest=True,
            installed_update=False,
            skipped_reason=update_policy.reason,
        )


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(UTC)
