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

"""Activate managed Comfy targets and route startup output."""

from __future__ import annotations

import json
from pathlib import Path
import os
import time
from typing import TextIO
from typing import Callable, Protocol

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import InstallationContext
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_launcher import ManagedTaskFactory
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
    log_warning_exception,
)

_LOGGER = get_logger("app.bootstrap.managed_target_activation")
_STARTUP_HARNESS_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS"
_HARNESS_COMFY_OUTPUT_LOG_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG"
_HARNESS_COMFY_OUTPUT_TIMELINE_ENV = (
    "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_TIMELINE"
)
_HARNESS_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_HARNESS_FANOUT_MARKERS = {
    "Prestartup times for custom nodes:": "prestartup_times",
    "Starting server": "starting_server",
    "To see the GUI go to:": "gui_url",
}
_harness_comfy_output_log: TextIO | None = None
_harness_comfy_output_log_path: Path | None = None
_harness_comfy_output_timeline: TextIO | None = None
_harness_comfy_output_timeline_path: Path | None = None
_harness_comfy_output_timeline_started_ns = time.perf_counter_ns()
_harness_fanout_record_count = 0
_harness_fanout_total_ms = 0.0
_harness_fanout_max_ms = 0.0


class ComfyOutputStreamProtocol(Protocol):
    """Append managed startup output to the shell transcript stream."""

    def append_line(self, line: str) -> None:
        """Append one output line."""


def activate_target(
    *,
    installation_context: InstallationContext,
    splash: LaunchSplashClient | None,
    comfy_output_stream: ComfyOutputStreamProtocol,
    startup_diagnostics: ComfyStartupDiagnosticsCollector,
    launch_task_factory: ManagedTaskFactory,
    process_pump_task_factory: ManagedTaskFactory,
) -> process_manager.ManagedComfyState | None:
    """Activate the selected Comfy target before the shell opens."""

    target = installation_context.comfy_target
    active_splash = splash

    def detach_splash() -> None:
        """Stop forwarding startup output to a disposed splash endpoint."""

        nonlocal active_splash
        active_splash = None

    def fan_out(line: ApplicationText) -> None:
        """Forward one line while allowing the splash endpoint to detach."""

        fan_out_splash_and_shell_output(
            splash=active_splash,
            comfy_output_stream=comfy_output_stream,
            line=render_application_text(line),
            on_splash_disposed=detach_splash,
        )

    fan_out(
        app_text(
            "Activating %1 Comfy target at %2:%3.",
            target.mode.value,
            target.endpoint.host,
            target.endpoint.port,
        )
    )
    if target.launch_owned and target.workspace_path is not None:
        return process_manager.start_comfyui_background_managed(
            endpoint=target.endpoint,
            workspace=target.workspace_path,
            runtime_state_dir=installation_context.runtime_state_dir,
            diagnostics=startup_diagnostics,
            launch_task_factory=launch_task_factory,
            process_pump_task_factory=process_pump_task_factory,
            python_executable=(
                target.python_binding.executable
                if target.python_binding is not None
                else None
            ),
            on_log=lambda line: collect_and_fan_out_comfy_output(
                startup_diagnostics=startup_diagnostics,
                splash=active_splash,
                comfy_output_stream=comfy_output_stream,
                line=line,
                on_splash_disposed=detach_splash,
            ),
            on_status=lambda line: collect_and_fan_out_comfy_output(
                startup_diagnostics=startup_diagnostics,
                splash=active_splash,
                comfy_output_stream=comfy_output_stream,
                line=line,
                on_splash_disposed=detach_splash,
            ),
            on_progress=lambda line: fan_out_transient_comfy_progress(
                splash=active_splash,
                comfy_output_stream=comfy_output_stream,
                line=line,
                on_splash_disposed=detach_splash,
            ),
        )
    return None


