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

"""Qualify selection persistence across genuine headless Windows process exits."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import pytest

from launcher.sugarsubstitute_launcher import generation_supervision
from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.generation_dispatch import (
    dispatch_selected_launcher,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from .native_terminal_event import TerminalEvent
from .support import _write_bundle_tree, _write_installed_layout

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("outcome", ["nonzero", "terminate", "kill", "restart"])
def test_postready_native_exit_preserves_selection_and_election(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Use real readiness, Crashpad, native process containment, and authenticated broker IPC."""
    root = _write_installed_layout(tmp_path / "installation")
    layout = InstallLayout.from_root(root, target=WINDOWS_X64)
    native = (
        Path(__file__).resolve().parents[4]
        / "third_party"
        / "bin"
        / "crashpad"
        / "windows-x64"
    )
    layout.crashpad_handler_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(native / "crashpad_handler.exe", layout.crashpad_handler_path)
    shutil.copy2(
        native / "sugarsubstitute_crashpad_client.dll",
        layout.crashpad_client_library_path,
    )
    staged = root / "launcher" / "updates" / "candidate"
    _write_bundle_tree(staged, marker="selected launcher")
    assets = staged / "launcher-bin" / "launcher_assets"
    assets.mkdir()
    (assets / "launcher-contract.json").write_text(
        '{"schema_version":1,"delegation_protocol":1}', encoding="utf-8"
    )
    selection = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)
    candidate = selection.publish(staged, version="0.27.1")
    selection.activate(candidate)
    event_name = "Local\\SugarSubstitute-Terminal-" + uuid4().hex
    event = TerminalEvent(event_name, create=True)
    interpreter = sys.executable

    launches: list[Path] = []

    def start(
        command: Sequence[str], environment: Mapping[str, str]
    ) -> tuple[CandidateProcess, Path]:
        """Replace only the external executable with the headless protocol fixture."""
        launches.append(Path(command[0]))
        assert Path(command[0]) == candidate.root / "SugarSubstitute.exe"
        child_environment = dict(environment)
        child_environment.update(
            PROOF_TERMINAL_EVENT=event_name,
            PROOF_EXIT_MODE=(
                "nonzero" if outcome == "restart" and len(launches) > 1 else outcome
            ),
            PROOF_INSTALL_ROOT=str(root),
            PYTHONPATH=str(Path(__file__).resolve().parents[4]),
        )
        return spawn_supervised_process(
            (
                interpreter,
                "-m",
                "tests.launcher.update_activation.transaction.generation_exit_child",
            ),
            environment=child_environment,
            allow_handoff=True,
        )

    class PostReadinessExit(ApplicationReadinessSupervisor):
        """Apply a native terminal action after the real readiness owner admits the child."""

        def launch_until_ready(
            self,
            *,
            layout: InstallLayout,
            command: Sequence[str],
            environment: Mapping[str, str],
            expected_exit: Callable[[CandidateProcess], bool] | None = None,
        ) -> CandidateProcess:
            """Guarantee that termination occurs after authenticated readiness."""
            process = super().launch_until_ready(
                layout=layout,
                command=command,
                environment=environment,
                expected_exit=expected_exit,
            )
            if outcome == "terminate":
                process.terminate()
            elif outcome == "kill":
                process.kill()
            else:
                event.signal()
            return process

    def report(
        layout: InstallLayout, incident: str, environment: Mapping[str, str]
    ) -> None:
        """Keep diagnostic publication while omitting the visible reporter boundary."""
        assert incident

    crash = ApplicationCrashSupervisor(reporter_starter=report)
    monkeypatch.setattr(
        generation_supervision, "ApplicationCrashSupervisor", lambda: crash
    )
    supervisor = generation_supervision.LauncherGenerationSupervisor(
        readiness=PostReadinessExit(process_starter=start)
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    owner = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    try:
        with owner:
            result = dispatch_selected_launcher(
                layout=layout, broker=owner, arguments=(), supervisor=supervisor
            )
            assert result is not None and result != 0
            assert len(launches) == (2 if outcome == "restart" else 1)
            assert selection.resolve() == candidate
            assert not (candidate.root.parent / "rejected.json").exists()
            owner.bind_startup_presenter(lambda _: "existing-owner")
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=root,
                    invocation=ApplicationInvocation.capture(["launcher"]),
                )
                is None
            )
        incidents = CrashIncidentStore(
            layout.appdata_dir / "diagnostics" / "crashes"
        ).pending()
        assert len(incidents) == (2 if outcome == "restart" else 1)
        assert incidents[0].exit_code != 0
    finally:
        event.close()
