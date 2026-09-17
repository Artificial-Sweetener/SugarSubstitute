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

"""Exercise preparation through the private headless bootstrap and native owner."""

from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.repair_preparation_child import (
    run_repair_preparation_invocation,
)
from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    REPAIR_EXECUTION_ENDPOINT_ENV,
)
from launcher.sugarsubstitute_launcher.repair_process_supervisor import (
    RepairProcessError,
    RepairProcessSupervisor,
)


def test_preparation_requires_capability_before_reading_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reject direct worker input before touching the named path or loading a provider."""
    monkeypatch.delenv(REPAIR_EXECUTION_ENDPOINT_ENV, raising=False)
    with pytest.raises(ValueError, match="supervisor capability"):
        run_repair_preparation_invocation(
            (f"--repair-preparation-input={tmp_path / 'missing.json'}",)
        )
    assert list(tmp_path.iterdir()) == []
    assert run_repair_preparation_invocation(("--ordinary-launch",)) is None


@pytest.mark.parametrize(
    "arguments",
    [
        ("--repair-preparation-input=",),
        ("--repair-preparation-input=a", "--ordinary-launch"),
        ("--repair-preparation-input=a", "--repair-preparation-input=b"),
    ],
)
def test_preparation_rejects_ambiguous_private_invocation(
    arguments: tuple[str, ...],
) -> None:
    """Keep a malformed private operation from falling through into interactive startup."""
    with pytest.raises(ValueError, match="exactly one"):
        run_repair_preparation_invocation(arguments)


@pytest.mark.platforms("windows")
def test_native_preparation_failure_cleans_up_without_opening_ui(
    tmp_path: Path,
) -> None:
    """Run the real bootstrap and native family owner against only a missing fixture."""
    supervisor = RepairProcessSupervisor(
        command_builder=lambda: (
            sys.executable,
            "-m",
            "launcher.sugarsubstitute_launcher",
            f"--repair-preparation-input={tmp_path / 'missing.json'}",
        ),
        startup_log_path=tmp_path / "worker.log",
    )
    progress: list[dict[str, object]] = []
    output: list[str] = []
    with pytest.raises(RepairProcessError, match="missing.json"):
        supervisor.run(progress_observer=progress.append, output_callback=output.append)
    assert supervisor.safe_to_close
    assert progress == []
    assert not (tmp_path / "missing.json").exists()
