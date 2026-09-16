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

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.repair_execution_supervisor import (
    RepairExecutionCancelled,
    RepairProcessError,
    RepairExecutionSupervisor,
)
from sugarsubstitute_shared.installation_mutation import (
    installation_mutation,
    InstallationMutationBusyError,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentityError,
    wait_for_process_exit,
)


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
    supervisor = RepairExecutionSupervisor(
        command_builder=lambda candidate: (
            sys.executable,
            "-m",
            "tests.launcher.repair.execution_process_fixture",
            str(candidate.install_root),
            outcome,
        )
    )
    if outcome.startswith("succeeded"):
        supervisor.run(
            request,
            progress_observer=lambda _value: None,
            output_callback=lambda _line: None,
        )
    else:
        with pytest.raises(RepairProcessError):
            supervisor.run(
                request,
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
    supervisor = RepairExecutionSupervisor(
        command_builder=lambda candidate: (
            sys.executable,
            "-m",
            "tests.launcher.repair.execution_process_fixture",
            str(candidate.install_root),
            mode,
        )
    )
    started = Event()
    with ThreadPoolExecutor(max_workers=1) as execution:
        future = execution.submit(
            supervisor.run,
            request,
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
            with pytest.raises(RepairExecutionCancelled):
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
