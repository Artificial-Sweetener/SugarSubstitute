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

"""Verify exact-version, mutation-free repair artifact preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pytest

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparationError,
    RepairPreparationService,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import StagedAppPayload
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget


@dataclass(frozen=True, slots=True)
class _ReleaseSource:
    """Expose one deterministic release manifest."""

    manifest: ReleaseManifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the configured release manifest."""

        return self.manifest


class _AppStager:
    """Record and materialize an application staging request."""

    def __init__(self) -> None:
        """Initialize the staging-call count."""

        self.calls = 0

    def stage(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
        destination_dir: Path,
    ) -> StagedAppPayload:
        """Create a representative staged application."""

        del layout
        self.calls += 1
        destination_dir.mkdir(parents=True)
        (destination_dir / "version.txt").write_text(manifest.version, encoding="utf-8")
        return StagedAppPayload(manifest.version, destination_dir)


class _LauncherStager:
    """Record and materialize a launcher staging request."""

    def __init__(self) -> None:
        """Initialize the staging-call count."""

        self.calls = 0

    def stage_bundle(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
        destination_dir: Path,
    ) -> Path:
        """Create a representative staged launcher bundle."""

        del install_root, asset
        self.calls += 1
        destination_dir.mkdir(parents=True)
        for relative in target.required_file_relative_paths:
            path = destination_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(version, encoding="utf-8")
        (destination_dir / target.support_relative_path).mkdir(
            parents=True, exist_ok=True
        )
        return destination_dir


def _manifest(
    *, version: str = "1.2.3", include_launcher: bool = True
) -> ReleaseManifest:
    """Build one immutable test manifest."""

    asset = ReleaseAsset(
        filename="artifact.zip",
        url="https://example.invalid/artifact.zip",
        sha256="a" * 64,
        size_bytes=123,
    )
    launchers = {WINDOWS_X64.key: asset} if include_launcher else {}
    return ReleaseManifest(
        schema_version=2,
        channel="stable",
        version=version,
        minimum_launcher_version="1.0.0",
        app=asset,
        launchers=MappingProxyType(launchers),
        installers=MappingProxyType({}),
    )


def test_preparation_stages_exact_version_without_touching_active_install(
    tmp_path: Path,
) -> None:
    """Background preparation must finish the independent bundle before handoff."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute", target=WINDOWS_X64)
    layout.app_dir.mkdir(parents=True)
    layout.runtime_dir.mkdir(parents=True)
    app_sentinel = layout.app_dir / "sentinel.txt"
    runtime_sentinel = layout.runtime_dir / "sentinel.txt"
    app_sentinel.write_bytes(b"active-app")
    runtime_sentinel.write_bytes(b"active-runtime")
    app_stager = _AppStager()
    launcher_stager = _LauncherStager()

    preparation = RepairPreparationService(
        app_stager=app_stager,
        launcher_stager=launcher_stager,
    ).prepare_application_repair(
        layout=layout,
        release_source=_ReleaseSource(_manifest()),
        expected_version="1.2.3",
    )

    assert app_sentinel.read_bytes() == b"active-app"
    assert runtime_sentinel.read_bytes() == b"active-runtime"
    assert app_stager.calls == 1
    assert launcher_stager.calls == 1
    assert PreparedRepairRequest.load(preparation.request_path) == preparation.request
    assert preparation.request.version == "1.2.3"
    assert preparation.request.helper_bundle_dir is not None
    assert (
        preparation.request.helper_bundle_dir / "launcher-bin/LauncherUi.exe"
    ).is_file()
    assert preparation.request.staged_app_dir.is_relative_to(
        layout.root / ".repair" / "staging" / "1.2.3"
    )


def test_preparation_reports_work_before_publishing_readiness(tmp_path: Path) -> None:
    """Only report complete preparation after the immutable request can be reopened."""
    layout = InstallLayout.from_root(tmp_path, target=WINDOWS_X64)
    observations: list[PreparationProgress] = []

    class ObservedAppStager(_AppStager):
        """Observe reported work at the external payload boundary."""

        def stage(
            self,
            *,
            layout: InstallLayout,
            manifest: ReleaseManifest,
            destination_dir: Path,
        ) -> StagedAppPayload:
            """Require the phase to be visible before its potentially slow work starts."""
            assert observations[-1].stage is PreparationStage.APPLICATION
            assert observations[-1].completed_fraction < 1
            return super().stage(
                layout=layout, manifest=manifest, destination_dir=destination_dir
            )

    result = RepairPreparationService(
        app_stager=ObservedAppStager(),
        launcher_stager=_LauncherStager(),
        progress_observer=observations.append,
    ).prepare_bound_application_repair(
        layout=layout, release_source=_ReleaseSource(_manifest())
    )
    assert observations[0].stage is PreparationStage.RELEASE
    assert observations[-1].stage is PreparationStage.READY
    assert observations[-1].completed_fraction == 1
    assert PreparedRepairRequest.load(result.request_path) == result.request
    fractions = [progress.completed_fraction for progress in observations]
    assert fractions == sorted(fractions)


@pytest.mark.parametrize("failure", ["helper", "request"])
def test_failed_preparation_never_reports_ready_or_changes_active_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Keep late preparation failures distinct from a durable repair handoff."""
    layout = InstallLayout.from_root(tmp_path, target=WINDOWS_X64)
    layout.app_dir.mkdir(parents=True)
    sentinel = layout.app_dir / "active.txt"
    sentinel.write_bytes(b"installed application")
    observations: list[PreparationProgress] = []

    def fail_helper(request: PreparedRepairRequest) -> Path:
        """Represent an unavailable destination for the independent helper."""
        raise OSError("synthetic helper write failure")

    def fail_request(request: PreparedRepairRequest, path: Path) -> None:
        """Represent a failed durable request write after helper preparation."""
        raise OSError("synthetic request write failure")

    if failure == "helper":
        monkeypatch.setattr(
            "launcher.sugarsubstitute_launcher.application.repair."
            "preparation_service.stage_independent_repair_bundle",
            fail_helper,
        )
    else:
        monkeypatch.setattr(PreparedRepairRequest, "save", fail_request)

    service = RepairPreparationService(
        app_stager=_AppStager(),
        launcher_stager=_LauncherStager(),
        progress_observer=observations.append,
    )
    with pytest.raises(OSError, match=f"synthetic {failure} write failure"):
        service.prepare_bound_application_repair(
            layout=layout, release_source=_ReleaseSource(_manifest())
        )

    assert observations[-1].stage is PreparationStage.HELPER
    assert all(progress.completed_fraction < 1 for progress in observations)
    assert sentinel.read_bytes() == b"installed application"


