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

"""Tests for the startup measurement harness."""

from __future__ import annotations

import sys
import time as time_module
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Mapping, cast

import pytest

from tools import startup_harness


def test_parse_comfy_import_times_reads_custom_node_block() -> None:
    """Comfy import timing output should become structured harness data."""

    output = """
Import times for custom nodes:
   0.2 seconds: E:\\ComfyUI\\custom_nodes\\sugarcubes
   1.4 seconds (IMPORT FAILED): E:\\ComfyUI\\custom_nodes\\broken

Other output
"""

    assert startup_harness.parse_comfy_import_times(output) == (
        {
            "seconds": 0.2,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\sugarcubes",
        },
        {
            "seconds": 1.4,
            "status": "failed",
            "modulePath": r"E:\ComfyUI\custom_nodes\broken",
        },
    )


def test_parse_comfy_import_times_ignores_comfy_ansi_info_prefix() -> None:
    """ANSI-colored Comfy log prefixes should not hide import timing records."""

    output = """
Import times for custom nodes:
\x1b[32m[INFO]\x1b[0m    0.1 seconds: E:\\ComfyUI\\custom_nodes\\SugarCubes
\x1b[32m[INFO]\x1b[0m    0.2 seconds (IMPORT FAILED): E:\\ComfyUI\\custom_nodes\\broken
"""

    assert startup_harness.parse_comfy_import_times(output) == (
        {
            "seconds": 0.1,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\SugarCubes",
        },
        {
            "seconds": 0.2,
            "status": "failed",
            "modulePath": r"E:\ComfyUI\custom_nodes\broken",
        },
    )


def test_parse_comfy_prestartup_times_reads_custom_node_block() -> None:
    """Comfy prestartup timing output should become structured harness data."""

    output = """
Prestartup times for custom nodes:
\x1b[32m[INFO]\x1b[0m    0.0 seconds: E:\\ComfyUI\\custom_nodes\\SubstituteManagedModelRoot
\x1b[32m[INFO]\x1b[0m    2.9 seconds: E:\\ComfyUI\\custom_nodes\\ComfyUI-Manager
\x1b[32m[INFO]\x1b[0m    0.4 seconds (PRESTARTUP FAILED): E:\\ComfyUI\\custom_nodes\\broken
"""

    assert startup_harness.parse_comfy_prestartup_times(output) == (
        {
            "seconds": 0.0,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\SubstituteManagedModelRoot",
        },
        {
            "seconds": 2.9,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\ComfyUI-Manager",
        },
        {
            "seconds": 0.4,
            "status": "failed",
            "modulePath": r"E:\ComfyUI\custom_nodes\broken",
        },
    )


def test_command_run_payload_includes_termination_kind(tmp_path: Path) -> None:
    """Long-lived process summaries should distinguish harness kills from exits."""

    result = startup_harness.CommandRunResult(
        name="direct-comfy",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12.3,
        output_path=tmp_path / "direct-comfy.log",
        route_measurements=(),
        parsed_import_times=(),
    )

    assert result.to_payload()["terminationKind"] == "killed_after_ready"


def test_command_run_payload_includes_raw_ready_elapsed_ms(tmp_path: Path) -> None:
    """Process summaries should expose readiness before settle and route probes."""

    result = startup_harness.CommandRunResult(
        name="direct-comfy",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12000.0,
        output_path=tmp_path / "direct-comfy.log",
        route_measurements=(),
        parsed_import_times=(),
        ready_elapsed_ms=8500.25,
    )

    payload = result.to_payload()

    assert payload["elapsedMs"] == 12000.0
    assert payload["readyElapsedMs"] == 8500.25


def test_command_run_payload_includes_startup_trace_measurements(
    tmp_path: Path,
) -> None:
    """App-managed summaries should expose parsed startup trace timings."""

    result = startup_harness.CommandRunResult(
        name="app-managed",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12.3,
        output_path=tmp_path / "app-managed.log",
        route_measurements=(),
        parsed_import_times=(),
        diagnostic_artifacts=(
            {"name": "startup_trace", "path": str(tmp_path / "trace.jsonl")},
        ),
        startup_trace_measurements={"eventCount": 2},
    )

    payload = result.to_payload()

    assert payload["diagnosticArtifacts"] == [
        {"name": "startup_trace", "path": str(tmp_path / "trace.jsonl")}
    ]
    assert payload["startupTraceMeasurements"] == {"eventCount": 2}


