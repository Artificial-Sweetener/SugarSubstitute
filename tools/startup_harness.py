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

"""Run repeatable headless startup measurements for SugarSubstitute and ComfyUI."""

from __future__ import annotations

import argparse
import configparser
import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from substitute.infrastructure.comfy.managed_model_root import (  # noqa: E402
    MANAGED_MODEL_ROOT_ENV,
    ManagedModelRootStore,
)

DEFAULT_COMFY_ROOT = Path(r"E:\ComfyUI")
DEFAULT_SUBSTITUTE_BACKEND_ROOT = (
    DEFAULT_COMFY_ROOT / "custom_nodes" / "substitute-backend"
)
DEFAULT_SUGARCUBES_ROOT = DEFAULT_COMFY_ROOT / "custom_nodes" / "sugarcubes"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8188
DEFAULT_READY_TIMEOUT_SECONDS = 180.0
DEFAULT_SETTLE_SECONDS = 5.0
DEFAULT_CYCLES = 1
DEFAULT_DEPENDENCY_ROUTE_ORDER = "substitute-first"
STARTUP_HARNESS_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "startup_harness"
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SUBSTITUTE_CUBE_TRACE_HEADER = "X-Substitute-Cube-Trace"
APP_MANAGED_COMFY_OUTPUT_LOG_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG"
APP_MANAGED_COMFY_OUTPUT_TIMELINE_ENV = (
    "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_TIMELINE"
)
LOOPBACK_BINDABLE_HOSTS = frozenset({"127.0.0.1", "::1"})
MANAGER_CONFIG_SECTION = "default"


class StartupHarnessError(RuntimeError):
    """Raised when the startup harness cannot complete a requested cycle."""


