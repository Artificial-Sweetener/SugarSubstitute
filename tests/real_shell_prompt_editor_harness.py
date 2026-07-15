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

"""Real-shell harness for prompt editor interaction and rendering scenarios."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import json
import math
import platform
import random
import sys
from time import perf_counter
from types import SimpleNamespace
from typing import Any, cast

from PySide6 import QtCore
from PySide6.QtCore import (
    QCoreApplication,
    QEventLoop,
    QPoint,
    QRect,
    QRectF,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QGuiApplication,
    QImage,
    QKeySequence,
    QMouseEvent,
    QTextCursor,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
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
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ThumbnailAssetRepository,
)
from substitute.application.node_behavior import NodeBehaviorService
from substitute.application.ports import (
    NodeDefinitionHydrationResult,
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor import PromptLoraCatalogLookup
from substitute.application.user_presets import UserPresetService
from substitute.application.workflows import WorkflowSessionService
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
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
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    RecordingPromptAutocompleteGateway,
)
from tests.execution_test_helpers import immediate_editor_panel_execution_factories


@dataclass(frozen=True, slots=True)
class PromptWorkflowHandle:
    """Identify one prompt workflow mounted in the real shell."""

    alias: str
    workflow_id: str
    cube_alias: str
    cube_state: CubeState


@dataclass(frozen=True, slots=True)
class PromptFieldHandle:
    """Identify one real prompt editor field inside a rendered node card."""

    workflow: PromptWorkflowHandle
    node_name: str
    field_key: str
    editor: PromptEditor


@dataclass(frozen=True, slots=True)
class PromptEditorKeyRoute:
    """Record the visible and state route around one real Qt key action."""

    key_name: str
    text: str
    modifiers: str
    focus_before: str
    focus_after: str
    active_window_before: str
    active_window_after: str
    source_before: str
    source_after: str
    cursor_before: int
    cursor_after: int
    dropdown_visible_before: bool
    dropdown_visible_after: bool
    ghost_visible_before: bool
    ghost_visible_after: bool
    inserted_text: str


@dataclass(frozen=True, slots=True)
class PromptEditorTraceAction:
    """Describe one replayable editor action."""

    kind: str
    value: str
    key: int | None = None
    modifiers: int = 0


@dataclass(frozen=True, slots=True)
class PromptEditorTrace:
    """Record a deterministic sequence of user-like prompt editor actions."""

    actions: tuple[PromptEditorTraceAction, ...]
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class PromptEditorObservedEvent:
    """Record one production owner call observed by the harness."""

    index: int
    owner: str
    method: str
    source_before: str
    source_after: str
    cursor_before: int
    cursor_after: int
    preview_before: str
    preview_after: str
    session_before: str
    session_after: str
    panel_before: str
    panel_after: str
    result: str


@dataclass(frozen=True, slots=True)
class PromptEditorContextMenuTrace:
    """Record one real-shell prompt context-menu opening and optional action trigger."""

    source_before: str
    source_after: str
    clicked_text: str
    click_source_position: int | None
    menu_rows: tuple[str, ...]
    submenu_rows: tuple[tuple[str, tuple[str, ...]], ...]
    trigger_action_texts: tuple[str, ...]
    trigger_action_full_labels: tuple[str, ...]
    triggered_action_text: str | None
    lora_snapshot_readiness_before: str
    lora_snapshot_unavailable_before: str | None
    lora_snapshot_action_count_before: int
    lora_snapshot_readiness_after: str
    lora_snapshot_unavailable_after: str | None
    lora_snapshot_action_count_after: int
    cached_scheduled_lora_count_before: int | None
    cached_scheduled_lora_count_after: int | None
    event_dispatch_elapsed_ms: float = 0.0
    menu_exec_elapsed_ms: float = 0.0
    menu_population_elapsed_ms: float = 0.0
    captured_menu_row_count: int = 0
    captured_submenu_row_count: int = 0
    captured_action_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptInlineLoraMenuProbe:
    """Capture one production inline-LoRA token menu presentation."""

    menu_rows: tuple[str, ...]
    trigger_action_texts: tuple[str, ...]
    trigger_action_full_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptSegmentScopeProbe:
    """Capture every owner boundary feeding the save-segment dialog."""

    candidate_kind: str | None
    candidate_value: str | None
    active_snapshot_readiness: str
    active_snapshot_reason: str | None
    active_snapshot_item_value: str | None
    active_snapshot_family_labels: tuple[str, ...]
    editor_snapshot_readiness: str
    editor_snapshot_reason: str | None
    editor_scope_titles: tuple[str, ...]
    editor_scope_full_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptSegmentDialogProbe:
    """Capture the exact scope payload passed to the production dialog runner."""

    title: str
    selected_text: str
    scope_titles: tuple[str, ...]
    scope_full_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptEditorVisibleLayoutRow:
    """Record one visible projection row in viewport coordinates."""

    row_index: int
    source_start: int
    source_end: int
    document_top: float
    viewport_top: float
    height: float
    text: str
    has_inline_object: bool = False
    expected_height: float | None = None
    expected_text_baseline: float | None = None


@dataclass(frozen=True, slots=True)
class PromptEditorVisibleTextFragment:
    """Record one visible projection text fragment in viewport coordinates."""

    fragment_index: int
    source_start: int
    source_end: int
    document_rect: tuple[float, float, float, float]
    viewport_rect: tuple[float, float, float, float]
    document_baseline: float
    viewport_baseline: float
    text: str
    expected_document_baseline: float | None = None
    expected_viewport_baseline: float | None = None
    expected_height: float | None = None


@dataclass(frozen=True, slots=True)
class PromptEditorStateSnapshot:
    """Capture prompt editor geometry plus code-level diagnostic owner state."""

    label: str
    source_text: str
    selected_text: str
    selected_source_text: str
    selection_range: tuple[int, int]
    selection_rects: tuple[tuple[float, float, float, float], ...]
    cursor_position: int
    display_mode: str
    focus_widget_path: str
    active_window_path: str
    target_event_widget_path: str
    geometries: Mapping[str, tuple[int, int, int, int] | None]
    global_geometries: Mapping[str, tuple[int, int, int, int] | None]
    scroll_values: Mapping[str, int]
    device_pixel_ratio: float
    autocomplete_gateway_calls: tuple[tuple[str, int], ...]
    popup_widget_exists: bool
    popup_state_visible: bool
    popup_visual_visible: bool
    popup_global_rect: tuple[int, int, int, int] | None
    ghost_visual_visible: bool
    expected_ghost_suffix: str
    autocomplete_preview_active: bool
    autocomplete_preview_suffix: str
    autocomplete_preview_source_position: int | None
    autocomplete_session_lifecycle: str
    autocomplete_session_mode: str
    autocomplete_session_selected_index: int
    autocomplete_session_prefix: str
    autocomplete_session_word_start: int | None
    autocomplete_session_word_end: int | None
    autocomplete_session_active_tag_end: int | None
    autocomplete_session_suggestions: tuple[str, ...]
    autocomplete_has_active_session: bool
    autocomplete_presenter_panel_visible: bool
    autocomplete_presenter_panel_under_mouse: bool
    autocomplete_source_revision: int | None
    autocomplete_snapshot_source_length: int | None
    autocomplete_snapshot_cursor_position: int | None
    source_revision: int | None
    editing_session_source_revision: int | None
    editing_session_cursor_position: int | None
    editing_session_anchor_position: int | None
    document_view_source_text: str
    projection_document_source_text: str
    active_projection_source_text: str
    layout_projection_source_text: str
    projection_text: str
    active_projection_text: str
    layout_projection_text: str
    layout_uses_projection_document: bool
    layout_uses_active_projection_document: bool
    paint_cache_key_present: bool
    paint_cache_source_revision: int | None
    paint_cache_projection_document_identity_matches_layout: bool
    paint_cache_layout_snapshot_identity_matches_layout: bool
    paint_cache_ghosted_run_ids: tuple[str, ...]
    autocomplete_ghost_paint_visible_by_owner_state: bool
    projection_freshness: str
    projection_has_pending_update: bool
    projection_has_stale_geometry: bool
    caret_state_source_position: int | None
    anchor_state_source_position: int | None
    caret_map_source_length: int | None
    caret_map_stop_count: int | None
    caret_preferred_x: float | None
    caret_rect_override: tuple[float, float, float, float] | None
    skip_next_same_source_soft_wrap_move: bool
    projection_token_count: int
    projection_run_count: int
    layout_line_count: int
    layout_text_fragment_count: int
    layout_inline_object_fragment_count: int
    layout_content_width: float
    layout_content_height: float
    layout_text_width: float
    projection_metrics_text_line_height: float | None
    projection_metrics_ascent: float | None
    projection_metrics_descent: float | None
    projection_metrics_document_margin: float | None
    projection_metrics_content_left_inset: float | None
    projection_metrics_content_height: float | None
    shell_natural_height: int | None
    shell_effective_height: int | None
    shell_minimum_editor_height: int | None
    shell_outer_vertical_padding: int | None
    shell_document_vertical_padding: int | None
    visible_layout_rows: tuple[PromptEditorVisibleLayoutRow, ...]
    visible_text_fragments: tuple[PromptEditorVisibleTextFragment, ...]
    caret_token_id: str | None
    anchor_token_id: str | None
    caret_token_id_resolves: bool
    anchor_token_id_resolves: bool
    caret_rect: tuple[float, float, float, float] | None
    viewport_rect: tuple[int, int, int, int]
    caret_rect_finite: bool
    caret_rect_has_area: bool
    caret_rect_intersects_viewport: bool
    vertical_scroll_minimum: int
    vertical_scroll_maximum: int
    vertical_scroll_page_step: int
    horizontal_scroll_minimum: int
    horizontal_scroll_maximum: int
    horizontal_scroll_page_step: int
    transient_caret_geometry_present: bool
    transient_caret_geometry_valid: bool
    transient_insertion_overlay_present: bool
    transient_insertion_overlay_valid: bool
    transient_insertion_overlay_source_range: tuple[int, int] | None
    transient_insertion_overlay_viewport_rect: tuple[float, float, float, float] | None
    transient_insertion_overlay_repaint_rect: tuple[float, float, float, float] | None
    transient_deletion_overlay_present: bool
    transient_deletion_overlay_valid: bool
    transient_deletion_overlay_source_range: tuple[int, int] | None
    transient_deletion_overlay_viewport_rects: tuple[
        tuple[float, float, float, float],
        ...,
    ]
    transient_deletion_overlay_erase_rects: tuple[
        tuple[float, float, float, float],
        ...,
    ]
    transient_deletion_overlay_repaint_rect: tuple[float, float, float, float] | None
    undo_available: bool
    redo_available: bool
    undo_depth: int
    redo_depth: int
    undo_max_depth: int
    redo_max_depth: int
    undo_edit_block_depth: int
    undo_pending_state_present: bool
    undo_typing_group_active: bool
    undo_typing_group_last_cursor_position: int | None
    undo_delete_group_active: bool
    undo_delete_group_key: int | None
    observed_event_start_index: int
    observed_event_end_index: int
    recent_observed_events: tuple[PromptEditorObservedEvent, ...]


@dataclass(frozen=True, slots=True)
class PromptEditorAbuseFinding:
    """Record one visible-symptom failure from a seeded abuse campaign."""

    symptom: str
    owner_hypothesis: str
    action_index: int
    source_before: str
    source_after: str
    artifact_path: str


@dataclass(frozen=True, slots=True)
class PromptEditorAbuseReport:
    """Summarize one seeded real-shell prompt editor abuse campaign."""

    seed: int
    sizes: tuple[tuple[int, int], ...]
    action_count: int
    findings: tuple[PromptEditorAbuseFinding, ...]
    suspicious_successes: tuple[str, ...]
    grouped_failures: Mapping[str, tuple[str, ...]]
    report_path: Path


class RealShellPromptEditorHarness:
    """Drive a production-mounted prompt editor through real shell containers."""

    def __init__(
        self,
        *,
        autocomplete_results: (
            Mapping[str, tuple[PromptAutocompleteSuggestion, ...]] | None
        ) = None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        user_preset_service: UserPresetService | None = None,
        model_catalog_service: ModelCatalogLookup | None = None,
        artifact_root: Path | None = None,
    ) -> None:
        """Create the shell and fake only external infrastructure services.

        Standalone ``PromptEditor(...)`` construction is insufficient here because
        the reported failures involve focus routing, field-state wiring, overlays,
        shell visibility, and paint lifecycle around a prompt editor as mounted by
        the editor panel. This harness therefore starts from the same shell
        containers used by the app and loads the target field through
        ``EditorPanel.load_all_cubes``.
        """

        self.app = _ensure_qapp()
        self.autocomplete_gateway = RecordingPromptAutocompleteGateway(
            autocomplete_results or _default_autocomplete_results()
        )
        self.artifact_root = artifact_root or (
            Path.cwd() / "artifacts" / "prompt_editor_harness"
        )
        self.shell = _HarnessShell(
            self.autocomplete_gateway,
            prompt_lora_catalog_service=prompt_lora_catalog_service,
            thumbnail_asset_repository=thumbnail_asset_repository,
            user_preset_service=user_preset_service,
            model_catalog_service=model_catalog_service,
        )
        self.workflows: dict[str, PromptWorkflowHandle] = {}
        self._trace_actions: list[PromptEditorTraceAction] = []
        self._observed_events: list[PromptEditorObservedEvent] = []
        self._observed_editor_ids: set[int] = set()

    def close(self) -> None:
        """Close real Qt widgets owned by the harness."""

        self.shell.close()
        self.process_events()

    def add_prompt_workflow(
        self,
        alias: str = "prompt-harness",
        *,
        initial_text: str = "",
        model_node_type: str | None = None,
        model_field_key: str | None = None,
        model_value: str | None = None,
        activate: bool = True,
    ) -> PromptFieldHandle:
        """Add one workflow and render a CLIP prompt field through EditorPanel."""

        workflow_id = f"workflow-{alias}"
        cube_alias = "Prompt Cube"
        cube_state = _prompt_cube_state(
            initial_text,
            alias=cube_alias,
            model_node_type=model_node_type,
            model_field_key=model_field_key,
            model_value=model_value,
        )
        workflow = WorkflowState(
            cubes={cube_alias: cube_state},
            stack_order=[cube_alias],
            metadata={"name": alias},
        )
        if not self.workflows:
            self.shell.workflow_session_service.replace_workflows(
                {workflow_id: workflow},
                active_workflow_id=workflow_id,
            )
        else:
            self.shell.workflow_session_service.add_existing_workflow(
                workflow_id,
                workflow,
                activate=activate,
            )
        self.shell.workflow_tabbar.addTab(workflow_id, alias)
        self.shell.install_workflow_surface(workflow_id)

        handle = PromptWorkflowHandle(
            alias=alias,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_state=cube_state,
        )
        self.workflows[alias] = handle
        if activate:
            self.activate_workflow(alias)

        panel = self.shell.editor_panels[workflow_id]
        panel.load_all_cubes(
            [(cube_alias, cube_state)],
            cube_states={cube_alias: cube_state},
            stack_order=[cube_alias],
        )
        if activate:
            self.shell.editor_panel_container.setCurrentWidget(panel)
            self.shell.editor_panel = panel
            panel.show()
            panel.reveal_loaded_cube(cube_alias)
        self._finalize_panel_projection(panel)
        field_key = (cube_alias, "positive_prompt", "text")
        input_widgets = _panel_input_widgets(panel)
        self.wait_until(lambda: field_key in input_widgets)
        editor = input_widgets[field_key]
        if not isinstance(editor, PromptEditor):
            raise AssertionError(f"target field is {type(editor)!r}, not PromptEditor")
        if activate:
            self.wait_until(lambda: editor.isVisible())
        self.process_events()
        field = PromptFieldHandle(
            workflow=handle,
            node_name="positive_prompt",
            field_key="text",
            editor=editor,
        )
        self._install_editor_observability(field)
        return field

    def add_anima_prompt_workflow(
        self,
        *,
        initial_text: str,
        model_value: str,
    ) -> PromptFieldHandle:
        """Mount the production three-cube Anima projection shape."""

        alias = "anima-prompt-harness"
        workflow_id = f"workflow-{alias}"
        stack_order = [
            "Anima/Text to Image",
            "Anima/Diffusion Upscale",
            "Anima/Automask Detailer",
        ]
        cube_states = {
            stack_order[0]: _anima_prompt_cube_state(
                initial_text,
                alias=stack_order[0],
                model_value=model_value,
            ),
            stack_order[1]: _anima_prompt_cube_state(
                "upscale prompt",
                alias=stack_order[1],
                model_value="",
            ),
            stack_order[2]: _anima_prompt_cube_state(
                "detailer prompt",
                alias=stack_order[2],
                model_value="",
            ),
        }
        workflow = WorkflowState(
            cubes=cube_states,
            stack_order=stack_order,
            metadata={"name": alias},
        )
        self.shell.workflow_session_service.replace_workflows(
            {workflow_id: workflow},
            active_workflow_id=workflow_id,
        )
        self.shell.workflow_tabbar.addTab(workflow_id, alias)
        self.shell.install_workflow_surface(workflow_id)
        handle = PromptWorkflowHandle(
            alias=alias,
            workflow_id=workflow_id,
            cube_alias=stack_order[0],
            cube_state=cube_states[stack_order[0]],
        )
        self.workflows[alias] = handle
        self.activate_workflow(alias)
        panel = self.shell.editor_panels[workflow_id]
        panel.load_all_cubes(
            [(cube_alias, cube_states[cube_alias]) for cube_alias in stack_order],
            cube_states=cube_states,
            stack_order=stack_order,
        )
        self.shell.editor_panel_container.setCurrentWidget(panel)
        self.shell.editor_panel = panel
        panel.show()
        for cube_alias in stack_order:
            panel.reveal_loaded_cube(cube_alias)
        self._finalize_panel_projection(panel)
        field_key = (stack_order[0], "positive_prompt", "text")
        input_widgets = _panel_input_widgets(panel)
        self.wait_until(lambda: field_key in input_widgets)
        editor = input_widgets[field_key]
        if not isinstance(editor, PromptEditor):
            raise AssertionError(f"target field is {type(editor)!r}, not PromptEditor")
        self.process_events(cycles=8)
        field = PromptFieldHandle(
            workflow=handle,
            node_name="positive_prompt",
            field_key="text",
            editor=editor,
        )
        self._install_editor_observability(field)
        return field

    def probe_prompt_segment_scopes(
        self,
        field: PromptFieldHandle,
    ) -> PromptSegmentScopeProbe:
        """Capture model and segment state without refreshing either owner."""

        panel = self.shell.editor_panels[field.workflow.workflow_id]
        candidate = panel.active_model_context_controller.current_model()
        active_snapshot = panel.active_model_snapshot_controller.snapshot
        segment_controller = cast(Any, field.editor)._segment_preset_controller
        editor_snapshot = segment_controller.snapshot
        scopes = editor_snapshot.save_state.save_scopes
        return PromptSegmentScopeProbe(
            candidate_kind=None if candidate is None else candidate.model_kind,
            candidate_value=None if candidate is None else candidate.value,
            active_snapshot_readiness=active_snapshot.status.readiness.value,
            active_snapshot_reason=active_snapshot.status.unavailable_reason,
            active_snapshot_item_value=(
                None
                if active_snapshot.catalog_item is None
                else active_snapshot.catalog_item.backend_value
            ),
            active_snapshot_family_labels=tuple(
                association.label for association in active_snapshot.family_associations
            ),
            editor_snapshot_readiness=editor_snapshot.status.readiness.value,
            editor_snapshot_reason=editor_snapshot.status.unavailable_reason,
            editor_scope_titles=tuple(scope.title for scope in scopes),
            editor_scope_full_labels=tuple(scope.full_label for scope in scopes),
        )

    def probe_prompt_segment_dialog(
        self,
        field: PromptFieldHandle,
        *,
        selected_text: str,
    ) -> PromptSegmentDialogProbe:
        """Capture the production save request without displaying a modal dialog."""

        requests: list[object] = []

        def capture_request(request: object) -> None:
            """Record one dialog request and simulate cancellation."""

            requests.append(request)
            return None

        controller = cast(Any, field.editor)._segment_preset_controller
        controller.save_selected_segment_as_preset(
            selected_text,
            dialog_runner=capture_request,
        )
        if len(requests) != 1:
            raise AssertionError(
                f"expected one dialog request, received {len(requests)}"
            )
        request = cast(Any, requests[0])
        return PromptSegmentDialogProbe(
            title=str(request.title),
            selected_text=str(request.selected_text),
            scope_titles=tuple(scope.title for scope in request.scopes),
            scope_full_labels=tuple(scope.full_label for scope in request.scopes),
        )

    def activate_workflow(self, alias: str, *, force_refresh: bool = True) -> None:
        """Activate one workflow through the production workspace coordinator."""

        workflow_id = self.workflows[alias].workflow_id
        self.shell.workflow_workspace.activate_workflow(
            workflow_id,
            source="workflow_tab",
            force_refresh=force_refresh,
        )
        self.process_events()

    def activate_workflow_for_trace(
        self,
        alias: str,
        *,
        force_refresh: bool = True,
    ) -> None:
        """Activate a workflow and record the route as a replayable trace action."""

        self.activate_workflow(alias, force_refresh=force_refresh)
        self._trace_actions.append(PromptEditorTraceAction("activate_workflow", alias))

    def workflow_round_trip(self, field: PromptFieldHandle) -> PromptFieldHandle:
        """Switch away from a prompt workflow and back through real shell routing."""

        secondary_alias = f"{field.workflow.alias}-secondary"
        if secondary_alias not in self.workflows:
            self.add_prompt_workflow(
                secondary_alias,
                initial_text="secondary prompt",
                activate=False,
            )
        self.activate_workflow_for_trace(secondary_alias)
        self.activate_workflow_for_trace(field.workflow.alias)
        return self.prompt_field(field.workflow.alias)

    def prompt_field(self, alias: str) -> PromptFieldHandle:
        """Resolve the current real prompt editor field for one workflow alias."""

        workflow = self.workflows[alias]
        panel = self.shell.editor_panels[workflow.workflow_id]
        field_key = (workflow.cube_alias, "positive_prompt", "text")
        input_widgets = _panel_input_widgets(panel)
        widget = input_widgets[field_key]
        if not isinstance(widget, PromptEditor):
            raise AssertionError(f"target field is {type(widget)!r}, not PromptEditor")
        self.wait_until(lambda: widget.isVisible())
        return PromptFieldHandle(
            workflow=workflow,
            node_name="positive_prompt",
            field_key="text",
            editor=widget,
        )

    def focus_editor(self, field: PromptFieldHandle) -> QWidget:
        """Focus the real prompt projection surface used for keyboard input."""

        field.editor.show()
        self.shell.show()
        self.shell.raise_()
        self.shell.activateWindow()
        focus_target = _editor_event_widget(field.editor)
        focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
        self.process_events(cycles=8)
        return focus_target

    def replace_text_with_keys(self, field: PromptFieldHandle, text: str) -> None:
        """Replace prompt source through real selection and key events."""

        target = self.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.SelectAll)
        QTest.keyClicks(target, text)
        self._trace_actions.append(PromptEditorTraceAction("replace_text", text))
        self.process_events(cycles=8)

    def type_text(self, field: PromptFieldHandle, text: str) -> None:
        """Type text into the real prompt editor focus target."""

        target = self.focus_editor(field)
        QTest.keyClicks(target, text)
        self._trace_actions.append(PromptEditorTraceAction("type_text", text))
        self.process_events(cycles=8)

    def paste_text(self, field: PromptFieldHandle, text: str) -> None:
        """Paste text through the real clipboard and editor key route."""

        target = self.focus_editor(field)
        QApplication.clipboard().setText(text)
        QTest.keySequence(target, QKeySequence.StandardKey.Paste)
        self._trace_actions.append(PromptEditorTraceAction("paste_text", text))
        self.process_events(cycles=8)

    def undo(self, field: PromptFieldHandle) -> None:
        """Undo through the real editor key route."""

        target = self.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.Undo)
        self._trace_actions.append(PromptEditorTraceAction("undo", ""))
        self.process_events(cycles=8)

    def redo(self, field: PromptFieldHandle) -> None:
        """Redo through the real editor key route."""

        target = self.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.Redo)
        self._trace_actions.append(PromptEditorTraceAction("redo", ""))
        self.process_events(cycles=8)

    def set_source_cursor_position(
        self,
        field: PromptFieldHandle,
        position: int,
    ) -> None:
        """Place the real source cursor at one exact source boundary."""

        cursor = cast(Any, field.editor).textCursor()
        cursor.setPosition(position)
        field.editor.setTextCursor(cursor)
        self.process_events(cycles=4)

    def set_rich_rendering(
        self,
        field: PromptFieldHandle,
        *,
        enabled: bool,
    ) -> None:
        """Switch the real editor between projected and exact-source display."""

        field.editor.setRichPromptRenderingEnabled(enabled)
        self.process_events(cycles=8)

    def press_key(
        self,
        field: PromptFieldHandle,
        key: Qt.Key,
        *,
        text: str = "",
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> PromptEditorKeyRoute:
        """Send one key event and return a before/after route diagnostic."""

        target = self.focus_editor(field)
        before = self.capture_state_snapshot(field, label="before-key")
        QTest.keyClick(target, key, modifiers)
        self._trace_actions.append(
            PromptEditorTraceAction(
                "press_key",
                text,
                key=_enum_value(key),
                modifiers=_enum_value(modifiers),
            )
        )
        self.process_events(cycles=8)
        after = self.capture_state_snapshot(field, label="after-key")
        return PromptEditorKeyRoute(
            key_name=Qt.Key(key).name,
            text=text,
            modifiers=str(Qt.KeyboardModifier(modifiers).name),
            focus_before=before.focus_widget_path,
            focus_after=after.focus_widget_path,
            active_window_before=before.active_window_path,
            active_window_after=after.active_window_path,
            source_before=before.source_text,
            source_after=after.source_text,
            cursor_before=before.cursor_position,
            cursor_after=after.cursor_position,
            dropdown_visible_before=before.popup_visual_visible,
            dropdown_visible_after=after.popup_visual_visible,
            ghost_visible_before=before.ghost_visual_visible,
            ghost_visible_after=after.ghost_visual_visible,
            inserted_text=_inserted_text(before.source_text, after.source_text),
        )

    def move_cursor_to_end(self, field: PromptFieldHandle) -> None:
        """Move the real prompt cursor to the end through Qt cursor APIs."""

        cursor = cast(Any, field.editor).textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        field.editor.setTextCursor(cursor)
        self.process_events(cycles=4)

    def scroll_editor(self, field: PromptFieldHandle, target: str) -> None:
        """Scroll the mounted editor viewport through its real scrollbar owner."""

        scrollbar = field.editor.verticalScrollBar()
        if target == "top":
            value = scrollbar.minimum()
        elif target == "middle":
            value = (scrollbar.minimum() + scrollbar.maximum()) // 2
        elif target == "bottom":
            value = scrollbar.maximum()
        else:
            raise AssertionError(f"unknown scroll target {target!r}")
        scrollbar.setValue(value)
        self._trace_actions.append(PromptEditorTraceAction("scroll_editor", target))
        self.process_events(cycles=8)

    def seed_text_directly(self, field: PromptFieldHandle, text: str) -> None:
        """Seed editor text for setup-only abuse paths through a replayable action."""

        self.press_key(field, Qt.Key.Key_Escape)
        cast(Any, field.editor).setPlainText(text)
        self._trace_actions.append(PromptEditorTraceAction("seed_text_directly", text))
        self.process_events(cycles=8)
        self.move_cursor_to_end(field)

    def move_cursor_inside_text(self, field: PromptFieldHandle, text: str) -> None:
        """Place the caret inside the first matching source fragment."""

        source = field.editor.toPlainText()
        index = source.index(text)
        cursor = cast(Any, field.editor).textCursor()
        cursor.setPosition(index + 1)
        field.editor.setTextCursor(cursor)
        self.process_events(cycles=4)

    def click_away_from_editor(self) -> None:
        """Click a real focusable shell widget outside the prompt editor."""

        focus_target = self.shell.canvas_tabs.canvas_map["Input"]
        if not isinstance(focus_target, QWidget):
            raise AssertionError("Input canvas must be a focusable QWidget")
        focus_target.setFocus(Qt.FocusReason.MouseFocusReason)
        QTest.mouseClick(
            focus_target,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            focus_target.rect().center(),
        )
        self._trace_actions.append(PromptEditorTraceAction("click_away", ""))
        self.process_events(cycles=10)

    def trace_prompt_context_menu(
        self,
        field: PromptFieldHandle,
        *,
        clicked_text: str,
        trigger_first_lora_action: bool = False,
        trigger_lora_action_label: str | None = None,
        before_trigger_lora_action: Callable[[], None] | None = None,
        populate_lazy_submenus: bool = True,
    ) -> PromptEditorContextMenuTrace:
        """Open a real prompt context menu and capture LoRA trigger action state.

        Args:
            field: Mounted production prompt field to exercise.
            clicked_text: Visible source fragment that receives the right-click.
            trigger_first_lora_action: Trigger the first captured LoRA action.
            trigger_lora_action_label: Trigger the action whose visible or full label
                matches this value.
            before_trigger_lora_action: Run a lifecycle mutation after menu capture
                but before triggering the selected LoRA action.
            populate_lazy_submenus: Populate lazy QFluent submenus for inspection.
        """

        if trigger_first_lora_action and trigger_lora_action_label is not None:
            raise ValueError("choose either the first action or a named action")

        from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
            RoundMenu,
        )
        from substitute.presentation.editor.prompt_editor.shell import (
            context_menu_controller as prompt_context_menu_module,
        )

        editor = field.editor
        source_before = editor.toPlainText()
        local_pos = _viewport_position_for_source_text(editor, clicked_text)
        viewport = editor.viewport()
        global_pos = viewport.mapToGlobal(local_pos)
        click_source_position = _source_position_for_text(editor, clicked_text)
        snapshot_before = _prepared_lora_action_snapshot(editor, source_before)
        cached_before = _cached_scheduled_loras(editor, source_before)
        captured_menu_rows: list[str] = []
        captured_submenu_rows: list[tuple[str, tuple[str, ...]]] = []
        captured_trigger_actions: list[QAction] = []
        triggered_action_text: str | None = None
        original_exec = RoundMenu.exec
        text_menu_class = cast(
            Any, prompt_context_menu_module
        )._PromptEditorTextEditMenu
        original_text_menu_exec = text_menu_class.exec
        event_dispatch_elapsed_ms = 0.0
        menu_exec_elapsed_ms = 0.0
        text_menu_exec_elapsed_ms = 0.0

        def capture_exec(menu: object, *_args: object, **_kwargs: object) -> None:
            """Capture the real QFluent menu instead of showing a native popup."""

            nonlocal menu_exec_elapsed_ms
            nonlocal triggered_action_text
            started_at = perf_counter()
            captured_menu_rows.extend(_round_menu_rows(menu))
            if populate_lazy_submenus:
                _populate_lazy_round_menu_submenus(menu)
            captured_submenu_rows.extend(_round_menu_submenu_rows(menu))
            captured_trigger_actions.extend(_round_menu_trigger_actions(menu))
            action = _selected_trigger_action(
                tuple(captured_trigger_actions),
                trigger_first=trigger_first_lora_action,
                requested_label=trigger_lora_action_label,
            )
            if action is not None:
                if before_trigger_lora_action is not None:
                    before_trigger_lora_action()
                triggered_action_text = action.text()
                action.trigger()
            menu_exec_elapsed_ms += (perf_counter() - started_at) * 1000.0

        def capture_text_menu_exec(
            menu: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            """Measure prompt menu population before the final RoundMenu boundary."""

            nonlocal text_menu_exec_elapsed_ms
            started_at = perf_counter()
            try:
                return original_text_menu_exec(menu, *args, **kwargs)
            finally:
                text_menu_exec_elapsed_ms += (perf_counter() - started_at) * 1000.0

        RoundMenu.exec = capture_exec
        text_menu_class.exec = capture_text_menu_exec
        try:
            started_at = perf_counter()
            press_event = QMouseEvent(
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QPointF(local_pos),
                QtCore.QPointF(global_pos),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QCoreApplication.sendEvent(viewport, press_event)
            context_event = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                local_pos,
                global_pos,
            )
            QCoreApplication.sendEvent(viewport, context_event)
            event_dispatch_elapsed_ms = (perf_counter() - started_at) * 1000.0
            self.process_events(cycles=10)
        finally:
            text_menu_class.exec = original_text_menu_exec
            RoundMenu.exec = original_exec

        source_after = editor.toPlainText()
        snapshot_after = _prepared_lora_action_snapshot(editor, source_after)
        cached_after = _cached_scheduled_loras(editor, source_after)
        self._trace_actions.append(
            PromptEditorTraceAction("context_menu", clicked_text)
        )
        return PromptEditorContextMenuTrace(
            source_before=source_before,
            source_after=source_after,
            clicked_text=clicked_text,
            click_source_position=click_source_position,
            menu_rows=tuple(captured_menu_rows),
            submenu_rows=tuple(captured_submenu_rows),
            trigger_action_texts=tuple(
                action.text() for action in captured_trigger_actions
            ),
            trigger_action_full_labels=tuple(
                str(action.property("promptFullTriggerWordsLabel"))
                for action in captured_trigger_actions
            ),
            triggered_action_text=triggered_action_text,
            lora_snapshot_readiness_before=_snapshot_readiness(snapshot_before),
            lora_snapshot_unavailable_before=_snapshot_unavailable_reason(
                snapshot_before
            ),
            lora_snapshot_action_count_before=_snapshot_action_count(snapshot_before),
            lora_snapshot_readiness_after=_snapshot_readiness(snapshot_after),
            lora_snapshot_unavailable_after=_snapshot_unavailable_reason(
                snapshot_after
            ),
            lora_snapshot_action_count_after=_snapshot_action_count(snapshot_after),
            cached_scheduled_lora_count_before=(
                None if cached_before is None else len(cached_before)
            ),
            cached_scheduled_lora_count_after=(
                None if cached_after is None else len(cached_after)
            ),
            event_dispatch_elapsed_ms=event_dispatch_elapsed_ms,
            menu_exec_elapsed_ms=menu_exec_elapsed_ms,
            menu_population_elapsed_ms=max(
                0.0,
                text_menu_exec_elapsed_ms - menu_exec_elapsed_ms,
            ),
            captured_menu_row_count=len(captured_menu_rows),
            captured_submenu_row_count=sum(
                len(rows) for _title, rows in captured_submenu_rows
            ),
            captured_action_count=len(captured_trigger_actions),
        )

    def probe_inline_lora_context_menu(
        self,
        field: PromptFieldHandle,
    ) -> PromptInlineLoraMenuProbe:
        """Present the first projected LoRA token through its production presenter."""

        from qfluentwidgets.components.widgets.menu import (
            RoundMenu,
        )

        editor = field.editor
        surface = getattr(editor, "_surface")
        projection_document = getattr(surface, "_projection_document")
        token = next(
            (
                candidate
                for candidate in projection_document.tokens
                if getattr(getattr(candidate, "kind", None), "value", None) == "lora"
            ),
            None,
        )
        if token is None:
            raise AssertionError("mounted prompt has no projected LoRA token")
        captured_rows: list[str] = []
        captured_trigger_actions: list[QAction] = []
        original_exec = RoundMenu.exec

        def capture_exec(menu: object, *_args: object, **_kwargs: object) -> None:
            """Capture the rendered inline menu without displaying a popup."""

            captured_rows.extend(_round_menu_rows(menu))
            captured_trigger_actions.extend(_round_menu_trigger_actions(menu))

        RoundMenu.exec = capture_exec
        try:
            presenter = getattr(editor, "_inline_lora_menu_presenter")
            presenter.show_lora_context_menu(
                token,
                editor.viewport().mapToGlobal(editor.viewport().rect().center()),
            )
            self.process_events(cycles=10)
        finally:
            RoundMenu.exec = original_exec
        return PromptInlineLoraMenuProbe(
            menu_rows=tuple(captured_rows),
            trigger_action_texts=tuple(
                action.text() for action in captured_trigger_actions
            ),
            trigger_action_full_labels=tuple(
                str(action.property("promptFullTriggerWordsLabel"))
                for action in captured_trigger_actions
            ),
        )

    def switch_canvas(self, label: str) -> None:
        """Switch a real canvas tab through the shell canvas tab manager."""

        self.shell.canvas_tabs.focus_attached_canvas(label)
        canvas = self.shell.canvas_tabs.canvas_map[label]
        if isinstance(canvas, QWidget):
            canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        self._trace_actions.append(PromptEditorTraceAction("switch_canvas", label))
        self.process_events(cycles=10)

    def _install_editor_observability(self, field: PromptFieldHandle) -> None:
        """Wrap production editor collaborators with passive call tracing."""

        editor = field.editor
        if id(editor) in self._observed_editor_ids:
            return
        self._observed_editor_ids.add(id(editor))
        surface = getattr(editor, "_surface", None)
        interaction = getattr(editor, "_interaction_controller", None)
        autocomplete = getattr(interaction, "_autocomplete", None)
        autocomplete_timing = getattr(
            interaction,
            "_autocomplete_timing_controller",
            None,
        )
        autocomplete_preview_projection = getattr(
            surface,
            "_autocomplete_preview_projection_owner",
            None,
        )
        caret_preview_coordinator = getattr(
            surface,
            "_caret_autocomplete_preview_coordinator",
            None,
        )
        caret_movement_controller = getattr(
            surface,
            "_caret_movement_controller",
            None,
        )
        observed_targets = (
            (
                editor,
                "prompt editor event route",
                (
                    "_handle_prompt_key_press",
                    "focusOutEvent",
                    "hideEvent",
                    "set_autocomplete_preview_state",
                ),
            ),
            (
                interaction,
                "prompt editor interaction controller",
                (
                    "handle_key_press",
                    "handle_post_key_press",
                    "handle_focus_out",
                    "handle_hide",
                ),
            ),
            (
                autocomplete,
                "autocomplete lifecycle owner",
                (
                    "handle_key_press",
                    "dismiss_autocomplete",
                    "retarget_from_query_state",
                    "refresh_for_query",
                    "_present_active_surfaces",
                    "_publish_inline_completion_preview",
                    "_clear_inline_completion_preview",
                ),
            ),
            (
                autocomplete_timing,
                "autocomplete timing owner",
                (
                    "handle_post_key_press",
                    "handle_focus_out",
                    "handle_hide",
                    "_retarget_from_current_state",
                    "_retarget_from_source_snapshot",
                ),
            ),
            (
                surface,
                "projection source and caret owner",
                (
                    "set_autocomplete_preview_state",
                    "_insert_viewport_text",
                    "_replace_viewport_range",
                    "_backspace",
                    "_delete",
                    "_flush_pending_projection_update",
                    "_mark_source_text_changed",
                    "clear_autocomplete_preview_state",
                    "invalidate_autocomplete_preview_paint",
                ),
            ),
            (
                autocomplete_preview_projection,
                "autocomplete preview projection owner",
                ("set_preview_state",),
            ),
            (
                caret_preview_coordinator,
                "caret autocomplete preview coordinator",
                ("reconcile_after_caret_state_change",),
            ),
            (
                caret_movement_controller,
                "projection caret movement owner",
                ("move_horizontally", "move_vertically"),
            ),
        )
        for target, owner, method_names in observed_targets:
            for method_name in method_names:
                self._wrap_observed_method(
                    editor=editor,
                    target=target,
                    owner=owner,
                    method_name=method_name,
                )

    def _wrap_observed_method(
        self,
        *,
        editor: PromptEditor,
        target: object | None,
        owner: str,
        method_name: str,
    ) -> None:
        """Install one passive method wrapper when the collaborator exists."""

        if target is None:
            return
        original = getattr(target, method_name, None)
        if not callable(original) or getattr(
            original, "_prompt_harness_wrapped", False
        ):
            return

        def wrapper(*args: object, **kwargs: object) -> object:
            before = _compact_editor_state(editor)
            result: object = None
            result_repr = "<raised>"
            try:
                result = original(*args, **kwargs)
                result_repr = _short_repr(result)
                return result
            finally:
                after = _compact_editor_state(editor)
                self._observed_events.append(
                    PromptEditorObservedEvent(
                        index=len(self._observed_events),
                        owner=owner,
                        method=method_name,
                        source_before=str(before["source"]),
                        source_after=str(after["source"]),
                        cursor_before=int(before["cursor"]),
                        cursor_after=int(after["cursor"]),
                        preview_before=str(before["preview"]),
                        preview_after=str(after["preview"]),
                        session_before=str(before["session"]),
                        session_after=str(after["session"]),
                        panel_before=str(before["panel"]),
                        panel_after=str(after["panel"]),
                        result=result_repr,
                    )
                )

        setattr(wrapper, "_prompt_harness_wrapped", True)
        setattr(target, method_name, wrapper)

    def capture_state_snapshot(
        self,
        field: PromptFieldHandle,
        *,
        label: str,
    ) -> PromptEditorStateSnapshot:
        """Capture headless shell, editor, autocomplete, projection diagnostics."""

        self.process_events(cycles=6)
        editor = field.editor
        panel = self.shell.editor_panels[field.workflow.workflow_id]
        viewport = editor.viewport()
        popup = _autocomplete_panel(editor)
        cursor = cast(Any, editor).textCursor()
        selected_text = cursor.selectedText()
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        display_mode = str(editor.displayMode())
        autocomplete_preview = _autocomplete_preview_state(editor)
        autocomplete_state = _autocomplete_owner_state(editor)
        projection_state = _projection_owner_state(editor)
        expected_suffix = _expected_ghost_suffix(editor, autocomplete_preview)
        observed_event_start_index = max(0, len(self._observed_events) - 10000)
        recent_observed_events = tuple(
            self._observed_events[observed_event_start_index:]
        )
        popup_global_rect = _global_rect_tuple(popup) if popup is not None else None
        popup_visual_visible = bool(popup is not None and popup.isVisible())
        return PromptEditorStateSnapshot(
            label=label,
            source_text=editor.toPlainText(),
            selected_text=selected_text,
            selected_source_text=editor.toPlainText()[selection_start:selection_end],
            selection_range=(selection_start, selection_end),
            selection_rects=cast(
                tuple[tuple[float, float, float, float], ...],
                projection_state["selection_rects"],
            ),
            cursor_position=cursor.position(),
            display_mode=display_mode,
            focus_widget_path=_object_path(QApplication.focusWidget()),
            active_window_path=_object_path(QApplication.activeWindow()),
            target_event_widget_path=_object_path(_editor_event_widget(editor)),
            geometries={
                "shell": _rect_tuple(self.shell.geometry()),
                "panel": _rect_tuple(panel.geometry()),
                "editor": _rect_tuple(editor.geometry()),
                "viewport": _rect_tuple(viewport.geometry()),
                "popup": _rect_tuple(popup.geometry()) if popup is not None else None,
            },
            global_geometries={
                "shell": _global_rect_tuple(self.shell),
                "panel": _global_rect_tuple(panel),
                "editor": _global_rect_tuple(editor),
                "viewport": _global_rect_tuple(viewport),
                "popup": popup_global_rect,
            },
            scroll_values={
                "editor_vertical": editor.verticalScrollBar().value(),
                "editor_horizontal": _scrollbar_value(editor, "horizontalScrollBar"),
            },
            device_pixel_ratio=float(viewport.devicePixelRatioF()),
            autocomplete_gateway_calls=tuple(self.autocomplete_gateway.calls),
            popup_widget_exists=popup is not None,
            popup_state_visible=bool(popup is not None and popup.isVisible()),
            popup_visual_visible=popup_visual_visible,
            popup_global_rect=popup_global_rect,
            ghost_visual_visible=bool(
                projection_state["autocomplete_ghost_paint_visible_by_owner_state"]
            ),
            expected_ghost_suffix=expected_suffix,
            autocomplete_preview_active=autocomplete_preview is not None,
            autocomplete_preview_suffix=_autocomplete_preview_suffix(
                autocomplete_preview
            ),
            autocomplete_preview_source_position=(
                _autocomplete_preview_source_position(autocomplete_preview)
            ),
            autocomplete_session_lifecycle=autocomplete_state["lifecycle"],
            autocomplete_session_mode=autocomplete_state["mode"],
            autocomplete_session_selected_index=int(
                autocomplete_state["selected_index"]
            ),
            autocomplete_session_prefix=autocomplete_state["prefix"],
            autocomplete_session_word_start=_optional_int(
                autocomplete_state["word_start"]
            ),
            autocomplete_session_word_end=_optional_int(autocomplete_state["word_end"]),
            autocomplete_session_active_tag_end=_optional_int(
                autocomplete_state["active_tag_end"]
            ),
            autocomplete_session_suggestions=tuple(
                cast(tuple[str, ...], autocomplete_state["suggestions"])
            ),
            autocomplete_has_active_session=bool(autocomplete_state["has_active"]),
            autocomplete_presenter_panel_visible=bool(
                autocomplete_state["presenter_panel_visible"]
            ),
            autocomplete_presenter_panel_under_mouse=bool(
                autocomplete_state["presenter_panel_under_mouse"]
            ),
            autocomplete_source_revision=_optional_int(
                autocomplete_state["source_revision"]
            ),
            autocomplete_snapshot_source_length=_optional_int(
                autocomplete_state["snapshot_source_length"]
            ),
            autocomplete_snapshot_cursor_position=_optional_int(
                autocomplete_state["snapshot_cursor_position"]
            ),
            source_revision=_optional_int(projection_state["source_revision"]),
            editing_session_source_revision=_optional_int(
                projection_state["editing_session_source_revision"]
            ),
            editing_session_cursor_position=_optional_int(
                projection_state["editing_session_cursor_position"]
            ),
            editing_session_anchor_position=_optional_int(
                projection_state["editing_session_anchor_position"]
            ),
            document_view_source_text=projection_state["document_view_source_text"],
            projection_document_source_text=projection_state[
                "projection_document_source_text"
            ],
            active_projection_source_text=projection_state[
                "active_projection_source_text"
            ],
            layout_projection_source_text=projection_state[
                "layout_projection_source_text"
            ],
            projection_text=projection_state["projection_text"],
            active_projection_text=projection_state["active_projection_text"],
            layout_projection_text=projection_state["layout_projection_text"],
            layout_uses_projection_document=bool(
                projection_state["layout_uses_projection_document"]
            ),
            layout_uses_active_projection_document=bool(
                projection_state["layout_uses_active_projection_document"]
            ),
            paint_cache_key_present=bool(projection_state["paint_cache_key_present"]),
            paint_cache_source_revision=_optional_int(
                projection_state["paint_cache_source_revision"]
            ),
            paint_cache_projection_document_identity_matches_layout=bool(
                projection_state[
                    "paint_cache_projection_document_identity_matches_layout"
                ]
            ),
            paint_cache_layout_snapshot_identity_matches_layout=bool(
                projection_state["paint_cache_layout_snapshot_identity_matches_layout"]
            ),
            paint_cache_ghosted_run_ids=tuple(
                cast(tuple[str, ...], projection_state["paint_cache_ghosted_run_ids"])
            ),
            autocomplete_ghost_paint_visible_by_owner_state=bool(
                projection_state["autocomplete_ghost_paint_visible_by_owner_state"]
            ),
            projection_freshness=projection_state["projection_freshness"],
            projection_has_pending_update=bool(
                projection_state["projection_has_pending_update"]
            ),
            projection_has_stale_geometry=bool(
                projection_state["projection_has_stale_geometry"]
            ),
            caret_state_source_position=_optional_int(
                projection_state["caret_state_source_position"]
            ),
            anchor_state_source_position=_optional_int(
                projection_state["anchor_state_source_position"]
            ),
            caret_map_source_length=_optional_int(
                projection_state["caret_map_source_length"]
            ),
            caret_map_stop_count=_optional_int(
                projection_state["caret_map_stop_count"]
            ),
            caret_preferred_x=_optional_float(projection_state["caret_preferred_x"]),
            caret_rect_override=cast(
                tuple[float, float, float, float] | None,
                projection_state["caret_rect_override"],
            ),
            skip_next_same_source_soft_wrap_move=bool(
                projection_state["skip_next_same_source_soft_wrap_move"]
            ),
            projection_token_count=int(projection_state["projection_token_count"]),
            projection_run_count=int(projection_state["projection_run_count"]),
            layout_line_count=int(projection_state["layout_line_count"]),
            layout_text_fragment_count=int(
                projection_state["layout_text_fragment_count"]
            ),
            layout_inline_object_fragment_count=int(
                projection_state["layout_inline_object_fragment_count"]
            ),
            layout_content_width=float(projection_state["layout_content_width"]),
            layout_content_height=float(projection_state["layout_content_height"]),
            layout_text_width=float(projection_state["layout_text_width"]),
            projection_metrics_text_line_height=_optional_float(
                projection_state["projection_metrics_text_line_height"]
            ),
            projection_metrics_ascent=_optional_float(
                projection_state["projection_metrics_ascent"]
            ),
            projection_metrics_descent=_optional_float(
                projection_state["projection_metrics_descent"]
            ),
            projection_metrics_document_margin=_optional_float(
                projection_state["projection_metrics_document_margin"]
            ),
            projection_metrics_content_left_inset=_optional_float(
                projection_state["projection_metrics_content_left_inset"]
            ),
            projection_metrics_content_height=_optional_float(
                projection_state["projection_metrics_content_height"]
            ),
            shell_natural_height=_optional_int(
                projection_state["shell_natural_height"]
            ),
            shell_effective_height=_optional_int(
                projection_state["shell_effective_height"]
            ),
            shell_minimum_editor_height=_optional_int(
                projection_state["shell_minimum_editor_height"]
            ),
            shell_outer_vertical_padding=_optional_int(
                projection_state["shell_outer_vertical_padding"]
            ),
            shell_document_vertical_padding=_optional_int(
                projection_state["shell_document_vertical_padding"]
            ),
            visible_layout_rows=tuple(
                cast(
                    tuple[PromptEditorVisibleLayoutRow, ...],
                    projection_state["visible_layout_rows"],
                )
            ),
            visible_text_fragments=tuple(
                cast(
                    tuple[PromptEditorVisibleTextFragment, ...],
                    projection_state["visible_text_fragments"],
                )
            ),
            caret_token_id=cast(str | None, projection_state["caret_token_id"]),
            anchor_token_id=cast(str | None, projection_state["anchor_token_id"]),
            caret_token_id_resolves=bool(projection_state["caret_token_id_resolves"]),
            anchor_token_id_resolves=bool(projection_state["anchor_token_id_resolves"]),
            caret_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["caret_rect"],
            ),
            viewport_rect=cast(
                tuple[int, int, int, int],
                projection_state["viewport_rect"],
            ),
            caret_rect_finite=bool(projection_state["caret_rect_finite"]),
            caret_rect_has_area=bool(projection_state["caret_rect_has_area"]),
            caret_rect_intersects_viewport=bool(
                projection_state["caret_rect_intersects_viewport"]
            ),
            vertical_scroll_minimum=int(projection_state["vertical_scroll_minimum"]),
            vertical_scroll_maximum=int(projection_state["vertical_scroll_maximum"]),
            vertical_scroll_page_step=int(
                projection_state["vertical_scroll_page_step"]
            ),
            horizontal_scroll_minimum=int(
                projection_state["horizontal_scroll_minimum"]
            ),
            horizontal_scroll_maximum=int(
                projection_state["horizontal_scroll_maximum"]
            ),
            horizontal_scroll_page_step=int(
                projection_state["horizontal_scroll_page_step"]
            ),
            transient_caret_geometry_present=bool(
                projection_state["transient_caret_geometry_present"]
            ),
            transient_caret_geometry_valid=bool(
                projection_state["transient_caret_geometry_valid"]
            ),
            transient_insertion_overlay_present=bool(
                projection_state["transient_insertion_overlay_present"]
            ),
            transient_insertion_overlay_valid=bool(
                projection_state["transient_insertion_overlay_valid"]
            ),
            transient_insertion_overlay_source_range=cast(
                tuple[int, int] | None,
                projection_state["transient_insertion_overlay_source_range"],
            ),
            transient_insertion_overlay_viewport_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["transient_insertion_overlay_viewport_rect"],
            ),
            transient_insertion_overlay_repaint_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["transient_insertion_overlay_repaint_rect"],
            ),
            transient_deletion_overlay_present=bool(
                projection_state["transient_deletion_overlay_present"]
            ),
            transient_deletion_overlay_valid=bool(
                projection_state["transient_deletion_overlay_valid"]
            ),
            transient_deletion_overlay_source_range=cast(
                tuple[int, int] | None,
                projection_state["transient_deletion_overlay_source_range"],
            ),
            transient_deletion_overlay_viewport_rects=cast(
                tuple[tuple[float, float, float, float], ...],
                projection_state["transient_deletion_overlay_viewport_rects"],
            ),
            transient_deletion_overlay_erase_rects=cast(
                tuple[tuple[float, float, float, float], ...],
                projection_state["transient_deletion_overlay_erase_rects"],
            ),
            transient_deletion_overlay_repaint_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["transient_deletion_overlay_repaint_rect"],
            ),
            undo_available=bool(projection_state["undo_available"]),
            redo_available=bool(projection_state["redo_available"]),
            undo_depth=int(projection_state["undo_depth"]),
            redo_depth=int(projection_state["redo_depth"]),
            undo_max_depth=int(projection_state["undo_max_depth"]),
            redo_max_depth=int(projection_state["redo_max_depth"]),
            undo_edit_block_depth=int(projection_state["undo_edit_block_depth"]),
            undo_pending_state_present=bool(
                projection_state["undo_pending_state_present"]
            ),
            undo_typing_group_active=bool(projection_state["undo_typing_group_active"]),
            undo_typing_group_last_cursor_position=_optional_int(
                projection_state["undo_typing_group_last_cursor_position"]
            ),
            undo_delete_group_active=bool(projection_state["undo_delete_group_active"]),
            undo_delete_group_key=_optional_int(
                projection_state["undo_delete_group_key"]
            ),
            observed_event_start_index=observed_event_start_index,
            observed_event_end_index=len(self._observed_events),
            recent_observed_events=recent_observed_events,
        )

    def save_artifacts(
        self,
        name: str,
        *,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
        invariant: str,
        observed: str,
    ) -> Path:
        """Persist replayable JSON diagnostics for a failure."""

        directory = self.artifact_root / name
        directory.mkdir(parents=True, exist_ok=True)
        _write_snapshot_json(directory / "state-before.json", before)
        _write_snapshot_json(directory / "state-after.json", after)
        _write_metadata_json(directory / "metadata.json", self.shell, after)
        _write_trace_json(directory / "trace.json", self.trace())
        (directory / "README.md").write_text(
            "\n".join(
                (
                    f"# {name}",
                    "",
                    f"Invariant: {invariant}",
                    "",
                    f"Observed: {observed}",
                    "",
                    "Replay command:",
                    (
                        ".\\.venv\\Scripts\\python.exe -m pytest "
                        "tests\\test_real_shell_prompt_editor_autocomplete_scenarios.py -q"
                    ),
                    "",
                    "Likely owner path: real-shell harness diagnostic pending.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        return directory

    def invariant_violations(
        self,
        snapshot: PromptEditorStateSnapshot,
    ) -> tuple[str, ...]:
        """Return code-level prompt editor invariant violations for one snapshot."""

        violations: list[str] = []
        source_length = len(snapshot.source_text)
        if not 0 <= snapshot.cursor_position <= source_length:
            violations.append(
                f"cursor_out_of_source_bounds:{snapshot.cursor_position}:{source_length}"
            )
        selection_start, selection_end = snapshot.selection_range
        if not 0 <= selection_start <= selection_end <= source_length:
            violations.append(
                f"selection_out_of_source_bounds:{selection_start}:{selection_end}:"
                f"{source_length}"
            )
        if snapshot.selected_text not in _accepted_selected_text_for_source(
            snapshot.selected_source_text
        ):
            violations.append("selected_text_source_slice_mismatch")
        selection_is_empty = selection_start == selection_end
        if selection_is_empty and snapshot.selection_rects:
            violations.append("selection_rects_present_for_empty_selection")
        if snapshot.editing_session_cursor_position != snapshot.cursor_position:
            violations.append(
                "editing_session_cursor_mismatch:"
                f"{snapshot.editing_session_cursor_position}:{snapshot.cursor_position}"
            )
        if snapshot.caret_state_source_position != snapshot.cursor_position:
            violations.append(
                "caret_state_cursor_mismatch:"
                f"{snapshot.caret_state_source_position}:{snapshot.cursor_position}"
            )
        projection_is_allowed_to_lag = (
            snapshot.projection_has_pending_update
            and snapshot.projection_has_stale_geometry
        )
        if not selection_is_empty and not projection_is_allowed_to_lag:
            if not snapshot.selection_rects:
                violations.append("selection_rects_missing_for_nonempty_selection")
            for rect in snapshot.selection_rects:
                if not _rect_tuple_is_finite_nonnegative(rect):
                    violations.append(f"selection_rect_invalid:{rect}")
                elif not _document_rect_within_layout_envelope(
                    rect,
                    content_width=snapshot.layout_text_width,
                    content_height=snapshot.layout_content_height,
                ):
                    violations.append(f"selection_rect_outside_layout:{rect}")
        if (
            not projection_is_allowed_to_lag
            and snapshot.caret_map_source_length != source_length
        ):
            violations.append(
                f"caret_map_source_length_mismatch:{snapshot.caret_map_source_length}:"
                f"{source_length}"
            )
        if (
            snapshot.caret_map_stop_count is not None
            and snapshot.caret_map_stop_count < 1
        ):
            violations.append("caret_map_has_no_stops")
        if snapshot.caret_preferred_x is not None:
            if not math.isfinite(snapshot.caret_preferred_x):
                violations.append(
                    f"caret_preferred_x_not_finite:{snapshot.caret_preferred_x}"
                )
            elif snapshot.caret_preferred_x < -4.0:
                violations.append(
                    f"caret_preferred_x_negative:{snapshot.caret_preferred_x}"
                )
            elif snapshot.caret_preferred_x > snapshot.layout_text_width + 64.0:
                violations.append(
                    "caret_preferred_x_outside_layout_width:"
                    f"{snapshot.caret_preferred_x}:{snapshot.layout_text_width}"
                )
        if snapshot.caret_rect_override is not None:
            if not _rect_tuple_is_finite_nonnegative(snapshot.caret_rect_override):
                violations.append(
                    f"caret_rect_override_invalid:{snapshot.caret_rect_override}"
                )
            elif not _document_rect_within_layout_envelope(
                snapshot.caret_rect_override,
                content_width=snapshot.layout_text_width,
                content_height=snapshot.layout_content_height,
            ):
                violations.append(
                    f"caret_rect_override_outside_layout:{snapshot.caret_rect_override}"
                )
        if snapshot.projection_run_count < 0:
            violations.append("projection_run_count_negative")
        if snapshot.projection_token_count < 0:
            violations.append("projection_token_count_negative")
        if snapshot.layout_line_count < 0:
            violations.append("layout_line_count_negative")
        if snapshot.layout_text_fragment_count < 0:
            violations.append("layout_text_fragment_count_negative")
        if snapshot.layout_inline_object_fragment_count < 0:
            violations.append("layout_inline_object_fragment_count_negative")
        if (
            not math.isfinite(snapshot.layout_content_width)
            or snapshot.layout_content_width < 0.0
        ):
            violations.append(
                f"layout_content_width_invalid:{snapshot.layout_content_width}"
            )
        if (
            not math.isfinite(snapshot.layout_content_height)
            or snapshot.layout_content_height < 0.0
        ):
            violations.append(
                f"layout_content_height_invalid:{snapshot.layout_content_height}"
            )
        if (
            not math.isfinite(snapshot.layout_text_width)
            or snapshot.layout_text_width < 1.0
        ):
            violations.append(f"layout_text_width_invalid:{snapshot.layout_text_width}")
        if not snapshot.caret_token_id_resolves:
            violations.append(f"caret_token_id_unresolved:{snapshot.caret_token_id}")
        if not snapshot.anchor_token_id_resolves:
            violations.append(f"anchor_token_id_unresolved:{snapshot.anchor_token_id}")
        if not snapshot.caret_rect_finite:
            violations.append("caret_rect_not_finite")
        if not snapshot.caret_rect_has_area:
            violations.append("caret_rect_missing_area")
        if not (
            snapshot.vertical_scroll_minimum
            <= snapshot.scroll_values["editor_vertical"]
            <= snapshot.vertical_scroll_maximum
        ):
            violations.append(
                "vertical_scroll_value_out_of_range:"
                f"{snapshot.vertical_scroll_minimum}:"
                f"{snapshot.scroll_values['editor_vertical']}:"
                f"{snapshot.vertical_scroll_maximum}"
            )
        if snapshot.vertical_scroll_page_step < 0:
            violations.append("vertical_scroll_page_step_negative")
        if snapshot.vertical_scroll_maximum < snapshot.vertical_scroll_minimum:
            violations.append("vertical_scroll_range_inverted")
        if not (
            snapshot.horizontal_scroll_minimum
            <= snapshot.scroll_values["editor_horizontal"]
            <= snapshot.horizontal_scroll_maximum
        ):
            violations.append(
                "horizontal_scroll_value_out_of_range:"
                f"{snapshot.horizontal_scroll_minimum}:"
                f"{snapshot.scroll_values['editor_horizontal']}:"
                f"{snapshot.horizontal_scroll_maximum}"
            )
        if snapshot.horizontal_scroll_page_step < 0:
            violations.append("horizontal_scroll_page_step_negative")
        if snapshot.horizontal_scroll_maximum < snapshot.horizontal_scroll_minimum:
            violations.append("horizontal_scroll_range_inverted")
        if (
            snapshot.transient_caret_geometry_present
            and not snapshot.transient_caret_geometry_valid
        ):
            violations.append("stale_transient_caret_geometry")
        if (
            snapshot.transient_insertion_overlay_present
            and not snapshot.transient_insertion_overlay_valid
        ):
            violations.append("stale_transient_insertion_overlay")
        if snapshot.transient_insertion_overlay_source_range is not None:
            start, end = snapshot.transient_insertion_overlay_source_range
            if not 0 <= start <= end <= source_length:
                violations.append(
                    "transient_insertion_overlay_range_out_of_bounds:"
                    f"{start}:{end}:{source_length}"
                )
        if (
            snapshot.transient_insertion_overlay_present
            and snapshot.transient_insertion_overlay_valid
            and snapshot.transient_insertion_overlay_viewport_rect is None
        ):
            violations.append("transient_insertion_overlay_viewport_rect_missing")
        if (
            snapshot.transient_insertion_overlay_present
            and snapshot.transient_insertion_overlay_valid
            and snapshot.transient_insertion_overlay_repaint_rect is None
        ):
            violations.append("transient_insertion_overlay_repaint_rect_missing")
        for rect_name, overlay_rect in (
            (
                "transient_insertion_overlay_viewport_rect",
                snapshot.transient_insertion_overlay_viewport_rect,
            ),
            (
                "transient_insertion_overlay_repaint_rect",
                snapshot.transient_insertion_overlay_repaint_rect,
            ),
        ):
            if overlay_rect is None:
                continue
            if not _rect_tuple_is_finite_nonnegative(overlay_rect):
                violations.append(f"{rect_name}_invalid:{overlay_rect}")
            elif not _transient_dirty_rect_within_viewport_envelope(
                overlay_rect,
                snapshot.viewport_rect,
            ):
                violations.append(f"{rect_name}_too_broad:{overlay_rect}")
        if (
            snapshot.transient_deletion_overlay_present
            and not snapshot.transient_deletion_overlay_valid
        ):
            violations.append("stale_transient_deletion_overlay")
        if snapshot.transient_deletion_overlay_source_range is not None:
            start, end = snapshot.transient_deletion_overlay_source_range
            if not 0 <= start <= end:
                violations.append(
                    f"transient_deletion_overlay_range_invalid:{start}:{end}"
                )
        if (
            snapshot.transient_deletion_overlay_present
            and snapshot.transient_deletion_overlay_valid
            and not snapshot.transient_deletion_overlay_viewport_rects
        ):
            violations.append("transient_deletion_overlay_viewport_rects_missing")
        if (
            snapshot.transient_deletion_overlay_present
            and snapshot.transient_deletion_overlay_valid
            and not snapshot.transient_deletion_overlay_erase_rects
        ):
            violations.append("transient_deletion_overlay_erase_rects_missing")
        if (
            snapshot.transient_deletion_overlay_present
            and snapshot.transient_deletion_overlay_valid
            and snapshot.transient_deletion_overlay_repaint_rect is None
        ):
            violations.append("transient_deletion_overlay_repaint_rect_missing")
        for rect_name, rects in (
            (
                "transient_deletion_overlay_viewport_rect",
                snapshot.transient_deletion_overlay_viewport_rects,
            ),
            (
                "transient_deletion_overlay_erase_rect",
                snapshot.transient_deletion_overlay_erase_rects,
            ),
        ):
            for rect in rects:
                if not _rect_tuple_is_finite_nonnegative(rect):
                    violations.append(f"{rect_name}_invalid:{rect}")
                elif not _transient_dirty_rect_within_viewport_envelope(
                    rect,
                    snapshot.viewport_rect,
                ):
                    violations.append(f"{rect_name}_too_broad:{rect}")
        if snapshot.transient_deletion_overlay_repaint_rect is not None:
            repaint_rect = snapshot.transient_deletion_overlay_repaint_rect
            if not _rect_tuple_is_finite_nonnegative(repaint_rect):
                violations.append(
                    f"transient_deletion_overlay_repaint_rect_invalid:{repaint_rect}"
                )
            elif not _transient_dirty_rect_within_viewport_envelope(
                repaint_rect,
                snapshot.viewport_rect,
            ):
                violations.append(
                    f"transient_deletion_overlay_repaint_rect_too_broad:{repaint_rect}"
                )
        violations.extend(_projection_metrics_contract_violations(snapshot))
        violations.extend(_caret_row_height_contract_violations(snapshot))
        violations.extend(_transient_deletion_overerase_violations(snapshot))
        if snapshot.undo_depth < 0:
            violations.append("undo_depth_negative")
        if snapshot.redo_depth < 0:
            violations.append("redo_depth_negative")
        if snapshot.undo_edit_block_depth < 0:
            violations.append("undo_edit_block_depth_negative")
        if snapshot.undo_max_depth < 1:
            violations.append(f"undo_max_depth_invalid:{snapshot.undo_max_depth}")
        if snapshot.redo_max_depth < 1:
            violations.append(f"redo_max_depth_invalid:{snapshot.redo_max_depth}")
        if snapshot.undo_depth > snapshot.undo_max_depth:
            violations.append(
                f"undo_depth_exceeds_max:{snapshot.undo_depth}:{snapshot.undo_max_depth}"
            )
        if snapshot.redo_depth > snapshot.redo_max_depth:
            violations.append(
                f"redo_depth_exceeds_max:{snapshot.redo_depth}:{snapshot.redo_max_depth}"
            )
        if snapshot.undo_pending_state_present != (snapshot.undo_edit_block_depth > 0):
            violations.append(
                "undo_pending_state_edit_block_mismatch:"
                f"{snapshot.undo_pending_state_present}:"
                f"{snapshot.undo_edit_block_depth}"
            )
        if snapshot.undo_available != (snapshot.undo_depth > 0):
            violations.append(
                "undo_availability_depth_mismatch:"
                f"{snapshot.undo_available}:{snapshot.undo_depth}"
            )
        if snapshot.redo_available != (snapshot.redo_depth > 0):
            violations.append(
                "redo_availability_depth_mismatch:"
                f"{snapshot.redo_available}:{snapshot.redo_depth}"
            )
        if snapshot.undo_typing_group_active and snapshot.undo_delete_group_active:
            violations.append("undo_typing_and_delete_groups_both_active")
        if snapshot.undo_typing_group_active:
            if snapshot.undo_edit_block_depth <= 0:
                violations.append("undo_typing_group_without_edit_block")
            if snapshot.undo_typing_group_last_cursor_position is None:
                violations.append("undo_typing_group_missing_last_cursor")
            elif (
                not 0
                <= snapshot.undo_typing_group_last_cursor_position
                <= source_length
            ):
                violations.append(
                    "undo_typing_group_last_cursor_out_of_bounds:"
                    f"{snapshot.undo_typing_group_last_cursor_position}:"
                    f"{source_length}"
                )
        elif snapshot.undo_typing_group_last_cursor_position is not None:
            violations.append("undo_typing_group_last_cursor_without_active_group")
        if snapshot.undo_delete_group_active:
            if snapshot.undo_edit_block_depth <= 0:
                violations.append("undo_delete_group_without_edit_block")
            if snapshot.undo_delete_group_key is None:
                violations.append("undo_delete_group_missing_key")
        elif snapshot.undo_delete_group_key is not None:
            violations.append("undo_delete_group_key_without_active_group")
        if snapshot.document_view_source_text != snapshot.source_text:
            violations.append("document_view_source_mismatch")
        if (
            not projection_is_allowed_to_lag
            and snapshot.projection_document_source_text != snapshot.source_text
        ):
            violations.append("projection_document_source_mismatch")
        if (
            not projection_is_allowed_to_lag
            and snapshot.active_projection_source_text != snapshot.source_text
        ):
            violations.append("active_projection_source_mismatch")
        if (
            not snapshot.autocomplete_preview_active
            and snapshot.active_projection_text != snapshot.projection_text
        ):
            violations.append("active_projection_preview_leaked_without_preview_state")
        if (
            not projection_is_allowed_to_lag
            and not snapshot.autocomplete_preview_active
        ):
            if snapshot.autocomplete_ghost_paint_visible_by_owner_state:
                violations.append(
                    "autocomplete_ghost_paint_visible_without_preview_state"
                )
            if snapshot.layout_projection_source_text != snapshot.source_text:
                violations.append("layout_projection_source_mismatch")
            if snapshot.layout_projection_text != snapshot.projection_text:
                violations.append(
                    "layout_projection_preview_leaked_without_preview_state"
                )
            if (
                not snapshot.layout_uses_projection_document
                and snapshot.layout_projection_text != snapshot.projection_text
            ):
                violations.append("layout_not_restored_to_base_projection_document")
            if snapshot.paint_cache_ghosted_run_ids:
                violations.append(
                    "paint_cache_ghosted_runs_without_preview_state:"
                    f"{','.join(snapshot.paint_cache_ghosted_run_ids)}"
                )
        cache_can_be_reused = snapshot.selection_range[0] == snapshot.selection_range[1]
        if snapshot.paint_cache_key_present and cache_can_be_reused:
            if not snapshot.paint_cache_projection_document_identity_matches_layout:
                violations.append("paint_cache_projection_document_identity_mismatch")
            if not snapshot.paint_cache_layout_snapshot_identity_matches_layout:
                violations.append("paint_cache_layout_snapshot_identity_mismatch")
            if (
                not projection_is_allowed_to_lag
                and snapshot.paint_cache_source_revision != snapshot.source_revision
            ):
                violations.append(
                    "paint_cache_source_revision_mismatch:"
                    f"{snapshot.paint_cache_source_revision}:"
                    f"{snapshot.source_revision}"
                )
        if (
            snapshot.autocomplete_preview_active
            and snapshot.active_projection_source_text != snapshot.source_text
        ):
            violations.append("autocomplete_active_projection_source_mismatch")
        if snapshot.autocomplete_snapshot_source_length not in (None, source_length):
            violations.append(
                "autocomplete_snapshot_source_length_mismatch:"
                f"{snapshot.autocomplete_snapshot_source_length}:{source_length}"
            )
        if (
            snapshot.autocomplete_snapshot_cursor_position is not None
            and snapshot.autocomplete_snapshot_cursor_position
            != snapshot.cursor_position
            and snapshot.autocomplete_has_active_session
        ):
            violations.append(
                "autocomplete_snapshot_cursor_mismatch:"
                f"{snapshot.autocomplete_snapshot_cursor_position}:"
                f"{snapshot.cursor_position}"
            )
        if snapshot.autocomplete_has_active_session:
            violations.extend(self._autocomplete_session_violations(snapshot))
        if snapshot.autocomplete_preview_active:
            violations.extend(self._autocomplete_preview_violations(snapshot))
        if (
            snapshot.autocomplete_has_active_session
            and not snapshot.autocomplete_presenter_panel_visible
        ):
            violations.append("active_autocomplete_session_without_presenter_panel")
        if (
            snapshot.popup_state_visible
            and not snapshot.autocomplete_has_active_session
        ):
            violations.append("visible_popup_without_active_autocomplete_session")
        if snapshot.popup_state_visible:
            violations.extend(self._autocomplete_popup_geometry_violations(snapshot))
        return tuple(violations)

    def transition_invariant_violations(
        self,
        *,
        action_name: str,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
    ) -> tuple[str, ...]:
        """Return code-level invariant violations for one editor transition."""

        violations = list(self.invariant_violations(after))
        if "\t" in after.source_text:
            violations.append("literal_tab_in_source")
        if _has_disallowed_control_character(after.source_text):
            violations.append("control_character_in_source")
        if _action_should_leave_caret_visible(
            action_name,
            before=before,
            after=after,
        ) and not (
            after.projection_has_pending_update and after.projection_has_stale_geometry
        ):
            if not after.caret_rect_intersects_viewport:
                violations.append("caret_rect_outside_viewport_after_settle")
        violations.extend(
            _stable_single_character_content_height_violations(
                action_name=action_name,
                before=before,
                after=after,
            )
        )
        violations.extend(
            _non_uniform_visible_row_shift_violations(before=before, after=after)
        )
        violations.extend(
            _non_uniform_visible_fragment_shift_violations(
                action_name=action_name,
                before=before,
                after=after,
            )
        )
        violations.extend(
            _stable_single_character_geometry_violations(
                action_name=action_name,
                before=before,
                after=after,
            )
        )
        if action_name == "space" and after.source_text == f"{before.source_text} ":
            if (
                after.projection_has_stale_geometry
                or after.projection_document_source_text != after.source_text
                or after.active_projection_source_text != after.source_text
            ):
                violations.append("space_left_stale_projection_after_source_insert")
        if action_name in {
            "escape",
            "click_away",
            "caret",
            "selection",
            "canvas",
            "workflow",
        }:
            if _autocomplete_state_is_owned_or_visible(after):
                violations.append(f"{action_name}_left_autocomplete_active")
            if (
                before.autocomplete_preview_active
                and not after.autocomplete_preview_active
            ):
                violations.extend(
                    _autocomplete_dismissal_owner_violations(
                        before=before,
                        after=after,
                        action_name=action_name,
                    )
                )
        if action_name == "tab" and after.source_text == f"{before.source_text}\t":
            violations.append("tab_inserted_literal_tab")
        if action_name in {"backspace", "delete"}:
            if (
                after.projection_has_pending_update
                and after.projection_has_stale_geometry
            ):
                violations.append(f"{action_name}_left_stale_pending_projection")
        return tuple(dict.fromkeys(violations))

    def _autocomplete_preview_violations(
        self,
        snapshot: PromptEditorStateSnapshot,
    ) -> tuple[str, ...]:
        """Return invariant violations for projection-owned autocomplete preview."""

        violations: list[str] = []
        source_position = snapshot.autocomplete_preview_source_position
        if source_position is None:
            violations.append("autocomplete_preview_missing_source_position")
            return tuple(violations)
        if not 0 <= source_position <= len(snapshot.source_text):
            violations.append(
                "autocomplete_preview_source_position_out_of_bounds:"
                f"{source_position}:{len(snapshot.source_text)}"
            )
        if source_position != snapshot.cursor_position:
            violations.append(
                "autocomplete_preview_not_at_cursor:"
                f"{source_position}:{snapshot.cursor_position}"
            )
        if _source_prefix_ends_with_autocomplete_delimiter(
            snapshot.source_text,
            source_position,
        ):
            violations.append("autocomplete_preview_after_source_delimiter")
        if not snapshot.autocomplete_has_active_session:
            violations.append("autocomplete_preview_without_active_session")
        if not snapshot.autocomplete_presenter_panel_visible:
            violations.append("autocomplete_preview_without_presenter_panel")
        if not snapshot.popup_state_visible:
            violations.append("autocomplete_preview_without_visible_popup_widget")
        if not snapshot.autocomplete_preview_suffix:
            violations.append("autocomplete_preview_empty_suffix")
        return tuple(violations)

    def _autocomplete_session_violations(
        self,
        snapshot: PromptEditorStateSnapshot,
    ) -> tuple[str, ...]:
        """Return invariant violations for autocomplete lifecycle/session state."""

        violations: list[str] = []
        suggestion_count = len(snapshot.autocomplete_session_suggestions)
        if snapshot.autocomplete_session_lifecycle not in {"active", "refreshing"}:
            violations.append(
                "autocomplete_active_session_invalid_lifecycle:"
                f"{snapshot.autocomplete_session_lifecycle}"
            )
        if snapshot.autocomplete_session_mode not in {
            "tag",
            "scene",
            "wildcard",
            "lora",
        }:
            violations.append(
                f"autocomplete_active_session_invalid_mode:{snapshot.autocomplete_session_mode}"
            )
        if snapshot.autocomplete_session_mode != "lora" and suggestion_count <= 0:
            violations.append("autocomplete_active_session_without_suggestions")
        if snapshot.autocomplete_session_mode != "lora" and not (
            0 <= snapshot.autocomplete_session_selected_index < suggestion_count
        ):
            violations.append(
                "autocomplete_selected_index_out_of_bounds:"
                f"{snapshot.autocomplete_session_selected_index}:{suggestion_count}"
            )
        if snapshot.autocomplete_session_mode in {"tag", "scene", "wildcard"}:
            word_start = snapshot.autocomplete_session_word_start
            word_end = snapshot.autocomplete_session_word_end
            if word_start is None or word_end is None:
                violations.append("autocomplete_session_missing_word_range")
            elif not 0 <= word_start <= word_end <= len(snapshot.source_text):
                violations.append(
                    "autocomplete_session_word_range_out_of_bounds:"
                    f"{word_start}:{word_end}:{len(snapshot.source_text)}"
                )
            elif word_end != snapshot.cursor_position:
                violations.append(
                    "autocomplete_session_word_end_not_at_cursor:"
                    f"{word_end}:{snapshot.cursor_position}"
                )
        active_tag_end = snapshot.autocomplete_session_active_tag_end
        if active_tag_end is not None and not (
            0 <= active_tag_end <= len(snapshot.source_text)
        ):
            violations.append(
                "autocomplete_session_active_tag_end_out_of_bounds:"
                f"{active_tag_end}:{len(snapshot.source_text)}"
            )
        return tuple(violations)

    def _autocomplete_popup_geometry_violations(
        self,
        snapshot: PromptEditorStateSnapshot,
    ) -> tuple[str, ...]:
        """Return invariant violations for autocomplete popup geometry."""

        violations: list[str] = []
        popup_rect = snapshot.popup_global_rect
        viewport_rect = snapshot.global_geometries.get("viewport")
        if popup_rect is None:
            violations.append("visible_popup_missing_global_rect")
            return tuple(violations)
        if not _int_rect_tuple_has_area(popup_rect):
            violations.append(f"visible_popup_global_rect_invalid:{popup_rect}")
        if viewport_rect is None:
            violations.append("visible_popup_missing_viewport_global_rect")
            return tuple(violations)
        if not _int_rect_tuple_has_area(viewport_rect):
            violations.append(
                f"visible_popup_viewport_global_rect_invalid:{viewport_rect}"
            )
        if not _popup_rect_is_anchored_to_viewport(
            popup_rect=popup_rect,
            viewport_rect=viewport_rect,
        ):
            violations.append(
                f"visible_popup_not_anchored_to_editor:{popup_rect}:{viewport_rect}"
            )
        return tuple(violations)

    def trace(self) -> PromptEditorTrace:
        """Return the replay trace recorded by real harness actions."""

        return PromptEditorTrace(actions=tuple(self._trace_actions))

    def replay(
        self,
        field: PromptFieldHandle,
        trace: PromptEditorTrace,
    ) -> None:
        """Replay actions through the same real shell and focused editor path."""

        for action in trace.actions:
            if action.kind == "type_text":
                self.type_text(field, action.value)
            elif action.kind == "paste_text":
                self.paste_text(field, action.value)
            elif action.kind == "undo":
                self.undo(field)
            elif action.kind == "redo":
                self.redo(field)
            elif action.kind == "replace_text":
                self.replace_text_with_keys(field, action.value)
            elif action.kind == "press_key" and action.key is not None:
                self.press_key(
                    field,
                    Qt.Key(action.key),
                    text=action.value,
                    modifiers=Qt.KeyboardModifier(action.modifiers),
                )
            elif action.kind == "click_away":
                self.click_away_from_editor()
            elif action.kind == "switch_canvas":
                self.switch_canvas(action.value)
            elif action.kind == "activate_workflow":
                if action.value not in self.workflows:
                    self.add_prompt_workflow(
                        action.value,
                        initial_text="secondary prompt",
                        activate=False,
                    )
                self.activate_workflow(action.value)
            elif action.kind == "scroll_editor":
                self.scroll_editor(field, action.value)
            elif action.kind == "seed_text_directly":
                self.seed_text_directly(field, action.value)
            else:
                raise AssertionError(f"unknown trace action {action!r}")

    def minimized_trace(
        self,
        trace: PromptEditorTrace,
        predicate: Callable[[PromptEditorTrace], bool],
    ) -> PromptEditorTrace:
        """Remove actions while preserving the caller's visible failure predicate."""

        actions = list(trace.actions)
        index = 0
        while index < len(actions):
            candidate = PromptEditorTrace(
                tuple(actions[:index] + actions[index + 1 :]),
                seed=trace.seed,
            )
            if predicate(candidate):
                actions = list(candidate.actions)
                continue
            index += 1
        return PromptEditorTrace(tuple(actions), seed=trace.seed)

    def run_seeded_abuse_campaign(
        self,
        field: PromptFieldHandle,
        *,
        seed: int,
        sizes: Sequence[tuple[int, int]] = ((860, 560), (1040, 760), (1280, 820)),
        steps_per_size: int = 8,
    ) -> PromptEditorAbuseReport:
        """Run a bounded autocomplete-heavy abuse campaign against the real editor."""

        rng = random.Random(seed)
        findings: list[PromptEditorAbuseFinding] = []
        suspicious_successes: list[str] = []
        action_index = 0
        for width, height in sizes:
            self.shell.resize(width, height)
            self.process_events(cycles=10)
            self.replace_text_with_keys(field, "")
            for _step in range(steps_per_size):
                before = self.capture_state_snapshot(
                    field,
                    label=f"abuse-before-{action_index}",
                )
                action_name = self._run_abuse_action(field, rng)
                after = self.capture_state_snapshot(
                    field,
                    label=f"abuse-after-{action_index}",
                )
                finding = self._finding_for_abuse_transition(
                    field=field,
                    action_index=action_index,
                    action_name=action_name,
                    before=before,
                    after=after,
                )
                if finding is not None:
                    findings.append(finding)
                elif action_name in {"tab", "escape", "resize"}:
                    suspicious_successes.append(
                        (
                            f"{action_index}:{action_name}:"
                            f"{before.source_text!r}->{after.source_text!r}:"
                            f"panel={after.autocomplete_presenter_panel_visible}:"
                            f"preview={after.autocomplete_preview_active}:"
                            f"session={after.autocomplete_has_active_session}"
                        )
                    )
                action_index += 1
        report_path = self._write_abuse_report(
            seed=seed,
            sizes=tuple(sizes),
            action_count=action_index,
            findings=tuple(findings),
            suspicious_successes=tuple(suspicious_successes),
        )
        return PromptEditorAbuseReport(
            seed=seed,
            sizes=tuple(sizes),
            action_count=action_index,
            findings=tuple(findings),
            suspicious_successes=tuple(suspicious_successes),
            grouped_failures=_group_abuse_findings(findings),
            report_path=report_path,
        )

    def _run_abuse_action(
        self,
        field: PromptFieldHandle,
        rng: random.Random,
    ) -> str:
        """Run one randomized but bounded abuse action."""

        action = rng.choice(
            (
                "prefix",
                "space",
                "tab",
                "escape",
                "backspace",
                "delete",
                "cursor",
                "shift_selection",
                "selection_replace",
                "paste_multiline",
                "undo_redo",
                "projected_token_walk",
                "long_document_navigation",
                "multiline_backpack_up",
                "multiline_backpack_up",
                "scroll_editor",
                "workflow_round_trip",
                "resize",
                "click_away",
                "canvas",
            )
        )
        if action == "prefix":
            self.type_text(field, rng.choice(("re", "1g", "ha", "backpack")))
        elif action == "space":
            self.press_key(field, Qt.Key.Key_Space, text=" ")
        elif action == "tab":
            self.press_key(field, Qt.Key.Key_Tab, text="\t")
        elif action == "escape":
            self.press_key(field, Qt.Key.Key_Escape)
        elif action == "backspace":
            self.press_key(field, Qt.Key.Key_Backspace)
        elif action == "delete":
            self.press_key(field, Qt.Key.Key_Delete)
        elif action == "cursor":
            self.press_key(
                field,
                rng.choice(
                    (
                        Qt.Key.Key_Left,
                        Qt.Key.Key_Right,
                        Qt.Key.Key_Up,
                        Qt.Key.Key_Down,
                        Qt.Key.Key_Home,
                        Qt.Key.Key_End,
                        Qt.Key.Key_PageUp,
                        Qt.Key.Key_PageDown,
                    )
                ),
            )
        elif action == "shift_selection":
            self.press_key(
                field,
                rng.choice(
                    (
                        Qt.Key.Key_Left,
                        Qt.Key.Key_Right,
                        Qt.Key.Key_Home,
                        Qt.Key.Key_End,
                    )
                ),
                modifiers=Qt.KeyboardModifier.ShiftModifier,
            )
            return "selection"
        elif action == "selection_replace":
            source = field.editor.toPlainText()
            if source:
                start = rng.randrange(0, len(source))
                end = rng.randrange(start, len(source) + 1)
                cursor = cast(Any, field.editor).textCursor()
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                cast(Any, field.editor).setTextCursor(cursor)
                self.process_events(cycles=4)
            self.type_text(field, rng.choice(("alpha", "backpack", "1girl")))
            return "selection_replace"
        elif action == "paste_multiline":
            QApplication.clipboard().setText(
                rng.choice(
                    (
                        "alpha\nbeta",
                        "backpack basket\nempty eyes",
                        "(small:1.20),\nwhite dress",
                    )
                )
            )
            target = self.focus_editor(field)
            QTest.keySequence(target, QKeySequence.StandardKey.Paste)
            self.process_events(cycles=8)
            return "paste"
        elif action == "undo_redo":
            target = self.focus_editor(field)
            QTest.keySequence(target, QKeySequence.StandardKey.Undo)
            self.process_events(cycles=6)
            QTest.keySequence(target, QKeySequence.StandardKey.Redo)
            self.process_events(cycles=6)
            return "undo_redo"
        elif action == "projected_token_walk":
            self.replace_text_with_keys(
                field,
                "alpha, (small:1.20), <lora:missing:1.00>, omega",
            )
            self.move_cursor_to_end(field)
            for _ in range(rng.randint(2, 8)):
                self.press_key(field, Qt.Key.Key_Left)
            for _ in range(rng.randint(2, 8)):
                self.press_key(field, Qt.Key.Key_Right)
            return "caret"
        elif action == "long_document_navigation":
            long_prompt = "\n".join(
                f"line {index:02d} backpack basket empty eyes pointy ears"
                for index in range(16)
            )
            self.seed_text_directly(field, long_prompt)
            self.press_key(field, Qt.Key.Key_End)
            self.press_key(
                field,
                rng.choice((Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)),
            )
            self.press_key(field, Qt.Key.Key_Home)
            return "caret"
        elif action == "multiline_backpack_up":
            self.replace_text_with_keys(field, "empty eyes, pointy ears, sharp teeth")
            self.press_key(field, Qt.Key.Key_Return, text="\n")
            self.move_cursor_to_end(field)
            self.type_text(field, "backpack")
            self.press_key(field, Qt.Key.Key_Up)
            return "caret"
        elif action == "scroll_editor":
            if field.editor.verticalScrollBar().maximum() <= 0:
                self.seed_text_directly(
                    field,
                    "\n".join(
                        f"line {index:02d} backpack basket empty eyes pointy ears"
                        for index in range(24)
                    ),
                )
            self.scroll_editor(field, rng.choice(("top", "middle", "bottom")))
            return "scroll"
        elif action == "workflow_round_trip":
            self.workflow_round_trip(field)
            return "workflow"
        elif action == "resize":
            self.shell.resize(rng.choice((820, 960, 1180)), rng.choice((520, 700, 860)))
            self.process_events(cycles=10)
        elif action == "canvas":
            self.switch_canvas("Output")
            self.switch_canvas("Input")
        else:
            self.click_away_from_editor()
            self.focus_editor(field)
        return action

    def _finding_for_abuse_transition(
        self,
        *,
        field: PromptFieldHandle,
        action_index: int,
        action_name: str,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
    ) -> PromptEditorAbuseFinding | None:
        """Classify one abuse transition by code-level invariant symptom."""

        _ = field
        violations = self.transition_invariant_violations(
            action_name=action_name,
            before=before,
            after=after,
        )
        if not violations:
            return None
        symptom = violations[0]
        owner = _owner_hypothesis_for_violation(symptom)
        artifact = self.save_artifacts(
            f"abuse-{action_index}-{_safe_artifact_name(symptom)}",
            before=before,
            after=after,
            invariant=symptom,
            observed=(
                f"violations={violations}; "
                f"{before.source_text!r}->{after.source_text!r}"
            ),
        )
        return PromptEditorAbuseFinding(
            symptom=symptom,
            owner_hypothesis=owner,
            action_index=action_index,
            source_before=before.source_text,
            source_after=after.source_text,
            artifact_path=str(artifact),
        )

    def _write_abuse_report(
        self,
        *,
        seed: int,
        sizes: tuple[tuple[int, int], ...],
        action_count: int,
        findings: tuple[PromptEditorAbuseFinding, ...],
        suspicious_successes: tuple[str, ...],
    ) -> Path:
        """Write grouped abuse campaign output for later triage."""

        directory = self.artifact_root / f"abuse-seed-{seed}"
        directory.mkdir(parents=True, exist_ok=True)
        report_path = directory / "report.json"
        payload = {
            "seed": seed,
            "sizes": sizes,
            "action_count": action_count,
            "findings": [
                {
                    "symptom": finding.symptom,
                    "owner_hypothesis": finding.owner_hypothesis,
                    "action_index": finding.action_index,
                    "source_before": finding.source_before,
                    "source_after": finding.source_after,
                    "artifact_path": finding.artifact_path,
                }
                for finding in findings
            ],
            "suspicious_successes": suspicious_successes,
            "grouped_failures": _group_abuse_findings(findings),
        }
        report_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report_path

    def drain_events_for(self, duration_ms: int) -> None:
        """Process Qt events for a short fixed duration."""

        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.start(duration_ms)
        while deadline.isActive():
            self.process_events(cycles=2)
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec()
        self.process_events(cycles=4)

    def wait_until(
        self,
        predicate: Callable[[], object],
        *,
        timeout_ms: int = 3000,
    ) -> None:
        """Process Qt events until predicate succeeds or the timeout expires."""

        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.start(timeout_ms)
        while not bool(predicate()):
            if not deadline.isActive():
                raise AssertionError(f"timed out waiting for {predicate!r}")
            self.process_events(cycles=2)
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec()
        self.process_events(cycles=4)

    def process_events(self, *, cycles: int = 4) -> None:
        """Let queued Qt signals, timers, and projection work run."""

        for _index in range(cycles):
            self.app.processEvents()

    def _finalize_panel_projection(self, panel: EditorPanel) -> None:
        """Drain editor-panel projection work until the target field is materialized."""

        for _index in range(20):
            if panel.has_pending_visible_projection_commit():
                panel.finalize_pending_visible_projection()
            self.process_events(cycles=4)