def test_command_run_payload_includes_managed_comfy_timeline_measurements(
    tmp_path: Path,
) -> None:
    """App-managed summaries should expose parsed child-output timeline timings."""

    result = startup_harness.CommandRunResult(
        name="app-managed",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12.3,
        output_path=tmp_path / "app-managed.log",
        route_measurements=(),
        parsed_import_times=(),
        managed_comfy_timeline_measurements={"eventCount": 3},
    )

    assert result.to_payload()["managedComfyTimelineMeasurements"] == {"eventCount": 3}


def test_command_run_payload_includes_comfy_output_timeline_measurements(
    tmp_path: Path,
) -> None:
    """Direct Comfy summaries should expose parsed timestamped output timings."""

    result = startup_harness.CommandRunResult(
        name="direct-comfy",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12.3,
        output_path=tmp_path / "direct-comfy.log",
        route_measurements=(),
        parsed_import_times=(),
        comfy_output_timeline_measurements={
            "firstMilestoneMs": {"gui_url_printed": 10.0}
        },
    )

    payload = result.to_payload()

    assert payload["comfyOutputTimelineMeasurements"] == {
        "firstMilestoneMs": {"gui_url_printed": 10.0}
    }
    assert payload["ownedStartupMeasurements"] == {
        "comfyOutputMilestoneMs": {"gui_url_printed": 10.0}
    }


def test_command_run_payload_includes_diagnostic_events(tmp_path: Path) -> None:
    """Process summaries should expose parsed backend diagnostic events."""

    event: dict[str, object] = {
        "source": "SugarCubes",
        "channel": "cube_library",
        "event": "sugarcubes_library_readiness_timing",
        "fields": {"dependency_requirement_sets": 68.612},
    }
    result = startup_harness.CommandRunResult(
        name="direct-comfy",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12.3,
        output_path=tmp_path / "direct-comfy.log",
        route_measurements=(),
        parsed_import_times=(),
        diagnostic_events=(event,),
    )

    assert result.to_payload()["diagnosticEvents"] == [event]