@dataclass(frozen=True, slots=True)
class HarnessPaths:
    """Describe the repository and workspace paths measured by the harness."""

    sugar_substitute_root: Path
    comfy_root: Path
    substitute_backend_root: Path
    sugarcubes_root: Path

    @classmethod
    def from_roots(
        cls,
        *,
        sugar_substitute_root: Path,
        comfy_root: Path,
        substitute_backend_root: Path | None,
        sugarcubes_root: Path | None,
    ) -> HarnessPaths:
        """Resolve path inputs into one immutable path bundle."""

        resolved_comfy = comfy_root.expanduser().resolve()
        return cls(
            sugar_substitute_root=sugar_substitute_root.expanduser().resolve(),
            comfy_root=resolved_comfy,
            substitute_backend_root=(
                substitute_backend_root.expanduser().resolve()
                if substitute_backend_root is not None
                else resolved_comfy / "custom_nodes" / "substitute-backend"
            ),
            sugarcubes_root=(
                sugarcubes_root.expanduser().resolve()
                if sugarcubes_root is not None
                else resolved_comfy / "custom_nodes" / "sugarcubes"
            ),
        )

    @property
    def comfy_python(self) -> Path:
        """Return the Comfy workspace Python executable."""

        candidates = (
            self.comfy_root / "venv" / "Scripts" / "python.exe",
            self.comfy_root / ".venv" / "Scripts" / "python.exe",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @property
    def sugar_substitute_python(self) -> Path:
        """Return the SugarSubstitute repository virtualenv Python executable."""

        return self.sugar_substitute_root / ".venv" / "Scripts" / "python.exe"


@dataclass(frozen=True, slots=True)
class CommandRunResult:
    """Capture one completed command measurement."""

    name: str
    command: tuple[str, ...]
    cwd: Path
    exit_code: int | None
    termination_kind: str
    timed_out: bool
    ready: bool
    elapsed_ms: float
    output_path: Path
    route_measurements: tuple[dict[str, object], ...]
    parsed_import_times: tuple[dict[str, object], ...]
    diagnostic_events: tuple[dict[str, object], ...] = ()
    parsed_prestartup_times: tuple[dict[str, object], ...] = ()
    ready_elapsed_ms: float | None = None
    diagnostic_artifacts: tuple[dict[str, object], ...] = ()
    startup_trace_measurements: dict[str, object] | None = None
    comfy_output_timeline_measurements: dict[str, object] | None = None
    managed_comfy_timeline_measurements: dict[str, object] | None = None

    def to_payload(self) -> dict[str, object]:
        """Return one JSON-safe command result payload."""

        payload: dict[str, object] = {
            "name": self.name,
            "command": list(self.command),
            "cwd": str(self.cwd),
            "exitCode": self.exit_code,
            "terminationKind": self.termination_kind,
            "timedOut": self.timed_out,
            "ready": self.ready,
            "elapsedMs": round(self.elapsed_ms, 3),
            "outputPath": str(self.output_path),
            "routeMeasurements": list(self.route_measurements),
            "parsedImportTimes": list(self.parsed_import_times),
        }
        if self.parsed_prestartup_times:
            payload["parsedPrestartupTimes"] = list(self.parsed_prestartup_times)
        if self.diagnostic_events:
            payload["diagnosticEvents"] = list(self.diagnostic_events)
        if self.ready_elapsed_ms is not None:
            payload["readyElapsedMs"] = round(self.ready_elapsed_ms, 3)
        if self.diagnostic_artifacts:
            payload["diagnosticArtifacts"] = list(self.diagnostic_artifacts)
        if self.startup_trace_measurements is not None:
            payload["startupTraceMeasurements"] = self.startup_trace_measurements
        if self.comfy_output_timeline_measurements is not None:
            payload["comfyOutputTimelineMeasurements"] = (
                self.comfy_output_timeline_measurements
            )
        if self.managed_comfy_timeline_measurements is not None:
            payload["managedComfyTimelineMeasurements"] = (
                self.managed_comfy_timeline_measurements
            )
        owned_startup_measurements = summarize_owned_startup_measurements(self)
        if owned_startup_measurements:
            payload["ownedStartupMeasurements"] = owned_startup_measurements
        return payload


@dataclass(frozen=True, slots=True)
class RouteProbe:
    """Describe one HTTP endpoint probe captured during a startup cycle."""

    name: str
    url: str
    headers: Mapping[str, str]
    trace_id: str = ""


@dataclass(frozen=True, slots=True)
class TimelineOutputRecord:
    """Capture one timestamped managed Comfy output line."""

    elapsed_ms: float
    line: str
    monotonic_ns: int | None = None


@dataclass(slots=True)
class TemporaryManagerConfigResult:
    """Describe a reversible ComfyUI-Manager config experiment."""

    config_path: Path
    original_values: Mapping[str, str | None]
    temporary_values: Mapping[str, str]
    restored_values: Mapping[str, str | None]

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-safe summary of the temporary config override."""

        return {
            "configPath": str(self.config_path),
            "originalValues": dict(self.original_values),
            "temporaryValues": dict(self.temporary_values),
            "restoredValues": dict(self.restored_values),
        }


@dataclass(frozen=True, slots=True)
class HarnessRunSummary:
    """Capture all measurements from one harness invocation."""

    run_dir: Path
    started_at: str
    paths: HarnessPaths
    results: tuple[CommandRunResult, ...]
    temporary_manager_config: TemporaryManagerConfigResult | None = None

    def to_payload(self) -> dict[str, object]:
        """Return the JSON summary written by the harness."""

        payload: dict[str, object] = {
            "schemaVersion": 1,
            "startedAt": self.started_at,
            "runDir": str(self.run_dir),
            "paths": {
                "sugarSubstituteRoot": str(self.paths.sugar_substitute_root),
                "comfyRoot": str(self.paths.comfy_root),
                "substituteBackendRoot": str(self.paths.substitute_backend_root),
                "sugarcubesRoot": str(self.paths.sugarcubes_root),
            },
            "results": [result.to_payload() for result in self.results],
        }
        if self.temporary_manager_config is not None:
            payload["temporaryManagerConfig"] = (
                self.temporary_manager_config.to_payload()
            )
        return payload


def run_harness(
    *,
    paths: HarnessPaths,
    cycles: int,
    modes: Sequence[str],
    host: str,
    port: int,
    ready_timeout_seconds: float,
    settle_seconds: float,
    artifact_root: Path,
    dependency_route_order: str = DEFAULT_DEPENDENCY_ROUTE_ORDER,
    defer_input_sam: bool = False,
    temporary_manager_config: Mapping[str, str] | None = None,
    log: Callable[[str], None] = print,
) -> HarnessRunSummary:
    """Run requested startup measurement cycles and write artifacts."""

    _validate_paths(paths)
    run_dir = _create_run_dir(artifact_root)
    started_at = _timestamp()
    results: list[CommandRunResult] = []
    with temporarily_override_manager_config(
        paths=paths,
        overrides=temporary_manager_config or {},
        log=log,
    ) as manager_config_result:
        for cycle in range(1, cycles + 1):
            cycle_dir = run_dir / f"cycle-{cycle:03d}"
            cycle_dir.mkdir(parents=True, exist_ok=True)
            log(f"[cycle {cycle}/{cycles}] writing artifacts to {cycle_dir}")
            if "direct-comfy" in modes:
                results.append(
                    run_direct_comfy_cycle(
                        paths=paths,
                        cycle_dir=cycle_dir,
                        host=host,
                        port=port,
                        ready_timeout_seconds=ready_timeout_seconds,
                        settle_seconds=settle_seconds,
                        dependency_route_order=dependency_route_order,
                        log=log,
                    )
                )
            if "sugarcubes-maintenance" in modes:
                results.append(
                    run_sugarcubes_maintenance_cycle(
                        paths=paths,
                        cycle_dir=cycle_dir,
                        log=log,
                    )
                )
            if "app-managed" in modes:
                results.append(
                    run_app_managed_cycle(
                        paths=paths,
                        cycle_dir=cycle_dir,
                        host=host,
                        port=port,
                        ready_timeout_seconds=ready_timeout_seconds,
                        settle_seconds=settle_seconds,
                        dependency_route_order=dependency_route_order,
                        log=log,
                        defer_input_sam=defer_input_sam,
                    )
                )

    summary = HarnessRunSummary(
        run_dir=run_dir,
        started_at=started_at,
        paths=paths,
        results=tuple(results),
        temporary_manager_config=manager_config_result,
    )
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary.to_payload(), indent=2),
        encoding="utf-8",
    )
    log(f"[summary] {summary_path}")
    return summary


def run_direct_comfy_cycle(
    *,
    paths: HarnessPaths,
    cycle_dir: Path,
    host: str,
    port: int,
    ready_timeout_seconds: float,
    settle_seconds: float,
    log: Callable[[str], None],
    dependency_route_order: str = DEFAULT_DEPENDENCY_ROUTE_ORDER,
) -> CommandRunResult:
    """Start Comfy directly, measure readiness routes, then terminate it."""

    command = build_direct_comfy_command(paths=paths, host=host, port=port)
    output_path = cycle_dir / "direct-comfy.log"
    output_timeline_path = cycle_dir / "direct-comfy-output-timeline.jsonl"
    ready_url = f"http://{host}:{port}/system_stats"
    if http_endpoint_is_reachable(ready_url, timeout_seconds=1.0):
        raise StartupHarnessError(
            f"Refusing direct Comfy cycle because {ready_url} is already reachable."
        )
    routes = build_direct_comfy_route_probes(
        host=host,
        port=port,
        dependency_route_order=dependency_route_order,
    )
    return _run_server_process(
        name="direct-comfy",
        command=command,
        cwd=paths.comfy_root,
        output_path=output_path,
        output_timeline_path=output_timeline_path,
        ready_url=ready_url,
        route_urls=routes,
        ready_timeout_seconds=ready_timeout_seconds,
        settle_seconds=settle_seconds,
        env=_process_env(direct_comfy_environment_overrides(paths)),
        log=log,
    )


def run_app_managed_cycle(
    *,
    paths: HarnessPaths,
    cycle_dir: Path,
    host: str,
    port: int,
    ready_timeout_seconds: float,
    settle_seconds: float,
    log: Callable[[str], None],
    dependency_route_order: str = DEFAULT_DEPENDENCY_ROUTE_ORDER,
    defer_input_sam: bool = False,
) -> CommandRunResult:
    """Start SugarSubstitute's real managed startup path in headless mode."""

    command = build_app_managed_command(paths)
    output_path = cycle_dir / "app-managed.log"
    ready_url = f"http://{host}:{port}/system_stats"
    if http_endpoint_is_reachable(ready_url, timeout_seconds=1.0):
        raise StartupHarnessError(
            f"Refusing app-managed cycle because {ready_url} is already reachable."
        )
    trace_path = app_startup_trace_path(paths)
    trace_offset = trace_path.stat().st_size if trace_path.exists() else 0
    managed_comfy_output_path = cycle_dir / "app-managed-comfy-output.log"
    managed_comfy_output_timeline_path = (
        cycle_dir / "app-managed-comfy-output-timeline.jsonl"
    )
    try:
        managed_comfy_output_path.unlink()
    except FileNotFoundError:
        pass
    try:
        managed_comfy_output_timeline_path.unlink()
    except FileNotFoundError:
        pass
    result = _run_server_process(
        name="app-managed",
        command=command,
        cwd=paths.sugar_substitute_root,
        output_path=output_path,
        ready_url=ready_url,
        route_urls=build_direct_comfy_route_probes(
            host=host,
            port=port,
            dependency_route_order=dependency_route_order,
        ),
        ready_timeout_seconds=ready_timeout_seconds,
        settle_seconds=settle_seconds,
        env=_process_env(
            app_managed_environment_overrides(
                defer_input_sam,
                managed_comfy_output_path=managed_comfy_output_path,
                managed_comfy_output_timeline_path=managed_comfy_output_timeline_path,
            )
        ),
        log=log,
    )
    diagnostic_artifacts: list[dict[str, object]] = []
    diagnostic_events = result.diagnostic_events
    parsed_import_times = result.parsed_import_times
    managed_comfy_timeline_measurements: dict[str, object] | None = None
    if managed_comfy_output_path.exists():
        managed_comfy_output_text = managed_comfy_output_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        diagnostic_artifacts.append(
            {"name": "managed_comfy_output", "path": str(managed_comfy_output_path)}
        )
        diagnostic_events = (
            *diagnostic_events,
            *parse_diagnostic_events(managed_comfy_output_text),
        )
        parsed_prestartup_times = parse_comfy_prestartup_times(
            managed_comfy_output_text
        )
        parsed_import_times = (
            *parsed_import_times,
            *parse_comfy_import_times(managed_comfy_output_text),
        )
    else:
        parsed_prestartup_times = result.parsed_prestartup_times
    if managed_comfy_output_timeline_path.exists():
        timeline_text = managed_comfy_output_timeline_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        diagnostic_artifacts.append(
            {
                "name": "managed_comfy_output_timeline",
                "path": str(managed_comfy_output_timeline_path),
            }
        )
        managed_comfy_timeline_measurements = parse_managed_comfy_output_timeline(
            timeline_text
        )
    copied_trace = copy_app_startup_trace_delta(
        trace_path=trace_path,
        offset=trace_offset,
        destination=cycle_dir / "app-managed-startup-trace.jsonl",
    )
    if copied_trace is None:
        trace_measurements: dict[str, object] | None = None
    else:
        trace_text = copied_trace.read_text(encoding="utf-8", errors="replace")
        diagnostic_artifacts.append(
            {"name": "startup_trace", "path": str(copied_trace)}
        )
        trace_measurements = parse_startup_trace_measurements(trace_text)
    if (
        trace_measurements is not None
        and managed_comfy_timeline_measurements is not None
    ):
        add_managed_timeline_trace_correlation(
            timeline_measurements=managed_comfy_timeline_measurements,
            trace_measurements=trace_measurements,
        )
    if (
        not diagnostic_artifacts
        and trace_measurements is None
        and managed_comfy_timeline_measurements is None
    ):
        return result
    return CommandRunResult(
        name=result.name,
        command=result.command,
        cwd=result.cwd,
        exit_code=result.exit_code,
        termination_kind=result.termination_kind,
        timed_out=result.timed_out,
        ready=result.ready,
        elapsed_ms=result.elapsed_ms,
        output_path=result.output_path,
        route_measurements=result.route_measurements,
        parsed_import_times=parsed_import_times,
        diagnostic_events=diagnostic_events,
        parsed_prestartup_times=parsed_prestartup_times,
        ready_elapsed_ms=result.ready_elapsed_ms,
        diagnostic_artifacts=tuple(diagnostic_artifacts),
        startup_trace_measurements=trace_measurements,
        managed_comfy_timeline_measurements=managed_comfy_timeline_measurements,
    )


def app_managed_environment_overrides(
    defer_input_sam: bool,
    *,
    managed_comfy_output_path: Path | None = None,
    managed_comfy_output_timeline_path: Path | None = None,
) -> dict[str, str]:
    """Return environment overrides for one app-managed harness cycle."""

    overrides = {
        "PYTHONUNBUFFERED": "1",
        "QT_QPA_PLATFORM": "offscreen",
        "SUBSTITUTE_BACKEND_DIAGNOSTICS": "cube-library,startup",
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS": "1",
        "SUGARCUBES_DIAGNOSTICS": "1",
    }
    if managed_comfy_output_path is not None:
        overrides[APP_MANAGED_COMFY_OUTPUT_LOG_ENV] = str(managed_comfy_output_path)
    if managed_comfy_output_timeline_path is not None:
        overrides[APP_MANAGED_COMFY_OUTPUT_TIMELINE_ENV] = str(
            managed_comfy_output_timeline_path
        )
    if defer_input_sam:
        overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM"] = "1"
    return overrides


def direct_comfy_environment_overrides(paths: HarnessPaths) -> dict[str, str]:
    """Return direct-Comfy harness env overrides aligned with managed startup."""

    config = ManagedModelRootStore().load(paths.comfy_root)
    return {
        "PATH": str(paths.comfy_python.parent)
        + os.pathsep
        + os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "QT_QPA_PLATFORM": "offscreen",
        "SUBSTITUTE_BACKEND_DIAGNOSTICS": "cube-library,startup",
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS": "1",
        "SUGARCUBES_DIAGNOSTICS": "1",
        MANAGED_MODEL_ROOT_ENV: str(config.effective_model_root),
    }


def run_sugarcubes_maintenance_cycle(
    *,
    paths: HarnessPaths,
    cycle_dir: Path,
    log: Callable[[str], None],
) -> CommandRunResult:
    """Run SugarCubes offline dependency preflight against the Comfy workspace."""

    command = build_sugarcubes_maintenance_command(paths)
    output_path = cycle_dir / "sugarcubes-maintenance.log"
    started = time.monotonic()
    result = _run_hidden_command(
        command=command,
        cwd=paths.sugarcubes_root,
        timeout_seconds=600.0,
        env=_process_env({"PYTHONUNBUFFERED": "1", "SUGARCUBES_DIAGNOSTICS": "1"}),
    )
    elapsed_ms = (time.monotonic() - started) * 1000.0
    output_path.write_text(result.stdout, encoding="utf-8")
    log(f"[sugarcubes-maintenance] exit={result.returncode} elapsed={elapsed_ms:.1f}ms")
    return CommandRunResult(
        name="sugarcubes-maintenance",
        command=tuple(command),
        cwd=paths.sugarcubes_root,
        exit_code=result.returncode,
        termination_kind="process_exit",
        timed_out=False,
        ready=result.returncode == 0,
        elapsed_ms=elapsed_ms,
        output_path=output_path,
        route_measurements=(),
        parsed_import_times=(),
        diagnostic_events=parse_diagnostic_events(result.stdout),
    )


def build_direct_comfy_command(
    *,
    paths: HarnessPaths,
    host: str,
    port: int,
) -> tuple[str, ...]:
    """Return the direct Comfy startup command."""

    return (
        str(paths.comfy_python),
        str(paths.comfy_root / "main.py"),
        "--listen",
        host,
        "--port",
        str(port),
    )


def build_direct_comfy_route_probes(
    *,
    host: str,
    port: int,
    dependency_route_order: str = DEFAULT_DEPENDENCY_ROUTE_ORDER,
) -> tuple[RouteProbe, ...]:
    """Return the endpoint probes measured after direct Comfy readiness."""

    base_url = f"http://{host}:{port}"
    leading_probes = (
        RouteProbe(
            name="system_stats",
            url=f"{base_url}/system_stats",
            headers={},
        ),
        RouteProbe(
            name="substitute_capabilities",
            url=f"{base_url}/substitute/v1/capabilities",
            headers={},
        ),
    )
    substitute_dependency_probes = (
        RouteProbe(
            name="substitute_dependency_readiness",
            url=f"{base_url}/substitute/v1/cube-library/dependencies/readiness",
            headers={SUBSTITUTE_CUBE_TRACE_HEADER: "startup-harness-substitute-deps"},
            trace_id="startup-harness-substitute-deps",
        ),
        RouteProbe(
            name="substitute_dependency_readiness_repeat",
            url=f"{base_url}/substitute/v1/cube-library/dependencies/readiness",
            headers={
                SUBSTITUTE_CUBE_TRACE_HEADER: "startup-harness-substitute-deps-repeat"
            },
            trace_id="startup-harness-substitute-deps-repeat",
        ),
    )
    sugarcubes_dependency_probes = (
        RouteProbe(
            name="sugarcubes_dependency_readiness",
            url=f"{base_url}/sugarcubes/dependencies/readiness",
            headers={},
        ),
        RouteProbe(
            name="sugarcubes_dependency_readiness_repeat",
            url=f"{base_url}/sugarcubes/dependencies/readiness",
            headers={},
        ),
    )
    if dependency_route_order == "sugarcubes-first":
        return (
            *leading_probes,
            *sugarcubes_dependency_probes,
            *substitute_dependency_probes,
        )
    if dependency_route_order == "substitute-first":
        return (
            *leading_probes,
            *substitute_dependency_probes,
            *sugarcubes_dependency_probes,
        )
    raise ValueError(f"Unsupported dependency route order: {dependency_route_order}")


def build_app_managed_command(paths: HarnessPaths) -> tuple[str, ...]:
    """Return the SugarSubstitute managed startup command."""

    return (
        str(paths.sugar_substitute_python),
        str(paths.sugar_substitute_root / "main.py"),
        f"--install-root={paths.sugar_substitute_root}",
    )


def build_sugarcubes_maintenance_command(paths: HarnessPaths) -> tuple[str, ...]:
    """Return the SugarCubes offline dependency preflight command."""

    return (
        str(paths.comfy_python),
        "-m",
        "backend.maintenance",
        "cube-deps",
        "preflight",
        "--workspace",
        str(paths.comfy_root),
    )


def app_startup_trace_path(paths: HarnessPaths) -> Path:
    """Return the app startup trace path for the selected install root."""

    return (
        paths.sugar_substitute_root
        / "appdata"
        / "diagnostics"
        / "logs"
        / "startup-trace.jsonl"
    )


def copy_app_startup_trace_delta(
    *,
    trace_path: Path,
    offset: int,
    destination: Path,
) -> Path | None:
    """Copy trace records appended during one app-managed harness cycle."""

    if not trace_path.exists():
        return None
    with trace_path.open("rb") as source:
        source.seek(offset)
        payload = source.read()
    if not payload:
        return None
    destination.write_bytes(payload)
    return destination


def parse_startup_trace_measurements(trace_text: str) -> dict[str, object]:
    """Summarize key startup trace milestones from one app-managed run."""

    records = tuple(_startup_trace_records(trace_text))
    if not records:
        return {"eventCount": 0}
    first_timestamp = _record_timestamp(records[0])
    event_counts: dict[str, int] = {}
    first_event_ms: dict[str, float] = {}
    first_event_timestamp_ns: dict[str, int] = {}
    span_elapsed_ms: dict[str, float] = {}
    dependency_phase_elapsed_ms: dict[str, float] = {}
    pretrace_phase_elapsed_ms: dict[str, float] = {}
    input_canvas_qpane_features: list[dict[str, object]] = []
    for record in records:
        event = str(record.get("event", ""))
        if not event:
            continue
        event_counts[event] = event_counts.get(event, 0) + 1
        timestamp = _record_timestamp(record)
        if timestamp is not None and event not in first_event_ms:
            first_event_ms[event] = round((timestamp - first_timestamp) / 1_000_000, 3)
            first_event_timestamp_ns[event] = timestamp
        elapsed_ns = record.get("elapsed_ns")
        if isinstance(elapsed_ns, int):
            span_elapsed_ms[event] = round(elapsed_ns / 1_000_000, 3)
        if event == "composition.dependencies.phase":
            fields = record.get("fields")
            if isinstance(fields, Mapping):
                phase = fields.get("phase")
                elapsed_ms = fields.get("elapsed_ms")
                if isinstance(phase, str) and isinstance(elapsed_ms, int | float):
                    dependency_phase_elapsed_ms[phase] = round(float(elapsed_ms), 3)
        if event == "input_canvas.qpane_features":
            fields = record.get("fields")
            if isinstance(fields, Mapping):
                features = fields.get("features")
                reason = fields.get("reason")
                input_canvas_qpane_features.append(
                    {
                        "features": features if isinstance(features, str) else "",
                        "reason": reason if isinstance(reason, str) else "",
                    }
                )
        if event == "startup.pretrace.phase":
            fields = record.get("fields")
            if isinstance(fields, Mapping):
                source = fields.get("source")
                phase = fields.get("phase")
                elapsed_ms = fields.get("elapsed_ms")
                if (
                    isinstance(source, str)
                    and isinstance(phase, str)
                    and isinstance(elapsed_ms, int | float)
                ):
                    pretrace_phase_elapsed_ms[f"{source}:{phase}"] = round(
                        float(elapsed_ms),
                        3,
                    )
    return {
        "eventCount": len(records),
        "firstEventMs": {
            name: first_event_ms[name]
            for name in (
                "startup.trace.ready",
                "activate_target_task.end",
                "managed_comfy.process_launched",
                "readiness_timer.started",
                "build_shell_task.build_main_window",
                "mark_minimum_shell_ready_task.end",
                "readiness_timer.http_ready",
                "managed_comfy.wait_ready.result",
                "main_shell.shown",
            )
            if name in first_event_ms
        },
        "firstEventTimestampNs": {
            name: first_event_timestamp_ns[name]
            for name in (
                "startup.trace.ready",
                "managed_comfy.process_launched",
                "readiness_timer.http_ready",
                "managed_comfy.wait_ready.result",
                "main_shell.shown",
            )
            if name in first_event_timestamp_ns
        },
        "spanElapsedMs": {
            name: span_elapsed_ms[name]
            for name in (
                "activate_target_task.activate",
                "startup.import_runtime_modules",
                "startup.create_application",
                "startup.build_appearance_runtime",
                "startup.configure_theme",
                "startup.runtime_services.build",
                "composition.dependencies",
                "composition.import_main_window",
                "composition.construct_main_window",
                "build_shell_task.build_main_window",
                "mainwindow.build_workspace.workflow_tabbar",
                "mainwindow.build_workspace.editor_shell_containers",
                "mainwindow.build_workspace.comfy_output_panel",
                "mainwindow.build_workspace.canvas.create_tabs",
                "mainwindow.build_workspace.canvas_scaffold",
                "mainwindow.build_workspace.central_layout",
                "mainwindow.build_workspace.theme_styles",
                "canvas_tabs.create.input_canvas",
                "canvas_tabs.create.output_canvas",
                "canvas_tabs.create.manager",
                "managed_comfy.resolve_listener",
                "managed_comfy.ensure_setup",
                "managed_comfy.launch_process",
                "managed_comfy.wait_ready",
                "managed_setup.detect_hardware",
                "managed_setup.select_install_strategy",
                "managed_setup.existing.provision_manager",
                "managed_setup.existing.ensure_nodepacks",
                "managed_setup.existing.sugarcubes_baseline",
                "managed_setup.existing.validate_torch",
                "qpane_sam_warmup.ensure_dependencies",
                "startup.backend_ready_transition",
                "main_shell.show",
            )
            if name in span_elapsed_ms
        },
        "readinessAttempts": event_counts.get("readiness_timer.tick", 0),
        "readinessInFlightSkips": event_counts.get("readiness_probe.in_flight_skip", 0),
        "httpNotReadyCount": event_counts.get("readiness_timer.http_not_ready", 0),
        "modelMetadataProgressEvents": sum(
            count
            for event, count in event_counts.items()
            if event.startswith("model_metadata_refresh.progress")
        ),
        "dependencyPhaseElapsedMs": dependency_phase_elapsed_ms,
        "inputCanvasQPaneFeatures": input_canvas_qpane_features,
        "preTracePhaseElapsedMs": pretrace_phase_elapsed_ms,
    }


def parse_managed_comfy_output_timeline(timeline_text: str) -> dict[str, object]:
    """Summarize timestamped managed Comfy output into startup milestones."""

    records: list[TimelineOutputRecord] = []
    for raw_line in timeline_text.splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        line = payload.get("line")
        elapsed_ms = payload.get("elapsedMs")
        monotonic_ns = payload.get("monotonicNs")
        if isinstance(line, str) and isinstance(elapsed_ms, int | float):
            records.append(
                TimelineOutputRecord(
                    elapsed_ms=round(float(elapsed_ms), 3),
                    line=strip_ansi_prefix(line),
                    monotonic_ns=monotonic_ns
                    if isinstance(monotonic_ns, int)
                    else None,
                )
            )

    milestone_patterns = {
        "launching_comfy": "Launching ComfyUI.",
        "prestartup_times": "Prestartup times for custom nodes:",
        "manager_network_mode": "[ComfyUI-Manager] network_mode:",
        "manager_default_cache_updated": "[ComfyUI-Manager] default cache updated:",
        "manager_all_startup_tasks_completed": (
            "[ComfyUI-Manager] All startup tasks have been completed."
        ),
        "manager_fetch_registry": "FETCH ComfyRegistry Data:",
        "substitute_node_dependency_index": (
            "Substitute startup diagnostic "
            "event=substitute_node_dependency_index_timing"
        ),
        "managed_model_root_applied": "Substitute managed ComfyUI model root:",
        "custom_node_import_times": "Import times for custom nodes:",
        "starting_server": "Starting server",
        "gui_url_printed": "To see the GUI go to:",
        "sugarcubes_library_readiness": (
            "SugarCubes cube library diagnostic "
            "event=sugarcubes_library_readiness_timing"
        ),
    }
    first_milestone_ms: dict[str, float] = {}
    first_milestone_timestamp_ns: dict[str, int] = {}
    milestone_lines: dict[str, str] = {}
    for record in records:
        line = record.line
        for name, pattern in milestone_patterns.items():
            if name not in first_milestone_ms and pattern in line:
                first_milestone_ms[name] = record.elapsed_ms
                if record.monotonic_ns is not None:
                    first_milestone_timestamp_ns[name] = record.monotonic_ns
                milestone_lines[name] = line

    measurements: dict[str, object] = {
        "eventCount": len(records),
        "firstOutputMs": records[0].elapsed_ms if records else None,
        "firstOutputTimestampNs": records[0].monotonic_ns if records else None,
        "lastOutputMs": records[-1].elapsed_ms if records else None,
        "firstMilestoneMs": first_milestone_ms,
        "milestoneLines": milestone_lines,
        "largestOutputGaps": _largest_timeline_output_gaps(records),
        "largestChildOutputGaps": _largest_timeline_output_gaps(
            _managed_child_output_records(records)
        ),
    }
    if first_milestone_timestamp_ns:
        measurements["firstMilestoneTimestampNs"] = first_milestone_timestamp_ns
    return measurements


def add_managed_timeline_trace_correlation(
    *,
    timeline_measurements: dict[str, object],
    trace_measurements: Mapping[str, object],
) -> None:
    """Add monotonic timestamp deltas between child output and app trace marks."""

    milestone_timestamps = timeline_measurements.get("firstMilestoneTimestampNs")
    trace_timestamps = trace_measurements.get("firstEventTimestampNs")
    if not isinstance(milestone_timestamps, Mapping) or not isinstance(
        trace_timestamps,
        Mapping,
    ):
        return
    correlations = {
        "process_launched_to_managed_model_root": (
            "managed_comfy.process_launched",
            "managed_model_root_applied",
        ),
        "process_launched_to_prestartup": (
            "managed_comfy.process_launched",
            "prestartup_times",
        ),
        "process_launched_to_gui_url": (
            "managed_comfy.process_launched",
            "gui_url_printed",
        ),
        "starting_server_to_http_ready": (
            "starting_server",
            "readiness_timer.http_ready",
        ),
        "gui_url_printed_to_http_ready": (
            "gui_url_printed",
            "readiness_timer.http_ready",
        ),
        "starting_server_to_managed_wait_result": (
            "starting_server",
            "managed_comfy.wait_ready.result",
        ),
        "gui_url_printed_to_managed_wait_result": (
            "gui_url_printed",
            "managed_comfy.wait_ready.result",
        ),
    }
    deltas: dict[str, float] = {}
    for name, (start_name, end_name) in correlations.items():
        start_timestamp = (
            trace_timestamps.get(start_name)
            if start_name.startswith("managed_comfy.")
            else milestone_timestamps.get(start_name)
        )
        end_timestamp = (
            trace_timestamps.get(end_name)
            if end_name.startswith(("readiness_timer.", "managed_comfy."))
            else milestone_timestamps.get(end_name)
        )
        if isinstance(start_timestamp, int) and isinstance(end_timestamp, int):
            deltas[name] = round((end_timestamp - start_timestamp) / 1_000_000, 3)
    if deltas:
        timeline_measurements["startupTraceDeltaMs"] = deltas


def summarize_owned_startup_measurements(
    result: CommandRunResult,
) -> dict[str, object]:
    """Return compact owned startup measurements for run-to-run comparison."""

    summary: dict[str, object] = {}
    route_elapsed_ms = {
        str(route.get("name")): route["elapsedMs"]
        for route in result.route_measurements
        if isinstance(route.get("name"), str)
        and isinstance(route.get("elapsedMs"), int | float)
    }
    if route_elapsed_ms:
        summary["routeElapsedMs"] = route_elapsed_ms

    owned_import_seconds = _owned_custom_node_import_seconds(result.parsed_import_times)
    if owned_import_seconds:
        summary["ownedCustomNodeImportSeconds"] = owned_import_seconds

    prestartup = _prestartup_measurements(result.parsed_prestartup_times)
    if prestartup:
        summary["prestartup"] = prestartup

    substitute_backend = _substitute_backend_measurements(result.diagnostic_events)
    if substitute_backend:
        summary["substituteBackend"] = substitute_backend

    managed_output_fanout = _managed_output_fanout_measurements(
        result.diagnostic_events
    )
    if managed_output_fanout:
        summary["managedOutputFanout"] = managed_output_fanout

    sugarcubes = _sugarcubes_measurements(result.diagnostic_events)
    if sugarcubes:
        summary["sugarcubes"] = sugarcubes

    app_spans = _app_span_measurements(result.startup_trace_measurements)
    if app_spans:
        summary["appSpanElapsedMs"] = app_spans

    comfy_output_milestones = _managed_comfy_milestone_measurements(
        result.comfy_output_timeline_measurements
    )
    if comfy_output_milestones:
        summary["comfyOutputMilestoneMs"] = comfy_output_milestones
    comfy_output_phases = _managed_comfy_phase_measurements(
        result.comfy_output_timeline_measurements
    )
    if comfy_output_phases:
        summary["comfyOutputPhaseMs"] = comfy_output_phases

    managed_milestones = _managed_comfy_milestone_measurements(
        result.managed_comfy_timeline_measurements
    )
    if managed_milestones:
        summary["managedComfyMilestoneMs"] = managed_milestones
    managed_phases = _managed_comfy_phase_measurements(
        result.managed_comfy_timeline_measurements
    )
    if managed_phases:
        summary["managedComfyPhaseMs"] = managed_phases
    return summary


def _owned_custom_node_import_seconds(
    parsed_import_times: Sequence[Mapping[str, object]],
) -> dict[str, float]:
    """Return import timings for owned Comfy custom-node packages."""

    measurements: dict[str, float] = {}
    for item in parsed_import_times:
        module_path = item.get("modulePath")
        seconds = item.get("seconds")
        if not isinstance(module_path, str) or not isinstance(seconds, int | float):
            continue
        normalized = module_path.replace("\\", "/").casefold()
        if "substitute-backend" in normalized:
            measurements.setdefault("substituteBackend", round(float(seconds), 3))
        elif "substitutemanagedmodelroot" in normalized:
            measurements.setdefault("managedModelRoot", round(float(seconds), 3))
        elif "sugarcubes" in normalized:
            measurements.setdefault("sugarcubes", round(float(seconds), 3))
    return measurements


def _prestartup_measurements(
    parsed_prestartup_times: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return owned and slow custom-node prestartup timing highlights."""

    if not parsed_prestartup_times:
        return {}
    owned_seconds = _owned_custom_node_import_seconds(parsed_prestartup_times)
    normalized_rows: list[tuple[float, str, str]] = []
    for item in parsed_prestartup_times:
        seconds = item.get("seconds")
        module_path = item.get("modulePath")
        status = item.get("status")
        if not isinstance(seconds, int | float) or not isinstance(module_path, str):
            continue
        normalized_rows.append(
            (
                float(seconds),
                status if isinstance(status, str) else "",
                module_path,
            )
        )
    slowest = tuple(
        {"seconds": round(seconds, 3), "status": status, "modulePath": module_path}
        for seconds, status, module_path in sorted(
            normalized_rows,
            key=lambda row: row[0],
            reverse=True,
        )[:5]
    )
    measurements: dict[str, object] = {}
    if owned_seconds:
        measurements["ownedSeconds"] = owned_seconds
    if slowest:
        measurements["slowest"] = slowest
    return measurements


def _substitute_backend_measurements(
    diagnostic_events: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return Substitute BackEnd startup and route timing highlights."""

    measurements: dict[str, object] = {}
    backend_services = _first_diagnostic_event(
        diagnostic_events,
        "substitute_startup_timing",
        operation="backend_services",
    )
    register_extension = _first_diagnostic_event(
        diagnostic_events,
        "substitute_startup_timing",
        operation="register_extension",
    )
    service_scan = _first_diagnostic_event(
        diagnostic_events,
        "substitute_sugarcubes_active_service_scan_timing",
    )
    service_load = _first_diagnostic_event(
        diagnostic_events,
        "substitute_sugarcubes_load_services_timing",
    )
    capability_events = _diagnostic_events(
        diagnostic_events,
        "substitute_capabilities_timing",
    )

    for key, event in (
        ("backendServicesMs", backend_services),
        ("registerExtensionMs", register_extension),
        ("sugarcubesServiceScanMs", service_scan),
        ("sugarcubesServiceLoadMs", service_load),
    ):
        value = _diagnostic_float_field(event, "total_duration_ms")
        if value is not None:
            measurements[key] = value
    if capability_events:
        capability_times = tuple(
            value
            for value in (
                _diagnostic_float_field(event, "total_duration_ms")
                for event in capability_events
            )
            if value is not None
        )
        if capability_times:
            measurements["capabilitiesMs"] = capability_times
    return measurements


def _managed_output_fanout_measurements(
    diagnostic_events: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return app-owned managed Comfy output fanout timing highlights."""

    timing_events = _diagnostic_events(
        diagnostic_events,
        "managed_output_fanout_timing",
    )
    if not timing_events:
        return {}
    last_event = timing_events[-1]
    marker_last_fanout_ms: dict[str, float] = {}
    for event in timing_events:
        fields = event.get("fields")
        if not isinstance(fields, Mapping):
            continue
        marker = fields.get("marker")
        last_fanout_ms = fields.get("last_fanout_ms")
        if isinstance(marker, str) and isinstance(last_fanout_ms, int | float):
            marker_last_fanout_ms[marker] = round(float(last_fanout_ms), 3)

    measurements: dict[str, object] = {}
    for key, field_name in (
        ("recordCount", "record_count"),
        ("totalFanoutMs", "total_fanout_ms"),
        ("maxFanoutMs", "max_fanout_ms"),
    ):
        value = _diagnostic_float_field(last_event, field_name)
        if value is not None:
            measurements[key] = int(value) if key == "recordCount" else value
    if marker_last_fanout_ms:
        measurements["markerLastFanoutMs"] = marker_last_fanout_ms
    return measurements


def _sugarcubes_measurements(
    diagnostic_events: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return SugarCubes dependency-readiness timing highlights."""

    measurements: dict[str, object] = {}
    library_readiness = _first_diagnostic_event(
        diagnostic_events,
        "sugarcubes_library_readiness_timing",
    )
    requirement_sets = _first_diagnostic_event(
        diagnostic_events,
        "sugarcubes_dependency_requirement_sets_timing",
    )
    inventory = _first_diagnostic_event(
        diagnostic_events,
        "sugarcubes_installed_dependency_inventory_timing",
    )
    version_readiness = _first_diagnostic_event(
        diagnostic_events,
        "sugarcubes_dependency_version_readiness_timing",
    )
    cache_hits = _diagnostic_events(
        diagnostic_events,
        "sugarcubes_library_readiness_cache_hit",
    )

    for key, event in (
        ("libraryReadinessMs", library_readiness),
        ("dependencyRequirementSetsMs", requirement_sets),
        ("installedDependencyInventoryMs", inventory),
        ("dependencyVersionReadinessMs", version_readiness),
    ):
        value = _diagnostic_float_field(event, "total_duration_ms")
        if value is not None:
            measurements[key] = value
    cached = _diagnostic_bool_field(requirement_sets, "cached")
    if cached is not None:
        measurements["dependencyRequirementSetsCached"] = cached
    source_signature_ms = _diagnostic_float_field(
        requirement_sets,
        "source_signature_build",
    )
    if source_signature_ms is not None:
        measurements["dependencySourceSignatureMs"] = source_signature_ms
    read_git_status_ms = _diagnostic_float_field(inventory, "read_git_status")
    if read_git_status_ms is not None:
        measurements["installedInventoryReadGitStatusMs"] = read_git_status_ms
    cache_hit_times = tuple(
        value
        for value in (
            _diagnostic_float_field(event, "total_duration_ms") for event in cache_hits
        )
        if value is not None
    )
    if cache_hit_times:
        measurements["libraryReadinessCacheHitMs"] = cache_hit_times
    return measurements


def _app_span_measurements(
    startup_trace_measurements: Mapping[str, object] | None,
) -> dict[str, float]:
    """Return key app-owned startup spans from parsed startup trace data."""

    if startup_trace_measurements is None:
        return {}
    span_elapsed_ms = startup_trace_measurements.get("spanElapsedMs")
    if not isinstance(span_elapsed_ms, Mapping):
        return {}
    keys = (
        "startup.import_runtime_modules",
        "startup.configure_theme",
        "composition.dependencies",
        "composition.import_main_window",
        "composition.construct_main_window",
        "build_shell_task.build_main_window",
        "managed_comfy.ensure_setup",
        "managed_comfy.launch_process",
        "managed_comfy.wait_ready",
    )
    return {
        key: round(float(value), 3)
        for key in keys
        if isinstance((value := span_elapsed_ms.get(key)), int | float)
    }


def _managed_comfy_milestone_measurements(
    managed_comfy_timeline_measurements: Mapping[str, object] | None,
) -> dict[str, float]:
    """Return key managed Comfy child-output milestones."""

    if managed_comfy_timeline_measurements is None:
        return {}
    first_milestone_ms = managed_comfy_timeline_measurements.get("firstMilestoneMs")
    if not isinstance(first_milestone_ms, Mapping):
        return {}
    keys = (
        "launching_comfy",
        "prestartup_times",
        "manager_network_mode",
        "manager_default_cache_updated",
        "manager_fetch_registry",
        "managed_model_root_applied",
        "custom_node_import_times",
        "starting_server",
        "gui_url_printed",
        "sugarcubes_library_readiness",
    )
    return {
        key: round(float(value), 3)
        for key in keys
        if isinstance((value := first_milestone_ms.get(key)), int | float)
    }


def _managed_comfy_phase_measurements(
    managed_comfy_timeline_measurements: Mapping[str, object] | None,
) -> dict[str, float]:
    """Return derived child-output startup phase durations."""

    if managed_comfy_timeline_measurements is None:
        return {}
    first_milestone_ms = managed_comfy_timeline_measurements.get("firstMilestoneMs")
    if not isinstance(first_milestone_ms, Mapping):
        return {}
    phase_pairs = (
        ("launchToPrestartup", "launching_comfy", "prestartup_times"),
        ("launchToManagedModelRoot", "launching_comfy", "managed_model_root_applied"),
        ("launchToGuiUrl", "launching_comfy", "gui_url_printed"),
        (
            "managedModelRootToPrestartup",
            "managed_model_root_applied",
            "prestartup_times",
        ),
        ("prestartupToManagerNetworkMode", "prestartup_times", "manager_network_mode"),
        ("prestartupToManagerFetch", "prestartup_times", "manager_fetch_registry"),
        (
            "prestartupToCustomNodeImports",
            "prestartup_times",
            "custom_node_import_times",
        ),
        ("prestartupToGuiUrl", "prestartup_times", "gui_url_printed"),
        ("managerNetworkModeToGuiUrl", "manager_network_mode", "gui_url_printed"),
        ("managerFetchToGuiUrl", "manager_fetch_registry", "gui_url_printed"),
        ("customNodeImportsToGuiUrl", "custom_node_import_times", "gui_url_printed"),
    )
    measurements: dict[str, float] = {}
    for name, start_key, end_key in phase_pairs:
        start = first_milestone_ms.get(start_key)
        end = first_milestone_ms.get(end_key)
        if isinstance(start, int | float) and isinstance(end, int | float):
            measurements[f"{name}Ms"] = round(float(end) - float(start), 3)
    return measurements


def _diagnostic_events(
    diagnostic_events: Sequence[Mapping[str, object]],
    event_name: str,
) -> tuple[Mapping[str, object], ...]:
    """Return diagnostic events matching one event name."""

    return tuple(
        event for event in diagnostic_events if event.get("event") == event_name
    )


def _first_diagnostic_event(
    diagnostic_events: Sequence[Mapping[str, object]],
    event_name: str,
    *,
    operation: str | None = None,
) -> Mapping[str, object] | None:
    """Return the first diagnostic event matching name and optional operation."""

    for event in diagnostic_events:
        if event.get("event") != event_name:
            continue
        if operation is None:
            return event
        fields = event.get("fields")
        if isinstance(fields, Mapping) and fields.get("operation") == operation:
            return event
    return None


def _diagnostic_float_field(
    event: Mapping[str, object] | None,
    field_name: str,
) -> float | None:
    """Return one numeric diagnostic field rounded for JSON output."""

    if event is None:
        return None
    fields = event.get("fields")
    if not isinstance(fields, Mapping):
        return None
    value = fields.get(field_name)
    if not isinstance(value, int | float):
        return None
    return round(float(value), 3)


def _diagnostic_bool_field(
    event: Mapping[str, object] | None,
    field_name: str,
) -> bool | None:
    """Return one boolean diagnostic field."""

    if event is None:
        return None
    fields = event.get("fields")
    if not isinstance(fields, Mapping):
        return None
    value = fields.get(field_name)
    return value if isinstance(value, bool) else None


def _largest_timeline_output_gaps(
    records: Sequence[TimelineOutputRecord],
) -> tuple[dict[str, object], ...]:
    """Return the largest gaps between adjacent managed Comfy output lines."""

    gaps: list[tuple[float, dict[str, object]]] = []
    previous: TimelineOutputRecord | None = None
    for record in records:
        if previous is not None:
            gap_ms = round(record.elapsed_ms - previous.elapsed_ms, 3)
            if gap_ms > 0:
                gaps.append(
                    (
                        gap_ms,
                        {
                            "gapMs": gap_ms,
                            "fromMs": round(previous.elapsed_ms, 3),
                            "toMs": round(record.elapsed_ms, 3),
                            "fromLine": _truncate_timeline_line(previous.line),
                            "toLine": _truncate_timeline_line(record.line),
                        },
                    )
                )
        previous = record
    return tuple(
        gap for _gap_ms, gap in sorted(gaps, key=lambda item: item[0], reverse=True)[:8]
    )


def _managed_child_output_records(
    records: Sequence[TimelineOutputRecord],
) -> tuple[TimelineOutputRecord, ...]:
    """Return managed timeline records that came from the Comfy child process."""

    first_child_index = 0
    for index, record in enumerate(records):
        if (
            "Substitute managed ComfyUI model root:" in record.line
            or "Prestartup times for custom nodes:" in record.line
        ):
            first_child_index = index
            break
    return tuple(
        record
        for record in records[first_child_index:]
        if not _managed_parent_status_line(record.line)
    )


def _managed_parent_status_line(line: str) -> bool:
    """Return whether one managed output line was produced by the parent launcher."""

    stripped = line.strip()
    return (
        stripped.startswith("Configured managed ComfyUI to use model files from ")
        or stripped
        in {
            "Managed ComfyUI setup is current.",
            "Launching ComfyUI.",
            "Waiting for ComfyUI to become ready...",
        }
        or stripped.startswith(
            "Substitute startup diagnostic event=managed_output_fanout_timing "
        )
    )


def _truncate_timeline_line(line: str, *, limit: int = 180) -> str:
    """Return one timeline line trimmed for compact JSON summaries."""

    normalized = " ".join(line.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _startup_trace_records(trace_text: str) -> tuple[dict[str, object], ...]:
    """Return decoded JSONL startup trace records."""

    records: list[dict[str, object]] = []
    for line in trace_text.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return tuple(records)


def _record_timestamp(record: Mapping[str, object]) -> int:
    """Return one trace record timestamp in nanoseconds."""

    timestamp = record.get("timestamp_ns")
    if isinstance(timestamp, int):
        return timestamp
    return 0


def parse_comfy_import_times(output: str) -> tuple[dict[str, object], ...]:
    """Parse Comfy custom-node import timing blocks from captured output."""

    return _parse_comfy_timing_block(
        output,
        heading="Import times for custom nodes:",
        failed_marker="(IMPORT FAILED)",
    )


def parse_comfy_prestartup_times(output: str) -> tuple[dict[str, object], ...]:
    """Parse Comfy custom-node prestartup timing blocks from captured output."""

    return _parse_comfy_timing_block(
        output,
        heading="Prestartup times for custom nodes:",
        failed_marker="(PRESTARTUP FAILED)",
    )


def _parse_comfy_timing_block(
    output: str,
    *,
    heading: str,
    failed_marker: str,
) -> tuple[dict[str, object], ...]:
    """Parse one Comfy custom-node timing block from captured output."""

    records: list[dict[str, object]] = []
    in_block = False
    for raw_line in output.splitlines():
        line = strip_ansi_prefix(raw_line).strip()
        if line == heading:
            in_block = True
            continue
        if not in_block:
            continue
        if not line:
            in_block = False
            continue
        seconds_text, separator, remainder = line.partition(" seconds")
        if not separator:
            continue
        try:
            seconds = float(seconds_text.strip())
        except ValueError:
            continue
        status = "failed" if failed_marker in remainder else "ok"
        _, _, module_path = remainder.partition(":")
        records.append(
            {
                "seconds": seconds,
                "status": status,
                "modulePath": module_path.strip(),
            }
        )
    return tuple(records)


def parse_diagnostic_events(output: str) -> tuple[dict[str, object], ...]:
    """Parse structured Substitute and SugarCubes diagnostic log events."""

    records: list[dict[str, object]] = []
    for raw_line in output.splitlines():
        line = strip_ansi_prefix(raw_line).strip()
        label, separator, payload = line.partition(" diagnostic event=")
        if not separator:
            continue
        event_name, fields_text = _split_diagnostic_event_payload(payload)
        if not event_name:
            continue
        source, channel = _diagnostic_source_and_channel(label)
        records.append(
            {
                "source": source,
                "channel": channel,
                "event": event_name,
                "fields": _parse_diagnostic_fields(fields_text),
            }
        )
    return tuple(records)


def _split_diagnostic_event_payload(payload: str) -> tuple[str, str]:
    """Return the event name and remaining key/value text."""

    event_name, separator, fields_text = payload.strip().partition(" ")
    if not separator:
        return event_name.strip(), ""
    return event_name.strip(), fields_text.strip()


def _diagnostic_source_and_channel(label: str) -> tuple[str, str]:
    """Return stable source and diagnostic channel names from one log label."""

    normalized = label.strip()
    parts = normalized.split()
    if not parts:
        return "", ""
    source = parts[0]
    channel_parts = parts[1:]
    if channel_parts and channel_parts[-1] == "diagnostic":
        channel_parts = channel_parts[:-1]
    return source, "_".join(part.casefold().replace("-", "_") for part in channel_parts)


def _parse_diagnostic_fields(fields_text: str) -> dict[str, object]:
    """Parse space-separated diagnostic key/value pairs."""

    fields: dict[str, object] = {}
    for token in fields_text.split():
        key, separator, value = token.partition("=")
        if not separator or not key:
            continue
        fields[key] = _parse_diagnostic_value(value)
    return fields


def _parse_diagnostic_value(value: str) -> object:
    """Return one JSON-safe diagnostic value."""

    if value == "[]":
        return []
    normalized = value.casefold()
    if normalized in {"true", "false"}:
        return normalized == "true"
    try:
        integer = int(value)
    except ValueError:
        pass
    else:
        return integer
    try:
        return float(value)
    except ValueError:
        return value


def strip_ansi_prefix(line: str) -> str:
    """Remove terminal color codes and Comfy log-level prefixes from one line."""

    normalized = ANSI_ESCAPE_PATTERN.sub("", line).strip()
    if normalized.startswith("[INFO]"):
        return normalized.removeprefix("[INFO]").strip()
    if normalized.startswith("[WARNING]"):
        return normalized.removeprefix("[WARNING]").strip()
    return normalized


def measure_route(
    probe: RouteProbe, *, timeout_seconds: float = 30.0
) -> dict[str, object]:
    """Measure one HTTP route and return a compact JSON-safe result."""

    started = time.monotonic()
    try:
        request = urllib.request.Request(
            probe.url,
            headers=dict(probe.headers),
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read(4096)
            status = int(getattr(response, "status", 0) or 0)
    except (OSError, urllib.error.URLError) as exc:
        return {
            "name": probe.name,
            "url": probe.url,
            "traceId": probe.trace_id,
            "ok": False,
            "status": 0,
            "elapsedMs": round((time.monotonic() - started) * 1000.0, 3),
            "errorType": type(exc).__name__,
        }
    return {
        "name": probe.name,
        "url": probe.url,
        "traceId": probe.trace_id,
        "ok": 200 <= status < 300,
        "status": status,
        "elapsedMs": round((time.monotonic() - started) * 1000.0, 3),
        "sampleBytes": len(payload),
    }


def wait_for_http_ready(url: str, *, timeout_seconds: float) -> bool:
    """Return whether an HTTP endpoint becomes reachable before timeout."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if url_loopback_port_is_available(url):
            return False
        try:
            with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
                if 200 <= int(getattr(response, "status", 0) or 0) < 500:
                    return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    return False


def http_endpoint_is_reachable(url: str, *, timeout_seconds: float) -> bool:
    """Return whether one HTTP endpoint responds during a short probe."""

    if url_loopback_port_is_available(url):
        return False
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= int(getattr(response, "status", 0) or 0) < 500
    except (OSError, urllib.error.URLError):
        return False


def url_loopback_port_is_available(url: str) -> bool:
    """Return whether a literal loopback URL target can be bound immediately."""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if host not in LOOPBACK_BINDABLE_HOSTS:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return _local_port_is_available(host=host, port=port)


def _local_port_is_available(*, host: str, port: int) -> bool:
    """Return whether one literal loopback port can be bound immediately."""

    family = socket.AF_INET6 if host == "::1" else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
    except OSError:
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line options and run the startup harness."""

    _configure_stdio()
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    paths = HarnessPaths.from_roots(
        sugar_substitute_root=args.sugar_substitute_root,
        comfy_root=args.comfy_root,
        substitute_backend_root=args.substitute_backend_root,
        sugarcubes_root=args.sugarcubes_root,
    )
    summary = run_harness(
        paths=paths,
        cycles=args.cycles,
        modes=args.mode,
        host=args.host,
        port=args.port,
        ready_timeout_seconds=args.ready_timeout_seconds,
        settle_seconds=args.settle_seconds,
        artifact_root=args.artifact_root,
        dependency_route_order=args.dependency_route_order,
        defer_input_sam=args.defer_input_sam,
        temporary_manager_config=_temporary_manager_config_from_args(args),
    )
    print(f"HARNESS_SUMMARY {summary.run_dir / 'summary.json'}")
    return 0


@contextlib.contextmanager
def temporarily_override_manager_config(
    *,
    paths: HarnessPaths,
    overrides: Mapping[str, str],
    log: Callable[[str], None],
) -> Iterator[TemporaryManagerConfigResult | None]:
    """Temporarily edit ComfyUI-Manager config and restore the original bytes."""

    if not overrides:
        yield None
        return

    config_path = _manager_config_path(paths)
    if not config_path.exists():
        raise StartupHarnessError(
            f"ComfyUI-Manager config does not exist: {config_path}"
        )

    original_text = config_path.read_text(encoding="utf-8")
    original_values = _read_manager_config_values(config_path, overrides.keys())
    result = TemporaryManagerConfigResult(
        config_path=config_path,
        original_values=original_values,
        temporary_values=dict(overrides),
        restored_values={key: None for key in overrides},
    )
    try:
        _write_manager_config_values(config_path, overrides)
        log(
            "[manager-config] temporary override "
            + ", ".join(f"{key}={value}" for key, value in overrides.items())
            + f" in {config_path}"
        )
        yield result
    finally:
        config_path.write_text(original_text, encoding="utf-8")
        restored_values = _read_manager_config_values(config_path, overrides.keys())
        result.restored_values = restored_values
        log(f"[manager-config] restored {config_path}")


def _manager_config_path(paths: HarnessPaths) -> Path:
    """Return the active ComfyUI-Manager config path for this Comfy layout."""

    modern_path = paths.comfy_root / "user" / "__manager" / "config.ini"
    if modern_path.exists():
        return modern_path
    return paths.comfy_root / "user" / "default" / "ComfyUI-Manager" / "config.ini"


def _read_manager_config_values(
    config_path: Path, keys: Iterable[str]
) -> dict[str, str | None]:
    """Read selected ComfyUI-Manager config values from disk."""

    parser = configparser.ConfigParser(strict=False)
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(MANAGER_CONFIG_SECTION):
        return {key: None for key in keys}
    section = parser[MANAGER_CONFIG_SECTION]
    return {key: section.get(key) for key in keys}


def _write_manager_config_values(
    config_path: Path, overrides: Mapping[str, str]
) -> None:
    """Write selected ComfyUI-Manager config values for one harness experiment."""

    parser = configparser.ConfigParser(strict=False)
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(MANAGER_CONFIG_SECTION):
        parser.add_section(MANAGER_CONFIG_SECTION)
    for key, value in overrides.items():
        parser.set(MANAGER_CONFIG_SECTION, key, value)
    with config_path.open("w", encoding="utf-8") as config_file:
        parser.write(config_file)


def _run_server_process(
    *,
    name: str,
    command: Sequence[str],
    cwd: Path,
    output_path: Path,
    ready_url: str | None,
    route_urls: Sequence[RouteProbe],
    ready_timeout_seconds: float,
    settle_seconds: float,
    env: Mapping[str, str],
    log: Callable[[str], None],
    output_timeline_path: Path | None = None,
) -> CommandRunResult:
    """Run a long-lived startup process until ready or timeout, then stop it."""

    startupinfo, creationflags = _hidden_process_options()
    started = time.monotonic()
    output_lines: list[str] = []
    output_timeline_lines: list[str] = []
    output_lock = threading.Lock()
    process = subprocess.Popen(  # noqa: S603
        list(command),
        cwd=str(cwd),
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    output_reader = _start_output_reader(
        process=process,
        output_lines=output_lines,
        output_timeline_lines=output_timeline_lines,
        output_lock=output_lock,
        started_at=started,
    )
    ready = False
    ready_elapsed_ms: float | None = None
    timed_out = False
    termination_kind = "process_exit"
    try:
        deadline = time.monotonic() + ready_timeout_seconds
        while time.monotonic() < deadline:
            if ready_url is None:
                if time.monotonic() - started >= settle_seconds:
                    ready = True
                    ready_elapsed_ms = (time.monotonic() - started) * 1000.0
                    break
            elif wait_for_http_ready(ready_url, timeout_seconds=0.75):
                ready = True
                ready_elapsed_ms = (time.monotonic() - started) * 1000.0
                break
            if process.poll() is not None:
                break
            time.sleep(0.25)
        else:
            timed_out = True

        if ready and settle_seconds > 0:
            time.sleep(settle_seconds)
        route_measurements = tuple(measure_route(probe) for probe in route_urls)
    finally:
        if process.poll() is None:
            if ready:
                termination_kind = "killed_after_ready"
            elif timed_out:
                termination_kind = "killed_after_timeout"
            else:
                termination_kind = "killed_before_ready"
            _kill_process_tree(process.pid)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            termination_kind = "killed_after_wait_timeout"
            _kill_process_tree(process.pid)
        output_reader.join(timeout=5)

    elapsed_ms = (time.monotonic() - started) * 1000.0
    with output_lock:
        output_text = "".join(output_lines)
        output_timeline_text = "".join(output_timeline_lines)
    output_path.write_text(output_text, encoding="utf-8")
    diagnostic_artifacts: tuple[dict[str, object], ...] = ()
    comfy_output_timeline_measurements: dict[str, object] | None = None
    if output_timeline_path is not None:
        output_timeline_path.write_text(output_timeline_text, encoding="utf-8")
        diagnostic_artifacts = (
            {"name": f"{name}_output_timeline", "path": str(output_timeline_path)},
        )
        comfy_output_timeline_measurements = parse_managed_comfy_output_timeline(
            output_timeline_text
        )
    parsed_import_times = parse_comfy_import_times(output_text)
    parsed_prestartup_times = parse_comfy_prestartup_times(output_text)
    diagnostic_events = parse_diagnostic_events(output_text)
    exit_code = process.poll()
    log(
        f"[{name}] ready={ready} exit={exit_code} "
        f"termination={termination_kind} elapsed={elapsed_ms:.1f}ms"
    )
    return CommandRunResult(
        name=name,
        command=tuple(command),
        cwd=cwd,
        exit_code=exit_code,
        termination_kind=termination_kind,
        timed_out=timed_out,
        ready=ready,
        elapsed_ms=elapsed_ms,
        output_path=output_path,
        route_measurements=route_measurements,
        parsed_import_times=parsed_import_times,
        diagnostic_events=diagnostic_events,
        parsed_prestartup_times=parsed_prestartup_times,
        ready_elapsed_ms=ready_elapsed_ms,
        diagnostic_artifacts=diagnostic_artifacts,
        comfy_output_timeline_measurements=comfy_output_timeline_measurements,
    )


def _run_hidden_command(
    *,
    command: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run one hidden finite command and capture merged output."""

    startupinfo, creationflags = _hidden_process_options()
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )


def _start_output_reader(
    *,
    process: subprocess.Popen[str],
    output_lines: list[str],
    output_timeline_lines: list[str],
    output_lock: threading.Lock,
    started_at: float,
) -> threading.Thread:
    """Start a daemon reader that drains process output without blocking polling."""

    def read_output() -> None:
        """Drain process stdout until the pipe closes."""

        stdout = process.stdout
        if stdout is None:
            return
        try:
            for line in stdout:
                monotonic_ns = time.monotonic_ns()
                elapsed_ms = round((time.monotonic() - started_at) * 1000.0, 3)
                timeline_payload = {
                    "event": "process_output",
                    "monotonicNs": monotonic_ns,
                    "elapsedMs": elapsed_ms,
                    "line": line.rstrip("\r\n"),
                }
                with output_lock:
                    output_lines.append(line)
                    output_timeline_lines.append(
                        json.dumps(timeline_payload, separators=(",", ":")) + "\n"
                    )
        except OSError:
            return

    thread = threading.Thread(
        target=read_output,
        name=f"startup-harness-output-{process.pid}",
        daemon=True,
    )
    thread.start()
    return thread


def _hidden_process_options() -> tuple[subprocess.STARTUPINFO | None, int]:
    """Return Windows hidden-window process options."""

    if sys.platform != "win32":
        return None, 0
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo, subprocess.CREATE_NO_WINDOW


def _kill_process_tree(pid: int) -> None:
    """Terminate a process tree started by this harness."""

    if sys.platform != "win32":
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def _process_env(overrides: Mapping[str, str]) -> dict[str, str]:
    """Return process environment with harness overrides applied."""

    env = os.environ.copy()
    env.update(overrides)
    return env


def _validate_paths(paths: HarnessPaths) -> None:
    """Fail early when required repositories or runtimes are unavailable."""

    required_paths = (
        paths.sugar_substitute_root / "main.py",
        paths.sugar_substitute_python,
        paths.comfy_root / "main.py",
        paths.comfy_python,
        paths.substitute_backend_root / "__init__.py",
        paths.sugarcubes_root / "__init__.py",
        paths.sugarcubes_root / "backend" / "maintenance.py",
    )
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        raise StartupHarnessError(
            "Startup harness missing required paths: "
            + ", ".join(str(path) for path in missing)
        )


def _create_run_dir(artifact_root: Path) -> Path:
    """Create a timestamped artifact directory for one harness invocation."""

    resolved_root = artifact_root.expanduser().resolve()
    base_name = _timestamp_for_path()
    for suffix in range(100):
        run_name = base_name if suffix == 0 else f"{base_name}-{suffix:02d}"
        run_dir = resolved_root / run_name
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return run_dir
    raise StartupHarnessError(
        f"Unable to create unique run directory under {resolved_root}"
    )


def _timestamp() -> str:
    """Return an ISO-like local timestamp for summaries."""

    return datetime.now().astimezone().isoformat(timespec="seconds")


def _timestamp_for_path() -> str:
    """Return a filesystem-safe timestamp directory name."""

    return datetime.now().strftime("run-%Y%m%d-%H%M%S")


def _configure_stdio() -> None:
    """Use UTF-8 console IO so Comfy output cannot break the harness."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse startup harness command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run headless SugarSubstitute and ComfyUI startup measurements."
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=("direct-comfy", "sugarcubes-maintenance", "app-managed"),
        default=None,
        help="Measurement mode to run. May be passed more than once.",
    )
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--ready-timeout-seconds", type=float, default=DEFAULT_READY_TIMEOUT_SECONDS
    )
    parser.add_argument("--settle-seconds", type=float, default=DEFAULT_SETTLE_SECONDS)
    parser.add_argument(
        "--artifact-root", type=Path, default=STARTUP_HARNESS_ARTIFACT_ROOT
    )
    parser.add_argument(
        "--dependency-route-order",
        choices=("substitute-first", "sugarcubes-first"),
        default=DEFAULT_DEPENDENCY_ROUTE_ORDER,
        help=(
            "Route probe order for dependency readiness endpoints. Use "
            "sugarcubes-first to attribute first-readiness cost to the direct "
            "SugarCubes route before probing Substitute's wrapper."
        ),
    )
    parser.add_argument("--sugar-substitute-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--comfy-root", type=Path, default=DEFAULT_COMFY_ROOT)
    parser.add_argument("--substitute-backend-root", type=Path, default=None)
    parser.add_argument("--sugarcubes-root", type=Path, default=None)
    parser.add_argument(
        "--defer-input-sam",
        action="store_true",
        help=(
            "App-managed diagnostic mode: construct the Input canvas without "
            "eager SAM during the harness run."
        ),
    )
    parser.add_argument(
        "--temporary-manager-network-mode",
        choices=("public", "private", "offline"),
        default=None,
        help=(
            "Temporarily set ComfyUI-Manager network_mode for this harness run "
            "and restore the original config afterward."
        ),
    )
    parser.add_argument(
        "--temporary-manager-db-mode",
        choices=("local", "cache", "remote"),
        default=None,
        help=(
            "Temporarily set ComfyUI-Manager db_mode for this harness run and "
            "restore the original config afterward."
        ),
    )
    args = parser.parse_args(list(argv))
    if args.cycles < 1:
        parser.error("--cycles must be at least 1")
    if args.ready_timeout_seconds <= 0:
        parser.error("--ready-timeout-seconds must be positive")
    if args.settle_seconds < 0:
        parser.error("--settle-seconds cannot be negative")
    args.mode = tuple(args.mode or ("direct-comfy", "sugarcubes-maintenance"))
    return args


def _temporary_manager_config_from_args(args: argparse.Namespace) -> dict[str, str]:
    """Return requested temporary ComfyUI-Manager config overrides."""

    overrides: dict[str, str] = {}
    if args.temporary_manager_network_mode is not None:
        overrides["network_mode"] = str(args.temporary_manager_network_mode)
    if args.temporary_manager_db_mode is not None:
        overrides["db_mode"] = str(args.temporary_manager_db_mode)
    return overrides


if __name__ == "__main__":
    raise SystemExit(main())
