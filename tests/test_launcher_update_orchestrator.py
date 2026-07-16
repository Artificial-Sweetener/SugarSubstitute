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

"""Tests for launcher pre-launch update orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig, UpdateCheckConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.payload import AppPayloadInstallResult
from launcher.sugarsubstitute_launcher.runtime import RuntimeProvisioningResult
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherMinimumVersionError,
    LauncherUpdateOrchestrator,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget


def test_pre_launch_update_skips_without_release_source(tmp_path: Path) -> None:
    """Normal launch should remain safe when no update source is configured."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)

    result = LauncherUpdateOrchestrator(now=_fixed_now).run(
        layout=layout,
        config=config,
        release_source=None,
        no_update_check=False,
    )

    assert result.skipped_reason == "release_source_unconfigured"
    assert result.checked_manifest is False
    assert not layout.state_path.exists()


def test_pre_launch_update_installs_newer_manifest_and_writes_state(
    tmp_path: Path,
) -> None:
    """A newer manifest should install the payload and persist the new version."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)
    source = _ReleaseSource(_manifest(version="0.4.0"))
    installer = _PayloadInstaller(version="0.4.0")
    runtime_reconciler = _RuntimeReconciler()
    progress = _Progress()

    result = LauncherUpdateOrchestrator(
        payload_installer=installer,
        runtime_reconciler=runtime_reconciler,
        now=_fixed_now,
    ).run(
        layout=layout,
        config=config,
        release_source=source,
        no_update_check=False,
        progress=progress,
    )

    assert result.checked_manifest is True
    assert result.installed_update is True
    assert installer.installed_layouts == [layout]
    assert runtime_reconciler.reconciled_layouts == [layout]
    assert LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"
    assert progress.lines == [
        "Checking for SugarSubstitute updates.",
        "Installing SugarSubstitute 0.4.0.",
        "Preparing SugarSubstitute runtime.",
        "Installed SugarSubstitute 0.4.0.",
    ]


def test_pre_launch_update_skips_current_manifest_and_records_check(
    tmp_path: Path,
) -> None:
    """A current installed version should record the check without reinstalling."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)
    LauncherUpdateState(installed_app_version="0.4.0").save(layout.state_path)
    installer = _PayloadInstaller(version="0.4.0")
    runtime_reconciler = _RuntimeReconciler()

    result = LauncherUpdateOrchestrator(
        payload_installer=installer,
        runtime_reconciler=runtime_reconciler,
        now=_fixed_now,
    ).run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(_manifest(version="0.4.0")),
        no_update_check=False,
    )

    state = LauncherUpdateState.load(layout.state_path)
    assert result.skipped_reason == "installed_current"
    assert result.installed_update is False
    assert installer.installed_layouts == []
    assert runtime_reconciler.reconciled_layouts == []
    assert state.installed_app_version == "0.4.0"
    assert state.last_update_check_utc == _fixed_now()


def test_pre_launch_update_respects_disabled_policy(tmp_path: Path) -> None:
    """Disabled update checks should not load the manifest."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(
        layout=layout,
        update_check=UpdateCheckConfig(enabled=False),
    )

    result = LauncherUpdateOrchestrator(now=_fixed_now).run(
        layout=layout,
        config=config,
        release_source=_FailingReleaseSource(),
        no_update_check=False,
    )

    assert result.skipped_reason == "config_disabled"
    assert result.checked_manifest is False


def test_pre_launch_update_failure_returns_safe_result(tmp_path: Path) -> None:
    """Manifest failures should not prevent launching an existing app."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)

    result = LauncherUpdateOrchestrator(now=_fixed_now).run(
        layout=layout,
        config=config,
        release_source=_FailingReleaseSource(),
        no_update_check=False,
    )

    assert result.checked_manifest is True
    assert result.installed_update is False
    assert result.failure_reason == "RuntimeError"
    assert not layout.state_path.exists()