def test_command_run_payload_includes_owned_startup_measurements(
    tmp_path: Path,
) -> None:
    """Process summaries should include compact owned startup timing highlights."""

    result = startup_harness.CommandRunResult(
        name="app-managed",
        command=("python", "main.py"),
        cwd=tmp_path,
        exit_code=1,
        termination_kind="killed_after_ready",
        timed_out=False,
        ready=True,
        elapsed_ms=12000.0,
        output_path=tmp_path / "app-managed.log",
        route_measurements=({"name": "substitute_capabilities", "elapsedMs": 8.0},),
        parsed_import_times=(
            {
                "seconds": 0.1,
                "status": "ok",
                "modulePath": r"E:\ComfyUI\custom_nodes\Substitute-BackEnd",
            },
            {
                "seconds": 0.0,
                "status": "ok",
                "modulePath": r"E:\ComfyUI\custom_nodes\SugarCubes",
            },
        ),
        parsed_prestartup_times=(
            {
                "seconds": 0.0,
                "status": "ok",
                "modulePath": r"E:\ComfyUI\custom_nodes\SubstituteManagedModelRoot",
            },
            {
                "seconds": 2.9,
                "status": "ok",
                "modulePath": r"E:\ComfyUI\custom_nodes\ComfyUI-Manager",
            },
        ),
        diagnostic_events=(
            {
                "event": "substitute_startup_timing",
                "fields": {
                    "operation": "backend_services",
                    "total_duration_ms": 28.7,
                },
            },
            {
                "event": "substitute_capabilities_timing",
                "fields": {"total_duration_ms": 8.6},
            },
            {
                "event": "managed_output_fanout_timing",
                "fields": {
                    "record_count": 10,
                    "total_fanout_ms": 73.2,
                    "max_fanout_ms": 65.0,
                    "last_fanout_ms": 0.8,
                    "marker": "prestartup_times",
                },
            },
            {
                "event": "managed_output_fanout_timing",
                "fields": {
                    "record_count": 250,
                    "total_fanout_ms": 301.4,
                    "max_fanout_ms": 65.0,
                    "last_fanout_ms": 0.2,
                    "marker": "gui_url",
                },
            },
            {
                "event": "sugarcubes_dependency_requirement_sets_timing",
                "fields": {
                    "total_duration_ms": 12.3,
                    "cached": True,
                    "source_signature_build": 12.0,
                },
            },
            {
                "event": "sugarcubes_installed_dependency_inventory_timing",
                "fields": {
                    "total_duration_ms": 29.7,
                    "read_git_status": 22.7,
                },
            },
            {
                "event": "sugarcubes_library_readiness_cache_hit",
                "fields": {"total_duration_ms": 4.2},
            },
        ),
        startup_trace_measurements={
            "spanElapsedMs": {
                "composition.dependencies": 243.174,
                "managed_comfy.wait_ready": 17389.429,
            }
        },
        managed_comfy_timeline_measurements={
            "firstMilestoneMs": {
                "launching_comfy": 100.0,
                "prestartup_times": 3500.0,
                "manager_fetch_registry": 16397.5,
                "gui_url_printed": 17162.852,
            }
        },
    )

    assert result.to_payload()["ownedStartupMeasurements"] == {
        "routeElapsedMs": {"substitute_capabilities": 8.0},
        "ownedCustomNodeImportSeconds": {
            "substituteBackend": 0.1,
            "sugarcubes": 0.0,
        },
        "prestartup": {
            "ownedSeconds": {
                "managedModelRoot": 0.0,
            },
            "slowest": (
                {
                    "seconds": 2.9,
                    "status": "ok",
                    "modulePath": r"E:\ComfyUI\custom_nodes\ComfyUI-Manager",
                },
                {
                    "seconds": 0.0,
                    "status": "ok",
                    "modulePath": (
                        r"E:\ComfyUI\custom_nodes\SubstituteManagedModelRoot"
                    ),
                },
            ),
        },
        "substituteBackend": {
            "backendServicesMs": 28.7,
            "capabilitiesMs": (8.6,),
        },
        "managedOutputFanout": {
            "recordCount": 250,
            "totalFanoutMs": 301.4,
            "maxFanoutMs": 65.0,
            "markerLastFanoutMs": {
                "prestartup_times": 0.8,
                "gui_url": 0.2,
            },
        },
        "sugarcubes": {
            "dependencyRequirementSetsMs": 12.3,
            "dependencyRequirementSetsCached": True,
            "dependencySourceSignatureMs": 12.0,
            "installedDependencyInventoryMs": 29.7,
            "installedInventoryReadGitStatusMs": 22.7,
            "libraryReadinessCacheHitMs": (4.2,),
        },
        "appSpanElapsedMs": {
            "composition.dependencies": 243.174,
            "managed_comfy.wait_ready": 17389.429,
        },
        "managedComfyMilestoneMs": {
            "launching_comfy": 100.0,
            "prestartup_times": 3500.0,
            "manager_fetch_registry": 16397.5,
            "gui_url_printed": 17162.852,
        },
        "managedComfyPhaseMs": {
            "launchToPrestartupMs": 3400.0,
            "launchToGuiUrlMs": 17062.852,
            "prestartupToManagerFetchMs": 12897.5,
            "prestartupToGuiUrlMs": 13662.852,
            "managerFetchToGuiUrlMs": 765.352,
        },
    }


def test_app_managed_environment_overrides_can_defer_input_sam() -> None:
    """App-managed diagnostics should opt into no-eager-SAM only when requested."""

    default_overrides = startup_harness.app_managed_environment_overrides(False)
    defer_overrides = startup_harness.app_managed_environment_overrides(True)
    output_overrides = startup_harness.app_managed_environment_overrides(
        False,
        managed_comfy_output_path=Path("managed-comfy.log"),
        managed_comfy_output_timeline_path=Path("managed-comfy-timeline.jsonl"),
    )

    assert default_overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS"] == "1"
    assert default_overrides["SUBSTITUTE_BACKEND_DIAGNOSTICS"] == "cube-library,startup"
    assert "SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM" not in default_overrides
    assert defer_overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM"] == "1"
    assert (
        output_overrides[startup_harness.APP_MANAGED_COMFY_OUTPUT_LOG_ENV]
        == "managed-comfy.log"
    )
    assert (
        output_overrides[startup_harness.APP_MANAGED_COMFY_OUTPUT_TIMELINE_ENV]
        == "managed-comfy-timeline.jsonl"
    )