def test_progress_presentation_failure_cannot_abort_preparation(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Persist usable repair inputs even when the presentation observer fails."""
    calls = 0

    def unavailable_view(progress: PreparationProgress) -> None:
        """Represent a disposed presentation receiver during worker completion."""
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic disposed progress receiver")

    result = RepairPreparationService(
        app_stager=_AppStager(),
        launcher_stager=_LauncherStager(),
        progress_observer=unavailable_view,
    ).prepare_bound_application_repair(
        layout=InstallLayout.from_root(tmp_path, target=WINDOWS_X64),
        release_source=_ReleaseSource(_manifest()),
    )

    assert PreparedRepairRequest.load(result.request_path) == result.request
    assert calls == 1
    assert "synthetic disposed progress receiver" in caplog.text


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        (_manifest(version="1.2.4"), "version mismatch"),
        (_manifest(include_launcher=False), "has no launcher"),
    ],
)
def test_preparation_rejects_incomplete_exact_release_before_staging(
    tmp_path: Path,
    manifest: ReleaseManifest,
    message: str,
) -> None:
    """Missing exact artifacts must fail before any download or extraction begins."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute", target=WINDOWS_X64)
    app_stager = _AppStager()
    launcher_stager = _LauncherStager()

    with pytest.raises(RepairPreparationError, match=message):
        RepairPreparationService(
            app_stager=app_stager,
            launcher_stager=launcher_stager,
        ).prepare_application_repair(
            layout=layout,
            release_source=_ReleaseSource(manifest),
            expected_version="1.2.3",
        )

    assert app_stager.calls == 0
    assert launcher_stager.calls == 0


def test_repeated_repair_preparation_preserves_the_first_attempt(
    tmp_path: Path,
) -> None:
    """Keep each prepared request and staged input independent until execution."""
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    service = RepairPreparationService(
        app_stager=_AppStager(), launcher_stager=_LauncherStager()
    )
    first = service.prepare_application_repair(
        layout=layout,
        release_source=_ReleaseSource(_manifest()),
        expected_version="1.2.3",
    )
    original = first.request_path.read_bytes()
    app_original = (first.request.staged_app_dir / "version.txt").read_bytes()
    second = service.prepare_application_repair(
        layout=layout,
        release_source=_ReleaseSource(_manifest()),
        expected_version="1.2.3",
    )
    assert second.request_path != first.request_path
    assert second.request.staged_app_dir != first.request.staged_app_dir
    assert second.request.staged_launcher_dir != first.request.staged_launcher_dir
    assert first.request_path.read_bytes() == original
    assert (first.request.staged_app_dir / "version.txt").read_bytes() == app_original
    assert PreparedRepairRequest.load(first.request_path) == first.request
    assert PreparedRepairRequest.load(second.request_path) == second.request
