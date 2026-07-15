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

"""Compose the production-like shell infrastructure for Output canvas scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)

from substitute.application.generation import (
    VisualAuthorizationService,
    WorkflowProgressService,
)
from substitute.application.workflows import WorkflowSessionService
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.workflow import ImageMeta, WorkflowState
from substitute.presentation.shell.generation_feedback_coalescer import (
    GenerationFeedbackCoalescer,
)
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_feedback_dispatcher import (
    GenerationFeedbackDispatcher,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    GenerationFeedbackPresenter,
)
from substitute.presentation.shell.generation_feedback_sink import (
    ShellGenerationFeedbackSink,
)
from substitute.presentation.shell.main_window_composition import (
    compose_output_canvas_controllers,
)
from substitute.presentation.shell.main_window_dependencies import (
    InstallationPathBundle,
)
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)
from substitute.presentation.shell.main_window_workspace import (
    build_main_window_workspace,
)
from substitute.presentation.shell.workspace_canvas_actions import (
    WorkspaceCanvasActions,
)
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.ui_load_activity import (
    default_prompt_projection_ui_load_activity,
)


class _HarnessShell(QMainWindow):
    """Own the real canvas workspace and output feedback chain under test."""

    progress_update_signal = Signal(float, object)
    resize_requested = Signal(int)
    clear_output_signal = Signal(str)
    preview_image_signal = Signal(object)
    add_output_image_signal = Signal(str, QImage, object)
    canvas_tabs: Any
    generation_feedback_dispatcher: GenerationFeedbackDispatcher
    output_canvas: Any
    output_canvas_projection_coordinator: Any
    output_image_pipeline: Any
    workflow_tabbar: Any
    workflow_workspace: WorkflowWorkspaceCoordinator

    def __init__(self, canvas_io_service: "_CanvasIoService") -> None:
        """Build the real workspace scaffold and output controllers."""

        super().__init__()
        self.execution_runtime = ExecutionRuntime()
        self.canvas_io_service = canvas_io_service
        self.path_bundle = _path_bundle()
        self.output_preview_registry = OutputPreviewRegistry()
        self.visual_authorization_service = VisualAuthorizationService()
        self.workflow_progress_service = WorkflowProgressService()
        self.prompt_interaction_activity_tracker = _PromptInteractionTracker()
        self.generation_job_queue_service = _GenerationJobQueueService()
        self.workflow_surface_invalidation_service = (
            WorkflowSurfaceInvalidationService()
        )
        self.workflow_activity_service = SimpleNamespace(
            record_output=lambda *_args, **_kwargs: False
        )
        self.progressOverlay = QWidget()
        self.workflowOverlayBar = _ProgressBar()
        self.samplerOverlayBar = _ProgressBar()
        self.progress_overlay_controller = SimpleNamespace(
            position_progress_overlay=lambda *_args, **_kwargs: None
        )
        self.generation_progress_strip_registry = SimpleNamespace(
            apply_progress_view=lambda *_args, **_kwargs: None
        )
        self.generation_action_controller = GenerationActionController(self)
        self.settings_route_controller = SimpleNamespace(
            show_workflow_workspace=lambda *_args, **_kwargs: None
        )
        self.search_overlay_controller = SimpleNamespace(
            position_search_box=lambda *_args, **_kwargs: None
        )
        self.editor_busy = SimpleNamespace(
            refresh_active_surface=lambda *_args, **_kwargs: None
        )
        self.output_scene_run_service = SimpleNamespace(run_for_id=lambda _run_id: None)
        self._comfy_output_stream = TerminalOutputStream(max_lines=50)
        self._taskbar_progress_presenter = SimpleNamespace(
            clear_progress=lambda: None,
            set_progress=lambda _value: None,
        )
        self.cube_stacks: dict[str, QWidget] = {}
        self.editor_panels: dict[str, object] = {}
        self.override_managers: dict[str, object] = {}
        self._pending_restored_workflow_snapshots: dict[str, object] = {}
        self.generationActionCluster = None
        self.error_reports: list[object] = []

        self.workspace_canvas_actions = WorkspaceCanvasActions(
            cast(Any, self),
            error_presenter=_ErrorPresenter(self.error_reports),
        )
        self._menu_container = QWidget()
        self._menu_container.setLayout(QHBoxLayout())
        workspace_parts = build_main_window_workspace(
            self,
            backdrop_mode=None,
            menu_container=self._menu_container,
            comfy_output_stream=self._comfy_output_stream,
            output_preview_registry=self.output_preview_registry,
            open_single_external_editor=(
                self.workspace_canvas_actions.open_image_in_external_editor
            ),
            open_all_external_editor=(
                self.workspace_canvas_actions.open_images_in_external_editor
            ),
        )
        self.workflow_tab_service = workspace_parts.workflow_tab_service
        self.workflow_session_service: WorkflowSessionService[WorkflowState] = cast(
            WorkflowSessionService[WorkflowState],
            workspace_parts.workflow_session_service,
        )
        self.workflow_tabbar = workspace_parts.workflow_tabbar
        self.canvas_tabs = workspace_parts.canvas_tabs
        self.cube_stack_container: QStackedWidget = workspace_parts.cube_stack_container
        self.editor_panel_container: QStackedWidget = (
            workspace_parts.editor_panel_container
        )
        self.input_canvas_state_service = workspace_parts.input_canvas_state_service
        self.output_canvas_state_service = workspace_parts.output_canvas_state_service
        self.output_canvas_projection_coordinator = (
            workspace_parts.output_canvas_projection_coordinator
        )
        self.workflow_canvas_projection_coordinator = (
            workspace_parts.workflow_canvas_projection_coordinator
        )
        self.canvas_image_registry = workspace_parts.canvas_image_registry
        self.output_floating_chrome_factory = (
            workspace_parts.output_floating_chrome_factory
        )
        self.output_canvas = self.canvas_tabs.canvas_map["Output"]
        self.workflow_workspace = WorkflowWorkspaceCoordinator(
            cast(WorkflowWorkspaceView, self)
        )
        compose_output_canvas_controllers(self)
        self.generation_feedback_presenter = GenerationFeedbackPresenter(self)
        self.generation_feedback_sink = ShellGenerationFeedbackSink(self)
        self.generation_feedback_dispatcher = GenerationFeedbackDispatcher(
            sink=self.generation_feedback_sink,
            coalescer=GenerationFeedbackCoalescer(
                _workflow_progress=self.workflow_progress_service,
                _visual_authorization=self.visual_authorization_service,
            ),
            idle_flush_interval_ms=1,
            active_prompt_flush_interval_ms=1,
            output_activity_marker=lambda reason: (
                default_prompt_projection_ui_load_activity().mark_output_activity(
                    reason=reason
                )
            ),
        )
        self.main_window_signal_binder = MainWindowSignalBinder(self)
        self.main_window_signal_binder.connect_generation_feedback_signals()
        self.main_window_signal_binder.connect_canvas_signals(
            input_canvas=self.canvas_tabs.canvas_map["Input"],
            output_canvas=self.output_canvas,
        )
        self.canvas_tabs.focus_attached_canvas("Output")

    def install_workflow_surface(self, workflow_id: str) -> None:
        """Install cached workflow widgets used by coordinator route switching."""

        cube_stack = self.cube_stacks.get(workflow_id)
        if cube_stack is None:
            cube_stack = QWidget()
            cube_stack.setObjectName(f"{workflow_id}-cube-stack")
            self.cube_stacks[workflow_id] = cube_stack
            self.cube_stack_container.addWidget(cube_stack)
        editor_panel = self.editor_panels.get(workflow_id)
        if editor_panel is None:
            editor_widget = _EditorPanel()
            editor_widget.setObjectName(f"{workflow_id}-editor-panel")
            self.editor_panels[workflow_id] = editor_widget
            self.editor_panel_container.addWidget(editor_widget)

    @property
    def active_editor_panel(self) -> object | None:
        """Return no editor panel; Output canvas tests do not build editors."""

        return None

    def get_active_workflow(self) -> WorkflowState | None:
        """Return the active workflow state."""

        return self.workflow_session_service.get_workflow(
            self.workflow_session_service.active_workflow_id
        )

    def _resolve_workflow_name(self, workflow_id: str) -> str:
        """Return the workflow display name used by output metadata."""

        workflow = self.workflow_session_service.get_workflow(workflow_id)
        if workflow is None:
            return workflow_id
        value = workflow.metadata.get("name", workflow_id)
        return str(value)

    def request_session_autosave(self) -> None:
        """Ignore autosave requests in the real-shell harness."""


class _CanvasIoService:
    """Provide deterministic image loading and metadata for fake outputs."""

    def __init__(self) -> None:
        """Create an empty in-memory image store."""

        self._images_by_path: dict[Path, QImage] = {}

    def store_image(self, path: Path, image: QImage) -> None:
        """Store one image under the fake generated path."""

        self._images_by_path[path] = image

    def load_output_image(self, source_path: Path) -> QImage | None:
        """Return a copy of a generated output image."""

        image = self._images_by_path.get(source_path)
        return None if image is None else image.copy()

    def resolve_node_meta_title(self, node_data: object) -> str:
        """Resolve a node title from a Comfy-like workflow payload."""

        if isinstance(node_data, Mapping):
            meta = node_data.get("_meta")
            if isinstance(meta, Mapping):
                title = meta.get("title")
                if isinstance(title, str) and title:
                    return title
        return "save-image"

    def resolve_workflow_label(self, metadata: object) -> str:
        """Resolve workflow label from workflow metadata."""

        if isinstance(metadata, Mapping):
            name = metadata.get("name")
            if isinstance(name, str) and name:
                return name
        return "Workflow"

    def build_output_image_metadata(
        self,
        *,
        workflow_name: str,
        node_meta_title: str,
        file_path: Path,
        source_key: str = "",
        source_label: str = "",
        node_id: str = "",
        list_index: int | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
        scene_run_id: str | None = None,
        scene_key: str | None = None,
        scene_title: str | None = None,
        scene_order: int | None = None,
        scene_count: int | None = None,
        width: int | None = None,
        height: int | None = None,
        cube_execution_duration_ms: float | None = None,
    ) -> ImageMeta:
        """Build domain metadata matching production output registration."""

        return ImageMeta(
            workflow_name=workflow_name,
            cube_name=source_label or node_meta_title,
            image_number=(list_index or 0) + 1,
            suffix="",
            path=str(file_path),
            source_key=source_key,
            source_label=source_label,
            node_id=node_id,
            generation_run_id=generation_run_id or "",
            prompt_id=prompt_id or "",
            client_id=client_id or "",
            scene_run_id=scene_run_id or "",
            scene_key=scene_key or "",
            scene_title=scene_title or "",
            scene_order=scene_order,
            scene_count=scene_count,
            width=width,
            height=height,
            list_index=list_index,
            cube_execution_duration_ms=cube_execution_duration_ms,
        )

    def open_image_in_external_editor(
        self, *, image: object, image_meta: object
    ) -> bool:
        """Decline external editor requests in tests."""

        _ = (image, image_meta)
        return False

    def open_images_in_external_editor(
        self,
        *,
        images: list[tuple[object, object]],
    ) -> bool:
        """Decline external editor requests in tests."""

        _ = images
        return False


class _GenerationJobQueueService:
    """Provide the generation queue surface used by the output pipeline."""

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Return no timing data for generated output metadata."""

        _ = (workflow_id, source_key, cube_alias)
        return None