def test_direct_comfy_environment_overrides_need_no_desktop_model_root(
    tmp_path: Path,
) -> None:
    """BackEnd prestartup owns model roots without harness environment state."""

    comfy_root = tmp_path / "ComfyUI"
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    overrides = startup_harness.direct_comfy_environment_overrides(paths)

    assert "SUGARSUB_MANAGED_MODEL_ROOT" not in overrides
    assert overrides["PATH"].startswith(str(paths.comfy_python.parent))
    assert overrides["PYTHONIOENCODING"] == "utf-8"
    assert overrides["QT_QPA_PLATFORM"] == "offscreen"
    assert overrides["SUBSTITUTE_BACKEND_DIAGNOSTICS"] == "cube-library,startup"
    assert overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS"] == "1"
    assert overrides["SUGARCUBES_DIAGNOSTICS"] == "1"


def test_harness_resolves_installed_sugarsubstitute_layout(tmp_path: Path) -> None:
    """App-managed measurements should run against a packaged installation."""

    install_root = tmp_path / "SugarSubstitute"
    installed_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    installed_main = install_root / "app" / "main.py"
    installed_python.parent.mkdir(parents=True)
    installed_python.write_text("", encoding="utf-8")
    installed_main.parent.mkdir(parents=True)
    installed_main.write_text("", encoding="utf-8")
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=install_root,
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert paths.sugar_substitute_python == installed_python
    assert paths.sugar_substitute_main == installed_main
    assert startup_harness.build_app_managed_command(paths) == (
        str(installed_python),
        str(installed_main),
        f"--install-root={install_root}",
    )