class _HarnessShell(QMainWindow):
    """Own the real workspace and real prompt editor panel under test."""

    progress_update_signal = Signal(float, object)
    resize_requested = Signal(int)
    clear_output_signal = Signal(str)
    preview_image_signal = Signal(object)
    add_output_image_signal = Signal(str, QImage, object)
    workflow_tabbar: Any
    workflow_workspace: WorkflowWorkspaceCoordinator
    editor_panel: EditorPanel

    def __init__(
        self,
        autocomplete_gateway: RecordingPromptAutocompleteGateway,
        *,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        user_preset_service: UserPresetService | None = None,
        model_catalog_service: ModelCatalogLookup | None = None,
    ) -> None:
        """Build the real shell scaffold and deterministic prompt services."""

        super().__init__()
        self.resize(1040, 760)
        self.node_definition_gateway = _PromptNodeDefinitionGateway()
        self.prompt_autocomplete_gateway = autocomplete_gateway
        self.prompt_wildcard_catalog_gateway = EmptyPromptWildcardCatalogGateway()
        self.node_behavior_service = NodeBehaviorService(
            node_definition_gateway=self.node_definition_gateway
        )
        self.danbooru_url_import_service = None
        self.danbooru_wiki_service = None
        self.danbooru_image_preview_service = None
        self.danbooru_recent_posts_service = None
        self.prompt_lora_catalog_service = prompt_lora_catalog_service
        self.scheduled_lora_provider = None
        self.prompt_scheduled_lora_service = None
        self.prompt_spellcheck_service = None
        self.prompt_feature_profile_service = None
        self.model_catalog_service = model_catalog_service
        self.model_choice_resolver = None
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.user_preset_service = user_preset_service
        self.workflow_issue_state = None

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
        self.editor_panels: dict[str, EditorPanel] = {}
        self.override_managers: dict[str, object] = {}
        self._pending_restored_workflow_snapshots: dict[str, object] = {}
        self.generationActionCluster = None
        self.error_reports: list[object] = []
        self.workspace_cube_stack_actions = SimpleNamespace(
            highlight_tab_for_cube=lambda *_args, **_kwargs: None
        )
        self.input_canvas_presenter = SimpleNamespace(
            handle_input_image_changed=lambda *_args, **_kwargs: None,
            handle_input_image_clicked=lambda *_args, **_kwargs: None,
            handle_input_mask_changed=lambda *_args, **_kwargs: None,
            handle_input_mask_clicked=lambda *_args, **_kwargs: None,
        )
        self.workspace_scene_generation_actions = SimpleNamespace(
            enqueue_prompt_scene=lambda *_args, **_kwargs: None
        )

        self.workspace_canvas_actions = WorkspaceCanvasActions(
            cast(Any, self),
            error_presenter=_ErrorPresenter(self.error_reports),
        )
        self._error_presenter = _ErrorPresenter(self.error_reports)
        self._menu_container = QWidget()
        self._menu_container.setLayout(QHBoxLayout())
        self.focus_sentinel = QPushButton("focus-sentinel", self._menu_container)
        self.focus_sentinel.setObjectName("PromptHarnessFocusSentinel")
        self.focus_sentinel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.focus_sentinel.setFixedSize(4, 4)
        menu_layout = self._menu_container.layout()
        if menu_layout is None:
            raise RuntimeError("Harness menu container must have a layout.")
        menu_layout.addWidget(self.focus_sentinel)
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
        self.output_canvas = self.canvas_tabs.canvas_map["Output"]
        self.workflow_workspace = WorkflowWorkspaceCoordinator(
            cast(WorkflowWorkspaceView, self)
        )
        self.main_window_signal_binder = MainWindowSignalBinder(self)
        self.main_window_signal_binder.connect_canvas_signals(
            input_canvas=self.canvas_tabs.canvas_map["Input"],
            output_canvas=self.output_canvas,
        )
        self.canvas_tabs.focus_attached_canvas("Input")
        self.show()

    def install_workflow_surface(self, workflow_id: str) -> None:
        """Install real workflow widgets used by coordinator route switching."""

        cube_stack = self.cube_stacks.get(workflow_id)
        if cube_stack is None:
            cube_stack = QWidget()
            cube_stack.setObjectName(f"{workflow_id}-cube-stack")
            self.cube_stacks[workflow_id] = cube_stack
            self.cube_stack_container.addWidget(cube_stack)
        editor_panel = self.editor_panels.get(workflow_id)
        if editor_panel is None:
            editor_panel = EditorPanel(
                node_definition_gateway=self.node_definition_gateway,
                prompt_autocomplete_gateway=self.prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=(self.prompt_wildcard_catalog_gateway),
                node_behavior_service=self.node_behavior_service,
                prompt_lora_catalog_service=self.prompt_lora_catalog_service,
                model_catalog_service=self.model_catalog_service,
                thumbnail_asset_repository=self.thumbnail_asset_repository,
                user_preset_service=self.user_preset_service,
                workflow_id=workflow_id,
                editor_panel_execution_factories=(
                    immediate_editor_panel_execution_factories()
                ),
            )
            editor_panel.mainwindow = self
            editor_panel.setObjectName(f"{workflow_id}-editor-panel")
            editor_panel.setMinimumWidth(412)
            self.main_window_signal_binder.connect_editor_panel_signals(editor_panel)
            self.editor_panels[workflow_id] = editor_panel
            self.editor_panel_container.addWidget(editor_panel)

    @property
    def active_editor_panel(self) -> EditorPanel | None:
        """Return the editor panel for the active workflow."""

        return self.editor_panels.get(self.workflow_session_service.active_workflow_id)

    def get_active_workflow(self) -> WorkflowState | None:
        """Return the active workflow state."""

        return self.workflow_session_service.get_workflow(
            self.workflow_session_service.active_workflow_id
        )

    def _resolve_workflow_name(self, workflow_id: str) -> str:
        """Return the workflow display name used by shell collaborators."""

        workflow = self.workflow_session_service.get_workflow(workflow_id)
        if workflow is None:
            return workflow_id
        value = workflow.metadata.get("name", workflow_id)
        return str(value)

    def request_session_autosave(self) -> None:
        """Ignore autosave requests in the real-shell harness."""


