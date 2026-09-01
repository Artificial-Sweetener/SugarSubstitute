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

"""Verify process-wide Python crash capture behavior."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from sugarsubstitute_shared.crash_reporting import (
    CrashBoundary,
    CrashIncidentStore,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    CRASH_RUN_TOKEN_ENV,
    CleanExitOutcome,
    CrashRunContext,
)
from sugarsubstitute_shared.crash_reporting.runtime import ProcessCrashRuntime


def _runtime(
    tmp_path: Path,
    *,
    terminate: list[int] | None = None,
) -> ProcessCrashRuntime:
    """Return an isolated runtime with a non-destructive terminator."""

    context = CrashRunContext.create(tmp_path / "diagnostics")
    return ProcessCrashRuntime(
        context=context,
        application_version="0.22.0",
        launch_arguments=("main.py", f"--install-root={tmp_path}", "--api-key=secret"),
        install_root=tmp_path,
        terminate=(terminate if terminate is not None else []).append,
    )


def test_runtime_installs_all_python_hooks_and_clears_child_secret(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Supervised startup should own every interpreter-level crash boundary."""

    del monkeypatch
    runtime = _runtime(tmp_path)
    environment = runtime.context.environment({})
    runtime.context.clear_secret_environment(environment)

    assert CRASH_RUN_TOKEN_ENV not in environment


def test_main_exception_records_copyable_redacted_incident(tmp_path: Path) -> None:
    """An uncaught main-thread error should become durable before process exit."""

    runtime = _runtime(tmp_path)
    try:
        raise RuntimeError(f"failed below {tmp_path} with password=hunter2")
    except RuntimeError as error:
        runtime.record_python_exception(
            error,
            kind=CrashKind.PYTHON_UNHANDLED,
            boundary=CrashBoundary.PROCESS_MAIN,
            thread_name="MainThread",
        )

    incident = CrashIncidentStore(runtime.context.incident_root).pending()[0]
    serialized = json.dumps(incident.to_json())
    assert str(tmp_path) not in serialized
    assert "hunter2" not in serialized
    assert "secret" not in serialized
    assert incident.kind is CrashKind.PYTHON_UNHANDLED
    assert "<install-root>" in serialized


def test_qt_exception_records_incident_before_fatal_termination(tmp_path: Path) -> None:
    """Qt dispatch failures should be durable before the process is terminated."""

    exit_codes: list[int] = []
    runtime = _runtime(tmp_path, terminate=exit_codes)

    runtime.record_qt_exception(ValueError("event failed"))

    assert exit_codes == [70]
    incident = CrashIncidentStore(runtime.context.incident_root).pending()[0]
    assert incident.exception_type == "ValueError"
    assert incident.boundary.value == "qt_event"


def test_execution_escape_records_incident_before_fatal_termination(
    tmp_path: Path,
) -> None:
    """A job escaping its lifecycle must never terminate at logging alone."""

    exit_codes: list[int] = []
    runtime = _runtime(tmp_path, terminate=exit_codes)

    runtime.record_execution_exception(RuntimeError("job boundary failed"))

    assert exit_codes == [70]
    incident = CrashIncidentStore(runtime.context.incident_root).pending()[0]
    assert incident.exception_type == "RuntimeError"
    assert incident.kind is CrashKind.PYTHON_UNHANDLED
    assert incident.boundary is CrashBoundary.EXECUTION_JOB


def test_clean_receipt_is_withheld_until_final_completion(tmp_path: Path) -> None:
    """Declaring intent alone must not let the supervisor accept a clean exit."""

    runtime = _runtime(tmp_path)

    runtime.request_clean_exit(CleanExitOutcome.CLOSED)

    assert runtime.context.validates_clean_exit(process_id=os.getpid()) is False
    runtime._complete_clean_exit()
    assert runtime.context.validates_clean_exit(process_id=os.getpid()) is True


def test_runtime_does_not_replace_interpreter_hooks_before_install(
    tmp_path: Path,
) -> None:
    """Runtime construction should remain side-effect free for composition tests."""

    original = sys.excepthook

    _runtime(tmp_path)

    assert sys.excepthook is original