def test_run_app_managed_cycle_parses_managed_comfy_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """App-managed summaries should include mirrored child Comfy diagnostics."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    def fake_run_server_process(**kwargs: object) -> startup_harness.CommandRunResult:
        """Write managed child output to the harness-requested mirror path."""

        env = cast(Mapping[str, str], kwargs["env"])
        Path(env[startup_harness.APP_MANAGED_COMFY_OUTPUT_LOG_ENV]).write_text(
            (
                "SugarCubes cube library diagnostic "
                "event=sugarcubes_library_readiness_timing ready=True\n"
            ),
            encoding="utf-8",
        )
        Path(env[startup_harness.APP_MANAGED_COMFY_OUTPUT_TIMELINE_ENV]).write_text(
            (
                '{"event":"managed_comfy_output","monotonicNs":1,'
                '"elapsedMs":1.0,"line":"Starting server"}\n'
            ),
            encoding="utf-8",
        )
        return startup_harness.CommandRunResult(
            name="app-managed",
            command=("python", "main.py"),
            cwd=paths.sugar_substitute_root,
            exit_code=1,
            termination_kind="killed_after_ready",
            timed_out=False,
            ready=True,
            elapsed_ms=1.0,
            output_path=tmp_path / "app-managed.log",
            route_measurements=(),
            parsed_import_times=(),
        )

    monkeypatch.setattr(
        startup_harness,
        "http_endpoint_is_reachable",
        lambda *_, **__: False,
    )
    monkeypatch.setattr(startup_harness, "_run_server_process", fake_run_server_process)

    result = startup_harness.run_app_managed_cycle(
        paths=paths,
        cycle_dir=tmp_path,
        host="127.0.0.1",
        port=8188,
        ready_timeout_seconds=1.0,
        settle_seconds=0.0,
        log=lambda _message: None,
    )

    assert result.diagnostic_events == (
        {
            "source": "SugarCubes",
            "channel": "cube_library",
            "event": "sugarcubes_library_readiness_timing",
            "fields": {"ready": True},
        },
    )
    assert result.diagnostic_artifacts == (
        {
            "name": "managed_comfy_output",
            "path": str(tmp_path / "app-managed-comfy-output.log"),
        },
        {
            "name": "managed_comfy_output_timeline",
            "path": str(tmp_path / "app-managed-comfy-output-timeline.jsonl"),
        },
    )
    assert result.managed_comfy_timeline_measurements == {
        "eventCount": 1,
        "firstOutputMs": 1.0,
        "firstOutputTimestampNs": 1,
        "lastOutputMs": 1.0,
        "firstMilestoneMs": {"starting_server": 1.0},
        "firstMilestoneTimestampNs": {"starting_server": 1},
        "milestoneLines": {"starting_server": "Starting server"},
        "largestOutputGaps": (),
        "largestChildOutputGaps": (),
    }


def test_parse_managed_comfy_output_timeline_summarizes_milestones() -> None:
    """Managed Comfy output timeline should expose repeatable startup milestones."""

    timeline = "\n".join(
        [
            (
                '{"event":"managed_comfy_output","monotonicNs":10,'
                '"elapsedMs":100.0,"line":"Launching ComfyUI."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":15,'
                '"elapsedMs":150.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'Substitute BackEnd configured ComfyUI model root: E:\\\\ImageGen Models"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":20,'
                '"elapsedMs":350.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                '[ComfyUI-Manager] network_mode: public"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":30,'
                '"elapsedMs":1000.0,"line":"FETCH ComfyRegistry Data: 5/159"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":40,'
                '"elapsedMs":1250.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'Starting server"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":50,'
                '"elapsedMs":1300.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'To see the GUI go to: http://127.0.0.1:8188"}'
            ),
        ]
    )

    measurements = startup_harness.parse_managed_comfy_output_timeline(timeline)

    assert measurements["eventCount"] == 6
    assert measurements["firstOutputMs"] == 100.0
    assert measurements["firstOutputTimestampNs"] == 10
    assert measurements["lastOutputMs"] == 1300.0
    assert measurements["firstMilestoneMs"] == {
        "launching_comfy": 100.0,
        "managed_model_root_applied": 150.0,
        "manager_network_mode": 350.0,
        "manager_fetch_registry": 1000.0,
        "starting_server": 1250.0,
        "gui_url_printed": 1300.0,
    }
    assert measurements["firstMilestoneTimestampNs"] == {
        "launching_comfy": 10,
        "managed_model_root_applied": 15,
        "manager_network_mode": 20,
        "manager_fetch_registry": 30,
        "starting_server": 40,
        "gui_url_printed": 50,
    }
    assert measurements["milestoneLines"] == {
        "launching_comfy": "Launching ComfyUI.",
        "managed_model_root_applied": (
            "Substitute BackEnd configured ComfyUI model root: E:\\ImageGen Models"
        ),
        "manager_network_mode": "[ComfyUI-Manager] network_mode: public",
        "manager_fetch_registry": "FETCH ComfyRegistry Data: 5/159",
        "starting_server": "Starting server",
        "gui_url_printed": "To see the GUI go to: http://127.0.0.1:8188",
    }
    largest_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestOutputGaps"],
    )
    largest_child_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestChildOutputGaps"],
    )
    assert largest_output_gaps[0] == {
        "gapMs": 650.0,
        "fromMs": 350.0,
        "toMs": 1000.0,
        "fromLine": "[ComfyUI-Manager] network_mode: public",
        "toLine": "FETCH ComfyRegistry Data: 5/159",
    }
    assert largest_child_output_gaps[0] == largest_output_gaps[0]


def test_parse_managed_comfy_output_timeline_reports_child_only_gaps() -> None:
    """Managed parent readiness messages should not hide child output gaps."""

    timeline = "\n".join(
        [
            (
                '{"event":"managed_comfy_output","monotonicNs":10,'
                '"elapsedMs":100.0,"line":"Launching ComfyUI."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":20,'
                '"elapsedMs":1100.0,"line":"Waiting for ComfyUI to become ready..."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":30,'
                '"elapsedMs":1200.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'Substitute BackEnd configured ComfyUI model root: E:\\\\ImageGen Models"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":40,'
                '"elapsedMs":1800.0,"line":"Waiting for ComfyUI to become ready..."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":50,'
                '"elapsedMs":1900.0,"line":"Found comfy_kitchen backend cuda"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":60,'
                '"elapsedMs":2500.0,"line":"ComfyUI-GGUF: Allowing full torch compile"}'
            ),
        ]
    )

    measurements = startup_harness.parse_managed_comfy_output_timeline(timeline)
    largest_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestOutputGaps"],
    )
    largest_child_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestChildOutputGaps"],
    )

    assert largest_output_gaps[0]["toLine"] == "Waiting for ComfyUI to become ready..."
    assert largest_child_output_gaps[0] == {
        "gapMs": 700.0,
        "fromMs": 1200.0,
        "toMs": 1900.0,
        "fromLine": "Substitute BackEnd configured ComfyUI model root: E:\\ImageGen Models",
        "toLine": "Found comfy_kitchen backend cuda",
    }


def test_run_harness_passes_defer_input_sam_to_app_managed_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness-level diagnostic flags should reach app-managed cycles."""

    received: list[bool] = []
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    def fake_app_managed_cycle(**kwargs: object) -> startup_harness.CommandRunResult:
        """Record app-managed harness arguments and return a minimal result."""

        received.append(bool(kwargs["defer_input_sam"]))
        return startup_harness.CommandRunResult(
            name="app-managed",
            command=("python", "main.py"),
            cwd=tmp_path,
            exit_code=1,
            termination_kind="killed_after_ready",
            timed_out=False,
            ready=True,
            elapsed_ms=1.0,
            output_path=tmp_path / "app-managed.log",
            route_measurements=(),
            parsed_import_times=(),
        )

    monkeypatch.setattr(startup_harness, "_validate_paths", lambda _paths: None)
    monkeypatch.setattr(
        startup_harness,
        "run_app_managed_cycle",
        fake_app_managed_cycle,
    )

    startup_harness.run_harness(
        paths=paths,
        cycles=1,
        modes=("app-managed",),
        host="127.0.0.1",
        port=8188,
        ready_timeout_seconds=1.0,
        settle_seconds=0.0,
        artifact_root=tmp_path / "artifacts",
        defer_input_sam=True,
        log=lambda _message: None,
    )

    assert received == [True]


