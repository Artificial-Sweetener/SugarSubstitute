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

"""Create measured workflow tab-switch profiling artifacts."""

# ruff: noqa: E402

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import cast, TypedDict

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from substitute.application.workflows import WorkflowSessionService, WorkflowTabService
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)

LOGGER = logging.getLogger("sugarsubstitute.tools.profile_workflow_tab_switch")
ARTIFACT_ROOT = Path("artifacts") / "workflow_tab_profile"
SWITCH_SEQUENCE = ("wf-a", "wf-b", "wf-c", "wf-a", "wf-c", "wf-b")


class ProfileRun(TypedDict):
    """Describe one tab-switch profiling row."""

    workflow_id: str
    route_ms: float
    canvas_ms: float
    ensure_workflow_ui_ms: float
    show_route_ms: float
    tab_select_ms: float
    cube_stack_swap_ms: float
    editor_panel_swap_ms: float
    override_projection_ms: float
    input_canvas_availability_ms: float
    overlay_refresh_ms: float
    activity_badge_ms: float
    overrides_projected: bool
    widgets_created: bool
    editor_rebuilt: bool
    deferred_requests: int
    info_logs: int


class ProfileArtifact(TypedDict):
    """Describe the latest profile artifact schema."""

    runs: list[ProfileRun]
    workflow_tab_reorder_supported: bool


class _InfoCountingHandler(logging.Handler):
    """Count INFO-and-above records emitted during profile switching."""

    def __init__(self) -> None:
        """Initialize an empty record counter."""

        super().__init__(level=logging.INFO)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        """Increment the counter for emitted INFO-level records."""

        if record.levelno >= logging.INFO:
            self.count += 1


class _TabItem:
    """Workflow tab item double for measured profile switching."""

    def __init__(self, workflow_id: str) -> None:
        """Store workflow route key and label."""

        self._workflow_id = workflow_id
        self._text = workflow_id

    def routeKey(self) -> str:
        """Return the workflow route key."""

        return self._workflow_id

    def text(self) -> str:
        """Return the workflow tab label."""

        return self._text

    def setRouteKey(self, key: str) -> None:
        """Replace the workflow route key."""

        self._workflow_id = key

    def setText(self, text: str) -> None:
        """Replace the workflow tab label."""

        self._text = text


class _TabBar:
    """Workflow tab bar double that records silent selection."""

    def __init__(self, workflow_ids: tuple[str, ...]) -> None:
        """Create tab items for workflow ids."""

        self.items = [_TabItem(workflow_id) for workflow_id in workflow_ids]
        self.itemMap = {item.routeKey(): item for item in self.items}
        self.selected: list[tuple[str, bool]] = []

    def addTab(self, routeKey: str, text: str) -> _TabItem:
        """Add a workflow tab item."""

        item = _TabItem(routeKey)
        item.setText(text)
        self.items.append(item)
        self.itemMap[routeKey] = item
        return item

    def count(self) -> int:
        """Return current tab count."""

        return len(self.items)

    def currentIndex(self) -> int:
        """Return selected tab index."""

        if not self.selected:
            return 0
        return self.workflow_ids_in_order().index(self.selected[-1][0])

    def tabItem(self, index: int) -> _TabItem:
        """Return a tab item by index."""

        return self.items[index]

    def workflow_ids_in_order(self) -> list[str]:
        """Return workflow ids in visual order."""

        return [item.routeKey() for item in self.items]

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record workflow selection."""

        self.selected.append((workflow_id, emit))

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Remove a workflow tab item."""

        del emit
        item = self.itemMap.pop(workflow_id)
        self.items.remove(item)


class _EditorPanel(QWidget):
    """Projection-aware editor widget for measured profile switching."""

    def __init__(self, clean_workflow_ids: set[str]) -> None:
        """Store which workflows are already projected cleanly."""

        super().__init__()
        self._clean_workflow_ids = clean_workflow_ids
        self.load_calls: list[str] = []

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: list[tuple[str, object]],
        cube_states: dict[str, CubeState],
        stack_order: list[str],
    ) -> object:
        """Return a deterministic signature for one workflow projection."""

        del cube_entries, cube_states, stack_order
        return workflow_id

    def is_projection_clean(self, signature: object) -> bool:
        """Return whether the signature is already cleanly projected."""

        return str(signature) in self._clean_workflow_ids

    def refresh_clean_projection(self, **kwargs: object) -> None:
        """Accept lightweight clean projection refreshes."""

        del kwargs

    def clear_model_field_load_progress(self) -> None:
        """Accept generation-feedback cleanup during workflow activation."""

    def load_all_cubes(self, **kwargs: object) -> None:
        """Record full editor rebuilds and complete synchronously."""

        workflow_id = str(kwargs.get("projection_signature", ""))
        self.load_calls.append(workflow_id)
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()


class _OverrideManager:
    """Override-manager profile double for route switching."""

    def detach_override_widgets(self) -> None:
        """Accept outgoing workflow toolbar detachment."""

    def _clear_all_override_widgets(self) -> None:
        """Accept outgoing workflow toolbar cleanup."""

    def dispose(self) -> None:
        """Accept workflow close disposal."""