class _ProgressBar:
    """Store progress-bar calls made by the real generation action controller."""

    def __init__(self) -> None:
        """Initialize deterministic progress state."""

        self.value = 0
        self.use_animation = True

    def setValue(self, value: int) -> None:
        """Store the latest projected progress value."""

        self.value = value

    def setUseAni(self, enabled: bool) -> None:
        """Store the requested animation state."""

        self.use_animation = enabled

    def isUseAni(self) -> bool:
        """Return the current animation state."""

        return self.use_animation


class _EditorPanel(QWidget):
    """Provide editor-panel progress APIs touched during workflow activation."""

    def clear_model_field_load_progress(self) -> None:
        """Ignore model-field progress clearing in Output canvas tests."""

    def set_model_field_load_progress(self, **_kwargs: object) -> None:
        """Ignore model-field progress updates in Output canvas tests."""


class _PromptInteractionTracker:
    """Provide inactive prompt-interaction scheduling state."""

    def is_prompt_interaction_active(self) -> bool:
        """Return that prompt interaction is inactive."""

        return False

    def ms_since_last_prompt_interaction(self) -> int:
        """Return a stable elapsed interaction value."""

        return 0


class _ErrorPresenter:
    """Record structured error reports without opening modal dialogs."""

    def __init__(self, reports: list[object]) -> None:
        """Store the shared report list."""

        self._reports = reports

    def show_error_report(self, report: object) -> None:
        """Record one report for harness assertions."""

        self._reports.append(report)


def _path_bundle() -> InstallationPathBundle:
    """Return deterministic local paths for shell collaborators."""

    root = Path("E:/devprojects/SugarSubstitute").resolve()
    return InstallationPathBundle(
        install_root=root,
        user_dir=root / ".tmp-user",
        projects_dir=root / ".tmp-projects",
        outputs_dir=root / ".tmp-outputs",
        sugar_scripts_dir=root / ".tmp-scripts",
        wildcards_dir=root / ".tmp-wildcards",
        managed_comfy_dir=root / ".tmp-comfy",
    )


def _ensure_qapp() -> QApplication:
    """Return the active QApplication or create one."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
