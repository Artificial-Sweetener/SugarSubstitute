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

"""Capture and optionally persist workflow tab-switch performance diagnostics."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from substitute.presentation.shell.workflow_route_projector import (
    WorkflowRouteProjectionResult,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.shell.workflow_tab_switch_diagnostics")
_WORKFLOW_TAB_PERF_ENV = "SUGARSUBSTITUTE_WORKFLOW_TAB_PERF"
_WORKFLOW_TAB_PERF_PATH_ENV = "SUGARSUBSTITUTE_WORKFLOW_TAB_PERF_PATH"
_DEFAULT_WORKFLOW_TAB_PERF_PATH = (
    Path("artifacts") / "workflow_tab_profile" / "live_tab_switches.jsonl"
)


@dataclass(frozen=True, slots=True)
class WorkflowTabSwitchDiagnostic:
    """Record non-fragile timing and work counters for one workflow projection."""

    workflow_id: str
    source: str
    tab_intent_received_at: float
    active_workflow_update_elapsed_ms: float
    route_projection_elapsed_ms: float
    canvas_projection_elapsed_ms: float
    ensure_workflow_ui_elapsed_ms: float
    show_route_elapsed_ms: float
    tab_select_elapsed_ms: float
    cube_stack_swap_elapsed_ms: float
    editor_panel_swap_elapsed_ms: float
    override_projection_elapsed_ms: float
    input_canvas_availability_elapsed_ms: float
    overlay_refresh_elapsed_ms: float
    activity_badge_elapsed_ms: float
    overrides_projected: bool
    widgets_created: bool
    editor_rebuilt: bool
    deferred_requests: int
    info_logs: int = 0


class WorkflowTabSwitchDiagnostics:
    """Own in-memory tab-switch diagnostics and optional JSONL persistence."""

    def __init__(self) -> None:
        """Initialize an empty diagnostic history."""

        self._last: WorkflowTabSwitchDiagnostic | None = None
        self._history: list[WorkflowTabSwitchDiagnostic] = []

    @property
    def last(self) -> WorkflowTabSwitchDiagnostic | None:
        """Return the latest workflow projection diagnostic row."""

        return self._last

    def history(self) -> tuple[WorkflowTabSwitchDiagnostic, ...]:
        """Return recorded workflow projection diagnostics."""

        return tuple(self._history)

    def record(
        self,
        *,
        source: str,
        tab_intent_received_at: float | None,
        active_workflow_update_elapsed_ms: float,
        route_projection: WorkflowRouteProjectionResult,
        editor_rebuilt: bool,
        deferred_requests: int,
    ) -> None:
        """Capture timing and work counters from one route projection result."""

        diagnostic = WorkflowTabSwitchDiagnostic(
            workflow_id=route_projection.workflow_id,
            source=source,
            tab_intent_received_at=tab_intent_received_at or perf_counter(),
            active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
            route_projection_elapsed_ms=route_projection.route_projection_elapsed_ms,
            canvas_projection_elapsed_ms=(
                route_projection.canvas_projection_elapsed_ms
            ),
            ensure_workflow_ui_elapsed_ms=(
                route_projection.ensure_workflow_ui_elapsed_ms
            ),
            show_route_elapsed_ms=route_projection.show_route_elapsed_ms,
            tab_select_elapsed_ms=route_projection.tab_select_elapsed_ms,
            cube_stack_swap_elapsed_ms=route_projection.cube_stack_swap_elapsed_ms,
            editor_panel_swap_elapsed_ms=route_projection.editor_panel_swap_elapsed_ms,
            override_projection_elapsed_ms=(
                route_projection.override_projection_elapsed_ms
            ),
            input_canvas_availability_elapsed_ms=(
                route_projection.input_canvas_availability_elapsed_ms
            ),
            overlay_refresh_elapsed_ms=route_projection.overlay_refresh_elapsed_ms,
            activity_badge_elapsed_ms=route_projection.activity_badge_elapsed_ms,
            overrides_projected=route_projection.overrides_projected,
            widgets_created=route_projection.created_widgets,
            editor_rebuilt=editor_rebuilt,
            deferred_requests=deferred_requests,
        )
        self._last = diagnostic
        self._history.append(diagnostic)
        self._log(diagnostic)
        self._write(diagnostic)

    @staticmethod
    def _log(diagnostic: WorkflowTabSwitchDiagnostic) -> None:
        """Log one diagnostic with stable structured timing fields."""

        log_debug(
            _LOGGER,
            "workflow tab switch diagnostic captured",
            workflow_id=diagnostic.workflow_id,
            source=diagnostic.source,
            active_workflow_update_elapsed_ms=(
                f"{diagnostic.active_workflow_update_elapsed_ms:.3f}"
            ),
            route_projection_elapsed_ms=(
                f"{diagnostic.route_projection_elapsed_ms:.3f}"
            ),
            canvas_projection_elapsed_ms=(
                f"{diagnostic.canvas_projection_elapsed_ms:.3f}"
            ),
            ensure_workflow_ui_elapsed_ms=(
                f"{diagnostic.ensure_workflow_ui_elapsed_ms:.3f}"
            ),
            show_route_elapsed_ms=f"{diagnostic.show_route_elapsed_ms:.3f}",
            tab_select_elapsed_ms=f"{diagnostic.tab_select_elapsed_ms:.3f}",
            cube_stack_swap_elapsed_ms=(f"{diagnostic.cube_stack_swap_elapsed_ms:.3f}"),
            editor_panel_swap_elapsed_ms=(
                f"{diagnostic.editor_panel_swap_elapsed_ms:.3f}"
            ),
            override_projection_elapsed_ms=(
                f"{diagnostic.override_projection_elapsed_ms:.3f}"
            ),
            input_canvas_availability_elapsed_ms=(
                f"{diagnostic.input_canvas_availability_elapsed_ms:.3f}"
            ),
            overlay_refresh_elapsed_ms=(f"{diagnostic.overlay_refresh_elapsed_ms:.3f}"),
            activity_badge_elapsed_ms=(f"{diagnostic.activity_badge_elapsed_ms:.3f}"),
            overrides_projected=diagnostic.overrides_projected,
            widgets_created=diagnostic.widgets_created,
            editor_rebuilt=diagnostic.editor_rebuilt,
            deferred_requests=diagnostic.deferred_requests,
        )

    @staticmethod
    def _write(diagnostic: WorkflowTabSwitchDiagnostic) -> None:
        """Append one diagnostic row when live persistence is enabled."""

        if not _workflow_tab_perf_enabled():
            return
        path = _workflow_tab_perf_path()
        payload = {
            "captured_at": datetime.now(UTC).isoformat(),
            **asdict(diagnostic),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to write workflow tab performance diagnostic",
                path=str(path),
                error=repr(error),
            )


def _workflow_tab_perf_enabled() -> bool:
    """Return whether live workflow-tab performance rows should be persisted."""

    return os.environ.get(_WORKFLOW_TAB_PERF_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _workflow_tab_perf_path() -> Path:
    """Return the JSONL output path for live workflow-tab performance rows."""

    configured_path = os.environ.get(_WORKFLOW_TAB_PERF_PATH_ENV, "").strip()
    path = Path(configured_path) if configured_path else _DEFAULT_WORKFLOW_TAB_PERF_PATH
    if path.is_absolute():
        return path
    return Path.cwd() / path


__all__ = ["WorkflowTabSwitchDiagnostic", "WorkflowTabSwitchDiagnostics"]