def test_temporary_manager_config_restores_original_file(tmp_path: Path) -> None:
    """Temporary Manager config experiments should restore exact file contents."""

    comfy_root = tmp_path / "ComfyUI"
    config_path = comfy_root / "user" / "__manager" / "config.ini"
    original_text = (
        "[default]\nnetwork_mode = public\ndb_mode = remote\nfile_logging = False\n"
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(original_text, encoding="utf-8")
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    with startup_harness.temporarily_override_manager_config(
        paths=paths,
        overrides={"network_mode": "offline", "db_mode": "cache"},
        log=lambda _message: None,
    ) as result:
        temporary_text = config_path.read_text(encoding="utf-8")
        assert "network_mode = offline" in temporary_text
        assert "db_mode = cache" in temporary_text
        assert result is not None
        assert result.original_values == {
            "network_mode": "public",
            "db_mode": "remote",
        }
        assert result.restored_values == {
            "network_mode": None,
            "db_mode": None,
        }

    assert config_path.read_text(encoding="utf-8") == original_text
    assert result.restored_values == {
        "network_mode": "public",
        "db_mode": "remote",
    }


def test_run_harness_summarizes_temporary_manager_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness summaries should record reversible Manager config experiments."""

    comfy_root = tmp_path / "ComfyUI"
    config_path = comfy_root / "user" / "__manager" / "config.ini"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[default]\nnetwork_mode = public\ndb_mode = remote\n",
        encoding="utf-8",
    )
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    def fake_app_managed_cycle(**_kwargs: object) -> startup_harness.CommandRunResult:
        """Return one minimal harness result."""

        return startup_harness.CommandRunResult(
            name="app-managed",
            command=("python", "main.py"),
            cwd=tmp_path,
            exit_code=1,
            termination_kind="killed_after_ready",
            timed_out=False,
            ready=True,
            elapsed_ms=1.0,
            output_path=tmp_path / "app-managed.log",
            route_measurements=(),
            parsed_import_times=(),
        )

    monkeypatch.setattr(startup_harness, "_validate_paths", lambda _paths: None)
    monkeypatch.setattr(
        startup_harness,
        "run_app_managed_cycle",
        fake_app_managed_cycle,
    )

    summary = startup_harness.run_harness(
        paths=paths,
        cycles=1,
        modes=("app-managed",),
        host="127.0.0.1",
        port=8188,
        ready_timeout_seconds=1.0,
        settle_seconds=0.0,
        artifact_root=tmp_path / "artifacts",
        temporary_manager_config={"network_mode": "offline", "db_mode": "cache"},
        log=lambda _message: None,
    )

    payload = summary.to_payload()
    assert payload["temporaryManagerConfig"] == {
        "configPath": str(config_path),
        "originalValues": {"network_mode": "public", "db_mode": "remote"},
        "temporaryValues": {"network_mode": "offline", "db_mode": "cache"},
        "restoredValues": {"network_mode": "public", "db_mode": "remote"},
    }
    assert "network_mode = public" in config_path.read_text(encoding="utf-8")


def test_harness_paths_resolve_default_custom_node_roots(tmp_path: Path) -> None:
    """Default custom-node roots should derive from the selected Comfy root."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert (
        paths.substitute_backend_root
        == (tmp_path / "ComfyUI" / "custom_nodes" / "substitute-backend").resolve()
    )
    assert (
        paths.sugarcubes_root
        == (tmp_path / "ComfyUI" / "custom_nodes" / "sugarcubes").resolve()
    )