def collect_and_fan_out_comfy_output(
    *,
    startup_diagnostics: ComfyStartupDiagnosticsCollector,
    splash: LaunchSplashClient | None,
    comfy_output_stream: ComfyOutputStreamProtocol,
    line: ApplicationText,
    on_splash_disposed: Callable[[], None] | None = None,
) -> None:
    """Collect one startup diagnostic record and forward it to visible sinks."""

    rendered_line = render_application_text(line)
    started_at = time.perf_counter()
    try:
        try:
            startup_diagnostics.append_output(rendered_line)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Failed to classify Comfy startup output",
                error=repr(error),
            )
        mirror_managed_comfy_output_for_harness(rendered_line)
        mirror_managed_comfy_output_timeline_for_harness(rendered_line)
        fan_out_splash_and_shell_output(
            splash=splash,
            comfy_output_stream=comfy_output_stream,
            line=rendered_line,
            on_splash_disposed=on_splash_disposed,
        )
    finally:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        record_harness_output_fanout_timing(rendered_line, elapsed_ms)


def fan_out_splash_and_shell_output(
    *,
    splash: LaunchSplashClient | None,
    comfy_output_stream: ComfyOutputStreamProtocol,
    line: str,
    on_splash_disposed: Callable[[], None] | None = None,
) -> None:
    """Forward one managed-Comfy output line to both splash and shell history."""

    if splash is not None:
        try:
            splash.append_log(line)
        except (OSError, RuntimeError) as error:
            log_warning(
                _LOGGER,
                "Dropped splash log line after splash disposal",
                error_type=type(error).__name__,
            )
            if on_splash_disposed is not None:
                on_splash_disposed()
    try:
        comfy_output_stream.append_line(line)
    except Exception as error:
        log_warning_exception(
            _LOGGER,
            "Dropped shell Comfy output line after output stream failure",
            error=error,
        )


def fan_out_transient_comfy_progress(
    *,
    splash: LaunchSplashClient | None,
    comfy_output_stream: ComfyOutputStreamProtocol,
    line: ApplicationText,
    on_splash_disposed: Callable[[], None] | None = None,
) -> None:
    """Render one localized progress message as a replaceable console tail row."""

    fan_out_splash_and_shell_output(
        splash=splash,
        comfy_output_stream=comfy_output_stream,
        line=f"{render_application_text(line)}\r",
        on_splash_disposed=on_splash_disposed,
    )


def mirror_managed_comfy_output_for_harness(line: str) -> None:
    """Mirror managed Comfy output to a harness-owned file when requested."""

    configured_path = os.environ.get(_HARNESS_COMFY_OUTPUT_LOG_ENV, "").strip()
    if not configured_path:
        return
    try:
        handle = _harness_output_log_handle(Path(configured_path))
        handle.write(f"{line.rstrip()}\n")
    except OSError as error:
        log_warning(
            _LOGGER,
            "Failed to mirror managed Comfy output for startup harness",
            error=repr(error),
            path=configured_path,
        )


def mirror_managed_comfy_output_timeline_for_harness(line: str) -> None:
    """Mirror managed Comfy output timing to a harness-owned JSONL file."""

    configured_path = os.environ.get(_HARNESS_COMFY_OUTPUT_TIMELINE_ENV, "").strip()
    if not configured_path:
        return
    now_ns = time.perf_counter_ns()
    payload = {
        "event": "managed_comfy_output",
        "monotonicNs": now_ns,
        "elapsedMs": round(
            (now_ns - _harness_comfy_output_timeline_started_ns) / 1_000_000,
            3,
        ),
        "line": line.rstrip(),
    }
    try:
        handle = _harness_output_timeline_handle(Path(configured_path))
        handle.write(f"{json.dumps(payload, ensure_ascii=False)}\n")
    except OSError as error:
        log_warning(
            _LOGGER,
            "Failed to mirror managed Comfy output timeline for startup harness",
            error=repr(error),
            path=configured_path,
        )


