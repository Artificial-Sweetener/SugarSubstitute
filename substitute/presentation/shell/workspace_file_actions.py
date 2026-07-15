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

"""Handle workspace save, load, and export flows in the shell layer."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from inspect import signature
from pathlib import Path
from typing import Any, Protocol, cast

from PySide6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.errors import (
    SubstituteOperationContext,
    build_cube_library_drift_report,
)
from substitute.application.generation import (
    RecipeOutputSibling,
    RecipeOutputSiblingDiscoveryResult,
)
from substitute.application.workflows import (
    is_default_workflow_tab_label,
    normalize_default_workflow_tab_label,
)
from substitute.application.recipes import (
    RecipeModelLoadResolver,
    RecipeModelResolutionRequired,
)
from substitute.application.model_metadata import (
    BackendModelDownloadJob,
    ModelDownloadStatus,
)
from substitute.presentation.shell.recipe_model_resolution_flow import (
    DeferredRecipeModelDownload,
)
from substitute.presentation.errors import ErrorPresenter, ErrorReportPresenterProtocol
from substitute.presentation.shell.cube_loader import (
    CubeLoadPresentationIntent,
    CubeLoadUiCallbacks,
    load_cube_async,
)
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
    EditorBusyDownloadState,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    CUBE_STRUCTURE_SURFACES,
    WorkflowInvalidationReason,
)
from substitute.presentation.shell.workflow_snapshot_materialization import (
    SnapshotMaterializationView,
    WorkflowSnapshotMaterializer,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_debug
from substitute.shared.logging.logger import log_info, log_warning

_LOGGER = get_logger("presentation.shell.workspace_file_actions")


def _mark_recipe_surfaces_dirty(view: object, workflow_id: str) -> None:
    """Record recipe-load maintenance intent when the shell exposes tracking."""

    service = getattr(view, "workflow_surface_invalidation_service", None)
    mark_dirty = getattr(service, "mark_dirty", None)
    if callable(mark_dirty):
        mark_dirty(
            workflow_id,
            CUBE_STRUCTURE_SURFACES,
            WorkflowInvalidationReason.RECIPE_LOADED,
        )


class WorkflowTabItemProtocol(Protocol):
    """Describe workflow-tab item operations used by file actions."""

    def text(self) -> str:
        """Return the current tab label."""

    def routeKey(self) -> str:
        """Return the workflow route key."""

    def setText(self, text: str) -> None:
        """Update the tab label."""


class WorkflowTabBarProtocol(Protocol):
    """Describe workflow-tab bar behavior used by file actions."""

    itemMap: Mapping[str, WorkflowTabItemProtocol]

    def currentIndex(self) -> int:
        """Return the current tab index."""

    def tabItem(self, index: int) -> WorkflowTabItemProtocol:
        """Return the tab item at index."""


class RecipeIoServiceProtocol(Protocol):
    """Describe recipe IO operations used by workspace file actions."""

    def build_default_recipe_path(
        self, workflow_name: str, sugar_scripts_dir: Path
    ) -> Path:
        """Build the canonical recipe path for one workflow name."""

    def validate_recipe_destination(
        self,
        destination_path: Path,
    ) -> Path:
        """Validate a user-selected recipe destination."""

    def save_workflow_recipe_to_default_path(
        self,
        workflow_name: str,
        workflow: object,
        sugar_scripts_dir: Path,
        *,
        global_override_scopes: Mapping[str, object] | None = None,
    ) -> Path:
        """Persist the active workflow to its canonical script path."""

    def save_workflow_recipe(
        self,
        destination_path: Path,
        *,
        workflow_name: str,
        workflow: object,
        global_override_scopes: Mapping[str, object] | None = None,
    ) -> None:
        """Persist the active workflow recipe."""

    def serialize_workflow_to_sugar_script(
        self,
        workflow: object,
        *,
        global_override_scopes: Mapping[str, object] | None = None,
    ) -> str:
        """Serialize workflow state for export."""

    def load_and_parse_recipe_document(
        self,
        source_path: Path,
    ) -> ParsedRecipeProtocol:
        """Load and parse a recipe document."""

    def parse_recipe_script(self, sugar_script_text: str) -> ParsedRecipeScriptProtocol:
        """Parse Sugar script text into recipe buffers."""


class WorkflowExportServiceProtocol(Protocol):
    """Describe workflow export operations used by file actions."""

    def build_default_export_path(self, workflow_name: str, output_dir: Path) -> Path:
        """Build the canonical workflow export path for one workflow name."""

    def validate_export_destination(
        self,
        destination_path: Path,
    ) -> Path:
        """Validate a user-selected workflow export destination."""

    def export_workflow_json(
        self,
        *,
        destination_path: Path,
        sugar_script_text: str,
        output_dir: Path,
        workflow: object | None = None,
    ) -> None:
        """Export sugar script to a Comfy workflow document."""


class WorkflowSessionServiceProtocol(Protocol):
    """Describe workflow session operations used by file actions."""

    workflows: dict[str, "WorkflowStateProtocol"]
    active_workflow_id: str

    def get_workflow(self, workflow_id: str) -> "WorkflowStateProtocol | None":
        """Return workflow state for one workflow id."""


class CubeStackProtocol(Protocol):
    """Describe cube-stack behavior used by load flow."""

    items: list[object]

    def count(self) -> int:
        """Return number of cube tabs."""

    def clear(self) -> None:
        """Remove all cube tabs."""

    def insertTab(self, index: int, **kwargs: object) -> object:
        """Insert a cube tab and return the created tab item."""

    def setCurrentIndex(self, index: int) -> None:
        """Select the current cube tab."""


class EditorPanelProtocol(Protocol):
    """Describe editor-panel behavior used by load flow."""

    def clear_layout(self) -> None:
        """Remove rendered cube widgets."""


class OverrideManagerProtocol(Protocol):
    """Describe override-manager behavior used by load flow."""

    def apply_global_overrides(self) -> None:
        """Apply active global overrides into workflow and UI state."""

    def current_serialization_scopes(self) -> Mapping[str, object] | None:
        """Return active SugarScript serialization scopes when available."""


class CanvasIoServiceProtocol(Protocol):
    """Describe canvas IO operations used by file actions."""

    def load_recipe_preview_image(self, source_path: Path) -> object | None:
        """Load one PNG recipe preview image from disk."""

    def build_output_image_metadata(
        self,
        *,
        workflow_name: str,
        node_meta_title: str,
        file_path: Path,
        source_key: str = "",
        source_label: str = "",
        scene_run_id: str | None = None,
        scene_key: str | None = None,
        scene_title: str | None = None,
        scene_order: int | None = None,
        scene_count: int | None = None,
        width: int | None = None,
        height: int | None = None,
        cube_execution_duration_ms: float | None = None,
    ) -> object:
        """Build metadata for one output image."""


class OutputImageRegistrarProtocol(Protocol):
    """Describe Output image materialization used by recipe PNG restore."""

    def add_output_image(
        self,
        workflow_id: str,
        image: object,
        image_meta: object,
    ) -> None:
        """Register one Output image and schedule any required projection."""


class WorkflowStateProtocol(Protocol):
    """Describe workflow state data consumed by workspace file actions."""

    cubes: dict[str, object]
    stack_order: list[str]
    global_overrides: dict[str, object]
    global_override_selections: dict[str, bool]
    override_control_states: dict[str, object]


class WorkspacePathBundleProtocol(Protocol):
    """Describe shell path roots used by file actions."""

    projects_dir: Path
    sugar_scripts_dir: Path


class ActiveWorkflowSurfaceRefresherProtocol(Protocol):
    """Describe structural active workflow surface reconciliation."""

    def refresh_active_workflow_surface(self) -> None:
        """Refresh active workflow surfaces after node-definition changes."""


class FileDialogProtocol(Protocol):
    """Describe file-dialog operations used by file actions."""

    def getSaveFileName(
        self,
        parent: object,
        caption: str,
        directory: str,
        filter: str = "",
    ) -> tuple[str, str]:
        """Return selected save path and filter."""

    def getOpenFileName(
        self,
        parent: object,
        caption: str,
        directory: str,
        filter: str = "",
    ) -> tuple[str, str]:
        """Return selected open path and filter."""


class MessageBoxProtocol(Protocol):
    """Describe message-box operations used by file actions."""

    def critical(self, parent: object, title: str, text: str) -> None:
        """Show a critical dialog."""


_DEFAULT_FILE_DIALOG: FileDialogProtocol = cast(FileDialogProtocol, QFileDialog)
_DEFAULT_MESSAGE_BOX: MessageBoxProtocol = cast(MessageBoxProtocol, QMessageBox)


class CubeLibraryManagementServiceProtocol(Protocol):
    """Describe Cube Library diagnostics used during recipe load."""

    def recipe_drift_messages(
        self,
        buffers: Mapping[str, Mapping[str, object]],
    ) -> tuple[str, ...]:
        """Return user-facing recipe cube drift notices."""


class IconTokenProtocol(Protocol):
    """Describe icon token behavior used for placeholder cube tabs."""

    def icon(self) -> object:
        """Return concrete icon payload."""


class RecipeOutputSiblingDiscoveryProtocol(Protocol):
    """Describe output sibling discovery used after loading recipe PNGs."""

    def discover_for_recipe_png(
        self,
        selected_path: Path,
        *,
        workflow_name: str,
    ) -> RecipeOutputSiblingDiscoveryResult:
        """Return same-folder output siblings for one recipe-bearing PNG."""


class CubeIconProviderProtocol(Protocol):
    """Describe the icon subset used for placeholder cube tabs."""

    CLOSE: IconTokenProtocol


class CubeLoaderProtocol(Protocol):
    """Describe async cube-loader entrypoint used by load flow."""

    def __call__(
        self,
        callbacks: CubeLoadUiCallbacks,
        *,
        cube_id: str,
        alias_name: str,
        placeholder_index: int,
        buffer_patch: dict[str, object] | None = None,
        reveal_after_load: bool = True,
        presentation_intent: CubeLoadPresentationIntent | None = None,
        on_load_finished: Callable[[str | None], None] | None = None,
    ) -> None:
        """Queue one cube for async load."""


class ParsedRecipeProtocol(Protocol):
    """Describe parsed recipe payload used by load flow."""

    loaded_document: object
    parsed_script: object


class LoadedRecipeDocumentProtocol(Protocol):
    """Describe recipe document metadata used during load."""

    source_path: Path
    source_kind: str


class ParsedRecipeScriptProtocol(Protocol):
    """Describe parsed script content needed by load flow."""

    buffers: Mapping[str, dict[str, object]]
    global_overrides: dict[str, object]
    global_override_selections: dict[str, bool]
    field_control_states_by_alias: Mapping[str, Mapping[str, Mapping[str, object]]]
    override_control_states: Mapping[str, object]
    project_name: str | None


class RecipeModelResolutionSummaryProtocol(Protocol):
    """Describe recipe model resolution counters used for diagnostics."""

    @property
    def literal_matches(self) -> int:
        """Return literal model references resolved."""

    @property
    def hash_matches(self) -> int:
        """Return hash model references resolved."""

    @property
    def unresolved_hashes(self) -> int:
        """Return hash references that still require resolution."""


class ResolvedRecipeModelScriptProtocol(Protocol):
    """Describe a resolved recipe script and its diagnostic summary."""

    parsed_script: ParsedRecipeScriptProtocol
    summary: RecipeModelResolutionSummaryProtocol


class _RecipeModelResolutionCancelled(RuntimeError):
    """Raised when the user cancels missing recipe model resolution."""


class _ExecutionCallbackDispatcher(Protocol):
    """Describe completion/progress dispatchers used by execution routes."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Publish one callback through the route's owner boundary."""