def test_build_direct_comfy_command_uses_workspace_python(tmp_path: Path) -> None:
    """Direct Comfy command should target the selected workspace and endpoint."""

    comfy_root = tmp_path / "ComfyUI"
    python_path = comfy_root / "venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert startup_harness.build_direct_comfy_command(
        paths=paths,
        host="127.0.0.1",
        port=8199,
    ) == (
        str(python_path.resolve()),
        str((comfy_root / "main.py").resolve()),
        "--listen",
        "127.0.0.1",
        "--port",
        "8199",
    )


def test_build_direct_comfy_route_probes_traces_substitute_dependency_route() -> None:
    """Substitute dependency probes should carry a stable backend trace header."""

    probes = startup_harness.build_direct_comfy_route_probes(
        host="127.0.0.1",
        port=8199,
    )
    substitute_probe = next(
        probe for probe in probes if probe.name == "substitute_dependency_readiness"
    )
    repeat_probe = next(
        probe
        for probe in probes
        if probe.name == "substitute_dependency_readiness_repeat"
    )

    assert (
        substitute_probe.headers[startup_harness.SUBSTITUTE_CUBE_TRACE_HEADER]
        == "startup-harness-substitute-deps"
    )
    assert substitute_probe.trace_id == "startup-harness-substitute-deps"
    assert (
        repeat_probe.headers[startup_harness.SUBSTITUTE_CUBE_TRACE_HEADER]
        == "startup-harness-substitute-deps-repeat"
    )
    assert repeat_probe.trace_id == "startup-harness-substitute-deps-repeat"


def test_build_direct_comfy_route_probes_can_probe_sugarcubes_dependencies_first() -> (
    None
):
    """Route order should make first-readiness attribution explicit."""

    probes = startup_harness.build_direct_comfy_route_probes(
        host="127.0.0.1",
        port=8199,
        dependency_route_order="sugarcubes-first",
    )

    assert [probe.name for probe in probes] == [
        "system_stats",
        "substitute_capabilities",
        "sugarcubes_dependency_readiness",
        "sugarcubes_dependency_readiness_repeat",
        "substitute_dependency_readiness",
        "substitute_dependency_readiness_repeat",
    ]


def test_build_sugarcubes_maintenance_command_uses_preflight(
    tmp_path: Path,
) -> None:
    """Maintenance command should run the read-only dependency preflight by default."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    command = startup_harness.build_sugarcubes_maintenance_command(paths)

    assert command[1:] == (
        "-m",
        "backend.maintenance",
        "cube-deps",
        "preflight",
        "--workspace",
        str((tmp_path / "ComfyUI").resolve()),
    )


def test_app_startup_trace_path_uses_install_root_appdata(tmp_path: Path) -> None:
    """App-managed trace capture should read the selected install-root trace."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert startup_harness.app_startup_trace_path(paths) == (
        (tmp_path / "SugarSubstitute")
        .resolve()
        .joinpath("appdata", "diagnostics", "logs", "startup-trace.jsonl")
    )


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
                '{"elapsed_ns":175000000,"event":"canvas_tabs.create.input_canvas",'
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
    assert span_elapsed_ms["canvas_tabs.create.input_canvas"] == 175.0
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


