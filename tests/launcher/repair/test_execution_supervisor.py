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

"""Prove repair cancellation releases native mutation ownership without user cleanup."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from threading import Event
from typing import Never

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.repair_process_supervisor import (
    RepairProcessCancelled,
    RepairProcessError,
    RepairProcessSupervisor,
)
from sugarsubstitute_shared.installation_mutation import (
    installation_mutation,
    InstallationMutationBusyError,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentityError,
    wait_for_process_exit,
)


def test_cancellation_before_start_never_builds_or_launches_a_child(
    tmp_path: Path,
) -> None:
    """Keep early Close authoritative before native admission or source work starts."""

    def reject_command() -> Never:
        """Fail if a cancelled operation reaches its process boundary."""
        raise AssertionError("Cancelled repair attempted to build a child command")

    supervisor = RepairProcessSupervisor(
        command_builder=reject_command, startup_log_path=tmp_path / "repair.log"
    )
    supervisor.request_cancel()
    with pytest.raises(RepairProcessCancelled):
        supervisor.run(
            progress_observer=lambda value: None, output_callback=lambda line: None
        )
    assert supervisor.safe_to_close
    assert not (tmp_path / ".repair").exists()


def test_cancel_during_command_resolution_prevents_native_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe Close again before entering the native child-creation boundary."""

    def resolve_command() -> tuple[str, ...]:
        """Deliver cancellation while resolving the immutable worker invocation."""
        supervisor.request_cancel()
        return (sys.executable, "-c", "pass")

    def reject_spawn(*args: object, **kwargs: object) -> Never:
        """Reject native admission after cancellation has already been requested."""
        del args, kwargs
        pytest.fail("Cancelled operation reached native child creation")

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.repair_process_supervisor.spawn_supervised_process",
        reject_spawn,
    )
    supervisor = RepairProcessSupervisor(
        command_builder=resolve_command,
        startup_log_path=tmp_path / "repair.log",
    )
    with pytest.raises(RepairProcessCancelled):
        supervisor.run(
            progress_observer=lambda value: None, output_callback=lambda line: None
        )
    assert supervisor.safe_to_close