class _PromptNodeDefinitionGateway:
    """Return deterministic live node definitions for the prompt fixture."""

    _SUPPORTED_NODE_CLASSES = frozenset(
        {"CLIPTextEncode", "SimpleSyrup.SimpleLoadAnima", "UNETLoader"}
    )

    def ensure_node_definitions(
        self,
        node_classes: Sequence[str],
    ) -> NodeDefinitionHydrationResult:
        """Report requested prompt fixture definitions as foreground-hydrated."""

        requested = tuple(node_classes)
        available = tuple(
            node_class
            for node_class in requested
            if node_class in self._SUPPORTED_NODE_CLASSES
        )
        unavailable = tuple(
            node_class
            for node_class in requested
            if node_class not in self._SUPPORTED_NODE_CLASSES
        )
        return NodeDefinitionHydrationResult(
            requested=requested,
            available=available,
            unavailable=unavailable,
        )

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one class definition in the gateway payload shape."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required class definition in the gateway payload shape."""

        definitions: dict[str, dict[str, object]] = {
            "CLIPTextEncode": {
                "input": {
                    "required": {
                        "text": ["STRING", {"multiline": True, "dynamicPrompts": True}]
                    }
                },
                "output": ["CONDITIONING"],
                "output_name": ["CONDITIONING"],
            },
            "SimpleSyrup.SimpleLoadAnima": {
                "input": {
                    "required": {
                        "diffusion_model": [["Anima/hassakuAnima_v11.safetensors"]]
                    }
                },
                "output": ["MODEL", "CLIP", "VAE"],
                "output_name": ["model", "clip", "vae"],
            },
            "UNETLoader": {
                "input": {"required": {"unet_name": [["flux.safetensors"]]}},
                "output": ["MODEL"],
                "output_name": ["MODEL"],
            },
        }
        definition = definitions.get(node_class)
        return {} if definition is None else {node_class: definition}


