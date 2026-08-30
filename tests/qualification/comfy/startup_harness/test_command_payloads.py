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

"""Test startup-harness command payload measurement projection."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from tools import startup_harness


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