def test_pre_launch_update_runtime_failure_does_not_record_new_version(
    tmp_path: Path,
) -> None:
    """Runtime reconciliation must complete before the update state is advanced."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)

    result = LauncherUpdateOrchestrator(
        payload_installer=_PayloadInstaller(version="0.4.0"),
        runtime_reconciler=_FailingRuntimeReconciler(),
        now=_fixed_now,
    ).run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(_manifest(version="0.4.0")),
        no_update_check=False,
    )

    assert result.checked_manifest is True
    assert result.installed_update is False
    assert result.failure_reason == "RuntimeError"
    assert not layout.state_path.exists()


def test_pre_launch_update_stages_newer_launcher_after_runtime_is_ready(
    tmp_path: Path,
) -> None:
    """The launcher should own future bundle updates after app reconciliation."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("python", encoding="utf-8")
    config = LauncherConfig.from_layout(layout=layout)
    base_manifest = _manifest(version="0.11.0")
    launcher_asset = ReleaseAsset(
        filename="launcher.zip",
        url="file:///launcher.zip",
        sha256="1" * 64,
        size_bytes=42,
    )
    manifest = ReleaseManifest(
        schema_version=base_manifest.schema_version,
        channel=base_manifest.channel,
        version=base_manifest.version,
        minimum_launcher_version=base_manifest.minimum_launcher_version,
        app=base_manifest.app,
        launchers={layout.target.key: launcher_asset},
        installers={},
    )
    stager = _LauncherStager(layout.launcher_update_request_path)

    result = LauncherUpdateOrchestrator(
        payload_installer=_PayloadInstaller(version="0.11.0"),
        runtime_reconciler=_RuntimeReconciler(),
        launcher_bundle_stager=stager,
        launcher_version="0.10.0",
        now=_fixed_now,
    ).run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(manifest),
        no_update_check=False,
    )

    assert result.launcher_update_request_path == str(
        layout.launcher_update_request_path
    )
    assert stager.versions == ["0.11.0"]
    assert stager.assets == [
        LauncherBundleAsset(
            filename=launcher_asset.filename,
            url=launcher_asset.url,
            sha256=launcher_asset.sha256,
            size_bytes=launcher_asset.size_bytes,
        )
    ]


def test_pre_launch_update_blocks_app_below_unavailable_launcher_minimum(
    tmp_path: Path,
) -> None:
    """A manifest minimum must fail closed when its launcher asset is absent."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)
    base = _manifest(version="0.11.0")
    manifest = ReleaseManifest(
        schema_version=base.schema_version,
        channel=base.channel,
        version=base.version,
        minimum_launcher_version="0.11.0",
        app=base.app,
        launchers={},
        installers={},
    )

    with pytest.raises(LauncherMinimumVersionError):
        LauncherUpdateOrchestrator(
            payload_installer=_PayloadInstaller(version="0.11.0"),
            runtime_reconciler=_RuntimeReconciler(),
            launcher_version="0.10.0",
            now=_fixed_now,
        ).run(
            layout=layout,
            config=config,
            release_source=_ReleaseSource(manifest),
            no_update_check=False,
        )
    assert not layout.state_path.exists()


def _fixed_now() -> datetime:
    """Return a deterministic UTC timestamp."""

    return datetime(2026, 7, 7, 12, tzinfo=UTC)


def _manifest(*, version: str, channel: str = "stable") -> ReleaseManifest:
    """Create one minimal release manifest for orchestrator tests."""

    return ReleaseManifest(
        schema_version=1,
        channel=channel,
        version=version,
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename=f"SugarSubstitute-app-v{version}.zip",
            url="file:///release.zip",
            sha256="0" * 64,
            size_bytes=1,
        ),
        launchers={},
        installers={},
    )


class _ReleaseSource:
    """Return one configured manifest."""

    def __init__(self, manifest: ReleaseManifest) -> None:
        """Store the manifest returned by this source."""

        self._manifest = manifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the configured manifest."""

        return self._manifest


class _FailingReleaseSource:
    """Raise when the orchestrator tries to load a manifest."""

    def load_manifest(self) -> ReleaseManifest:
        """Raise a deterministic manifest failure."""

        raise RuntimeError("manifest unavailable")


class _PayloadInstaller:
    """Record app payload install requests."""

    def __init__(self, *, version: str) -> None:
        """Store the version returned by installs."""

        self._version = version
        self.installed_layouts: list[InstallLayout] = []

    def install(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Record one install and return a successful result."""

        self.installed_layouts.append(layout)
        return AppPayloadInstallResult(version=self._version, app_dir=layout.app_dir)


class _RuntimeReconciler:
    """Record runtime reconciliation requests."""

    def __init__(self) -> None:
        """Create an empty reconciliation log."""

        self.reconciled_layouts: list[InstallLayout] = []

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        progress: object,
    ) -> RuntimeProvisioningResult:
        """Record one runtime reconciliation."""

        _ = progress
        self.reconciled_layouts.append(layout)
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=layout.app_dir / "requirements.txt",
        )


class _FailingRuntimeReconciler:
    """Fail when runtime reconciliation runs."""

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        progress: object,
    ) -> RuntimeProvisioningResult:
        """Raise a deterministic runtime reconciliation failure."""

        _ = layout
        _ = progress
        raise RuntimeError("runtime unavailable")


class _Progress:
    """Record update progress lines."""

    def __init__(self) -> None:
        """Create an empty progress log."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one progress line."""

        self.lines.append(line)


class _LauncherStager:
    """Record launcher staging requests."""

    def __init__(self, request_path: Path) -> None:
        """Store the request path returned by staging."""

        self._request_path = request_path
        self.versions: list[str] = []
        self.assets: list[LauncherBundleAsset] = []

    def stage(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
    ) -> Path:
        """Record one update and return its fake request path."""

        _ = install_root
        _ = target
        self.versions.append(version)
        self.assets.append(asset)
        return self._request_path