def record_harness_output_fanout_timing(line: str, elapsed_ms: float) -> None:
    """Record harness-only timing checkpoints for managed Comfy output fanout."""

    global _harness_fanout_record_count
    global _harness_fanout_total_ms
    global _harness_fanout_max_ms

    if not _startup_harness_enabled():
        return
    _harness_fanout_record_count += 1
    _harness_fanout_total_ms += elapsed_ms
    _harness_fanout_max_ms = max(_harness_fanout_max_ms, elapsed_ms)
    marker = _harness_fanout_marker(line)
    if marker is None:
        return
    diagnostic_line = (
        "Substitute startup diagnostic "
        "event=managed_output_fanout_timing "
        f"record_count={_harness_fanout_record_count} "
        f"total_fanout_ms={round(_harness_fanout_total_ms, 3)} "
        f"max_fanout_ms={round(_harness_fanout_max_ms, 3)} "
        f"last_fanout_ms={round(elapsed_ms, 3)} "
        f"marker={marker}"
    )
    mirror_managed_comfy_output_for_harness(diagnostic_line)
    mirror_managed_comfy_output_timeline_for_harness(diagnostic_line)


def _startup_harness_enabled() -> bool:
    """Return whether startup harness-only instrumentation is enabled."""

    return os.environ.get(_STARTUP_HARNESS_ENV, "").strip().lower() in (
        _HARNESS_TRUE_VALUES
    )


def _harness_fanout_marker(line: str) -> str | None:
    """Return the fanout checkpoint marker name for one managed output line."""

    for marker_text, marker_name in _HARNESS_FANOUT_MARKERS.items():
        if marker_text in line:
            return marker_name
    return None


def _harness_output_log_handle(path: Path) -> TextIO:
    """Return the current harness mirror log handle."""

    global _harness_comfy_output_log, _harness_comfy_output_log_path

    resolved_path = path.expanduser().resolve()
    if (
        _harness_comfy_output_log is not None
        and _harness_comfy_output_log_path == resolved_path
    ):
        return _harness_comfy_output_log
    if _harness_comfy_output_log is not None:
        _harness_comfy_output_log.close()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    _harness_comfy_output_log = resolved_path.open(
        "a",
        encoding="utf-8",
        buffering=1,
    )
    _harness_comfy_output_log_path = resolved_path
    return _harness_comfy_output_log


def _harness_output_timeline_handle(path: Path) -> TextIO:
    """Return the current harness mirror timeline handle."""

    global _harness_comfy_output_timeline, _harness_comfy_output_timeline_path

    resolved_path = path.expanduser().resolve()
    if (
        _harness_comfy_output_timeline is not None
        and _harness_comfy_output_timeline_path == resolved_path
    ):
        return _harness_comfy_output_timeline
    if _harness_comfy_output_timeline is not None:
        _harness_comfy_output_timeline.close()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    _harness_comfy_output_timeline = resolved_path.open(
        "a",
        encoding="utf-8",
        buffering=1,
    )
    _harness_comfy_output_timeline_path = resolved_path
    return _harness_comfy_output_timeline


def managed_startup_fatal_incident(
    comfy_state: object | None,
) -> ComfyStartupIncident | None:
    """Return the current managed startup fatal incident when one is available."""

    if comfy_state is None:
        return None
    if not isinstance(comfy_state, process_manager.ManagedComfyState):
        return None
    startup_result = comfy_state.startup_result
    if startup_result is None:
        return None
    return startup_result.fatal_incident


__all__ = [
    "ComfyOutputStreamProtocol",
    "activate_target",
    "collect_and_fan_out_comfy_output",
    "fan_out_splash_and_shell_output",
    "fan_out_transient_comfy_progress",
    "mirror_managed_comfy_output_for_harness",
    "mirror_managed_comfy_output_timeline_for_harness",
    "managed_startup_fatal_incident",
]