class _GenerationJobQueueService:
    """Provide queue timing APIs touched by shell collaborators."""

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
    """Store progress-bar calls made by shell controllers."""

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


def _prompt_cube_state(
    initial_text: str,
    *,
    alias: str,
    model_node_type: str | None = None,
    model_field_key: str | None = None,
    model_value: str | None = None,
) -> CubeState:
    """Build a minimal loaded cube state with one prompt node."""

    nodes: dict[str, object] = {
        "positive_prompt": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Positive Prompt"},
            "inputs": {"text": initial_text},
        }
    }
    if (
        model_node_type is not None
        and model_field_key is not None
        and model_value is not None
    ):
        nodes["model"] = {
            "class_type": model_node_type,
            "_meta": {"title": "Model"},
            "inputs": {model_field_key: model_value},
        }
    buffer: dict[str, object] = {
        "nodes": nodes,
        "definitions": {},
        "subgraphs": [],
    }
    return CubeState(
        cube_id="PromptHarness.cube",
        version="1.0",
        alias=alias,
        buffer=buffer,
        original_cube={"workflow": buffer},
        display_name="Prompt Harness Cube",
        dirty=False,
        ui={},
        field_control_states={},
    )


def _anima_prompt_cube_state(
    prompt: str,
    *,
    alias: str,
    model_value: str,
) -> CubeState:
    """Build one Anima cube with production model-before-prompt node order."""

    buffer: dict[str, object] = {
        "nodes": {
            "models": {
                "class_type": "SimpleSyrup.SimpleLoadAnima",
                "_meta": {"title": "Models"},
                "inputs": {"diffusion_model": model_value},
            },
            "positive_prompt": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "Positive Prompt"},
                "inputs": {"text": prompt},
            },
        },
        "definitions": {},
        "subgraphs": [],
    }
    return CubeState(
        cube_id=f"PromptHarness.{alias}.cube",
        version="1.0",
        alias=alias,
        buffer=buffer,
        original_cube={"workflow": buffer},
        display_name=alias,
        dirty=False,
        ui={},
        field_control_states={},
    )