def test_wait_for_http_ready_uses_supplied_probe_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness raw-ready probing should not use a hard-coded URL timeout."""

    observed: dict[str, object] = {}

    class _Response:
        """Minimal urlopen context manager."""

        status = 200

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    def fake_urlopen(url: str, *, timeout: float) -> _Response:
        """Capture the requested timeout and return an OK response."""

        observed["url"] = url
        observed["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(
        startup_harness,
        "url_loopback_port_is_available",
        lambda _url: False,
    )
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monotonic_values = iter((0.0, 0.0))
    monkeypatch.setattr(time_module, "monotonic", lambda: next(monotonic_values))

    assert (
        startup_harness.wait_for_http_ready(
            "http://127.0.0.1:8188/system_stats",
            timeout_seconds=0.75,
        )
        is True
    )
    assert observed == {
        "url": "http://127.0.0.1:8188/system_stats",
        "timeout": 0.75,
    }


def test_run_server_process_writes_timestamped_output_timeline(
    tmp_path: Path,
) -> None:
    """Direct process runs should produce parseable output timelines."""

    output_timeline_path = tmp_path / "direct-comfy-output-timeline.jsonl"

    result = startup_harness._run_server_process(
        name="direct-comfy",
        command=(
            sys.executable,
            "-c",
            (
                "import time; "
                "print('Starting server', flush=True); "
                "print('To see the GUI go to: http://127.0.0.1:8188', flush=True); "
                "time.sleep(2)"
            ),
        ),
        cwd=tmp_path,
        output_path=tmp_path / "direct-comfy.log",
        output_timeline_path=output_timeline_path,
        ready_url=None,
        route_urls=(),
        ready_timeout_seconds=5.0,
        settle_seconds=0.1,
        env=startup_harness._process_env({}),
        log=lambda _message: None,
    )

    assert result.ready is True
    assert result.diagnostic_artifacts == (
        {
            "name": "direct-comfy_output_timeline",
            "path": str(output_timeline_path),
        },
    )
    assert output_timeline_path.exists()
    assert result.comfy_output_timeline_measurements is not None
    milestones = cast(
        dict[str, float],
        result.comfy_output_timeline_measurements["firstMilestoneMs"],
    )
    assert set(milestones) == {"starting_server", "gui_url_printed"}
    assert 0.0 <= milestones["starting_server"] <= 5000.0
    assert milestones["starting_server"] <= milestones["gui_url_printed"] <= 5000.0


def test_wait_for_http_ready_skips_http_probe_when_loopback_port_is_bindable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness raw-ready probing should not wait on an absent local server."""

    def fail_urlopen(*_args: object, **_kwargs: object) -> object:
        """Fail if a bindable loopback port still falls through to HTTP."""

        raise AssertionError("urlopen should not be called for a bindable port")

    monkeypatch.setattr(
        startup_harness,
        "url_loopback_port_is_available",
        lambda _url: True,
    )
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    monotonic_values = iter((0.0, 0.0))
    monkeypatch.setattr(time_module, "monotonic", lambda: next(monotonic_values))

    assert (
        startup_harness.wait_for_http_ready(
            "http://127.0.0.1:8188/system_stats",
            timeout_seconds=0.75,
        )
        is False
    )


def test_http_endpoint_is_reachable_skips_http_probe_when_loopback_port_is_bindable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness preflight checks should be cheap when a loopback port is unused."""

    def fail_urlopen(*_args: object, **_kwargs: object) -> object:
        """Fail if a bindable loopback port still falls through to HTTP."""

        raise AssertionError("urlopen should not be called for a bindable port")

    monkeypatch.setattr(
        startup_harness,
        "url_loopback_port_is_available",
        lambda _url: True,
    )
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    assert (
        startup_harness.http_endpoint_is_reachable(
            "http://127.0.0.1:8188/system_stats",
            timeout_seconds=1.0,
        )
        is False
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:8188/system_stats", True),
        ("http://[::1]:8188/system_stats", True),
        ("http://localhost:8188/system_stats", False),
        ("http://example.invalid:8188/system_stats", False),
    ],
)
def test_url_loopback_port_is_available_checks_literal_loopback_hosts_only(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    expected: bool,
) -> None:
    """Only literal loopback hosts should use bindability as readiness evidence."""

    calls: list[tuple[str, int]] = []

    def fake_local_port_is_available(*, host: str, port: int) -> bool:
        """Capture the parsed literal loopback target."""

        calls.append((host, port))
        return True

    monkeypatch.setattr(
        startup_harness,
        "_local_port_is_available",
        fake_local_port_is_available,
    )

    assert startup_harness.url_loopback_port_is_available(url) is expected
    if expected:
        parsed_host = urllib.parse.urlparse(url).hostname
        assert parsed_host is not None
        assert calls == [(parsed_host, 8188)]
    else:
        assert calls == []


def test_parse_args_defaults_to_non_app_modes() -> None:
    """Default harness mode should avoid launching the Qt app until requested."""

    args = startup_harness._parse_args([])

    assert args.mode == ("direct-comfy", "sugarcubes-maintenance")


def test_create_run_dir_adds_suffix_on_timestamp_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parallel harness invocations should not collide on timestamped run paths."""

    monkeypatch.setattr(
        startup_harness,
        "_timestamp_for_path",
        lambda: "run-20260708-103208",
    )
    first_run = tmp_path / "run-20260708-103208"
    first_run.mkdir()

    run_dir = startup_harness._create_run_dir(tmp_path)

    assert run_dir == tmp_path / "run-20260708-103208-01"
    assert run_dir.exists()