@dataclass
class _ActiveRecipeModelDownload:
    """Keep one async recipe model download alive until completion."""

    cancellation: CancellationSource
    busy_token: object
    close_route: Callable[[], None]


@dataclass(frozen=True)
class RecipeModelResolutionRoute:
    """Carry the execution route for pre-materialization recipe model resolution."""

    submitter: TaskSubmitter
    close: Callable[[], None]


class RecipeModelResolutionRouteFactory(Protocol):
    """Create a recipe model resolution route for one workflow request."""

    def __call__(
        self,
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> RecipeModelResolutionRoute:
        """Return the route used to resolve recipe model references."""


@dataclass(frozen=True)
class RecipeModelDownloadRoute:
    """Carry the execution collaborators for one deferred model download."""

    submitter: TaskSubmitter
    progress_dispatcher: _ExecutionCallbackDispatcher
    close: Callable[[], None]


class RecipeModelDownloadRouteFactory(Protocol):
    """Create a deferred recipe model download route for one workflow request."""

    def __call__(
        self,
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> RecipeModelDownloadRoute:
        """Return the route used to download and resolve missing recipe models."""


@dataclass(frozen=True)
class _ResolvedRecipePayload:
    """Carry recipe model resolution output normalized for materialization."""

    parsed_script: ParsedRecipeScriptProtocol
    summary: RecipeModelResolutionSummaryProtocol
    deferred_model_download: DeferredRecipeModelDownload | None


class WorkspaceFileActionView(Protocol):
    """Describe the shell surface consumed by workspace file actions."""

    workflow_tabbar: WorkflowTabBarProtocol
    workflow_session_service: WorkflowSessionServiceProtocol
    recipe_io_service: RecipeIoServiceProtocol
    create_recipe_model_load_resolver: Callable[[], RecipeModelLoadResolver] | None
    workflow_export_service: WorkflowExportServiceProtocol
    cube_stacks: dict[str, CubeStackProtocol]
    editor_panels: dict[str, EditorPanelProtocol]
    active_override_manager: OverrideManagerProtocol | None
    canvas_io_service: CanvasIoServiceProtocol
    editor_busy: EditorBusyControllerProtocol
    active_workflow_surface_refresher: ActiveWorkflowSurfaceRefresherProtocol
    _pending_cubes: dict[str, int]
    path_bundle: WorkspacePathBundleProtocol

    def get_active_workflow(self) -> WorkflowStateProtocol:
        """Return the active workflow state."""


class WorkspaceFileActions:
    """Own workspace save, load, and export orchestration."""

    def __init__(
        self,
        view: WorkspaceFileActionView,
        *,
        add_workflow_tab_requested: Callable[[], None],
        build_cube_load_ui_callbacks: Callable[..., CubeLoadUiCallbacks],
        output_image_registrar: OutputImageRegistrarProtocol,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        recipe_output_sibling_discovery_service: (
            RecipeOutputSiblingDiscoveryProtocol | None
        ) = None,
        log_exception_func: Callable[..., None] = log_exception,
        recipe_model_resolution_runner: (
            Callable[[Callable[[], RecipeModelLoadResolver], object], object] | None
        ) = None,
        recipe_model_resolution_handler: (
            Callable[[RecipeModelResolutionRequired], object | None] | None
        ) = None,
        recipe_model_resolution_route_factory: (
            RecipeModelResolutionRouteFactory | None
        ) = None,
        recipe_model_download_route_factory: (
            RecipeModelDownloadRouteFactory | None
        ) = None,
    ) -> None:
        """Store shell view and collaborator callbacks."""

        self._view = view
        self._add_workflow_tab_requested = add_workflow_tab_requested
        self._build_cube_load_ui_callbacks = build_cube_load_ui_callbacks
        self._output_image_registrar = output_image_registrar
        self._error_presenter = error_presenter
        self._recipe_output_sibling_discovery_service = (
            recipe_output_sibling_discovery_service
        )
        self._log_exception = log_exception_func
        self._recipe_model_resolution_runner = recipe_model_resolution_runner
        self._recipe_model_resolution_handler = recipe_model_resolution_handler
        self._recipe_model_resolution_route_factory = (
            recipe_model_resolution_route_factory
        )
        self._recipe_model_download_route_factory = recipe_model_download_route_factory
        self._active_recipe_model_downloads: list[_ActiveRecipeModelDownload] = []
        self._recipe_model_download_request_id = 0
        self._snapshot_materializer = WorkflowSnapshotMaterializer(
            cast(SnapshotMaterializationView, view),
            build_cube_load_ui_callbacks=build_cube_load_ui_callbacks,
        )

    def _projects_dir(self, projects_dir: Path | None) -> Path:
        """Resolve the projects root from explicit input or the shell path bundle."""

        if projects_dir is not None:
            return Path(projects_dir)
        path_bundle = getattr(self._view, "path_bundle", None)
        if path_bundle is not None:
            return Path(path_bundle.projects_dir)
        return Path(".")

    def _sugar_scripts_dir(self, sugar_scripts_dir: Path | None) -> Path:
        """Resolve the Sugar script root from explicit input or the path bundle."""

        if sugar_scripts_dir is not None:
            return Path(sugar_scripts_dir)
        path_bundle = getattr(self._view, "path_bundle", None)
        if path_bundle is not None:
            return Path(path_bundle.sugar_scripts_dir)
        return Path(".")

    def _active_global_override_scopes(self) -> Mapping[str, object] | None:
        """Return active override serialization scopes from the current manager."""

        manager = getattr(self._view, "active_override_manager", None)
        if manager is None:
            log_info(
                _LOGGER,
                "Workspace file action using legacy global override scope",
                reason="missing_active_override_manager",
            )
            return None
        scope_getter = getattr(manager, "current_serialization_scopes", None)
        if not callable(scope_getter):
            log_info(
                _LOGGER,
                "Workspace file action using legacy global override scope",
                reason="missing_scope_getter",
            )
            return None
        scopes = scope_getter()
        return cast(Mapping[str, object] | None, scopes)

    @staticmethod
    def _call_accepts_keyword(
        callable_obj: Callable[..., object], keyword: str
    ) -> bool:
        """Return whether a collaborator method advertises a keyword parameter."""

        try:
            return keyword in signature(callable_obj).parameters
        except (TypeError, ValueError):
            return False

    def on_save_clicked(self, *, sugar_scripts_dir: Path | None = None) -> None:
        """Save the active workflow into its workflow-named script directory."""

        view = self._view
        workflow_name = "untitled_workflow"
        recipe_path: Path | None = None
        resolved_sugar_scripts_dir = self._sugar_scripts_dir(sugar_scripts_dir)
        try:
            workflow_tab_index = view.workflow_tabbar.currentIndex()
            if workflow_tab_index >= 0:
                workflow_name = view.workflow_tabbar.tabItem(workflow_tab_index).text()

            recipe_path = view.recipe_io_service.build_default_recipe_path(
                workflow_name,
                resolved_sugar_scripts_dir,
            )
            active_workflow = view.get_active_workflow()
            global_override_scopes = self._active_global_override_scopes()
            save_default = view.recipe_io_service.save_workflow_recipe_to_default_path
            if global_override_scopes is not None and self._call_accepts_keyword(
                save_default, "global_override_scopes"
            ):
                save_default(
                    workflow_name,
                    workflow=active_workflow,
                    sugar_scripts_dir=resolved_sugar_scripts_dir,
                    global_override_scopes=global_override_scopes,
                )
            else:
                save_default(
                    workflow_name,
                    workflow=active_workflow,
                    sugar_scripts_dir=resolved_sugar_scripts_dir,
                )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            log_context: dict[str, str] = {
                "workflow_name": workflow_name,
                "sugar_scripts_dir": str(resolved_sugar_scripts_dir.resolve()),
            }
            if recipe_path is not None:
                log_context["destination_path"] = str(recipe_path)
            self._log_exception(_LOGGER, "Failed to save recipe", **log_context)

    def on_save_as_clicked(
        self,
        *,
        sugar_scripts_dir: Path | None = None,
        file_dialog: FileDialogProtocol = _DEFAULT_FILE_DIALOG,
    ) -> None:
        """Save the active workflow to a user-selected destination path."""

        view = self._view
        workflow_name = "untitled_workflow"
        destination_path: Path | None = None
        resolved_sugar_scripts_dir = self._sugar_scripts_dir(sugar_scripts_dir)
        try:
            workflow_tab_index = view.workflow_tabbar.currentIndex()
            if workflow_tab_index >= 0:
                workflow_name = view.workflow_tabbar.tabItem(workflow_tab_index).text()

            default_path = view.recipe_io_service.build_default_recipe_path(
                workflow_name,
                resolved_sugar_scripts_dir,
            )
            file_path_str, _ = file_dialog.getSaveFileName(
                view,
                "Save Sugar Script As...",
                str(default_path),
                "Sugar Script (*.sugar)",
            )
            if not file_path_str:
                return

            destination_path = Path(file_path_str).resolve()
            validated_destination_path = (
                view.recipe_io_service.validate_recipe_destination(destination_path)
            )
            active_workflow = view.get_active_workflow()
            global_override_scopes = self._active_global_override_scopes()
            save_recipe = view.recipe_io_service.save_workflow_recipe
            if global_override_scopes is not None and self._call_accepts_keyword(
                save_recipe, "global_override_scopes"
            ):
                save_recipe(
                    validated_destination_path,
                    workflow_name=workflow_name,
                    workflow=active_workflow,
                    global_override_scopes=global_override_scopes,
                )
            else:
                save_recipe(
                    validated_destination_path,
                    workflow_name=workflow_name,
                    workflow=active_workflow,
                )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            log_context: dict[str, str] = {
                "workflow_name": workflow_name,
                "sugar_scripts_dir": str(resolved_sugar_scripts_dir.resolve()),
            }
            if destination_path is not None:
                log_context["destination_path"] = str(destination_path)
            self._log_exception(_LOGGER, "Failed to save recipe as", **log_context)

    def on_export_comfy_workflow_clicked(
        self,
        *,
        output_dir: Path | None = None,
        file_dialog: FileDialogProtocol = _DEFAULT_FILE_DIALOG,
        message_box: MessageBoxProtocol = _DEFAULT_MESSAGE_BOX,
    ) -> None:
        """Export the active workflow to ComfyUI JSON."""

        view = self._view
        workflow_name = "untitled_workflow"
        destination_path: Path | None = None
        resolved_output_dir = self._projects_dir(output_dir)
        try:
            workflow_tab_index = view.workflow_tabbar.currentIndex()
            if workflow_tab_index >= 0:
                workflow_name = view.workflow_tabbar.tabItem(workflow_tab_index).text()

            active_workflow = view.get_active_workflow()
            global_override_scopes = self._active_global_override_scopes()
            serialize = view.recipe_io_service.serialize_workflow_to_sugar_script
            if global_override_scopes is not None and self._call_accepts_keyword(
                serialize, "global_override_scopes"
            ):
                sugar_script = serialize(
                    active_workflow,
                    global_override_scopes=global_override_scopes,
                )
            else:
                sugar_script = serialize(active_workflow)
            default_path = view.workflow_export_service.build_default_export_path(
                workflow_name,
                resolved_output_dir,
            )
            file_path_str, _ = file_dialog.getSaveFileName(
                view,
                "Export ComfyUI Workflow",
                str(default_path),
                "ComfyUI Workflow (*.json)",
            )
            if not file_path_str:
                return

            destination_path = view.workflow_export_service.validate_export_destination(
                Path(file_path_str).resolve()
            )
            view.workflow_export_service.export_workflow_json(
                destination_path=destination_path,
                sugar_script_text=sugar_script,
                output_dir=resolved_output_dir,
                workflow=active_workflow,
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            log_context: dict[str, str] = {
                "workflow_name": workflow_name,
                "output_dir": str(resolved_output_dir.resolve()),
            }
            if destination_path is not None:
                log_context["destination_path"] = str(destination_path)
            self._log_exception(_LOGGER, "Failed to export workflow", **log_context)
            self._show_exception_or_critical(
                error,
                title="Export workflow failed",
                message=f"Failed to export workflow: {error}",
                stage="export",
                context=SubstituteOperationContext(
                    operation="export_workflow_json",
                    workflow_id=getattr(
                        getattr(view, "workflow_session_service", None),
                        "active_workflow_id",
                        None,
                    ),
                    workflow_name=workflow_name,
                    path=str(destination_path)
                    if destination_path is not None
                    else None,
                    values={"output_dir": str(resolved_output_dir.resolve())},
                ),
                fallback_message_box=message_box,
                fallback_title="Export Error",
                fallback_message=f"Failed to export workflow:\n{error}",
            )

    def on_load_clicked(
        self,
        *,
        projects_dir: Path | None = None,
        sugar_scripts_dir: Path | None = None,
        file_dialog: FileDialogProtocol = _DEFAULT_FILE_DIALOG,
        cube_loader: CubeLoaderProtocol = load_cube_async,
        icon_provider: CubeIconProviderProtocol = FIF,
        message_box: MessageBoxProtocol = _DEFAULT_MESSAGE_BOX,
    ) -> None:
        """Select a recipe document and delegate path-based loading."""

        resolved_projects_dir = self._projects_dir(projects_dir)
        resolved_sugar_scripts_dir = self._sugar_scripts_dir(sugar_scripts_dir)
        selected_path_str, _ = file_dialog.getOpenFileName(
            self._view,
            "Open Recipe",
            str(resolved_sugar_scripts_dir),
            "Recipes and Images (*.sugar *.png)",
        )
        log_debug(
            _LOGGER,
            "Recipe load file dialog completed",
            selected_path=selected_path_str,
            selected=bool(selected_path_str),
        )
        if not selected_path_str:
            return

        self.load_recipe_document(
            Path(selected_path_str),
            projects_dir=resolved_projects_dir,
            cube_loader=cube_loader,
            icon_provider=icon_provider,
            message_box=message_box,
        )

    def load_recipe_document(
        self,
        source_path: Path,
        *,
        projects_dir: Path | None = None,
        cube_loader: CubeLoaderProtocol = load_cube_async,
        icon_provider: CubeIconProviderProtocol = FIF,
        message_box: MessageBoxProtocol = _DEFAULT_MESSAGE_BOX,
    ) -> str | None:
        """Load one recipe document path into a target workflow tab."""

        view = self._view
        resolved_projects_dir = self._projects_dir(projects_dir)
        current_index = view.workflow_tabbar.currentIndex()
        current_tab_item = view.workflow_tabbar.tabItem(current_index)
        current_id = current_tab_item.routeKey()
        current_workflow = view.workflow_session_service.get_workflow(current_id)
        log_debug(
            _LOGGER,
            "Recipe load flow started",
            projects_dir=resolved_projects_dir,
            current_index=current_index,
            current_workflow_id=current_id,
            current_tab_text=current_tab_item.text(),
            active_workflow_id=view.workflow_session_service.active_workflow_id,
            source_path=source_path,
        )

        is_blank_and_default = (
            current_workflow is not None
            and not current_workflow.stack_order
            and not current_workflow.cubes
            and is_default_workflow_tab_label(current_tab_item.text())
        )
        if is_blank_and_default:
            target_workflow_id = current_id
        else:
            self._add_workflow_tab_requested()
            target_workflow_id = view.workflow_session_service.active_workflow_id
        log_info(
            _LOGGER,
            "Recipe load target workflow resolved",
            target_workflow_id=target_workflow_id,
            reused_blank_default=is_blank_and_default,
            active_workflow_id=view.workflow_session_service.active_workflow_id,
        )

        selected_path = Path(source_path)
        log_debug(
            _LOGGER,
            "Recipe load selected path accepted",
            target_workflow_id=target_workflow_id,
            path=selected_path,
            suffix=selected_path.suffix.lower(),
        )

        try:
            parsed_recipe = view.recipe_io_service.load_and_parse_recipe_document(
                selected_path
            )
            loaded_document = cast(
                LoadedRecipeDocumentProtocol,
                parsed_recipe.loaded_document,
            )
            parsed_script = cast(
                ParsedRecipeScriptProtocol,
                parsed_recipe.parsed_script,
            )
            loaded_project_name = parsed_script.project_name
            model_load_resolver_factory = getattr(
                view,
                "create_recipe_model_load_resolver",
                None,
            )
            if callable(model_load_resolver_factory):
                if self._can_resolve_recipe_models_async():
                    self._resolve_recipe_model_references_async(
                        resolver_factory=model_load_resolver_factory,
                        parsed_script=parsed_script,
                        target_workflow_id=target_workflow_id,
                        loaded_document=loaded_document,
                        loaded_project_name=loaded_project_name,
                        resolved_projects_dir=resolved_projects_dir,
                        selected_path=selected_path,
                        icon_provider=icon_provider,
                        cube_loader=cube_loader,
                        message_box=message_box,
                    )
                    return target_workflow_id
                resolved_payload = self._resolved_recipe_payload(
                    self._resolve_recipe_model_references(
                        resolver_factory=model_load_resolver_factory,
                        parsed_script=parsed_script,
                    )
                )
                log_debug(
                    _LOGGER,
                    "Recipe model references resolved before materialization",
                    target_workflow_id=target_workflow_id,
                    literal_matches=resolved_payload.summary.literal_matches,
                    hash_matches=resolved_payload.summary.hash_matches,
                    unresolved_hashes=resolved_payload.summary.unresolved_hashes,
                    deferred_download=(
                        resolved_payload.deferred_model_download is not None
                    ),
                )
                parsed_script = resolved_payload.parsed_script
                deferred_model_download = resolved_payload.deferred_model_download
            else:
                deferred_model_download = None
            self._materialize_loaded_recipe_document(
                parsed_script=parsed_script,
                loaded_document=loaded_document,
                loaded_project_name=loaded_project_name,
                target_workflow_id=target_workflow_id,
                resolved_projects_dir=resolved_projects_dir,
                icon_provider=icon_provider,
                cube_loader=cube_loader,
                deferred_model_download=deferred_model_download,
            )
            return target_workflow_id
        except (_RecipeModelResolutionCancelled,):
            log_info(
                _LOGGER,
                "Recipe load cancelled during missing model resolution",
                workflow_id=target_workflow_id,
                path=str(selected_path.resolve()),
            )
            return None
        except (
            AttributeError,
            OSError,
            RecipeModelResolutionRequired,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            self._present_recipe_load_failure(
                error,
                target_workflow_id=target_workflow_id,
                selected_path=selected_path,
                resolved_projects_dir=resolved_projects_dir,
                message_box=message_box,
            )
            return None

    def _can_resolve_recipe_models_async(self) -> bool:
        """Return whether production recipe resolution can run through runtime."""

        return (
            self._recipe_model_resolution_runner is None
            and self._recipe_model_resolution_route_factory is not None
        )

    def _resolve_recipe_model_references_async(
        self,
        *,
        resolver_factory: Callable[[], RecipeModelLoadResolver],
        parsed_script: ParsedRecipeScriptProtocol,
        target_workflow_id: str,
        loaded_document: LoadedRecipeDocumentProtocol,
        loaded_project_name: str | None,
        resolved_projects_dir: Path,
        selected_path: Path,
        icon_provider: CubeIconProviderProtocol,
        cube_loader: CubeLoaderProtocol,
        message_box: MessageBoxProtocol,
    ) -> None:
        """Resolve recipe model hashes on the runtime lane before materialization."""

        if self._recipe_model_resolution_route_factory is None:
            raise RuntimeError(
                "recipe model resolution route factory is required "
                "for async resolution."
            )
        request_id = self._recipe_model_download_request_id + 1
        self._recipe_model_download_request_id = request_id
        route = self._recipe_model_resolution_route_factory(
            request_id=request_id,
            target_workflow_id=target_workflow_id,
        )
        scope = TaskScope(
            submitter=route.submitter,
            scope_id=f"recipe_model_resolution_{target_workflow_id}_{request_id}",
        )
        request: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="recipe_model_resolution",
                parts=(("workflow_id", target_workflow_id),),
            ),
            context=ExecutionContext(
                operation="recipe_model_resolution",
                reason="recipe_load_before_materialization",
                lane="recipe_model_resolution",
                safe_fields=(
                    ("workflow_id", target_workflow_id),
                    ("request_id", request_id),
                ),
            ),
            work=lambda _token: resolver_factory().resolve(cast(Any, parsed_script)),
        )

        def complete(outcome: TaskOutcome[object]) -> None:
            """Continue recipe materialization after model resolution settles."""

            try:
                if outcome.status == "cancelled":
                    log_info(
                        _LOGGER,
                        "Recipe model resolution cancelled before materialization",
                        workflow_id=target_workflow_id,
                        reason=outcome.cancellation_reason,
                    )
                    return
                if outcome.status == "failed":
                    error = outcome.error
                    if isinstance(error, RecipeModelResolutionRequired):
                        handled = self._handle_missing_recipe_models(error)
                        if handled is None:
                            log_info(
                                _LOGGER,
                                "Recipe load cancelled during missing model resolution",
                                workflow_id=target_workflow_id,
                                path=str(selected_path.resolve()),
                            )
                            return
                        self._continue_resolved_recipe_materialization(
                            resolved_script=handled,
                            loaded_document=loaded_document,
                            loaded_project_name=loaded_project_name,
                            target_workflow_id=target_workflow_id,
                            resolved_projects_dir=resolved_projects_dir,
                            icon_provider=icon_provider,
                            cube_loader=cube_loader,
                        )
                        return
                    self._present_recipe_load_failure(
                        error
                        if error is not None
                        else RuntimeError("Recipe model resolution failed."),
                        target_workflow_id=target_workflow_id,
                        selected_path=selected_path,
                        resolved_projects_dir=resolved_projects_dir,
                        message_box=message_box,
                    )
                    return
                self._continue_resolved_recipe_materialization(
                    resolved_script=outcome.result,
                    loaded_document=loaded_document,
                    loaded_project_name=loaded_project_name,
                    target_workflow_id=target_workflow_id,
                    resolved_projects_dir=resolved_projects_dir,
                    icon_provider=icon_provider,
                    cube_loader=cube_loader,
                )
            finally:
                scope.close(reason="recipe_model_resolution_finished")
                route.close()

        try:
            handle = scope.submit(request)
            handle.add_done_callback(
                complete,
                reason="recipe_model_resolution_completed",
            )
        except Exception:
            scope.close(reason="recipe_model_resolution_submit_failed")
            route.close()
            raise

    def _continue_resolved_recipe_materialization(
        self,
        *,
        resolved_script: object,
        loaded_document: LoadedRecipeDocumentProtocol,
        loaded_project_name: str | None,
        target_workflow_id: str,
        resolved_projects_dir: Path,
        icon_provider: CubeIconProviderProtocol,
        cube_loader: CubeLoaderProtocol,
    ) -> None:
        """Normalize a resolved recipe script and materialize the workflow."""

        resolved_payload = self._resolved_recipe_payload(resolved_script)
        log_debug(
            _LOGGER,
            "Recipe model references resolved before materialization",
            target_workflow_id=target_workflow_id,
            literal_matches=resolved_payload.summary.literal_matches,
            hash_matches=resolved_payload.summary.hash_matches,
            unresolved_hashes=resolved_payload.summary.unresolved_hashes,
            deferred_download=resolved_payload.deferred_model_download is not None,
        )
        self._materialize_loaded_recipe_document(
            parsed_script=resolved_payload.parsed_script,
            loaded_document=loaded_document,
            loaded_project_name=loaded_project_name,
            target_workflow_id=target_workflow_id,
            resolved_projects_dir=resolved_projects_dir,
            icon_provider=icon_provider,
            cube_loader=cube_loader,
            deferred_model_download=resolved_payload.deferred_model_download,
        )

    def _resolved_recipe_payload(
        self, resolved_script: object
    ) -> _ResolvedRecipePayload:
        """Normalize resolver output for common materialization."""

        if isinstance(resolved_script, DeferredRecipeModelDownload):
            return _ResolvedRecipePayload(
                parsed_script=cast(
                    ParsedRecipeScriptProtocol,
                    resolved_script.required.partial_script,
                ),
                summary=resolved_script.required.summary,
                deferred_model_download=resolved_script,
            )
        resolved_payload = cast(ResolvedRecipeModelScriptProtocol, resolved_script)
        return _ResolvedRecipePayload(
            parsed_script=resolved_payload.parsed_script,
            summary=resolved_payload.summary,
            deferred_model_download=None,
        )

    def _resolve_recipe_model_references(
        self,
        *,
        resolver_factory: Callable[[], RecipeModelLoadResolver],
        parsed_script: ParsedRecipeScriptProtocol,
    ) -> object:
        """Resolve recipe model hashes through the configured resolution boundary."""

        if self._recipe_model_resolution_runner is not None:
            try:
                return self._recipe_model_resolution_runner(
                    resolver_factory,
                    parsed_script,
                )
            except RecipeModelResolutionRequired as error:
                handled = self._handle_missing_recipe_models(error)
                if handled is not None:
                    return handled
                raise _RecipeModelResolutionCancelled from error
        try:
            return resolver_factory().resolve(cast(Any, parsed_script))
        except RecipeModelResolutionRequired as error:
            handled = self._handle_missing_recipe_models(error)
            if handled is not None:
                return handled
            raise _RecipeModelResolutionCancelled from error

    def _materialize_loaded_recipe_document(
        self,
        *,
        parsed_script: ParsedRecipeScriptProtocol,
        loaded_document: LoadedRecipeDocumentProtocol,
        loaded_project_name: str | None,
        target_workflow_id: str,
        resolved_projects_dir: Path,
        icon_provider: CubeIconProviderProtocol,
        cube_loader: CubeLoaderProtocol,
        deferred_model_download: DeferredRecipeModelDownload | None,
    ) -> None:
        """Materialize a parsed recipe document into the target workflow."""

        loaded_buffers = parsed_script.buffers
        loaded_global_overrides = parsed_script.global_overrides
        loaded_global_override_selections = getattr(
            parsed_script,
            "global_override_selections",
            {},
        )
        loaded_field_control_states = getattr(
            parsed_script,
            "field_control_states_by_alias",
            {},
        )
        loaded_override_control_states = getattr(
            parsed_script,
            "override_control_states",
            {},
        )
        log_debug(
            _LOGGER,
            "Recipe load parsed payload",
            target_workflow_id=target_workflow_id,
            source_path=loaded_document.source_path,
            source_kind=loaded_document.source_kind,
            loaded_project_name=loaded_project_name,
            alias_count=len(loaded_buffers),
            aliases=list(loaded_buffers.keys()),
            cube_ids=[
                str(buffer.get("cube_id", "")) for buffer in loaded_buffers.values()
            ],
            global_override_count=len(loaded_global_overrides),
            global_override_selection_count=len(loaded_global_override_selections),
        )
        self._present_recipe_drift_messages(
            loaded_buffers,
            workflow_id=target_workflow_id,
            source_path=loaded_document.source_path,
        )

        source_path = loaded_document.source_path
        if loaded_document.source_kind == "png":
            log_debug(
                _LOGGER,
                "Recipe load will restore PNG output image set",
                target_workflow_id=target_workflow_id,
                source_path=source_path,
            )

        workflow_name = loaded_project_name if loaded_project_name else source_path.stem
        unique_workflow_name = self._unique_workflow_tab_label(
            workflow_name,
            target_workflow_id,
        )
        log_info(
            _LOGGER,
            "Recipe load workflow label resolved",
            target_workflow_id=target_workflow_id,
            requested_workflow_name=workflow_name,
            resolved_workflow_name=unique_workflow_name,
        )
        log_debug(
            _LOGGER,
            "Recipe load materialization requested",
            target_workflow_id=target_workflow_id,
            workflow_name=unique_workflow_name,
            source_path=source_path,
            alias_count=len(loaded_buffers),
        )
        self._snapshot_materializer.materialize(
            workflow_id=target_workflow_id,
            workflow_name=unique_workflow_name,
            loaded_buffers=loaded_buffers,
            global_overrides=loaded_global_overrides,
            global_override_selections=loaded_global_override_selections,
            field_control_states_by_alias=loaded_field_control_states,
            override_control_states=loaded_override_control_states,
            projects_dir=resolved_projects_dir,
            icon_provider=icon_provider,
            cube_loader=cube_loader,
        )
        _mark_recipe_surfaces_dirty(self._view, target_workflow_id)

        if loaded_document.source_kind == "png":
            self._restore_loaded_recipe_png_outputs(
                source_path=source_path,
                target_workflow_id=target_workflow_id,
                discovery_workflow_name=workflow_name,
                metadata_workflow_name=unique_workflow_name,
            )
        if deferred_model_download is not None:
            self._start_deferred_recipe_model_download(
                request=deferred_model_download,
                target_workflow_id=target_workflow_id,
            )
        log_debug(
            _LOGGER,
            "Recipe load flow completed",
            target_workflow_id=target_workflow_id,
            workflow_name=unique_workflow_name,
            source_path=source_path,
            source_kind=loaded_document.source_kind,
            alias_count=len(loaded_buffers),
        )

    def _present_recipe_load_failure(
        self,
        error: BaseException,
        *,
        target_workflow_id: str,
        selected_path: Path,
        resolved_projects_dir: Path,
        message_box: MessageBoxProtocol,
    ) -> None:
        """Present a recipe load failure from sync or async load flow."""

        self._log_exception(
            _LOGGER,
            "Failed to load recipe",
            workflow_id=target_workflow_id,
            path=str(selected_path.resolve()),
            error=error,
        )
        self._show_exception_or_critical(
            error,
            title="Load recipe failed",
            message=f"Failed to load recipe: {error}",
            stage="load",
            context=SubstituteOperationContext(
                operation="load_recipe",
                workflow_id=target_workflow_id,
                path=str(selected_path.resolve()),
                values={"projects_dir": str(resolved_projects_dir.resolve())},
            ),
            fallback_message_box=message_box,
            fallback_title="Load Error",
            fallback_message=f"Failed to load recipe:\n{error}",
        )

    def _start_deferred_recipe_model_download(
        self,
        *,
        request: DeferredRecipeModelDownload,
        target_workflow_id: str,
    ) -> None:
        """Download missing recipe models while the materialized workflow is visible."""

        view = self._view
        model_label = _deferred_recipe_model_download_label(request)
        busy_token = view.editor_busy.begin(
            target_workflow_id,
            message=f"Downloading {model_label}",
        )
        self._recipe_model_download_request_id += 1
        request_id = self._recipe_model_download_request_id
        cancellation = CancellationSource(generation=request_id)
        route = self._recipe_model_download_route(
            request_id=request_id,
            target_workflow_id=target_workflow_id,
        )
        operation = _ActiveRecipeModelDownload(
            cancellation=cancellation,
            busy_token=busy_token,
            close_route=route.close,
        )
        self._active_recipe_model_downloads.append(operation)

        view.editor_busy.set_cancel_callback(
            busy_token,
            lambda: cancellation.cancel(reason="recipe_model_download_cancelled"),
        )

        def receive_progress(job: object) -> None:
            """Project backend download progress onto the workflow busy overlay."""

            if not isinstance(job, BackendModelDownloadJob):
                return
            self._update_recipe_model_download_overlay(
                busy_token=busy_token,
                job=job,
                model_label=model_label,
            )

        def receive_completed(outcome: TaskOutcome[object]) -> None:
            """Apply the resolved script and release workflow download state."""

            view.editor_busy.set_cancel_callback(busy_token, None)
            try:
                if outcome.status == "cancelled":
                    self._update_recipe_model_download_overlay(
                        busy_token=busy_token,
                        job=BackendModelDownloadJob(
                            job_id="cancelled",
                            status=ModelDownloadStatus.CANCELLED,
                            kind=request.required.references[0].kind,
                            sha256=request.required.references[0].sha256,
                            value=None,
                            result=None,
                            error=outcome.cancellation_reason,
                        ),
                        model_label=model_label,
                    )
                    return
                if outcome.status == "failed":
                    error = outcome.error
                    if error is None:
                        error = RuntimeError("Recipe model download failed.")
                    self._show_recipe_model_download_failure(error)
                    return
                self._apply_downloaded_recipe_models(
                    resolved_script=outcome.result,
                    request=request,
                    target_workflow_id=target_workflow_id,
                )
                self._mark_recipe_model_download_ready(target_workflow_id)
            finally:
                view.editor_busy.end(busy_token)
                if operation in self._active_recipe_model_downloads:
                    self._active_recipe_model_downloads.remove(operation)
                operation.close_route()

        self._update_recipe_model_download_overlay(
            busy_token=busy_token,
            job=BackendModelDownloadJob(
                job_id="pending",
                status=ModelDownloadStatus.QUEUED,
                kind=request.required.references[0].kind,
                sha256=request.required.references[0].sha256,
                value=None,
                result=None,
                error=None,
            ),
            model_label=model_label,
        )
        task_request: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="recipe_model_download",
                parts=(("workflow_id", target_workflow_id),),
                cancellation_generation=cancellation.generation,
            ),
            context=ExecutionContext(
                operation="recipe_model_download",
                reason="deferred_missing_recipe_model_download",
                lane="model_download",
                safe_fields=(
                    ("workflow_id", target_workflow_id),
                    ("request_id", request_id),
                    ("kind", request.required.references[0].kind),
                ),
            ),
            work=lambda token: request.service.download_and_resolve(
                request.required,
                api_key_override=request.api_key_override,
                progress_callback=lambda job: route.progress_dispatcher.publish(
                    lambda: receive_progress(job),
                    reason="recipe_model_download_progress",
                ),
                should_cancel=lambda: token.is_cancelled,
            ),
        )
        handle = route.submitter.submit(
            task_request,
            cancellation=cancellation,
        )
        handle.add_done_callback(
            receive_completed,
            reason="recipe_model_download_completed",
        )

    def _recipe_model_download_route(
        self,
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> RecipeModelDownloadRoute:
        """Build the execution route for one deferred recipe model download."""

        if self._recipe_model_download_route_factory is None:
            raise RuntimeError(
                "recipe model download route factory is required for model downloads."
            )
        return self._recipe_model_download_route_factory(
            request_id=request_id,
            target_workflow_id=target_workflow_id,
        )

    def _update_recipe_model_download_overlay(
        self,
        *,
        busy_token: object,
        job: BackendModelDownloadJob,
        model_label: str,
    ) -> None:
        """Update the workflow-scoped busy overlay with model-download progress."""

        detail = _recipe_model_download_detail(job)
        self._view.editor_busy.update_download(
            busy_token,
            EditorBusyDownloadState(
                title=f"Downloading {model_label}",
                message=_recipe_model_download_message(job, model_label=model_label),
                detail=detail,
                progress_per_mille=_recipe_model_download_progress(job),
                cancel_enabled=job.status
                not in {ModelDownloadStatus.COMPLETE, ModelDownloadStatus.FAILED},
            ),
        )

    def _apply_downloaded_recipe_models(
        self,
        *,
        resolved_script: object,
        request: DeferredRecipeModelDownload,
        target_workflow_id: str,
    ) -> None:
        """Apply downloaded model picker values to the already-loaded workflow."""

        parsed_script = cast(
            ParsedRecipeScriptProtocol,
            cast(Any, resolved_script).parsed_script,
        )
        workflow = self._view.workflow_session_service.workflows.get(target_workflow_id)
        if workflow is None:
            return
        workflow.global_overrides = parsed_script.global_overrides
        workflow.global_override_selections = dict(
            getattr(parsed_script, "global_override_selections", {})
        )
        workflow.override_control_states = dict(
            getattr(parsed_script, "override_control_states", {})
        )
        node_classes = self._apply_downloaded_model_values_to_workflow(
            workflow=workflow,
            parsed_script=parsed_script,
            request=request,
        )
        refreshed_node_classes = self._refresh_downloaded_model_node_definitions(
            node_classes=node_classes,
        )
        if target_workflow_id != self._view.workflow_session_service.active_workflow_id:
            return
        active_override_manager = getattr(self._view, "active_override_manager", None)
        sync_overrides = getattr(
            active_override_manager,
            "sync_state_from_workflow",
            None,
        )
        if callable(sync_overrides):
            sync_overrides()
        active_panel = self._view.editor_panels.get(target_workflow_id)
        refresh_projection = getattr(
            active_panel,
            "refresh_projection_after_node_definition_update",
            None,
        )
        if callable(refresh_projection) and refreshed_node_classes:
            refresh_projection(refreshed_node_classes=refreshed_node_classes)
        else:
            self._view.active_workflow_surface_refresher.refresh_active_workflow_surface()
        apply_overrides = getattr(
            active_override_manager, "apply_global_overrides", None
        )
        if callable(apply_overrides):
            apply_overrides()

    def _refresh_downloaded_model_node_definitions(
        self,
        *,
        node_classes: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Force-refresh Comfy choices for node classes that used downloaded models."""

        gateway = getattr(self._view, "node_definition_gateway", None)
        refresh = getattr(gateway, "refresh_node_definition", None)
        if not callable(refresh):
            return ()
        refreshed: list[str] = []
        for node_class in node_classes:
            payload = refresh(node_class)
            if isinstance(payload, Mapping) and node_class in payload:
                refreshed.append(node_class)
        return tuple(refreshed)

    def _apply_downloaded_model_values_to_workflow(
        self,
        *,
        workflow: WorkflowStateProtocol,
        parsed_script: ParsedRecipeScriptProtocol,
        request: DeferredRecipeModelDownload,
    ) -> tuple[str, ...]:
        """Patch downloaded model values into loaded cube runtime buffers."""

        node_classes: list[str] = []
        for reference in request.required.references:
            value = _model_reference_value(
                parsed_script=parsed_script,
                alias=reference.alias,
                node_name=reference.node_name,
                input_key=reference.input_key,
            )
            if value is None:
                continue
            cube_state = workflow.cubes.get(reference.alias)
            node = _workflow_model_reference_node(
                cube_state=cube_state,
                node_name=reference.node_name,
            )
            if node is None:
                continue
            class_type = node.get("class_type")
            if (
                isinstance(class_type, str)
                and class_type
                and class_type not in node_classes
            ):
                node_classes.append(class_type)
            inputs = _ensure_mutable_node_inputs(node)
            inputs[reference.input_key] = value
        return tuple(node_classes)

    def _show_recipe_model_download_failure(self, error: BaseException) -> None:
        """Present a failed deferred model download."""

        QMessageBox.warning(
            cast(Any, self._view),
            "Model download failed",
            str(error),
        )

    def _mark_recipe_model_download_ready(self, workflow_id: str) -> None:
        """Mark inactive workflow tabs after background recipe model downloads."""

        active_workflow_id = self._view.workflow_session_service.active_workflow_id
        if workflow_id == active_workflow_id:
            return
        set_unread = getattr(
            self._view.workflow_tabbar,
            "set_workflow_unread_result",
            None,
        )
        if callable(set_unread):
            set_unread(workflow_id, True)

    def _handle_missing_recipe_models(
        self,
        error: RecipeModelResolutionRequired,
    ) -> object | None:
        """Let presentation resolve missing recipe models before materialization."""

        handler = self._recipe_model_resolution_handler
        if handler is None:
            return None
        return handler(error)

    def _restore_loaded_recipe_png_outputs(
        self,
        *,
        source_path: Path,
        target_workflow_id: str,
        discovery_workflow_name: str,
        metadata_workflow_name: str,
    ) -> None:
        """Restore the selected recipe PNG and same-folder output siblings."""

        siblings = self._discover_loaded_recipe_png_outputs(
            source_path=source_path,
            workflow_id=target_workflow_id,
            workflow_name=discovery_workflow_name,
        )
        for sibling in siblings:
            self._add_loaded_recipe_output(
                sibling=sibling,
                target_workflow_id=target_workflow_id,
                metadata_workflow_name=metadata_workflow_name,
            )

    def _discover_loaded_recipe_png_outputs(
        self,
        *,
        source_path: Path,
        workflow_id: str,
        workflow_name: str,
    ) -> tuple[RecipeOutputSibling, ...]:
        """Return output siblings for a loaded recipe PNG with selected fallback."""

        fallback = self._selected_recipe_output_sibling(source_path)
        discovery_service = self._recipe_output_sibling_discovery_service
        if discovery_service is None:
            log_debug(
                _LOGGER,
                "Recipe output sibling discovery skipped",
                workflow_id=workflow_id,
                source_path=source_path,
                reason="service_unavailable",
            )
            return (fallback,)
        try:
            result = discovery_service.discover_for_recipe_png(
                source_path,
                workflow_name=workflow_name,
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            self._log_exception(
                _LOGGER,
                "Recipe output sibling discovery failed",
                workflow_id=workflow_id,
                source_path=str(source_path),
                error=error,
            )
            return (fallback,)

        siblings = self._ensure_selected_output_sibling(
            result.siblings,
            selected=fallback,
        )
        log_debug(
            _LOGGER,
            "Recipe output sibling discovery resolved",
            workflow_id=workflow_id,
            source_path=source_path,
            strategy=result.strategy,
            sibling_count=len(siblings),
            warnings=result.warnings,
        )
        return siblings

    def _add_loaded_recipe_output(
        self,
        *,
        sibling: RecipeOutputSibling,
        target_workflow_id: str,
        metadata_workflow_name: str,
    ) -> None:
        """Add one restored recipe output image to the output canvas if readable."""

        view = self._view
        qimg = view.canvas_io_service.load_recipe_preview_image(sibling.path)
        qimg_is_null_func = getattr(qimg, "isNull", None)
        qimg_is_null = (
            bool(qimg_is_null_func()) if callable(qimg_is_null_func) else False
        )
        if qimg is None or qimg_is_null:
            log_warning(
                _LOGGER,
                "Recipe output sibling image skipped",
                workflow_id=target_workflow_id,
                path=sibling.path,
                reason="image_load_failed",
                image_is_null=qimg_is_null,
            )
            return

        qimg_width = getattr(qimg, "width", None)
        qimg_height = getattr(qimg, "height", None)
        image_meta = view.canvas_io_service.build_output_image_metadata(
            workflow_name=metadata_workflow_name,
            node_meta_title=sibling.node_title or sibling.source_label or "Loaded",
            file_path=sibling.path,
            source_key=sibling.source_key,
            source_label=sibling.source_label,
            scene_run_id=sibling.scene_run_id,
            scene_key=sibling.scene_key,
            scene_title=sibling.scene_title,
            scene_order=sibling.scene_order,
            scene_count=sibling.scene_count,
            width=qimg_width() if callable(qimg_width) else None,
            height=qimg_height() if callable(qimg_height) else None,
        )
        self._output_image_registrar.add_output_image(
            target_workflow_id,
            qimg,
            image_meta,
        )
        log_debug(
            _LOGGER,
            "Recipe output sibling image restored",
            workflow_id=target_workflow_id,
            path=sibling.path,
            source_label=sibling.source_label,
        )

    @staticmethod
    def _selected_recipe_output_sibling(source_path: Path) -> RecipeOutputSibling:
        """Return the single selected PNG as the output restoration fallback."""

        return RecipeOutputSibling(
            path=source_path,
            source_key="loaded",
            source_label="Loaded",
            sequence=1,
            node_title="Loaded",
        )

    @staticmethod
    def _ensure_selected_output_sibling(
        siblings: tuple[RecipeOutputSibling, ...],
        *,
        selected: RecipeOutputSibling,
    ) -> tuple[RecipeOutputSibling, ...]:
        """Ensure the selected image appears exactly once in restored outputs."""

        selected_key = _normalized_path_key(selected.path)
        deduplicated: list[RecipeOutputSibling] = []
        seen: set[str] = set()
        selected_present = False
        for sibling in siblings:
            key = _normalized_path_key(sibling.path)
            if key == selected_key:
                selected_present = True
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(sibling)
        if not selected_present:
            return (selected, *deduplicated)
        return tuple(deduplicated)

    def _show_exception_or_critical(
        self,
        error: BaseException,
        *,
        title: str,
        message: str,
        stage: str,
        context: SubstituteOperationContext,
        fallback_message_box: MessageBoxProtocol,
        fallback_title: str,
        fallback_message: str,
    ) -> None:
        """Show a structured report when available, otherwise use legacy critical UI."""

        if self._error_presenter is not None:
            self._error_presenter.show_exception_report(
                title=title,
                message=message,
                stage=stage,
                error=error,
                context=context,
            )
            return
        fallback_message_box.critical(self._view, fallback_title, fallback_message)

    def _present_recipe_drift_messages(
        self,
        loaded_buffers: Mapping[str, dict[str, object]],
        *,
        workflow_id: str,
        source_path: Path,
    ) -> None:
        """Present Cube Library drift through the app error-report surface."""

        service = getattr(self._view, "cube_library_management_service", None)
        if service is None:
            return
        drift_service = cast(CubeLibraryManagementServiceProtocol, service)
        messages = drift_service.recipe_drift_messages(loaded_buffers)
        if not messages:
            return
        for message in messages:
            log_warning(
                _LOGGER,
                "Recipe cube library drift detected",
                drift_message=message,
            )
        report = build_cube_library_drift_report(
            messages,
            context=SubstituteOperationContext(
                operation="load_recipe_cube_library_drift",
                workflow_id=workflow_id,
                path=str(source_path),
                values={"message_count": len(messages), "messages": messages},
            ),
        )
        error_presenter = self._error_presenter
        using_fallback_presenter = error_presenter is None
        if error_presenter is None:
            error_presenter = ErrorPresenter(parent=self._view)
        log_debug(
            _LOGGER,
            "Presenting Cube Library drift report",
            workflow_id=workflow_id,
            source_path=source_path,
            message_count=len(messages),
            presenter_type=type(error_presenter).__name__,
            using_fallback_presenter=using_fallback_presenter,
        )
        error_presenter.show_error_report(report)

    def open_sugar_snapshot_as_new_workflow(
        self,
        *,
        workflow_name: str,
        sugar_script_text: str,
        projects_dir: Path | None = None,
        icon_provider: CubeIconProviderProtocol = FIF,
        cube_loader: CubeLoaderProtocol = load_cube_async,
    ) -> str | None:
        """Open one Sugar snapshot in a newly created active workflow tab."""

        view = self._view
        resolved_projects_dir = self._projects_dir(projects_dir)
        try:
            parsed_script = view.recipe_io_service.parse_recipe_script(
                sugar_script_text
            )
            self._add_workflow_tab_requested()
            target_workflow_id = view.workflow_session_service.active_workflow_id
            unique_workflow_name = self._unique_workflow_tab_label(
                workflow_name,
                target_workflow_id,
            )
            self._snapshot_materializer.materialize(
                workflow_id=target_workflow_id,
                workflow_name=unique_workflow_name,
                loaded_buffers=parsed_script.buffers,
                global_overrides=parsed_script.global_overrides,
                global_override_selections=getattr(
                    parsed_script,
                    "global_override_selections",
                    {},
                ),
                projects_dir=resolved_projects_dir,
                icon_provider=icon_provider,
                cube_loader=cube_loader,
            )
            return target_workflow_id
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            self._log_exception(
                _LOGGER,
                "Failed to open workflow snapshot",
                workflow_name=workflow_name,
                error=error,
            )
            return None

    def _unique_workflow_tab_label(
        self,
        base_name: str,
        target_workflow_id: str,
    ) -> str:
        """Return a unique tab label while ignoring the target workflow tab."""

        normalized = normalize_default_workflow_tab_label(base_name)
        existing_labels = {
            item.text()
            for workflow_id, item in self._view.workflow_tabbar.itemMap.items()
            if workflow_id != target_workflow_id
        }
        if normalized not in existing_labels:
            return normalized
        counter = 2
        while True:
            candidate = f"{normalized} ({counter})"
            if candidate not in existing_labels:
                return candidate
            counter += 1


def _normalized_path_key(path: Path) -> str:
    """Return a Windows-tolerant key for loaded output path comparisons."""

    return str(path).replace("\\", "/").casefold()


def _model_reference_value(
    *,
    parsed_script: ParsedRecipeScriptProtocol,
    alias: str,
    node_name: str,
    input_key: str,
) -> object | None:
    """Return the resolved model value from a parsed recipe patch."""

    buffer = parsed_script.buffers.get(alias)
    if not isinstance(buffer, Mapping):
        return None
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return None
    node = nodes.get(node_name)
    if not isinstance(node, Mapping):
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return None
    return inputs.get(input_key)


def _workflow_model_reference_node(
    *,
    cube_state: object,
    node_name: str,
) -> MutableMapping[str, object] | None:
    """Return one mutable runtime node from an already-loaded workflow cube."""

    cube_buffer = getattr(cube_state, "buffer", None)
    if not isinstance(cube_buffer, Mapping):
        return None
    nodes = cube_buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return None
    node = nodes.get(node_name)
    if not isinstance(node, MutableMapping):
        return None
    return cast(MutableMapping[str, object], node)


def _ensure_mutable_node_inputs(
    node: MutableMapping[str, object],
) -> MutableMapping[str, object]:
    """Return mutable node inputs, creating the input map when needed."""

    inputs = node.get("inputs")
    if isinstance(inputs, MutableMapping):
        return cast(MutableMapping[str, object], inputs)
    created_inputs: dict[str, object] = {}
    node["inputs"] = created_inputs
    return created_inputs


def _recipe_model_download_message(
    job: BackendModelDownloadJob,
    *,
    model_label: str,
) -> str:
    """Return user-facing workflow overlay copy for one download job."""

    if job.status is ModelDownloadStatus.QUEUED:
        return "Preparing the download."
    if job.status is ModelDownloadStatus.RUNNING:
        return job.detail or "Starting the model download."
    if job.status is ModelDownloadStatus.COMPLETE:
        return "The model has finished downloading."
    if job.status is ModelDownloadStatus.CANCELLED:
        return "Cancelling the model download."
    if job.status is ModelDownloadStatus.FAILED:
        return "The model download failed."
    return "Downloading the model this recipe needs."


def _deferred_recipe_model_download_label(
    request: DeferredRecipeModelDownload,
) -> str:
    """Return the best CivitAI model label for a deferred recipe download."""

    for reference in request.required.references:
        candidate = reference.candidate
        if candidate is None:
            continue
        model_name = candidate.model_name.strip()
        version_name = candidate.version_name.strip()
        if (
            model_name
            and version_name
            and version_name.casefold()
            not in {
                model_name.casefold(),
                "base",
            }
        ):
            return f"{model_name} - {version_name}"
        if model_name:
            return model_name
        if candidate.name.strip():
            return candidate.name.strip()
    return "model"


def _recipe_model_download_detail(job: BackendModelDownloadJob) -> str:
    """Return concise download byte progress text."""

    if job.status is ModelDownloadStatus.QUEUED:
        return "Waiting for the download to start..."
    if job.status is ModelDownloadStatus.COMPLETE:
        return "Updating the recipe..."
    if job.status is ModelDownloadStatus.CANCELLED:
        return "Cancelling download..."
    if job.status is ModelDownloadStatus.FAILED:
        return job.error or "Download failed."
    if job.bytes_downloaded is None or not job.bytes_total:
        return job.detail or "Downloading..."
    return (
        f"{_format_download_bytes(job.bytes_downloaded)} of "
        f"{_format_download_bytes(job.bytes_total)}"
    )


def _recipe_model_download_progress(job: BackendModelDownloadJob) -> int | None:
    """Return determinate progress in per-mille units when available."""

    if job.status is ModelDownloadStatus.COMPLETE:
        return 1000
    if job.bytes_downloaded is None or not job.bytes_total:
        return None
    return int(1000 * job.bytes_downloaded / max(1, job.bytes_total))


def _format_download_bytes(value: int) -> str:
    """Return a compact byte count for model download progress."""

    amount = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024.0 or unit == "GB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024.0
    return f"{amount:.1f} GB"


__all__ = [
    "RecipeModelDownloadRoute",
    "RecipeModelDownloadRouteFactory",
    "RecipeModelResolutionRoute",
    "RecipeModelResolutionRouteFactory",
    "WorkspaceFileActions",
    "WorkspaceFileActionView",
]