class _WorkflowCanvasProjectionCoordinator:
    """Workflow canvas projection profile double with distinct workflow projections."""

    def __init__(self) -> None:
        """Initialize projection state logs."""

        self.projected_workflow_ids: list[str] = []

    def project_workflow(self, workflows: object, active_workflow_id: str) -> None:
        """Record shared canvas route projection for one workflow."""

        del workflows
        self.projected_workflow_ids.append(active_workflow_id)

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: object,
        remaining_workflows: object,
    ) -> None:
        """Accept closed-workflow canvas pruning."""

        del closed_workflow_id, closed_workflow, remaining_workflows


class _Scheduler:
    """Deferred refresh scheduler double that records requests."""

    def __init__(self) -> None:
        """Initialize empty request storage."""

        self.requests: list[str] = []

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: object = None,
    ) -> None:
        """Record deferred reconciliation requests."""

        del force_refresh, reason, on_complete
        self.requests.append(workflow_id)

    def cancel(self, workflow_id: str | None = None) -> None:
        """Clear pending requests for compatibility."""

        if workflow_id is None:
            self.requests.clear()
            return
        self.requests = [request for request in self.requests if request != workflow_id]


class _ProfileView:
    """Qt-backed workflow workspace view for measured profile switching."""

    def __init__(self) -> None:
        """Create a controlled three-workflow route surface."""

        self.workflow_tab_service = WorkflowTabService()
        self.workflow_session_service = WorkflowSessionService(
            WorkflowState,
            default_workflow_id="wf-a",
        )
        self.workflow_session_service.add_workflow("wf-b")
        self.workflow_session_service.add_workflow("wf-c")
        for index, workflow_id in enumerate(("wf-a", "wf-b", "wf-c"), start=1):
            workflow = self.workflow_session_service.workflows[workflow_id]
            cube_alias = f"Cube {index}"
            workflow.cubes[cube_alias] = CubeState(
                cube_id=f"Profile/Workflow/{workflow_id}.cube",
                version="1.0.0",
                alias=cube_alias,
                original_cube={},
                buffer={"nodes": {"Profile": {"inputs": {"workflow": workflow_id}}}},
            )
            workflow.stack_order.append(cube_alias)
            workflow.metadata["profile_output_source"] = f"output-{workflow_id}.png"
        self.workflow_session_service.activate_workflow("wf-c")
        self.workflow_tabbar = _TabBar(("wf-a", "wf-b", "wf-c"))
        self.workflow_canvas_projection_coordinator = (
            _WorkflowCanvasProjectionCoordinator()
        )
        self.cube_stack_container = QStackedWidget()
        self.editor_panel_container = QStackedWidget()
        self.cube_stacks = {
            workflow_id: QWidget() for workflow_id in ("wf-a", "wf-b", "wf-c")
        }
        clean_workflow_ids = {"wf-a", "wf-b"}
        self.editor_panels = {
            workflow_id: _EditorPanel(clean_workflow_ids)
            for workflow_id in ("wf-a", "wf-b", "wf-c")
        }
        self.override_managers = {
            workflow_id: _OverrideManager() for workflow_id in ("wf-a", "wf-b", "wf-c")
        }
        for workflow_id in ("wf-a", "wf-b", "wf-c"):
            self.cube_stack_container.addWidget(self.cube_stacks[workflow_id])
            self.editor_panel_container.addWidget(self.editor_panels[workflow_id])
        self.cube_stack_container.setCurrentWidget(self.cube_stacks["wf-c"])
        self.editor_panel_container.setCurrentWidget(self.editor_panels["wf-c"])
        self._active_workspace_route = "wf-c"
        self.input_availability_refreshes: list[str] = []
        self.progress_projection_count = 0
        self.generation_action_controller = SimpleNamespace(
            project_active_workflow_progress=lambda: None,
        )

    def _create_new_workflow_ui(
        self,
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Reject unexpected widget materialization in the profile route."""

        raise AssertionError((workflow_id, set_as_current))

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Return existing workflow widgets."""

        del set_as_current
        return self.cube_stacks[workflow_id], self.editor_panels[workflow_id]

    @property
    def active_editor_panel(self) -> _EditorPanel | None:
        """Return no panel for floating search geometry in the profile harness."""

        return None

    def show_workflow_workspace(self) -> None:
        """Accept route-container workflow projection."""

    def set_active_workspace_route(self, workflow_id: str) -> None:
        """Record the active workspace route."""

        self._active_workspace_route = workflow_id

    def position_search_box(self) -> None:
        """Accept lightweight overlay positioning."""

    def refresh_editor_busy_overlay(self) -> None:
        """Accept busy overlay refresh."""

    def refresh_input_canvas_availability(self) -> None:
        """Record input-canvas availability refresh for active workflow."""

        self.input_availability_refreshes.append(
            self.workflow_session_service.active_workflow_id
        )

    def project_active_workflow_progress(self) -> None:
        """Record active workflow progress projection during route changes."""

        self.progress_projection_count += 1

    def _clear_all_model_field_load_progress(self) -> None:
        """Accept model-load progress clearing."""


def _app() -> QApplication:
    """Return a QApplication for the Qt-backed profile view."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def build_profile_artifact() -> ProfileArtifact:
    """Run a measured local profile sequence and return artifact rows."""

    _app()
    view = _ProfileView()
    scheduler = _Scheduler()
    coordinator = WorkflowWorkspaceCoordinator(
        cast(WorkflowWorkspaceView, view),
        surface_refresh_scheduler=scheduler,
    )
    shell_logger = logging.getLogger("sugarsubstitute.presentation.shell")
    info_counter = _InfoCountingHandler()
    shell_logger.addHandler(info_counter)
    runs: list[ProfileRun] = []
    try:
        for workflow_id in SWITCH_SEQUENCE:
            request_count_before = len(scheduler.requests)
            info_count_before = info_counter.count
            coordinator.activate_workflow(workflow_id, source="workflow_tab")
            diagnostic = coordinator.last_tab_switch_diagnostic
            if diagnostic is None:
                raise RuntimeError(f"missing diagnostic for {workflow_id}")
            editor = view.editor_panels[workflow_id]
            runs.append(
                {
                    "workflow_id": workflow_id,
                    "route_ms": diagnostic.route_projection_elapsed_ms,
                    "canvas_ms": diagnostic.canvas_projection_elapsed_ms,
                    "ensure_workflow_ui_ms": (diagnostic.ensure_workflow_ui_elapsed_ms),
                    "show_route_ms": diagnostic.show_route_elapsed_ms,
                    "tab_select_ms": diagnostic.tab_select_elapsed_ms,
                    "cube_stack_swap_ms": diagnostic.cube_stack_swap_elapsed_ms,
                    "editor_panel_swap_ms": diagnostic.editor_panel_swap_elapsed_ms,
                    "override_projection_ms": (
                        diagnostic.override_projection_elapsed_ms
                    ),
                    "input_canvas_availability_ms": (
                        diagnostic.input_canvas_availability_elapsed_ms
                    ),
                    "overlay_refresh_ms": diagnostic.overlay_refresh_elapsed_ms,
                    "activity_badge_ms": diagnostic.activity_badge_elapsed_ms,
                    "overrides_projected": diagnostic.overrides_projected,
                    "widgets_created": diagnostic.widgets_created,
                    "editor_rebuilt": bool(editor.load_calls),
                    "deferred_requests": len(scheduler.requests) - request_count_before,
                    "info_logs": info_counter.count - info_count_before,
                }
            )
    finally:
        shell_logger.removeHandler(info_counter)
    return {
        "runs": runs,
        "workflow_tab_reorder_supported": False,
    }


def write_profile_artifacts(root: Path = ARTIFACT_ROOT) -> None:
    """Write profile session scaffolding, latest JSON, and run manifest."""

    session_path = root / "generated_session"
    session_path.mkdir(parents=True, exist_ok=True)
    latest_path = root / "latest.json"
    manifest_path = root / "run_manifest.json"
    placeholder_images = session_path / "placeholder_images"
    placeholder_images.mkdir(parents=True, exist_ok=True)
    for workflow_id in ("wf-a", "wf-b", "wf-c"):
        (placeholder_images / f"{workflow_id}.txt").write_text(
            f"profile placeholder for {workflow_id}\n",
            encoding="utf-8",
        )
    (session_path / "session_manifest.json").write_text(
        json.dumps(
            {
                "workflow_ids": ["wf-a", "wf-b", "wf-c"],
                "distinct_editor_content": True,
                "distinct_canvas_state": True,
                "materialized_unprojected_workflow": "wf-c",
                "generation_output_history": ["output-wf-a.png"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact = build_profile_artifact()
    latest_path.write_text(
        json.dumps(artifact, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "generated_session_path": str(session_path),
                "launch_command": ".\\.venv\\Scripts\\python.exe main.py",
                "switch_sequence": list(SWITCH_SEQUENCE),
                "validation_steps": [
                    "Open the generated profile session.",
                    "Switch wf-a -> wf-b -> wf-c -> wf-a -> wf-c -> wf-b.",
                    "Confirm editor, cube stack, input canvas, and output canvas "
                    "track the selected workflow.",
                    "Inspect DEBUG route timing and INFO log count.",
                ],
                "observed_route_ms": [run["route_ms"] for run in artifact["runs"]],
                "observed_canvas_ms": [run["canvas_ms"] for run in artifact["runs"]],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    LOGGER.info(
        "workflow tab profile artifacts written",
        extra={"artifact_root": str(root), "session_path": str(session_path)},
    )


def main() -> None:
    """Create profile artifacts for manual workflow-tab validation."""

    logging.basicConfig(level=logging.INFO)
    write_profile_artifacts()


if __name__ == "__main__":
    main()