@pytest.mark.platforms("windows")
def test_cancel_during_native_exit_prevents_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Honor Close while the successful worker is still completing native cleanup."""
    from sugarsubstitute_shared.windows_process_family import WindowsProcessFamily

    native_wait = WindowsProcessFamily.wait
    supervisor = RepairProcessSupervisor(
        command_builder=lambda: (
            sys.executable,
            "-m",
            "tests.launcher.repair.execution_process_fixture",
            str(tmp_path),
            "succeeded",
        ),
        startup_log_path=tmp_path / "repair.log",
    )

    def cancel_at_exit(
        process: WindowsProcessFamily, timeout: float | None = None
    ) -> int:
        """Deliver Close at the native wait boundary without replacing native cleanup."""
        supervisor.request_cancel()
        return native_wait(process, timeout)

    monkeypatch.setattr(WindowsProcessFamily, "wait", cancel_at_exit)
    with pytest.raises(RepairProcessCancelled):
        supervisor.run(
            progress_observer=lambda _value: None,
            output_callback=lambda _line: None,
        )
    assert supervisor.safe_to_close
    with installation_mutation(tmp_path) as ownership:
        ownership.validate(tmp_path)


@pytest.mark.platforms("windows")
@pytest.mark.parametrize(
    "outcome",
    [
        "succeeded",
        "failed",
        "crash",
        "succeeded_child",
        "crash_child",
        "succeeded_exiting_child",
    ],
)
def test_terminal_outcomes_leave_no_mutation_owner(
    tmp_path: Path, outcome: str
) -> None:
    """Require success, failure and unexpected death to release the execution family."""
    request = PreparedRepairRequest(
        tmp_path,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        tmp_path / "staged-app",
        tmp_path / "staged-launcher",
        "a" * 64,
        "b" * 64,
    )
    supervisor = RepairProcessSupervisor(
        command_builder=lambda: (
            sys.executable,
            "-m",
            "tests.launcher.repair.execution_process_fixture",
            str(request.install_root),
            outcome,
        ),
        startup_log_path=tmp_path / "repair.log",
    )
    if outcome.startswith("succeeded"):
        supervisor.run(
            progress_observer=lambda _value: None,
            output_callback=lambda _line: None,
        )
    else:
        with pytest.raises(RepairProcessError):
            supervisor.run(
                progress_observer=lambda _value: None,
                output_callback=lambda _line: None,
            )
    assert supervisor.safe_to_close
    with installation_mutation(tmp_path) as ownership:
        ownership.validate(tmp_path)
    if outcome.endswith("_child"):
        try:
            with installation_mutation(tmp_path / "descendant") as ownership:
                ownership.validate(tmp_path / "descendant")
        except InstallationMutationBusyError as error:
            error.add_note(
                f"Descendant ownership after family completion: {error.owner_record!r}"
            )
            if error.owner_record is not None:
                try:
                    wait_for_process_exit(error.owner_record.process, timeout_seconds=0)
                except ProcessIdentityError as identity_error:
                    error.add_note(
                        f"Descendant exit was not confirmed: {identity_error}"
                    )
                else:
                    error.add_note("Native wait confirms the descendant has exited")
            raise


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("mode", ["freeze", "freeze_child"])
def test_cancel_frozen_repair_releases_its_native_mutation_owner(
    tmp_path: Path,
    mode: str,
) -> None:
    """Cancel an uncooperative hidden worker through its retained process family."""
    request = PreparedRepairRequest(
        tmp_path,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        tmp_path / "staged-app",
        tmp_path / "staged-launcher",
        "a" * 64,
        "b" * 64,
    )
    supervisor = RepairProcessSupervisor(
        command_builder=lambda: (
            sys.executable,
            "-m",
            "tests.launcher.repair.execution_process_fixture",
            str(request.install_root),
            mode,
        ),
        startup_log_path=tmp_path / "repair.log",
    )
    started = Event()
    with ThreadPoolExecutor(max_workers=1) as execution:
        future = execution.submit(
            supervisor.run,
            progress_observer=lambda _value: started.set(),
            output_callback=lambda _line: None,
        )
        try:
            assert started.wait(15), "Repair fixture did not acquire native ownership"
            assert not supervisor.safe_to_close
            with pytest.raises(InstallationMutationBusyError):
                with installation_mutation(tmp_path):
                    pytest.fail("The running repair lost mutation ownership")
            if mode.endswith("_child"):
                with pytest.raises(InstallationMutationBusyError):
                    with installation_mutation(tmp_path / "descendant"):
                        pytest.fail("The running descendant lost mutation ownership")
            supervisor.request_cancel()
            with pytest.raises(RepairProcessCancelled):
                future.result(timeout=15)
            assert supervisor.safe_to_close
            try:
                with installation_mutation(tmp_path) as ownership:
                    ownership.validate(tmp_path)
            except InstallationMutationBusyError as error:
                error.add_note(
                    f"Ownership record after family completion: {error.owner_record!r}"
                )
                if error.owner_record is not None:
                    try:
                        wait_for_process_exit(
                            error.owner_record.process, timeout_seconds=0
                        )
                    except ProcessIdentityError as identity_error:
                        error.add_note(
                            f"Owner exit was not confirmed: {identity_error}"
                        )
                    else:
                        error.add_note(
                            "Native wait confirms the recorded owner has exited"
                        )
                raise
            if mode.endswith("_child"):
                with installation_mutation(tmp_path / "descendant") as ownership:
                    ownership.validate(tmp_path / "descendant")
        finally:
            supervisor.request_cancel()
            if not future.done():
                future.result(timeout=15)
