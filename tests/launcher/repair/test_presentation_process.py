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

"""Verify the repair process retains native UI and crash dependencies."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Never
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher import repair_presentation_process
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface
from sugarsubstitute_shared.windows_long_paths import subprocess_path


@pytest.mark.parametrize("preparation_id", [None, "a" * 32])
def test_repair_child_and_crash_runtime_survive_live_bundle_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preparation_id: str | None
) -> None:
    """Retain diagnostics in the installation and load all native files independently."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    bundle = InstallLayout.from_root(
        layout.root / ".repair/helper/1.2.3/session/bundle", target=WINDOWS_X64
    )
    staging = layout.root / ".repair/staging/1.2.3"
    if preparation_id is not None:
        staging = staging / preparation_id
    request = PreparedRepairRequest(
        layout.root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
        helper_bundle_dir=bundle.root,
        preparation_id=preparation_id,
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bundle.executable_path))
    monkeypatch.setattr(
        sys, "_MEIPASS", str(bundle.launcher_support_path), raising=False
    )
    observed: list[tuple[str, ...]] = []
    log_paths: list[Path] = []

    class ObservedLaunch(RuntimeError):
        """Stop at the process boundary after inspecting its arguments."""

    def capture_launch(
        command: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        startup_log_path: Path | None = None,
    ) -> Never:
        """Require repair-owned diagnostic storage before starting a child."""
        assert startup_log_path is not None
        log_paths.append(startup_log_path)
        raise ObservedLaunch()

    monkeypatch.setattr(
        repair_presentation_process, "spawn_supervised_process", capture_launch
    )

    class LifecycleBoundary:
        """Inspect the real crash contract at the child-process boundary."""

        def __init__(
            self,
            *,
            accepted_surfaces: Collection[ApplicationReadinessSurface],
            crash_supervisor: ApplicationCrashSupervisor,
            process_starter: Callable[
                [Sequence[str], Mapping[str, str]], tuple[CandidateProcess, Path]
            ],
        ) -> None:
            """Retain the production crash owner without starting a native child."""
            assert tuple(accepted_surfaces) == (
                ApplicationReadinessSurface.LAUNCHER_WINDOW,
            )
            self.crash = crash_supervisor
            self.start = process_starter

        def supervise(
            self,
            *,
            layout: InstallLayout,
            command: Sequence[str],
            environment: Mapping[str, str],
        ) -> int:
            """Prove the emitted process and native dependency paths are independent."""
            context = self.crash.prepare(layout=layout, environment=environment).context
            assert context.crashpad_handler == bundle.crashpad_handler_path
            assert (
                context.crashpad_client_library == bundle.crashpad_client_library_path
            )
            assert context.incident_root.is_relative_to(layout.appdata_dir)
            observed.append(tuple(command))
            with pytest.raises(ObservedLaunch):
                self.start(command, environment)
            return 7

    monkeypatch.setattr(
        repair_presentation_process, "ApplicationLifecycleSupervisor", LifecycleBoundary
    )
    result = repair_presentation_process.IndependentRepairPresentation().run(
        request, {}
    )
    assert result == 7
    assert log_paths == [layout.root / ".repair/diagnostics/repair-child.log"]
    assert bundle.launcher_ui_executable_path is not None
    assert observed == [
        (
            subprocess_path(bundle.launcher_ui_executable_path),
            f"--repair-ui-request={subprocess_path(request.request_path)}",
        )
    ]