def _default_autocomplete_results() -> Mapping[
    str,
    tuple[PromptAutocompleteSuggestion, ...],
]:
    """Return deterministic autocomplete data for prompt-editor scenarios."""

    return {
        "re": (
            PromptAutocompleteSuggestion(
                "re:zero kara hajimeru isekai seikatsu", 16370
            ),
            PromptAutocompleteSuggestion("re:stage!", 1501),
            PromptAutocompleteSuggestion("re:creators", 728),
        ),
        "1g": (
            PromptAutocompleteSuggestion("1girl", 5_889_398),
            PromptAutocompleteSuggestion("1girls", 3424),
        ),
        "ha": (
            PromptAutocompleteSuggestion("hair ornament", 4100),
            PromptAutocompleteSuggestion("hair ribbon", 3800),
        ),
        "backpack": (
            PromptAutocompleteSuggestion("backpack basket", 240),
            PromptAutocompleteSuggestion("backpack strap", 120),
        ),
        "backpack ": (PromptAutocompleteSuggestion("backpack basket", 240),),
    }


def _ensure_qapp() -> QApplication:
    """Return the active QApplication or create one."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


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


def _editor_event_widget(editor: PromptEditor) -> QWidget:
    """Return the real widget receiving prompt editor key events."""

    focus_proxy = editor.focusProxy()
    if isinstance(focus_proxy, QWidget):
        return focus_proxy
    return editor


def _source_position_for_text(editor: PromptEditor, text: str) -> int:
    """Return the first source position occupied by visible text."""

    return editor.toPlainText().index(text)


def _viewport_position_for_source_text(editor: PromptEditor, text: str) -> QPoint:
    """Return a viewport-local point centered on one source text fragment."""

    source_start = _source_position_for_text(editor, text)
    fragments = editor.source_range_fragments(
        start=source_start,
        end=source_start + len(text),
    )
    if not fragments:
        raise AssertionError(f"no visible source fragment for {text!r}")
    return cast(QPoint, fragments[0].center().toPoint())


def _prepared_lora_action_snapshot(editor: PromptEditor, prompt_text: str) -> object:
    """Return the current prepared LoRA action snapshot without deriving it."""

    controller = getattr(editor, "_lora_trigger_word_controller")
    return controller.snapshot_for_prompt(prompt_text=prompt_text)


def _cached_scheduled_loras(
    editor: PromptEditor,
    prompt_text: str,
) -> tuple[object, ...] | None:
    """Return cached scheduled LoRAs exposed by the production editor."""

    controller = getattr(editor, "_lora_trigger_word_controller", None)
    cached_scheduled_loras = getattr(controller, "cached_scheduled_loras", None)
    if not callable(cached_scheduled_loras):
        return None
    return cast(tuple[object, ...] | None, cached_scheduled_loras(prompt_text))


def _snapshot_readiness(snapshot: object) -> str:
    """Return a compact readiness label for a LoRA action snapshot."""

    status = getattr(snapshot, "status", None)
    readiness = getattr(status, "readiness", None)
    return str(getattr(readiness, "value", readiness))


def _snapshot_unavailable_reason(snapshot: object) -> str | None:
    """Return the unavailable reason from a LoRA action snapshot."""

    status = getattr(snapshot, "status", None)
    reason = getattr(status, "unavailable_reason", None)
    return None if reason is None else str(reason)


def _snapshot_action_count(snapshot: object) -> int:
    """Return the number of prepared LoRA trigger-word actions."""

    return len(getattr(snapshot, "trigger_word_actions", ()))


def _round_menu_rows(menu: object) -> tuple[str, ...]:
    """Return top-level QFluent menu action labels from one opened menu."""

    actions = getattr(menu, "menuActions", None)
    if not callable(actions):
        return ()
    return tuple(action.text() for action in actions() if isinstance(action, QAction))


def _round_menu_submenu_rows(menu: object) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return submenu titles and action labels for one opened QFluent menu."""

    submenus = getattr(menu, "_subMenus", ())
    rows: list[tuple[str, tuple[str, ...]]] = []
    for submenu in submenus:
        title = getattr(submenu, "title", lambda: "")()
        rows.append((str(title), _round_menu_rows(submenu)))
    return tuple(rows)


def _populate_lazy_round_menu_submenus(menu: object) -> None:
    """Populate renderer-owned lazy QFluent submenus for inspection."""

    submenus = getattr(menu, "_subMenus", ())
    for submenu in submenus:
        populate = getattr(submenu, "populate_if_needed", None)
        if callable(populate):
            populate()


def _round_menu_trigger_actions(menu: object) -> tuple[QAction, ...]:
    """Return LoRA trigger-word actions from a menu and any captured submenus."""

    actions = list(_round_menu_actions(menu))
    submenus = getattr(menu, "_subMenus", ())
    for submenu in submenus:
        actions.extend(_round_menu_actions(submenu))
    return tuple(
        action
        for action in actions
        if action.text().startswith("Trigger words:")
        or action.property("promptFullTriggerWordsLabel") is not None
    )


def _round_menu_actions(menu: object) -> tuple[QAction, ...]:
    """Return QAction objects directly owned by one QFluent menu."""

    actions = getattr(menu, "menuActions", None)
    if not callable(actions):
        return ()
    return tuple(action for action in actions() if isinstance(action, QAction))


def _selected_trigger_action(
    actions: tuple[QAction, ...],
    *,
    trigger_first: bool,
    requested_label: str | None,
) -> QAction | None:
    """Return the trigger action selected by one context-menu probe."""

    if trigger_first:
        return actions[0] if actions else None
    if requested_label is None:
        return None
    for action in actions:
        full_label = action.property("promptFullTriggerWordsLabel")
        if action.text() == requested_label or full_label == requested_label:
            return action
    return None


def _autocomplete_panel(editor: PromptEditor) -> QWidget | None:
    """Return the composed autocomplete panel when normal construction created it."""

    panel = getattr(editor, "_autocomplete_panel", None)
    if isinstance(panel, QWidget):
        return panel
    return None


def _autocomplete_preview_state(editor: PromptEditor) -> object | None:
    """Return projection-owned autocomplete preview state without using popup state."""

    surface = getattr(editor, "_surface", None)
    session = getattr(surface, "_session", None)
    return getattr(session, "autocomplete_preview", None)


def _autocomplete_preview_suffix(preview: object | None) -> str:
    """Return the projection-owned autocomplete preview suffix."""

    suffix = getattr(preview, "suffix_text", "")
    return suffix if isinstance(suffix, str) else ""


def _autocomplete_preview_source_position(preview: object | None) -> int | None:
    """Return the projection-owned autocomplete preview source position."""

    position = getattr(preview, "source_position", None)
    return position if isinstance(position, int) else None


def _autocomplete_owner_state(editor: PromptEditor) -> dict[str, Any]:
    """Return autocomplete lifecycle state from production owners."""

    autocomplete = getattr(editor, "_autocomplete", None)
    if autocomplete is None:
        interaction = getattr(editor, "_interaction_controller", None)
        autocomplete = getattr(interaction, "_autocomplete", None)
    sessions = getattr(autocomplete, "_sessions", None)
    state = getattr(sessions, "state", None)
    session = getattr(state, "session", None)
    presenter = getattr(autocomplete, "_presenter", None)
    ghost_snapshot = getattr(state, "ghost_text_source_snapshot", None)
    suggestions = tuple(
        suggestion.tag
        for suggestion in getattr(session, "suggestions", ())
        if isinstance(getattr(suggestion, "tag", None), str)
    )
    has_active_session = getattr(sessions, "has_active_session", None)
    panel_visible = getattr(presenter, "panel_visible", None)
    panel_under_mouse = getattr(presenter, "panel_under_mouse", None)
    return {
        "lifecycle": _safe_enum_value(getattr(state, "lifecycle", "idle")),
        "mode": str(getattr(session, "mode", "none")),
        "selected_index": int(getattr(session, "selected_index", -1)),
        "prefix": str(getattr(session, "prefix", "")),
        "word_start": getattr(session, "word_start", None),
        "word_end": getattr(session, "word_end", None),
        "active_tag_end": getattr(session, "active_tag_end", None),
        "suggestions": suggestions,
        "has_active": bool(has_active_session())
        if callable(has_active_session)
        else False,
        "presenter_panel_visible": bool(panel_visible())
        if callable(panel_visible)
        else False,
        "presenter_panel_under_mouse": bool(panel_under_mouse())
        if callable(panel_under_mouse)
        else False,
        "source_revision": getattr(ghost_snapshot, "source_revision", None),
        "snapshot_source_length": getattr(ghost_snapshot, "source_length", None),
        "snapshot_cursor_position": getattr(ghost_snapshot, "cursor_position", None),
    }


