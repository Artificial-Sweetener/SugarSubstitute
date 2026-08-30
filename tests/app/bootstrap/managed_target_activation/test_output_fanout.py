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

"""Qualify managed Comfy output fan-out and diagnostics ownership."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest


from substitute.app.bootstrap import managed_target_activation
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)

from tests.app.bootstrap.managed_target_activation.support import (
    Diagnostics as _Diagnostics,
    DisposedSplash as _DisposedSplash,
    DisposedStream as _DisposedStream,
    FailingDiagnostics as _FailingDiagnostics,
    Splash as _Splash,
    Stream as _Stream,
)


def test_fan_out_splash_and_shell_output_routes_one_line_to_both_targets() -> None:
    """Managed startup output should reach both the splash and shell stream sinks."""

    splash_lines: list[str] = []
    stream_lines: list[str] = []
    fake_splash = type(
        "_Splash",
        (),
        {"append_log": lambda self, line: splash_lines.append(line)},
    )()
    fake_stream = type(
        "_Stream",
        (),
        {"append_line": lambda self, line: stream_lines.append(line)},
    )()

    managed_target_activation.fan_out_splash_and_shell_output(
        splash=fake_splash,
        comfy_output_stream=fake_stream,
        line="Launching ComfyUI.",
    )

    assert splash_lines == ["Launching ComfyUI."]
    assert stream_lines == ["Launching ComfyUI."]


def test_collect_and_fan_out_output_survives_classification_failure() -> None:
    """Output routing should still reach visible sinks if diagnostics fail."""

    splash = _Splash()
    stream = _Stream()

    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(
            ComfyStartupDiagnosticsCollector, _FailingDiagnostics()
        ),
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        line="backend output",
    )

    assert splash.lines == ["backend output"]
    assert stream.lines == ["backend output"]


def test_collect_and_fan_out_output_mirrors_harness_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness diagnostics should persist managed Comfy output without UI access."""

    mirror_path = tmp_path / "diagnostics" / "managed-comfy.log"
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG",
        str(mirror_path),
    )
    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        splash=None,
        comfy_output_stream=_Stream(),
        line="SugarCubes cube library diagnostic event=example ready=True",
    )

    assert (
        mirror_path.read_text(encoding="utf-8")
        == "SugarCubes cube library diagnostic event=example ready=True\n"
    )


def test_collect_and_fan_out_output_mirrors_harness_timeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness timeline diagnostics should timestamp managed Comfy output."""

    timeline_path = tmp_path / "diagnostics" / "managed-comfy-timeline.jsonl"
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_TIMELINE",
        str(timeline_path),
    )

    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        splash=None,
        comfy_output_stream=_Stream(),
        line="Starting server",
    )

    records = [
        json.loads(line)
        for line in timeline_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records == [
        {
            "event": "managed_comfy_output",
            "monotonicNs": records[0]["monotonicNs"],
            "elapsedMs": records[0]["elapsedMs"],
            "line": "Starting server",
        }
    ]
    assert isinstance(records[0]["monotonicNs"], int)
    assert isinstance(records[0]["elapsedMs"], float)


def test_collect_and_fan_out_output_records_harness_fanout_timing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness fanout timing should be mirrored at managed startup markers."""

    log_path = tmp_path / "diagnostics" / "managed-comfy.log"
    timeline_path = tmp_path / "diagnostics" / "managed-comfy-timeline.jsonl"
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG",
        str(log_path),
    )
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_TIMELINE",
        str(timeline_path),
    )
    monkeypatch.setattr(managed_target_activation, "_harness_fanout_record_count", 0)
    monkeypatch.setattr(managed_target_activation, "_harness_fanout_total_ms", 0.0)
    monkeypatch.setattr(managed_target_activation, "_harness_fanout_max_ms", 0.0)
    stream = _Stream()

    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        splash=None,
        comfy_output_stream=stream,
        line="Starting server",
    )

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines[0] == "Starting server"
    assert log_lines[1].startswith(
        "Substitute startup diagnostic event=managed_output_fanout_timing "
    )
    assert "record_count=1" in log_lines[1]
    assert "marker=starting_server" in log_lines[1]
    assert stream.lines == ["Starting server"]

    timeline_lines = timeline_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in timeline_lines]
    assert [record["line"] for record in records] == [log_lines[0], log_lines[1]]


def test_fan_out_splash_and_shell_output_tolerates_disposed_splash() -> None:
    """Disposed splash widgets should not block shell output history."""

    stream = _Stream()

    managed_target_activation.fan_out_splash_and_shell_output(
        splash=cast(Any, _DisposedSplash()),
        comfy_output_stream=stream,
        line="late output",
    )

    assert stream.lines == ["late output"]


def test_fan_out_splash_and_shell_output_tolerates_disposed_shell_stream() -> None:
    """Disposed shell output streams should not break managed output fan-out."""

    splash = _Splash()

    managed_target_activation.fan_out_splash_and_shell_output(
        splash=cast(Any, splash),
        comfy_output_stream=_DisposedStream(),
        line="late output",
    )

    assert splash.lines == ["late output"]


def test_managed_startup_fatal_incident_reads_state_result() -> None:
    """Managed fatal incident lookup should read the process startup result."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="ComfyUI failed to start",
        message="Process exited.",
        fingerprint="fatal-a",
    )
    state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(Path("E:/state"))
    )
    state.startup_result = ManagedStartupReadinessResult(
        ready=False,
        fatal_incident=incident,
    )

    assert managed_target_activation.managed_startup_fatal_incident(state) is incident
    assert managed_target_activation.managed_startup_fatal_incident(None) is None
    assert managed_target_activation.managed_startup_fatal_incident(object()) is None
