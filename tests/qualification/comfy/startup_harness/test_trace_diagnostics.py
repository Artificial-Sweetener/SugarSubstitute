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

"""Test startup trace and diagnostic event correlation."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from typing import cast
from tools import startup_harness


def test_copy_app_startup_trace_delta_writes_only_new_bytes(tmp_path: Path) -> None:
    """Trace capture should isolate the current harness cycle."""

    source = tmp_path / "startup-trace.jsonl"
    source.write_bytes(b"old\nnew\n")
    destination = tmp_path / "cycle-trace.jsonl"

    copied = startup_harness.copy_app_startup_trace_delta(
        trace_path=source,
        offset=len("old\n".encode("utf-8")),
        destination=destination,
    )

    assert copied == destination
    assert destination.read_text(encoding="utf-8") == "new\n"


def test_parse_startup_trace_measurements_summarizes_key_events() -> None:
    """Trace summaries should identify app, shell, and backend readiness gates."""

    trace_text = "\n".join(
        [
            (
                '{"event":"startup.trace.ready","fields":{},"kind":"mark",'
                '"sequence":1,"timestamp_ns":1000000000}'
            ),
            (
                '{"event":"activate_target_task.end","fields":{},'
                '"kind":"mark","sequence":2,"timestamp_ns":1100000000}'
            ),
            (
                '{"elapsed_ns":75000000,"event":"startup.import_runtime_modules",'
                '"fields":{},"kind":"span","sequence":3,'
                '"timestamp_ns":1250000000}'
            ),
            (
                '{"elapsed_ns":8000000,"event":"startup.create_application",'
                '"fields":{},"kind":"span","sequence":4,'
                '"timestamp_ns":1260000000}'
            ),
            (
                '{"elapsed_ns":46000000,"event":"startup.build_appearance_runtime",'
                '"fields":{},"kind":"span","sequence":5,'
                '"timestamp_ns":1310000000}'
            ),
            (
                '{"elapsed_ns":413000000,"event":"startup.configure_theme",'
                '"fields":{},"kind":"span","sequence":6,'
                '"timestamp_ns":1730000000}'
            ),
            (
                '{"elapsed_ns":250000000,"event":"build_shell_task.build_main_window",'
                '"fields":{},"kind":"span","sequence":7,'
                '"timestamp_ns":1500000000}'
            ),
            (
                '{"elapsed_ns":175000000,"event":"canvas_host.create.input_canvas",'
                '"fields":{},"kind":"span","sequence":8,'
                '"timestamp_ns":1520000000}'
            ),
            (
                '{"event":"composition.dependencies.phase",'
                '"fields":{"phase":"imports","elapsed_ms":123.456},'
                '"kind":"mark","sequence":9,"timestamp_ns":1530000000}'
            ),
            (
                '{"elapsed_ns":120000000,"event":"managed_comfy.ensure_setup",'
                '"fields":{},"kind":"span","sequence":10,'
                '"timestamp_ns":1550000000}'
            ),
            (
                '{"event":"managed_comfy.process_launched","fields":{},'
                '"kind":"mark","sequence":11,"timestamp_ns":1580000000}'
            ),
            (
                '{"event":"input_canvas.qpane_features",'
                '"fields":{"features":"mask","reason":"startup_harness_defer_sam"},'
                '"kind":"mark","sequence":12,"timestamp_ns":1560000000}'
            ),
            (
                '{"event":"readiness_timer.tick","fields":{},'
                '"kind":"mark","sequence":13,"timestamp_ns":1600000000}'
            ),
            (
                '{"event":"readiness_probe.in_flight_skip","fields":{},'
                '"kind":"mark","sequence":14,"timestamp_ns":1700000000}'
            ),
            (
                '{"event":"readiness_timer.http_not_ready","fields":{},'
                '"kind":"mark","sequence":15,"timestamp_ns":1800000000}'
            ),
            (
                '{"event":"readiness_timer.http_ready","fields":{},'
                '"kind":"mark","sequence":16,"timestamp_ns":2100000000}'
            ),
            (
                '{"event":"startup.pretrace.phase",'
                '"fields":{"source":"entrypoint","phase":"entrypoint.import_startup",'
                '"elapsed_ms":42.125},"kind":"mark","sequence":17,'
                '"timestamp_ns":2200000000}'
            ),
        ]
    )

    measurements = startup_harness.parse_startup_trace_measurements(trace_text)
    first_event_ms = cast(dict[str, float], measurements["firstEventMs"])
    first_event_timestamps = cast(
        dict[str, int],
        measurements["firstEventTimestampNs"],
    )
    span_elapsed_ms = cast(dict[str, float], measurements["spanElapsedMs"])

    assert measurements["eventCount"] == 17
    assert first_event_ms["activate_target_task.end"] == 100.0
    assert first_event_ms["managed_comfy.process_launched"] == 580.0
    assert first_event_ms["readiness_timer.http_ready"] == 1100.0
    assert first_event_timestamps["startup.trace.ready"] == 1000000000
    assert first_event_timestamps["managed_comfy.process_launched"] == 1580000000
    assert first_event_timestamps["readiness_timer.http_ready"] == 2100000000
    assert span_elapsed_ms["startup.import_runtime_modules"] == 75.0
    assert span_elapsed_ms["startup.create_application"] == 8.0
    assert span_elapsed_ms["startup.build_appearance_runtime"] == 46.0
    assert span_elapsed_ms["startup.configure_theme"] == 413.0
    assert span_elapsed_ms["build_shell_task.build_main_window"] == 250.0
    assert span_elapsed_ms["canvas_host.create.input_canvas"] == 175.0
    assert span_elapsed_ms["managed_comfy.ensure_setup"] == 120.0
    assert measurements["readinessAttempts"] == 1
    assert measurements["readinessInFlightSkips"] == 1
    assert measurements["httpNotReadyCount"] == 1
    assert measurements["dependencyPhaseElapsedMs"] == {"imports": 123.456}
    assert measurements["inputCanvasQPaneFeatures"] == [
        {"features": "mask", "reason": "startup_harness_defer_sam"}
    ]
    assert measurements["preTracePhaseElapsedMs"] == {
        "entrypoint:entrypoint.import_startup": 42.125,
    }


def test_add_managed_timeline_trace_correlation_records_monotonic_deltas() -> None:
    """Timeline and startup trace summaries should expose same-clock deltas."""

    timeline_measurements: dict[str, object] = {
        "firstOutputTimestampNs": 900_000_000,
        "firstMilestoneTimestampNs": {
            "managed_model_root_applied": 900_000_000,
            "prestartup_times": 925_000_000,
            "starting_server": 1_000_000_000,
            "gui_url_printed": 1_010_000_000,
        },
    }
    trace_measurements: dict[str, object] = {
        "firstEventTimestampNs": {
            "managed_comfy.process_launched": 875_000_000,
            "readiness_timer.http_ready": 1_125_000_000,
            "managed_comfy.wait_ready.result": 1_750_000_000,
        },
    }

    startup_harness.add_managed_timeline_trace_correlation(
        timeline_measurements=timeline_measurements,
        trace_measurements=trace_measurements,
    )

    assert timeline_measurements["startupTraceDeltaMs"] == {
        "process_launched_to_managed_model_root": 25.0,
        "process_launched_to_prestartup": 50.0,
        "process_launched_to_gui_url": 135.0,
        "starting_server_to_http_ready": 125.0,
        "gui_url_printed_to_http_ready": 115.0,
        "starting_server_to_managed_wait_result": 750.0,
        "gui_url_printed_to_managed_wait_result": 740.0,
    }


def test_parse_diagnostic_events_reads_backend_startup_records() -> None:
    """Backend startup diagnostics should become structured harness records."""

    output = """
\x1b[32m[INFO]\x1b[0m Substitute startup diagnostic event=substitute_startup_timing operation=backend_services total_duration_ms=71.455 cube_library=0.224 prompt_queue=0.044
\x1b[32m[INFO]\x1b[0m SugarCubes cube library diagnostic event=sugarcubes_library_readiness_timing dependency_requirement_sets=68.612 git_contains_check_count=0 include_internal_payload=False slow_entries=[] ready=true
"""

    assert startup_harness.parse_diagnostic_events(output) == (
        {
            "source": "Substitute",
            "channel": "startup",
            "event": "substitute_startup_timing",
            "fields": {
                "operation": "backend_services",
                "total_duration_ms": 71.455,
                "cube_library": 0.224,
                "prompt_queue": 0.044,
            },
        },
        {
            "source": "SugarCubes",
            "channel": "cube_library",
            "event": "sugarcubes_library_readiness_timing",
            "fields": {
                "dependency_requirement_sets": 68.612,
                "git_contains_check_count": 0,
                "include_internal_payload": False,
                "slow_entries": [],
                "ready": True,
            },
        },
    )