def _projection_owner_state(editor: PromptEditor) -> dict[str, Any]:
    """Return source, caret, and projection state from the real projection owner."""

    surface = getattr(editor, "_surface", None)
    editing_session = getattr(surface, "_editing_session", None)
    document_view = getattr(surface, "_document_view", None)
    projection_document = getattr(surface, "_projection_document", None)
    active_projection_document = getattr(surface, "_active_projection_document", None)
    layout = getattr(surface, "_layout", None)
    layout_projection_document = getattr(layout, "projection_document", None)
    layout_snapshot = getattr(layout, "_snapshot", None)
    paint_cache = getattr(surface, "_projection_paint_cache", None)
    paint_cache_key = getattr(paint_cache, "cache_key", None)
    paint_cache_state = getattr(paint_cache_key, "paint_state", None)
    ghosted_run_ids = tuple(
        str(run_id) for run_id in getattr(paint_cache_state, "ghosted_run_ids", ())
    )
    projection_session = getattr(surface, "_session", None)
    transient_overlays = getattr(surface, "_transient_edit_overlays", None)
    freshness_controller = getattr(surface, "_projection_freshness_controller", None)
    caret_state = getattr(surface, "_cursor_state", None)
    anchor_state = getattr(surface, "_anchor_state", None)
    caret_map_document = (
        active_projection_document
        if getattr(projection_session, "autocomplete_preview", None) is not None
        else projection_document
    )
    caret_map = getattr(caret_map_document, "caret_map", None)
    caret_preferred_x = getattr(surface, "_preferred_x", None)
    caret_rect_override = getattr(surface, "_caret_rect_override", None)
    freshness = getattr(freshness_controller, "freshness", None)
    pending_update = getattr(freshness_controller, "has_pending_update", None)
    stale_geometry = getattr(
        freshness_controller,
        "has_stale_projection_geometry",
        None,
    )
    has_pending_update = bool(pending_update()) if callable(pending_update) else False
    has_stale_geometry = bool(stale_geometry()) if callable(stale_geometry) else False
    freshness_is_stale_safe = has_stale_geometry
    source_revision = getattr(surface, "_source_revision", None)
    insertion_overlay = getattr(transient_overlays, "insertion_overlay", None)
    deletion_overlay = getattr(transient_overlays, "deletion_overlay", None)
    caret_geometry = getattr(transient_overlays, "caret_geometry", None)
    valid_insertion_overlay = _valid_transient_insertion_overlay(
        transient_overlays=transient_overlays,
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_revision=source_revision,
    )
    valid_deletion_overlay = _valid_transient_deletion_overlay(
        transient_overlays=transient_overlays,
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_revision=source_revision,
    )
    valid_caret_geometry = _valid_transient_caret_geometry(
        transient_overlays=transient_overlays,
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_revision=source_revision,
        cursor_position=getattr(caret_state, "source_position", None),
        anchor_position=getattr(anchor_state, "source_position", None),
    )
    selection = _surface_selection(surface)
    selection_rects = _layout_selection_rects(layout, selection)
    layout_metrics = getattr(layout, "metrics", None)
    scroll_offset = _surface_scroll_offset(surface)
    insertion_overlay_viewport_rect = _transient_insertion_overlay_viewport_rect(
        transient_overlays=transient_overlays,
        overlay=valid_insertion_overlay,
        metrics=layout_metrics,
        scroll_offset=scroll_offset,
    )
    insertion_overlay_repaint_rect = _transient_insertion_overlay_repaint_rect(
        transient_overlays=transient_overlays,
        overlay=valid_insertion_overlay,
        metrics=layout_metrics,
        scroll_offset=scroll_offset,
    )
    deletion_overlay_viewport_rects = _transient_deletion_overlay_viewport_rects(
        transient_overlays=transient_overlays,
        overlay=valid_deletion_overlay,
        scroll_offset=scroll_offset,
    )
    deletion_overlay_erase_rects = _transient_deletion_overlay_erase_rects(
        transient_overlays=transient_overlays,
        overlay=valid_deletion_overlay,
        scroll_offset=scroll_offset,
    )
    deletion_overlay_repaint_rect = _transient_deletion_overlay_repaint_rect(
        transient_overlays=transient_overlays,
        overlay=valid_deletion_overlay,
        scroll_offset=scroll_offset,
    )
    undo_stack = getattr(editing_session, "_undo_stack", None)
    caret_rect = _surface_caret_rect(surface)
    viewport = surface.viewport() if surface is not None else None
    viewport_rect = viewport.rect() if viewport is not None else QRect()
    vertical_scrollbar = surface.verticalScrollBar() if surface is not None else None
    horizontal_scrollbar = (
        surface.horizontalScrollBar() if surface is not None else None
    )
    layout_content_size = _layout_content_size(layout)
    layout_metrics = getattr(layout, "metrics", None)
    shell_sizing = getattr(editor, "_sizing", None)
    caret_token_id = getattr(caret_state, "token_id", None)
    anchor_token_id = getattr(anchor_state, "token_id", None)
    paint_cache_projection_identity = getattr(
        paint_cache_key,
        "projection_document_identity",
        None,
    )
    paint_cache_layout_snapshot_identity = getattr(
        paint_cache_key,
        "layout_snapshot_identity",
        None,
    )
    return {
        "source_revision": source_revision,
        "editing_session_source_revision": getattr(
            editing_session,
            "source_revision",
            None,
        ),
        "editing_session_cursor_position": getattr(
            editing_session,
            "cursor_position",
            None,
        ),
        "editing_session_anchor_position": getattr(
            editing_session,
            "anchor_position",
            None,
        ),
        "document_view_source_text": str(getattr(document_view, "source_text", "")),
        "projection_document_source_text": str(
            getattr(projection_document, "source_text", "")
        ),
        "active_projection_source_text": str(
            getattr(active_projection_document, "source_text", "")
        ),
        "layout_projection_source_text": str(
            getattr(layout_projection_document, "source_text", "")
        ),
        "projection_text": str(getattr(projection_document, "projection_text", "")),
        "active_projection_text": str(
            getattr(active_projection_document, "projection_text", "")
        ),
        "layout_projection_text": str(
            getattr(layout_projection_document, "projection_text", "")
        ),
        "layout_uses_projection_document": (
            layout_projection_document is projection_document
        ),
        "layout_uses_active_projection_document": (
            layout_projection_document is active_projection_document
        ),
        "paint_cache_key_present": paint_cache_key is not None,
        "paint_cache_source_revision": getattr(
            paint_cache_key, "source_revision", None
        ),
        "paint_cache_projection_document_identity_matches_layout": (
            paint_cache_key is None
            or paint_cache_projection_identity == id(layout_projection_document)
        ),
        "paint_cache_layout_snapshot_identity_matches_layout": (
            paint_cache_key is None
            or paint_cache_layout_snapshot_identity == id(layout_snapshot)
        ),
        "paint_cache_ghosted_run_ids": ghosted_run_ids,
        "autocomplete_ghost_paint_visible_by_owner_state": bool(
            (
                layout_projection_document is not None
                and projection_document is not None
                and getattr(layout_projection_document, "projection_text", "")
                != getattr(projection_document, "projection_text", "")
            )
            or ghosted_run_ids
        ),
        "projection_freshness": _safe_enum_value(freshness),
        "projection_has_pending_update": bool(has_pending_update),
        "projection_has_stale_geometry": bool(has_stale_geometry),
        "caret_state_source_position": getattr(caret_state, "source_position", None),
        "anchor_state_source_position": getattr(anchor_state, "source_position", None),
        "caret_map_source_length": getattr(caret_map, "source_length", None),
        "caret_map_stop_count": None
        if caret_map is None
        else len(getattr(caret_map, "stops", ())),
        "selection_rects": _rectfs_tuple(selection_rects),
        "caret_preferred_x": caret_preferred_x
        if isinstance(caret_preferred_x, int | float)
        else None,
        "caret_rect_override": _rectf_tuple(
            caret_rect_override if isinstance(caret_rect_override, QRectF) else None
        ),
        "skip_next_same_source_soft_wrap_move": bool(
            getattr(surface, "_skip_next_same_source_soft_wrap_move", False)
        ),
        "projection_token_count": len(getattr(projection_document, "tokens", ())),
        "projection_run_count": len(getattr(projection_document, "runs", ())),
        "layout_line_count": _layout_count(layout, "line_count"),
        "layout_text_fragment_count": _layout_count(layout, "text_fragment_count"),
        "layout_inline_object_fragment_count": _layout_count(
            layout,
            "inline_object_fragment_count",
        ),
        "layout_content_width": layout_content_size[0],
        "layout_content_height": layout_content_size[1],
        "layout_text_width": float(getattr(layout, "_text_width", 0.0)),
        "projection_metrics_text_line_height": _optional_float(
            getattr(layout_metrics, "text_line_height", None)
        ),
        "projection_metrics_ascent": _optional_float(
            getattr(layout_metrics, "text_ascent", None)
        ),
        "projection_metrics_descent": _optional_float(
            getattr(layout_metrics, "text_descent", None)
        ),
        "projection_metrics_document_margin": _optional_float(
            getattr(layout_metrics, "document_margin", None)
        ),
        "projection_metrics_content_left_inset": _optional_float(
            getattr(layout_metrics, "content_left_inset", None)
        ),
        "projection_metrics_content_height": _projection_metrics_content_height(
            layout=layout,
            metrics=layout_metrics,
        ),
        "shell_natural_height": _optional_int(
            getattr(shell_sizing, "_last_natural_height", None)
        ),
        "shell_effective_height": _optional_int(
            getattr(shell_sizing, "_last_effective_height", None)
        ),
        "shell_minimum_editor_height": _shell_minimum_editor_height(shell_sizing),
        "shell_outer_vertical_padding": _shell_outer_vertical_padding(shell_sizing),
        "shell_document_vertical_padding": _shell_document_vertical_padding(
            shell_sizing
        ),
        "visible_layout_rows": _visible_layout_rows(
            layout=layout,
            metrics=layout_metrics,
            source_text=editor.toPlainText(),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        ),
        "visible_text_fragments": _visible_text_fragments(
            layout=layout,
            metrics=layout_metrics,
            source_text=editor.toPlainText(),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        ),
        "caret_token_id": caret_token_id if isinstance(caret_token_id, str) else None,
        "anchor_token_id": anchor_token_id
        if isinstance(anchor_token_id, str)
        else None,
        "caret_token_id_resolves": _token_id_resolves(
            active_projection_document,
            caret_token_id,
        ),
        "anchor_token_id_resolves": _token_id_resolves(
            active_projection_document,
            anchor_token_id,
        ),
        "caret_rect": _rectf_tuple(caret_rect),
        "viewport_rect": _rect_tuple(viewport_rect),
        "caret_rect_finite": _rectf_is_finite(caret_rect),
        "caret_rect_has_area": bool(
            caret_rect is not None
            and caret_rect.width() >= 1.0
            and caret_rect.height() >= 1.0
        ),
        "caret_rect_intersects_viewport": bool(
            caret_rect is not None
            and QRectF(viewport_rect)
            .adjusted(-4.0, -4.0, 4.0, 4.0)
            .intersects(caret_rect)
        ),
        "vertical_scroll_minimum": _scrollbar_minimum(vertical_scrollbar),
        "vertical_scroll_maximum": _scrollbar_maximum(vertical_scrollbar),
        "vertical_scroll_page_step": _scrollbar_page_step(vertical_scrollbar),
        "horizontal_scroll_minimum": _scrollbar_minimum(horizontal_scrollbar),
        "horizontal_scroll_maximum": _scrollbar_maximum(horizontal_scrollbar),
        "horizontal_scroll_page_step": _scrollbar_page_step(horizontal_scrollbar),
        "transient_caret_geometry_present": caret_geometry is not None,
        "transient_caret_geometry_valid": valid_caret_geometry is not None,
        "transient_insertion_overlay_present": insertion_overlay is not None,
        "transient_insertion_overlay_valid": valid_insertion_overlay is not None,
        "transient_insertion_overlay_source_range": (
            None
            if insertion_overlay is None
            else (
                int(getattr(insertion_overlay, "source_start", 0)),
                int(getattr(insertion_overlay, "source_start", 0))
                + len(str(getattr(insertion_overlay, "text", ""))),
            )
        ),
        "transient_insertion_overlay_viewport_rect": _rectf_tuple(
            insertion_overlay_viewport_rect
        ),
        "transient_insertion_overlay_repaint_rect": _rectf_tuple(
            insertion_overlay_repaint_rect
        ),
        "transient_deletion_overlay_present": deletion_overlay is not None,
        "transient_deletion_overlay_valid": valid_deletion_overlay is not None,
        "transient_deletion_overlay_source_range": (
            None
            if deletion_overlay is None
            else (
                int(getattr(deletion_overlay, "source_start", 0)),
                int(getattr(deletion_overlay, "source_end", 0)),
            )
        ),
        "transient_deletion_overlay_viewport_rects": _rectfs_tuple(
            deletion_overlay_viewport_rects
        ),
        "transient_deletion_overlay_erase_rects": _rectfs_tuple(
            deletion_overlay_erase_rects
        ),
        "transient_deletion_overlay_repaint_rect": _rectf_tuple(
            deletion_overlay_repaint_rect
        ),
        "undo_available": bool(editing_session.can_undo())
        if editing_session is not None
        else False,
        "redo_available": bool(editing_session.can_redo())
        if editing_session is not None
        else False,
        "undo_depth": int(getattr(undo_stack, "undo_depth", 0)),
        "redo_depth": int(getattr(undo_stack, "redo_depth", 0)),
        "undo_max_depth": int(getattr(undo_stack, "_max_undo_states", 0)),
        "redo_max_depth": int(getattr(undo_stack, "_max_redo_states", 0)),
        "undo_edit_block_depth": int(getattr(undo_stack, "edit_block_depth", 0)),
        "undo_pending_state_present": (
            getattr(undo_stack, "_pending_undo_state", None) is not None
        ),
        "undo_typing_group_active": bool(
            getattr(undo_stack, "typing_group_active", False)
        ),
        "undo_typing_group_last_cursor_position": getattr(
            undo_stack,
            "_typing_group_last_cursor_position",
            None,
        ),
        "undo_delete_group_active": bool(
            getattr(undo_stack, "delete_group_active", False)
        ),
        "undo_delete_group_key": getattr(undo_stack, "_delete_group_key", None),
    }


def _valid_transient_insertion_overlay(
    *,
    transient_overlays: object | None,
    freshness_is_stale_safe: bool,
    source_revision: object,
) -> object | None:
    """Return insertion overlay validity from the production overlay owner."""

    valid_insertion_overlay = getattr(
        transient_overlays,
        "valid_insertion_overlay",
        None,
    )
    if not callable(valid_insertion_overlay) or not isinstance(source_revision, int):
        return None
    result: object = valid_insertion_overlay(
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_revision=source_revision,
    )
    return result


def _valid_transient_deletion_overlay(
    *,
    transient_overlays: object | None,
    freshness_is_stale_safe: bool,
    source_revision: object,
) -> object | None:
    """Return deletion overlay validity from the production overlay owner."""

    valid_deletion_overlay = getattr(
        transient_overlays,
        "valid_deletion_overlay",
        None,
    )
    if not callable(valid_deletion_overlay) or not isinstance(source_revision, int):
        return None
    result: object = valid_deletion_overlay(
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_revision=source_revision,
    )
    return result


def _valid_transient_caret_geometry(
    *,
    transient_overlays: object | None,
    freshness_is_stale_safe: bool,
    source_revision: object,
    cursor_position: object,
    anchor_position: object,
) -> object | None:
    """Return caret-geometry validity from the production overlay owner."""

    valid_caret_geometry = getattr(
        transient_overlays,
        "valid_caret_geometry",
        None,
    )
    if (
        not callable(valid_caret_geometry)
        or not isinstance(source_revision, int)
        or not isinstance(cursor_position, int)
        or not isinstance(anchor_position, int)
    ):
        return None
    result: object = valid_caret_geometry(
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_revision=source_revision,
        cursor_position=cursor_position,
        anchor_position=anchor_position,
    )
    return result


def _layout_count(layout: object | None, method_name: str) -> int:
    """Return one layout metric count from a no-arg layout method."""

    method = getattr(layout, method_name, None)
    if not callable(method):
        return 0
    result = method()
    return int(result) if isinstance(result, int) else 0


def _layout_content_size(layout: object | None) -> tuple[float, float]:
    """Return layout content width and height without painting."""

    content_size = getattr(layout, "content_size", None)
    if not callable(content_size):
        return (0.0, 0.0)
    size = content_size()
    width = getattr(size, "width", None)
    height = getattr(size, "height", None)
    return (
        float(width()) if callable(width) else 0.0,
        float(height()) if callable(height) else 0.0,
    )


def _visible_layout_rows(
    *,
    layout: object | None,
    metrics: object | None,
    source_text: str,
    viewport_rect: QRect,
    scroll_offset: float,
) -> tuple[PromptEditorVisibleLayoutRow, ...]:
    """Return projection rows that should be visible in the current viewport."""

    snapshot = getattr(layout, "_snapshot", None)
    lines = getattr(snapshot, "lines", ())
    if not isinstance(lines, Sequence):
        return ()
    viewport_top = float(viewport_rect.top())
    viewport_bottom = float(viewport_rect.bottom())
    rows: list[PromptEditorVisibleLayoutRow] = []
    for row_index, line in enumerate(lines):
        document_top = _optional_float(getattr(line, "top", None))
        height = _optional_float(getattr(line, "height", None))
        source_start = _optional_int(getattr(line, "source_start", None))
        source_end = _optional_int(getattr(line, "source_end", None))
        if (
            document_top is None
            or height is None
            or source_start is None
            or source_end is None
        ):
            continue
        row_viewport_top = document_top - scroll_offset
        row_viewport_bottom = row_viewport_top + height
        if row_viewport_bottom < viewport_top - 2.0:
            continue
        if row_viewport_top > viewport_bottom + 2.0:
            continue
        safe_start = max(0, min(source_start, len(source_text)))
        safe_end = max(safe_start, min(source_end, len(source_text)))
        fragments = getattr(line, "fragments", ())
        has_inline_object = any(
            fragment.__class__.__name__ == "PromptProjectionInlineObjectFragment"
            for fragment in fragments
        )
        expected_height = _expected_row_height(line=line, metrics=metrics)
        expected_baseline = _metrics_text_baseline(
            metrics=metrics,
            row_top=document_top,
            row_height=height,
        )
        rows.append(
            PromptEditorVisibleLayoutRow(
                row_index=row_index,
                source_start=source_start,
                source_end=source_end,
                document_top=document_top,
                viewport_top=row_viewport_top,
                height=height,
                text=source_text[safe_start:safe_end],
                has_inline_object=has_inline_object,
                expected_height=expected_height,
                expected_text_baseline=expected_baseline,
            )
        )
    return tuple(rows)


def _visible_text_fragments(
    *,
    layout: object | None,
    metrics: object | None,
    source_text: str,
    viewport_rect: QRect,
    scroll_offset: float,
) -> tuple[PromptEditorVisibleTextFragment, ...]:
    """Return projection text fragments visible in the current viewport."""

    snapshot = getattr(layout, "_snapshot", None)
    fragments = getattr(snapshot, "text_fragments", ())
    if not isinstance(fragments, Sequence):
        return ()
    viewport_top = float(viewport_rect.top())
    viewport_bottom = float(viewport_rect.bottom())
    visible_fragments: list[PromptEditorVisibleTextFragment] = []
    for fragment_index, fragment in enumerate(fragments):
        rect = getattr(fragment, "rect", None)
        if not isinstance(rect, QRectF):
            continue
        fragment_viewport_top = rect.top() - scroll_offset
        fragment_viewport_bottom = rect.bottom() - scroll_offset
        if fragment_viewport_bottom < viewport_top - 2.0:
            continue
        if fragment_viewport_top > viewport_bottom + 2.0:
            continue
        source_start, source_end = _fragment_source_range(
            getattr(fragment, "source_positions", ())
        )
        safe_start = max(0, min(source_start, len(source_text)))
        safe_end = max(safe_start, min(source_end, len(source_text)))
        baseline = _optional_float(getattr(fragment, "baseline", None))
        if baseline is None:
            continue
        expected_height = _optional_float(getattr(metrics, "text_line_height", None))
        expected_baseline = _metrics_text_baseline(
            metrics=metrics,
            row_top=rect.top(),
            row_height=rect.height(),
        )
        visible_fragments.append(
            PromptEditorVisibleTextFragment(
                fragment_index=fragment_index,
                source_start=source_start,
                source_end=source_end,
                document_rect=_qrectf_tuple(rect),
                viewport_rect=(
                    rect.left(),
                    fragment_viewport_top,
                    rect.width(),
                    rect.height(),
                ),
                document_baseline=baseline,
                viewport_baseline=baseline - scroll_offset,
                text=source_text[safe_start:safe_end],
                expected_document_baseline=expected_baseline,
                expected_viewport_baseline=None
                if expected_baseline is None
                else expected_baseline - scroll_offset,
                expected_height=expected_height,
            )
        )
    return tuple(visible_fragments)


def _expected_row_height(*, line: object, metrics: object | None) -> float | None:
    """Return the row height expected by the projection metrics contract."""

    text_line_height = _optional_float(getattr(metrics, "text_line_height", None))
    if text_line_height is None:
        return None
    expected_height = text_line_height
    fragments = getattr(line, "fragments", ())
    if isinstance(fragments, Sequence):
        for fragment in fragments:
            if fragment.__class__.__name__ != "PromptProjectionInlineObjectFragment":
                continue
            rect = getattr(fragment, "rect", None)
            if isinstance(rect, QRectF):
                expected_height = max(expected_height, float(rect.height()))
    return expected_height


def _metrics_text_baseline(
    *,
    metrics: object | None,
    row_top: float,
    row_height: float,
) -> float | None:
    """Return the expected baseline from a projection metrics object."""

    baseline_for_row = getattr(metrics, "text_baseline_for_row", None)
    if not callable(baseline_for_row):
        return None
    result = baseline_for_row(row_top=row_top, row_height=row_height)
    return _optional_float(result)


def _projection_metrics_content_height(
    *,
    layout: object | None,
    metrics: object | None,
) -> float | None:
    """Return the content height implied by metrics and current layout rows."""

    snapshot = getattr(layout, "_snapshot", None)
    lines = getattr(snapshot, "lines", ())
    content_height_for_rows = getattr(metrics, "content_height_for_rows", None)
    if not isinstance(lines, Sequence) or not callable(content_height_for_rows):
        return None
    row_heights: list[float] = []
    for line in lines:
        height = _optional_float(getattr(line, "height", None))
        if height is None:
            return None
        row_heights.append(height)
    return _optional_float(content_height_for_rows(tuple(row_heights)))


def _shell_minimum_editor_height(shell_sizing: object | None) -> int | None:
    """Return the shell controller minimum editor height when available."""

    minimum_editor_height = getattr(shell_sizing, "minimum_editor_height", None)
    if not callable(minimum_editor_height):
        return None
    result = minimum_editor_height()
    return result if isinstance(result, int) else None


def _shell_outer_vertical_padding(shell_sizing: object | None) -> int | None:
    """Return shell-owned outer vertical padding from the sizing controller."""

    outer_vertical_padding = getattr(shell_sizing, "_outer_vertical_padding", None)
    if not callable(outer_vertical_padding):
        return None
    result = outer_vertical_padding()
    return result if isinstance(result, int) else None


def _shell_document_vertical_padding(shell_sizing: object | None) -> int | None:
    """Return document vertical padding from the sizing controller."""

    document_vertical_padding = getattr(
        shell_sizing,
        "_document_vertical_padding",
        None,
    )
    if not callable(document_vertical_padding):
        return None
    result = document_vertical_padding()
    return result if isinstance(result, int) else None


def _fragment_source_range(source_positions: object) -> tuple[int, int]:
    """Return a half-open source range covered by one projection fragment."""

    if not isinstance(source_positions, Sequence):
        return (0, 0)
    positions = tuple(
        position
        for position in source_positions
        if isinstance(position, int) and position >= 0
    )
    if not positions:
        return (0, 0)
    return min(positions), max(positions) + 1


def _qrectf_tuple(rect: QRectF) -> tuple[float, float, float, float]:
    """Return a stable tuple for one floating-point Qt rect."""

    return (rect.left(), rect.top(), rect.width(), rect.height())


def _surface_selection(surface: object | None) -> object | None:
    """Return the projection-owned source selection model from the surface."""

    selection = getattr(surface, "_selection", None)
    if not callable(selection):
        return None
    result: object = selection()
    return result


def _layout_selection_rects(
    layout: object | None,
    selection: object | None,
) -> tuple[QRectF, ...]:
    """Return document-local selection rects from the projection layout owner."""

    selection_rects = getattr(layout, "selection_rects", None)
    if not callable(selection_rects):
        return ()
    return _qrectf_sequence(selection_rects(selection))


def _token_id_resolves(
    projection_document: object | None,
    token_id: object,
) -> bool:
    """Return whether an optional caret token id resolves in the projection document."""

    if not isinstance(token_id, str):
        return True
    token_by_id = getattr(projection_document, "token_by_id", None)
    if not callable(token_by_id):
        return False
    return token_by_id(token_id) is not None


def _compact_editor_state(editor: PromptEditor) -> dict[str, Any]:
    """Return cheap state used around observed production owner calls."""

    cursor = cast(Any, editor).textCursor()
    preview = _autocomplete_preview_state(editor)
    autocomplete_state = _autocomplete_owner_state(editor)
    return {
        "source": editor.toPlainText(),
        "cursor": cursor.position(),
        "preview": (
            "<none>"
            if preview is None
            else (
                f"{_autocomplete_preview_source_position(preview)}:"
                f"{_autocomplete_preview_suffix(preview)!r}"
            )
        ),
        "session": (
            f"{autocomplete_state['lifecycle']}:"
            f"{autocomplete_state['mode']}:"
            f"{autocomplete_state['prefix']!r}:"
            f"{autocomplete_state['selected_index']}"
        ),
        "panel": (
            f"presenter={autocomplete_state['presenter_panel_visible']}:"
            f"active={autocomplete_state['has_active']}"
        ),
    }


def _short_repr(value: object) -> str:
    """Return a bounded representation for observed call results."""

    text = repr(value)
    if len(text) > 120:
        return f"{text[:117]}..."
    return text


def _safe_enum_value(value: object) -> str:
    """Return a stable string for enum-like values."""

    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


def _optional_int(value: object) -> int | None:
    """Return value when it is an int, otherwise None."""

    return value if isinstance(value, int) else None


def _optional_float(value: object) -> float | None:
    """Return value as a float when it is numeric, otherwise None."""

    return float(value) if isinstance(value, int | float) else None


def _accepted_selected_text_for_source(source_text: str) -> tuple[str, str]:
    """Return accepted editor selected-text representations for a source slice."""

    return source_text, source_text.replace("\n", "\u2029")


def _autocomplete_state_is_owned_or_visible(
    snapshot: PromptEditorStateSnapshot,
) -> bool:
    """Return whether any autocomplete owner or surface remains active."""

    return bool(
        snapshot.autocomplete_preview_active
        or snapshot.autocomplete_has_active_session
        or snapshot.autocomplete_presenter_panel_visible
        or snapshot.popup_state_visible
    )


def _projection_metrics_contract_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return geometry mismatches against the projection metrics authority."""

    violations: list[str] = []
    for row in snapshot.visible_layout_rows:
        if row.expected_height is not None and not _float_close(
            row.height,
            row.expected_height,
        ):
            violations.append(
                "text_only_row_height_mismatch"
                if not row.has_inline_object
                else "inline_row_height_mismatch"
            )
        if (
            not row.has_inline_object
            and row.expected_text_baseline is not None
            and not _row_contains_fragment_with_baseline(
                row=row,
                fragments=snapshot.visible_text_fragments,
                baseline=row.expected_text_baseline,
            )
            and row.text
        ):
            violations.append(f"text_only_row_baseline_mismatch:{row.row_index}")
    for fragment in snapshot.visible_text_fragments:
        if fragment.expected_height is not None and not _float_close(
            fragment.viewport_rect[3],
            fragment.expected_height,
        ):
            violations.append(
                f"text_fragment_height_mismatch:{fragment.fragment_index}"
            )
        if fragment.expected_document_baseline is not None and not _float_close(
            fragment.document_baseline,
            fragment.expected_document_baseline,
        ):
            violations.append(
                f"text_fragment_baseline_mismatch:{fragment.fragment_index}"
            )
    if snapshot.projection_metrics_content_height is not None and not _float_close(
        snapshot.layout_content_height,
        snapshot.projection_metrics_content_height,
    ):
        violations.append(
            "content_height_contract_mismatch:"
            f"{snapshot.layout_content_height:.3f}:"
            f"{snapshot.projection_metrics_content_height:.3f}"
        )
    violations.extend(_shell_height_contract_violations(snapshot))
    return tuple(violations)


def _row_contains_fragment_with_baseline(
    *,
    row: PromptEditorVisibleLayoutRow,
    fragments: tuple[PromptEditorVisibleTextFragment, ...],
    baseline: float,
) -> bool:
    """Return whether one row has a text fragment at the expected baseline."""

    row_bottom = row.document_top + row.height
    for fragment in fragments:
        fragment_top = fragment.document_rect[1]
        if fragment_top < row.document_top - 0.5 or fragment_top > row_bottom + 0.5:
            continue
        if _float_close(fragment.document_baseline, baseline):
            return True
    return False


def _shell_height_contract_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return shell sizing mismatches against projection metrics and padding."""

    if (
        snapshot.projection_metrics_text_line_height is None
        or snapshot.shell_document_vertical_padding is None
        or snapshot.shell_outer_vertical_padding is None
        or snapshot.shell_natural_height is None
        or snapshot.shell_natural_height <= 0
    ):
        return ()
    minimum_document_height = math.ceil(
        snapshot.projection_metrics_text_line_height
        + snapshot.shell_document_vertical_padding
    )
    expected_natural_height = (
        max(math.ceil(snapshot.layout_content_height), minimum_document_height)
        + snapshot.shell_outer_vertical_padding
    )
    if abs(snapshot.shell_natural_height - expected_natural_height) <= 1:
        return ()
    return (
        "shell_height_contract_mismatch:"
        f"{snapshot.shell_natural_height}:{expected_natural_height}",
    )


def _caret_row_height_contract_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return caret height mismatches against the row containing the caret."""

    if snapshot.caret_rect is None:
        return ()
    caret_y = snapshot.caret_rect[1]
    caret_height = snapshot.caret_rect[3]
    for row in snapshot.visible_layout_rows:
        if row.viewport_top - 0.5 <= caret_y <= row.viewport_top + row.height + 0.5:
            if not _float_close(caret_height, row.height):
                return (
                    f"caret_rect_height_mismatch:{caret_height:.3f}:{row.height:.3f}",
                )
            return ()
    return ()


def _transient_deletion_overerase_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return transient deletion erase bands that damage unrelated text."""

    source_range = snapshot.transient_deletion_overlay_source_range
    if (
        source_range is None
        or not snapshot.transient_deletion_overlay_valid
        or not snapshot.transient_deletion_overlay_erase_rects
    ):
        return ()
    affected_fragments = tuple(
        fragment
        for fragment in snapshot.visible_text_fragments
        if _ranges_overlap(
            source_range,
            (fragment.source_start, fragment.source_end),
        )
    )
    if not affected_fragments:
        return ()
    allowed_padding = 3.0
    left_bound = min(fragment.viewport_rect[0] for fragment in affected_fragments)
    violations: list[str] = []
    for erase_rect in snapshot.transient_deletion_overlay_erase_rects:
        if erase_rect[0] < left_bound - allowed_padding:
            violations.append(
                "transient_deletion_overerase_left:"
                f"{erase_rect[0]:.3f}:{left_bound:.3f}"
            )
        for fragment in snapshot.visible_text_fragments:
            if _ranges_overlap(
                source_range,
                (fragment.source_start, fragment.source_end),
            ):
                continue
            if _rects_intersect(erase_rect, fragment.viewport_rect):
                violations.append(
                    f"transient_deletion_overerase_neighbor:{fragment.fragment_index}"
                )
                break
    return tuple(violations)


def _ranges_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    """Return whether two half-open source ranges overlap."""

    return first[0] < second[1] and second[0] < first[1]


def _rects_intersect(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    """Return whether two serialized rectangles intersect with positive area."""

    first_left, first_top, first_width, first_height = first
    second_left, second_top, second_width, second_height = second
    return (
        first_left < second_left + second_width
        and second_left < first_left + first_width
        and first_top < second_top + second_height
        and second_top < first_top + first_height
    )


def _float_close(first: float, second: float, *, tolerance: float = 0.51) -> bool:
    """Return whether two geometry floats are equivalent for harness assertions."""

    return abs(first - second) <= tolerance


def _non_uniform_visible_row_shift_violations(
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when stable visible rows move by different amounts."""

    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    if abs(before.layout_content_height - after.layout_content_height) > 0.5:
        return ()
    before_rows = {row.row_index: row for row in before.visible_layout_rows}
    after_rows = {row.row_index: row for row in after.visible_layout_rows}
    shared_indexes = tuple(
        row_index for row_index in sorted(before_rows) if row_index in after_rows
    )
    if len(shared_indexes) < 2:
        return ()
    row_deltas = tuple(
        (
            row_index,
            after_rows[row_index].viewport_top - before_rows[row_index].viewport_top,
        )
        for row_index in shared_indexes
    )
    delta_values = tuple(delta for _row_index, delta in row_deltas)
    if max(delta_values) - min(delta_values) <= 0.75:
        return ()
    return (
        "non_uniform_visible_row_shift:"
        f"rows={_format_row_delta_summary(row_deltas)}:"
        f"scroll_delta={after.scroll_values['editor_vertical'] - before.scroll_values['editor_vertical']}:"
        f"editor_height_delta={_geometry_height_delta(before, after, 'editor')}:"
        f"viewport_height_delta={_geometry_height_delta(before, after, 'viewport')}",
    )


def _stable_single_character_content_height_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when stable one-character edits change content height."""

    if action_name not in {"space", "type_text"}:
        return ()
    inserted_text = _inserted_text(before.source_text, after.source_text)
    if len(inserted_text) != 1 or inserted_text in "\r\n\t":
        return ()
    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    content_height_delta = after.layout_content_height - before.layout_content_height
    if abs(content_height_delta) <= 0.75:
        return ()
    row_summary = _format_changed_row_geometry_summary(before=before, after=after)
    return (
        "stable_single_character_content_height_shift:"
        f"inserted={inserted_text!r}:"
        f"content_height_delta={content_height_delta:.2f}:"
        f"line_count={before.layout_line_count}:"
        f"rows={row_summary}:"
        f"editor_height_delta={_geometry_height_delta(before, after, 'editor')}:"
        f"viewport_height_delta={_geometry_height_delta(before, after, 'viewport')}",
    )


def _stable_single_character_geometry_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when stable one-character edits move editor chrome."""

    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    inserted_text = _inserted_text(before.source_text, after.source_text)
    if action_name not in {"space", "type_text"} or len(inserted_text) != 1:
        return ()
    if inserted_text in "\r\n\t":
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    if abs(before.layout_content_width - after.layout_content_width) > 0.5:
        return ()
    if abs(before.layout_content_height - after.layout_content_height) > 0.5:
        return ()
    changed_geometry = tuple(
        (
            key,
            _geometry_height_delta(before, after, key),
        )
        for key in ("panel", "editor", "viewport")
        if _geometry_height_delta(before, after, key) not in (None, 0)
    )
    if not changed_geometry:
        return ()
    geometry_summary = ",".join(
        f"{key}:{height_delta}" for key, height_delta in changed_geometry
    )
    return (
        "stable_single_character_geometry_shift:"
        f"inserted={inserted_text!r}:"
        f"geometry_height_delta={geometry_summary}:"
        f"line_count={before.layout_line_count}:"
        f"content_height={before.layout_content_height:.2f}",
    )


def _format_changed_row_geometry_summary(
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> str:
    """Return visible rows whose top or height changed across one transition."""

    before_rows = {row.row_index: row for row in before.visible_layout_rows}
    after_rows = {row.row_index: row for row in after.visible_layout_rows}
    changed_rows: list[str] = []
    for row_index in sorted(before_rows):
        after_row = after_rows.get(row_index)
        if after_row is None:
            continue
        before_row = before_rows[row_index]
        top_delta = after_row.viewport_top - before_row.viewport_top
        height_delta = after_row.height - before_row.height
        if abs(top_delta) <= 0.25 and abs(height_delta) <= 0.25:
            continue
        changed_rows.append(f"{row_index}:{top_delta:.2f}/{height_delta:.2f}")
        if len(changed_rows) >= 12:
            break
    return ",".join(changed_rows)


def _non_uniform_visible_fragment_shift_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when stable visible text fragments move unevenly."""

    if action_name not in {"space", "type_text"}:
        return ()
    inserted_text = _inserted_text(before.source_text, after.source_text)
    if len(inserted_text) != 1 or inserted_text in "\r\n\t":
        return ()
    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    if not _visible_row_source_ranges_are_stable(before=before, after=after):
        return ()
    if abs(before.layout_content_width - after.layout_content_width) > 0.5:
        return ()
    if abs(before.layout_content_height - after.layout_content_height) > 0.5:
        return ()
    insert_position = _single_insert_position(before.source_text, after.source_text)
    if insert_position is None:
        return ()
    before_fragments = _stable_visible_fragment_map(
        before.visible_text_fragments,
        insert_position=insert_position,
    )
    after_fragments = {
        _visible_fragment_key(fragment): fragment
        for fragment in after.visible_text_fragments
    }
    shared_keys = tuple(key for key in before_fragments if key in after_fragments)
    if len(shared_keys) < 2:
        return ()
    fragment_deltas = tuple(
        (
            before_fragments[key].fragment_index,
            after_fragments[key].viewport_baseline
            - before_fragments[key].viewport_baseline,
        )
        for key in shared_keys
    )
    delta_values = tuple(delta for _fragment_index, delta in fragment_deltas)
    if max(delta_values) - min(delta_values) <= 0.75:
        return ()
    return (
        "non_uniform_visible_fragment_shift:"
        f"fragments={_format_fragment_delta_summary(fragment_deltas)}:"
        f"scroll_delta={after.scroll_values['editor_vertical'] - before.scroll_values['editor_vertical']}:"
        f"editor_height_delta={_geometry_height_delta(before, after, 'editor')}:"
        f"viewport_height_delta={_geometry_height_delta(before, after, 'viewport')}",
    )


def _stable_visible_fragment_map(
    fragments: Sequence[PromptEditorVisibleTextFragment],
    *,
    insert_position: int,
) -> dict[tuple[int, int, str], PromptEditorVisibleTextFragment]:
    """Return visible fragments outside the insertion span keyed by post-edit source."""

    stable_fragments: dict[tuple[int, int, str], PromptEditorVisibleTextFragment] = {}
    for fragment in fragments:
        if fragment.source_start < insert_position < fragment.source_end:
            continue
        if fragment.source_start >= insert_position:
            key = (
                fragment.source_start + 1,
                fragment.source_end + 1,
                fragment.text,
            )
        else:
            key = _visible_fragment_key(fragment)
        stable_fragments[key] = fragment
    return stable_fragments


def _visible_row_source_ranges_are_stable(
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> bool:
    """Return whether shared visible rows still cover the same logical text."""

    insert_position = _single_insert_position(before.source_text, after.source_text)
    before_rows = {row.row_index: row for row in before.visible_layout_rows}
    after_rows = {row.row_index: row for row in after.visible_layout_rows}
    shared_indexes = tuple(index for index in before_rows if index in after_rows)
    if len(shared_indexes) < 2:
        return False
    for row_index in shared_indexes:
        before_row = before_rows[row_index]
        after_row = after_rows[row_index]
        expected_start = before_row.source_start
        expected_end = before_row.source_end
        if insert_position is not None and before_row.source_start >= insert_position:
            expected_start += 1
            expected_end += 1
        elif (
            insert_position is not None
            and before_row.source_start < insert_position <= before_row.source_end
        ):
            expected_end += 1
        if (
            after_row.source_start != expected_start
            or after_row.source_end != expected_end
        ):
            return False
    return True


def _visible_fragment_key(
    fragment: PromptEditorVisibleTextFragment,
) -> tuple[int, int, str]:
    """Return the stable source/text identity for one visible text fragment."""

    return (fragment.source_start, fragment.source_end, fragment.text)


def _format_fragment_delta_summary(
    fragment_deltas: Sequence[tuple[int, float]],
) -> str:
    """Return a compact fragment-delta summary for artifact diagnostics."""

    return ",".join(
        f"{fragment_index}:{delta:.2f}"
        for fragment_index, delta in fragment_deltas[:12]
    )


def _format_row_delta_summary(row_deltas: Sequence[tuple[int, float]]) -> str:
    """Return a compact row-delta summary for artifact diagnostics."""

    return ",".join(f"{row_index}:{delta:.2f}" for row_index, delta in row_deltas[:12])


def _geometry_height_delta(
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
    key: str,
) -> int | None:
    """Return one captured geometry height delta when both snapshots have it."""

    before_rect = before.geometries.get(key)
    after_rect = after.geometries.get(key)
    if before_rect is None or after_rect is None:
        return None
    return after_rect[3] - before_rect[3]


def _action_should_leave_caret_visible(
    action_name: str,
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> bool:
    """Return whether one abuse action should settle with a visible caret."""

    if action_name not in {
        "prefix",
        "space",
        "backspace",
        "delete",
        "caret",
        "selection",
        "selection_replace",
        "paste",
        "undo_redo",
    }:
        return False
    return (
        before.source_text != after.source_text
        or before.cursor_position != after.cursor_position
        or before.selection_range != after.selection_range
    )


def _autocomplete_dismissal_owner_violations(
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
    action_name: str,
) -> tuple[str, ...]:
    """Return missing owner-path evidence for autocomplete preview dismissal."""

    transition_events = tuple(
        event
        for event in after.recent_observed_events
        if before.observed_event_end_index
        <= event.index
        < after.observed_event_end_index
    )
    violations: list[str] = []
    preview_owner_clear = any(
        event.owner == "autocomplete preview projection owner"
        and event.method == "set_preview_state"
        and event.preview_before != "<none>"
        and event.preview_after == "<none>"
        for event in transition_events
    )
    if not preview_owner_clear:
        violations.append(f"{action_name}_dismissal_without_preview_owner_clear")
    paint_invalidation = any(
        event.owner == "projection source and caret owner"
        and event.method == "invalidate_autocomplete_preview_paint"
        for event in transition_events
    )
    if not paint_invalidation:
        violations.append(f"{action_name}_dismissal_without_preview_paint_invalidation")
    if action_name == "caret":
        caret_preview_reconcile = any(
            event.owner == "caret autocomplete preview coordinator"
            and event.method == "reconcile_after_caret_state_change"
            for event in transition_events
        )
        if not caret_preview_reconcile:
            violations.append("caret_dismissal_without_preview_reconciliation_owner")
    return tuple(violations)


def _source_prefix_ends_with_autocomplete_delimiter(
    source_text: str,
    source_position: int,
) -> bool:
    """Return whether preview would start after a hard tag-query delimiter."""

    if source_position <= 0:
        return False
    return source_text[source_position - 1] in ",\r\n"


def _panel_input_widgets(
    panel: EditorPanel,
) -> dict[tuple[str, str, str], QWidget]:
    """Return the dynamic editor-panel field registry with a strict type."""

    return cast(
        dict[tuple[str, str, str], QWidget],
        getattr(panel, "input_widgets_by_field_key"),
    )


def _scrollbar_value(widget: QWidget, accessor_name: str) -> int:
    """Return a scrollbar value from a Qt widget dynamic accessor."""

    accessor = getattr(widget, accessor_name, None)
    if not callable(accessor):
        return 0
    scrollbar = accessor()
    value = getattr(scrollbar, "value", None)
    if not callable(value):
        return 0
    return int(value())


def _scrollbar_minimum(scrollbar: object | None) -> int:
    """Return one scrollbar minimum or zero for missing test doubles."""

    minimum = getattr(scrollbar, "minimum", None)
    return int(minimum()) if callable(minimum) else 0


def _scrollbar_maximum(scrollbar: object | None) -> int:
    """Return one scrollbar maximum or zero for missing test doubles."""

    maximum = getattr(scrollbar, "maximum", None)
    return int(maximum()) if callable(maximum) else 0


def _scrollbar_page_step(scrollbar: object | None) -> int:
    """Return one scrollbar page step or zero for missing test doubles."""

    page_step = getattr(scrollbar, "pageStep", None)
    return int(page_step()) if callable(page_step) else 0


def _surface_caret_rect(surface: object | None) -> QRectF | None:
    """Return the current surface-owned caret rect without painting."""

    current_caret_rect = getattr(surface, "_current_caret_rect", None)
    if not callable(current_caret_rect):
        return None
    rect = current_caret_rect()
    return QRectF(rect) if isinstance(rect, QRectF) else None


def _surface_scroll_offset(surface: object | None) -> float:
    """Return the projection surface scroll offset used by paint geometry owners."""

    scroll_offset = getattr(surface, "_scroll_offset", None)
    if not callable(scroll_offset):
        return 0.0
    result = scroll_offset()
    return float(result) if isinstance(result, int | float) else 0.0


def _transient_insertion_overlay_viewport_rect(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    metrics: object | None,
    scroll_offset: float,
) -> QRectF | None:
    """Return the owner-computed viewport rect for a valid insertion overlay."""

    if overlay is None or metrics is None:
        return None
    viewport_rect = getattr(transient_overlays, "insertion_overlay_viewport_rect", None)
    if not callable(viewport_rect):
        return None
    result = viewport_rect(
        overlay,
        metrics=metrics,
        scroll_offset=scroll_offset,
    )
    return QRectF(result) if isinstance(result, QRectF) else None


def _transient_insertion_overlay_repaint_rect(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    metrics: object | None,
    scroll_offset: float,
) -> QRectF | None:
    """Return the owner-computed repaint rect for a valid insertion overlay."""

    if overlay is None or metrics is None:
        return None
    repaint_rect = getattr(transient_overlays, "insertion_overlay_repaint_rect", None)
    if not callable(repaint_rect):
        return None
    result = repaint_rect(
        previous_overlay=None,
        next_overlay=overlay,
        metrics=metrics,
        scroll_offset=scroll_offset,
    )
    return QRectF(result) if isinstance(result, QRectF) else None


def _transient_deletion_overlay_viewport_rects(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    scroll_offset: float,
) -> tuple[QRectF, ...]:
    """Return owner-computed viewport rects for a valid deletion overlay."""

    if overlay is None:
        return ()
    viewport_rects = getattr(
        transient_overlays, "deletion_overlay_viewport_rects", None
    )
    if not callable(viewport_rects):
        return ()
    return _qrectf_sequence(viewport_rects(overlay, scroll_offset=scroll_offset))


def _transient_deletion_overlay_erase_rects(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    scroll_offset: float,
) -> tuple[QRectF, ...]:
    """Return owner-computed erase rects for a valid deletion overlay."""

    if overlay is None:
        return ()
    erase_rects = getattr(transient_overlays, "deletion_overlay_erase_rects", None)
    if not callable(erase_rects):
        return ()
    return _qrectf_sequence(erase_rects(overlay, scroll_offset=scroll_offset))


def _transient_deletion_overlay_repaint_rect(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    scroll_offset: float,
) -> QRectF | None:
    """Return the owner-computed repaint rect for a valid deletion overlay."""

    if overlay is None:
        return None
    repaint_rect = getattr(transient_overlays, "deletion_overlay_repaint_rect", None)
    if not callable(repaint_rect):
        return None
    result = repaint_rect(
        previous_overlay=None,
        next_overlay=overlay,
        scroll_offset=scroll_offset,
    )
    return QRectF(result) if isinstance(result, QRectF) else None


def _qrectf_sequence(value: object) -> tuple[QRectF, ...]:
    """Return a tuple of QRectF values from an owner-returned sequence."""

    if not isinstance(value, Sequence):
        return ()
    return tuple(QRectF(rect) for rect in value if isinstance(rect, QRectF))


def _rectf_tuple(rect: QRectF | None) -> tuple[float, float, float, float] | None:
    """Serialize one QRectF for headless diagnostics."""

    if rect is None:
        return None
    return rect.x(), rect.y(), rect.width(), rect.height()


def _rectfs_tuple(
    rects: Sequence[QRectF],
) -> tuple[
    tuple[float, float, float, float],
    ...,
]:
    """Serialize QRectF values for headless diagnostics."""

    return tuple(
        rect_tuple for rect in rects if (rect_tuple := _rectf_tuple(rect)) is not None
    )


def _rectf_is_finite(rect: QRectF | None) -> bool:
    """Return whether one QRectF contains only finite coordinates."""

    if rect is None:
        return False
    return all(
        math.isfinite(value)
        for value in (rect.x(), rect.y(), rect.width(), rect.height())
    )


def _rect_tuple_is_finite_nonnegative(
    rect: tuple[float, float, float, float],
) -> bool:
    """Return whether serialized geometry has finite coordinates and dimensions."""

    _, _, width, height = rect
    return (
        all(math.isfinite(value) for value in rect) and width >= 0.0 and height >= 0.0
    )


def _transient_dirty_rect_within_viewport_envelope(
    rect: tuple[float, float, float, float],
    viewport_rect: tuple[int, int, int, int],
) -> bool:
    """Return whether a transient dirty rect is not wider or taller than its viewport."""

    _, _, rect_width, rect_height = rect
    _, _, viewport_width, viewport_height = viewport_rect
    return (
        rect_width <= max(0, viewport_width) + 64.0
        and rect_height <= max(0, viewport_height) + 64.0
    )


def _document_rect_within_layout_envelope(
    rect: tuple[float, float, float, float],
    *,
    content_width: float,
    content_height: float,
) -> bool:
    """Return whether a document-local rect fits the known layout content envelope."""

    x, y, width, height = rect
    return (
        x >= -64.0
        and y >= -64.0
        and x + width <= max(0.0, content_width) + 64.0
        and y + height <= max(0.0, content_height) + 64.0
    )


def _expected_ghost_suffix(
    editor: PromptEditor,
    autocomplete_preview: object | None,
) -> str:
    """Return the diagnostic autocomplete preview suffix when available."""

    preview_suffix = _autocomplete_preview_suffix(autocomplete_preview)
    if preview_suffix:
        return preview_suffix
    autocomplete = getattr(editor, "_autocomplete", None)
    session = getattr(autocomplete, "_session_controller", None)
    current = getattr(session, "current_suggestion", None)
    if callable(current):
        suggestion = current()
        tag = getattr(suggestion, "tag", "")
        source = editor.toPlainText()
        if isinstance(tag, str) and tag.startswith(source):
            return tag[len(source) :]
    preview = getattr(editor, "_autocomplete_preview_state", None)
    suffix = getattr(preview, "suffix", "")
    return suffix if isinstance(suffix, str) else ""


def _rect_tuple(rect: QRect) -> tuple[int, int, int, int]:
    """Serialize one QRect."""

    return rect.x(), rect.y(), rect.width(), rect.height()


def _int_rect_tuple_has_area(rect: tuple[int, int, int, int]) -> bool:
    """Return whether one serialized integer rect has positive area."""

    return rect[2] > 0 and rect[3] > 0


def _popup_rect_is_anchored_to_viewport(
    *,
    popup_rect: tuple[int, int, int, int],
    viewport_rect: tuple[int, int, int, int],
) -> bool:
    """Return whether a popup remains plausibly anchored to its editor viewport."""

    popup_x, popup_y, popup_width, popup_height = popup_rect
    viewport_x, viewport_y, viewport_width, viewport_height = viewport_rect
    horizontal_padding = 64
    vertical_padding = 512
    popup_right = popup_x + popup_width
    viewport_right = viewport_x + viewport_width
    return (
        popup_right >= viewport_x - horizontal_padding
        and popup_x <= viewport_right + horizontal_padding
        and popup_y >= viewport_y - vertical_padding
        and popup_y <= viewport_y + viewport_height + vertical_padding
        and popup_height <= max(viewport_height, 1) + vertical_padding
    )


def _global_rect_tuple(widget: QWidget | None) -> tuple[int, int, int, int] | None:
    """Serialize one widget geometry in global coordinates."""

    if widget is None:
        return None
    top_left = widget.mapToGlobal(QPoint(0, 0))
    return top_left.x(), top_left.y(), widget.width(), widget.height()


def _object_path(widget: QWidget | None) -> str:
    """Return a stable enough diagnostic path for a Qt widget."""

    if widget is None:
        return "<none>"
    names: list[str] = []
    current: QWidget | None = widget
    while current is not None:
        object_name = current.objectName()
        label = (
            type(current).__name__
            if not object_name
            else f"{type(current).__name__}#{object_name}"
        )
        names.append(label)
        current = current.parentWidget()
    return " <- ".join(names)


def _inserted_text(before: str, after: str) -> str:
    """Return inserted source text for simple before/after diagnostics."""

    if after.startswith(before):
        return after[len(before) :]
    insert_position = _single_insert_position(before, after)
    if insert_position is not None:
        inserted_length = len(after) - len(before)
        return after[insert_position : insert_position + inserted_length]
    return ""


def _single_insert_position(before: str, after: str) -> int | None:
    """Return the insertion offset when ``after`` is ``before`` plus text."""

    if len(after) <= len(before):
        return None
    prefix_length = 0
    max_prefix = min(len(before), len(after))
    while prefix_length < max_prefix and before[prefix_length] == after[prefix_length]:
        prefix_length += 1
    suffix_length = 0
    max_suffix = len(before) - prefix_length
    while (
        suffix_length < max_suffix
        and before[len(before) - 1 - suffix_length]
        == after[len(after) - 1 - suffix_length]
    ):
        suffix_length += 1
    inserted_length = len(after) - len(before)
    if prefix_length + suffix_length != len(before):
        return None
    if inserted_length <= 0:
        return None
    return prefix_length


def _enum_value(value: object) -> int:
    """Return the integer payload for Qt enum and flag values."""

    raw_value = getattr(value, "value", value)
    if isinstance(raw_value, int):
        return raw_value
    return int(cast(Any, raw_value))


def _snapshot_json(snapshot: PromptEditorStateSnapshot) -> dict[str, object]:
    """Serialize snapshot diagnostics without embedding image payloads."""

    return {
        "label": snapshot.label,
        "source_text": snapshot.source_text,
        "selected_text": snapshot.selected_text,
        "selected_source_text": snapshot.selected_source_text,
        "selection_range": snapshot.selection_range,
        "selection_rects": snapshot.selection_rects,
        "cursor_position": snapshot.cursor_position,
        "display_mode": snapshot.display_mode,
        "focus_widget_path": snapshot.focus_widget_path,
        "active_window_path": snapshot.active_window_path,
        "target_event_widget_path": snapshot.target_event_widget_path,
        "geometries": dict(snapshot.geometries),
        "global_geometries": dict(snapshot.global_geometries),
        "scroll_values": dict(snapshot.scroll_values),
        "device_pixel_ratio": snapshot.device_pixel_ratio,
        "autocomplete_gateway_calls": snapshot.autocomplete_gateway_calls,
        "popup_widget_exists": snapshot.popup_widget_exists,
        "popup_state_visible": snapshot.popup_state_visible,
        "popup_visual_visible": snapshot.popup_visual_visible,
        "popup_global_rect": snapshot.popup_global_rect,
        "ghost_visual_visible": snapshot.ghost_visual_visible,
        "expected_ghost_suffix": snapshot.expected_ghost_suffix,
        "autocomplete_preview_active": snapshot.autocomplete_preview_active,
        "autocomplete_preview_suffix": snapshot.autocomplete_preview_suffix,
        "autocomplete_preview_source_position": (
            snapshot.autocomplete_preview_source_position
        ),
        "autocomplete_session_lifecycle": snapshot.autocomplete_session_lifecycle,
        "autocomplete_session_mode": snapshot.autocomplete_session_mode,
        "autocomplete_session_selected_index": (
            snapshot.autocomplete_session_selected_index
        ),
        "autocomplete_session_prefix": snapshot.autocomplete_session_prefix,
        "autocomplete_session_word_start": snapshot.autocomplete_session_word_start,
        "autocomplete_session_word_end": snapshot.autocomplete_session_word_end,
        "autocomplete_session_active_tag_end": (
            snapshot.autocomplete_session_active_tag_end
        ),
        "autocomplete_session_suggestions": snapshot.autocomplete_session_suggestions,
        "autocomplete_has_active_session": snapshot.autocomplete_has_active_session,
        "autocomplete_presenter_panel_visible": (
            snapshot.autocomplete_presenter_panel_visible
        ),
        "autocomplete_presenter_panel_under_mouse": (
            snapshot.autocomplete_presenter_panel_under_mouse
        ),
        "autocomplete_source_revision": snapshot.autocomplete_source_revision,
        "autocomplete_snapshot_source_length": (
            snapshot.autocomplete_snapshot_source_length
        ),
        "autocomplete_snapshot_cursor_position": (
            snapshot.autocomplete_snapshot_cursor_position
        ),
        "source_revision": snapshot.source_revision,
        "editing_session_source_revision": snapshot.editing_session_source_revision,
        "editing_session_cursor_position": snapshot.editing_session_cursor_position,
        "editing_session_anchor_position": snapshot.editing_session_anchor_position,
        "document_view_source_text": snapshot.document_view_source_text,
        "projection_document_source_text": snapshot.projection_document_source_text,
        "active_projection_source_text": snapshot.active_projection_source_text,
        "layout_projection_source_text": snapshot.layout_projection_source_text,
        "projection_text": snapshot.projection_text,
        "active_projection_text": snapshot.active_projection_text,
        "layout_projection_text": snapshot.layout_projection_text,
        "layout_uses_projection_document": snapshot.layout_uses_projection_document,
        "layout_uses_active_projection_document": (
            snapshot.layout_uses_active_projection_document
        ),
        "paint_cache_key_present": snapshot.paint_cache_key_present,
        "paint_cache_source_revision": snapshot.paint_cache_source_revision,
        "paint_cache_projection_document_identity_matches_layout": (
            snapshot.paint_cache_projection_document_identity_matches_layout
        ),
        "paint_cache_layout_snapshot_identity_matches_layout": (
            snapshot.paint_cache_layout_snapshot_identity_matches_layout
        ),
        "paint_cache_ghosted_run_ids": snapshot.paint_cache_ghosted_run_ids,
        "autocomplete_ghost_paint_visible_by_owner_state": (
            snapshot.autocomplete_ghost_paint_visible_by_owner_state
        ),
        "projection_freshness": snapshot.projection_freshness,
        "projection_has_pending_update": snapshot.projection_has_pending_update,
        "projection_has_stale_geometry": snapshot.projection_has_stale_geometry,
        "caret_state_source_position": snapshot.caret_state_source_position,
        "anchor_state_source_position": snapshot.anchor_state_source_position,
        "caret_map_source_length": snapshot.caret_map_source_length,
        "caret_map_stop_count": snapshot.caret_map_stop_count,
        "caret_preferred_x": snapshot.caret_preferred_x,
        "caret_rect_override": snapshot.caret_rect_override,
        "skip_next_same_source_soft_wrap_move": (
            snapshot.skip_next_same_source_soft_wrap_move
        ),
        "projection_token_count": snapshot.projection_token_count,
        "projection_run_count": snapshot.projection_run_count,
        "layout_line_count": snapshot.layout_line_count,
        "layout_text_fragment_count": snapshot.layout_text_fragment_count,
        "layout_inline_object_fragment_count": (
            snapshot.layout_inline_object_fragment_count
        ),
        "layout_content_width": snapshot.layout_content_width,
        "layout_content_height": snapshot.layout_content_height,
        "layout_text_width": snapshot.layout_text_width,
        "visible_layout_rows": [
            {
                "row_index": row.row_index,
                "source_start": row.source_start,
                "source_end": row.source_end,
                "document_top": row.document_top,
                "viewport_top": row.viewport_top,
                "height": row.height,
                "text": row.text,
            }
            for row in snapshot.visible_layout_rows
        ],
        "visible_text_fragments": [
            {
                "fragment_index": fragment.fragment_index,
                "source_start": fragment.source_start,
                "source_end": fragment.source_end,
                "document_rect": fragment.document_rect,
                "viewport_rect": fragment.viewport_rect,
                "document_baseline": fragment.document_baseline,
                "viewport_baseline": fragment.viewport_baseline,
                "text": fragment.text,
            }
            for fragment in snapshot.visible_text_fragments
        ],
        "caret_token_id": snapshot.caret_token_id,
        "anchor_token_id": snapshot.anchor_token_id,
        "caret_token_id_resolves": snapshot.caret_token_id_resolves,
        "anchor_token_id_resolves": snapshot.anchor_token_id_resolves,
        "caret_rect": snapshot.caret_rect,
        "viewport_rect": snapshot.viewport_rect,
        "caret_rect_finite": snapshot.caret_rect_finite,
        "caret_rect_has_area": snapshot.caret_rect_has_area,
        "caret_rect_intersects_viewport": snapshot.caret_rect_intersects_viewport,
        "vertical_scroll_minimum": snapshot.vertical_scroll_minimum,
        "vertical_scroll_maximum": snapshot.vertical_scroll_maximum,
        "vertical_scroll_page_step": snapshot.vertical_scroll_page_step,
        "horizontal_scroll_minimum": snapshot.horizontal_scroll_minimum,
        "horizontal_scroll_maximum": snapshot.horizontal_scroll_maximum,
        "horizontal_scroll_page_step": snapshot.horizontal_scroll_page_step,
        "transient_caret_geometry_present": snapshot.transient_caret_geometry_present,
        "transient_caret_geometry_valid": snapshot.transient_caret_geometry_valid,
        "transient_insertion_overlay_present": (
            snapshot.transient_insertion_overlay_present
        ),
        "transient_insertion_overlay_valid": (
            snapshot.transient_insertion_overlay_valid
        ),
        "transient_insertion_overlay_source_range": (
            snapshot.transient_insertion_overlay_source_range
        ),
        "transient_insertion_overlay_viewport_rect": (
            snapshot.transient_insertion_overlay_viewport_rect
        ),
        "transient_insertion_overlay_repaint_rect": (
            snapshot.transient_insertion_overlay_repaint_rect
        ),
        "transient_deletion_overlay_present": (
            snapshot.transient_deletion_overlay_present
        ),
        "transient_deletion_overlay_valid": snapshot.transient_deletion_overlay_valid,
        "transient_deletion_overlay_source_range": (
            snapshot.transient_deletion_overlay_source_range
        ),
        "transient_deletion_overlay_viewport_rects": (
            snapshot.transient_deletion_overlay_viewport_rects
        ),
        "transient_deletion_overlay_erase_rects": (
            snapshot.transient_deletion_overlay_erase_rects
        ),
        "transient_deletion_overlay_repaint_rect": (
            snapshot.transient_deletion_overlay_repaint_rect
        ),
        "undo_available": snapshot.undo_available,
        "redo_available": snapshot.redo_available,
        "undo_depth": snapshot.undo_depth,
        "redo_depth": snapshot.redo_depth,
        "undo_max_depth": snapshot.undo_max_depth,
        "redo_max_depth": snapshot.redo_max_depth,
        "undo_edit_block_depth": snapshot.undo_edit_block_depth,
        "undo_pending_state_present": snapshot.undo_pending_state_present,
        "undo_typing_group_active": snapshot.undo_typing_group_active,
        "undo_typing_group_last_cursor_position": (
            snapshot.undo_typing_group_last_cursor_position
        ),
        "undo_delete_group_active": snapshot.undo_delete_group_active,
        "undo_delete_group_key": snapshot.undo_delete_group_key,
        "observed_event_start_index": snapshot.observed_event_start_index,
        "observed_event_end_index": snapshot.observed_event_end_index,
        "recent_observed_events": [
            {
                "index": event.index,
                "owner": event.owner,
                "method": event.method,
                "source_before": event.source_before,
                "source_after": event.source_after,
                "cursor_before": event.cursor_before,
                "cursor_after": event.cursor_after,
                "preview_before": event.preview_before,
                "preview_after": event.preview_after,
                "session_before": event.session_before,
                "session_after": event.session_after,
                "panel_before": event.panel_before,
                "panel_after": event.panel_after,
                "result": event.result,
            }
            for event in snapshot.recent_observed_events
        ],
    }


def _write_snapshot_json(path: Path, snapshot: PromptEditorStateSnapshot) -> None:
    """Write one snapshot diagnostic JSON file."""

    path.write_text(
        json.dumps(_snapshot_json(snapshot), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_metadata_json(
    path: Path,
    shell: _HarnessShell,
    snapshot: PromptEditorStateSnapshot,
) -> None:
    """Write environment and shell metadata for replay diagnostics."""

    screen = QGuiApplication.primaryScreen()
    metadata = {
        "python": sys.version,
        "qt_version": QtCore.qVersion(),
        "qt_platform": QGuiApplication.platformName(),
        "os": platform.platform(),
        "screen_device_pixel_ratio": None
        if screen is None
        else screen.devicePixelRatio(),
        "shell_size": snapshot.geometries.get("shell"),
        "editor_panel_size": snapshot.geometries.get("panel"),
        "editor_viewport_size": snapshot.geometries.get("viewport"),
        "active_workflow_id": shell.workflow_session_service.active_workflow_id,
        "autocomplete_fixtures": _default_autocomplete_fixture_json(),
    }
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def _write_trace_json(path: Path, trace: PromptEditorTrace) -> None:
    """Write one replay trace JSON file."""

    payload = {
        "seed": trace.seed,
        "actions": [
            {
                "kind": action.kind,
                "value": action.value,
                "key": action.key,
                "modifiers": action.modifiers,
            }
            for action in trace.actions
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _group_abuse_findings(
    findings: Sequence[PromptEditorAbuseFinding],
) -> dict[str, tuple[str, ...]]:
    """Group abuse failures by visible symptom, then owner hypothesis."""

    grouped: dict[str, set[str]] = {}
    for finding in findings:
        grouped.setdefault(finding.symptom, set()).add(finding.owner_hypothesis)
    return {
        symptom: tuple(sorted(owner_hypotheses))
        for symptom, owner_hypotheses in sorted(grouped.items())
    }


def _owner_hypothesis_for_violation(violation: str) -> str:
    """Map one invariant failure to the first likely production owner."""

    if "tab" in violation or "control_character" in violation:
        return "prompt editor keymap/interactions"
    if "autocomplete" in violation or "session" in violation or "popup" in violation:
        return "autocomplete lifecycle/session owner"
    if "caret" in violation or "cursor" in violation:
        return "projection source-to-visual caret-map owner"
    if "geometry_shift" in violation:
        return "prompt editor sizing owner"
    if "visible_row_shift" in violation or "visible_fragment_shift" in violation:
        return "projection layout, paint cache, or editor sizing owner"
    if "projection" in violation or "document_view" in violation:
        return "projection source/change and repaint owner"
    if "selection" in violation:
        return "prompt editor selection owner"
    return "prompt editor event route/focus target"


def _safe_artifact_name(value: str) -> str:
    """Return a Windows-safe artifact path component."""

    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in value
    ).strip("-")


def _default_autocomplete_fixture_json() -> dict[str, list[str]]:
    """Return autocomplete fixture tags in JSON-friendly form."""

    return {
        prefix: [suggestion.tag for suggestion in suggestions]
        for prefix, suggestions in _default_autocomplete_results().items()
    }


def _has_disallowed_control_character(text: str) -> bool:
    """Return whether prompt source contains key-event control characters."""

    return any(ord(character) < 32 and character != "\n" for character in text)


__all__ = [
    "PromptEditorAbuseFinding",
    "PromptEditorAbuseReport",
    "PromptEditorContextMenuTrace",
    "PromptEditorKeyRoute",
    "PromptEditorTrace",
    "PromptEditorTraceAction",
    "PromptEditorStateSnapshot",
    "PromptEditorVisibleLayoutRow",
    "PromptEditorVisibleTextFragment",
    "PromptFieldHandle",
    "PromptWorkflowHandle",
    "RealShellPromptEditorHarness",
]
