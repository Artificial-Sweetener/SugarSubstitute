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

"""Run incremental editor cube inserts without full projection rebuilds."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from time import perf_counter

from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_timing,
)

from .incremental_insert_motion import (
    EditorIncrementalInsertMotion,
    PreparedIncrementalInsertMotion,
)
from .incremental_insert_ports import EditorIncrementalInsertPorts
from .projection_build_registry import CubeSectionBuildReuseDecision
from .projection_models import (
    EditorIncrementalInsertCompletionState,
    EditorIncrementalInsertPlan,
    EditorIncrementalInsertRequest,
)
from .projection_preparation import (
    EditorProjectionPreparation,
    cube_definition_identity,
)
from .projection_session_models import InsertCompletionPhase

_LOGGER = get_logger("presentation.editor.panel.incremental_insert_pipeline")


class EditorIncrementalInsertPipeline:
    """Own single-cube insert preparation, publication, and completion."""

    def __init__(self, ports: EditorIncrementalInsertPorts) -> None:
        """Store explicit collaborators needed by incremental insert orchestration."""

        self._ports = ports
        self._motion = EditorIncrementalInsertMotion(ports.motion)

    def insert_cube(self, request: EditorIncrementalInsertRequest) -> None:
        """Insert one cube widget without rebuilding existing cube sections."""

        ports = self._ports
        panel = ports.panel
        self._log_insert_started(request)
        active_projection_session = ports.projection_sessions.owns(
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
        )
        if active_projection_session is not None:
            ports.session_completions.attach_insert(
                session=active_projection_session,
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                completion_phase=request.completion_phase,
                on_complete=request.on_complete,
                reason="active_full_projection",
            )
            return
        preparation = ports.projection_preparation.prepare_projection(
            ((request.cube_alias, request.cube_state),),
            cube_states=request.cube_states,
            stack_order=request.stack_order,
            reason="cube_added",
            workflow_id=request.workflow_id,
            previous_cube_states=request.previous_cube_states,
            previous_stack_order=request.previous_stack_order,
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="editor_insert_prepared",
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            completion_phase=request.completion_phase,
            panel_stack_order=list(panel._stack_order or []),
            panel_cube_aliases=list(panel._cube_states or {}),
            behavior_transaction_started=preparation.behavior_transaction_started,
            behavior_snapshot_type=type(preparation.behavior_snapshot).__name__,
        )
        plan = self._prepare_incremental_insert_plan(request, preparation)
        self._repopulate_incremental_insert_layout(plan)
        state = EditorIncrementalInsertCompletionState()
        if plan.build_session is not None:
            ports.hidden_build_scheduler.schedule_cube_build_session(
                plan.build_session,
                on_first_usable=lambda: self._finish_insert_first_usable(plan, state),
                on_complete=lambda: self._finish_insert(plan, state),
                is_current=lambda: ports.build_registry.is_current(
                    request.cube_alias,
                    plan.build_token,
                ),
                on_cancel=lambda: self._cancel_incremental_insert(plan),
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_insert_build_session_scheduled",
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                completion_phase=request.completion_phase,
            )
            return
        self._finish_insert(plan, state)

    def _log_insert_started(self, request: EditorIncrementalInsertRequest) -> None:
        """Log the stable inputs for one incremental insert."""

        log_debug(
            _LOGGER,
            "Cube load detail",
            event="editor_insert_start",
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            completion_phase=request.completion_phase,
            incoming_stack_order=list(request.stack_order or []),
            incoming_cube_aliases=list(request.cube_states or {}),
            previous_stack_order=request.previous_stack_order or [],
            previous_cube_aliases=list(request.previous_cube_states or {}),
            existing_widget_aliases=list(self._ports.panel.cube_widgets),
        )

    def _prepare_incremental_insert_plan(
        self,
        request: EditorIncrementalInsertRequest,
        preparation: EditorProjectionPreparation,
    ) -> EditorIncrementalInsertPlan:
        """Prepare the widget, build token, and registry state for an insert."""

        ports = self._ports
        panel = ports.panel
        built_new_widget = False
        build_session: object | None = None
        cube_widget = panel.cube_widgets.get(request.cube_alias)
        reuse_decision: CubeSectionBuildReuseDecision | None = None
        if cube_widget is not None:
            reuse_decision = ports.build_registry.reuse_decision(
                request.cube_alias,
                cube_widget,
                cube_definition_identity(request.cube_alias, request.cube_state),
            )
        can_reuse_existing_widget = (
            reuse_decision is not None and reuse_decision.can_reuse
        )
        log_info(
            _LOGGER,
            "Checked editor cube widget reuse after definition identity comparison",
            event="frontend_update_editor_reuse_decision",
            trace_id=f"cube-update:{request.workflow_id}:{request.cube_alias}",
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            incoming_cube_state_object_id=id(request.cube_state),
            incoming_cube_version=getattr(request.cube_state, "version", ""),
            existing_widget_present=cube_widget is not None,
            existing_widget_object_id=id(cube_widget) if cube_widget else "",
            build_registry_can_reuse=can_reuse_existing_widget,
            build_registry_record_present=(
                reuse_decision.record_present if reuse_decision is not None else False
            ),
            build_registry_record_state=(
                reuse_decision.record_state if reuse_decision is not None else None
            ),
        )
        replacing_existing_widget = (
            cube_widget is not None and not can_reuse_existing_widget
        )
        prepared_motion = self._motion.prepare(
            requested=request.motion_requested,
            cube_alias=request.cube_alias,
            creates_widget=cube_widget is None or replacing_existing_widget,
            replaces_widget=replacing_existing_widget,
        )
        if cube_widget is not None and not can_reuse_existing_widget:
            ports.projection_lifecycle.discard_cube_widget(
                request.cube_alias,
                reason="stale_incremental_insert",
            )
            cube_widget = None
        if cube_widget is None:
            build_session = panel._begin_build_cube_widget(
                request.cube_alias,
                request.cube_state,
            )
            cube_widget = getattr(build_session, "widget")
            build_token = ports.build_registry.start(
                alias=request.cube_alias,
                widget=cube_widget,
                session=build_session,
                snapshot_identity=preparation.snapshot_identity,
                definition_identity=cube_definition_identity(
                    request.cube_alias,
                    request.cube_state,
                ),
            )
            ports.projection_completions.register_pending_insert(
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                token=build_token,
                completion_phase=request.completion_phase,
                on_complete=request.on_complete,
            )
            panel.cube_widgets[request.cube_alias] = cube_widget
            panel.cube_sections[request.cube_alias] = cube_widget
            built_new_widget = True
            if replacing_existing_widget:
                ports.render_reconciler.set_cube_widget_update_wash(
                    cube_widget,
                    visible=True,
                )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_insert_build_session_started",
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                widget_type=type(cube_widget).__name__,
                deferred_node_count=getattr(build_session, "deferred_node_count", None),
                first_usable_reached=getattr(
                    build_session,
                    "first_usable_reached",
                    None,
                ),
            )
        else:
            build_token = object()
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_insert_reused_existing_widget",
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                widget_type=type(cube_widget).__name__,
            )
        return EditorIncrementalInsertPlan(
            request=request,
            preparation=preparation,
            cube_widget=cube_widget,
            build_token=build_token,
            build_session=build_session,
            built_new_widget=built_new_widget,
            motion_generation=prepared_motion.generation,
            motion_target=prepared_motion.target,
        )

    def _repopulate_incremental_insert_layout(
        self,
        plan: EditorIncrementalInsertPlan,
    ) -> None:
        """Attach the inserted cube widget in current stack order."""

        ports = self._ports
        panel = ports.panel
        ordered_widgets = [
            (alias, panel.cube_widgets[alias])
            for alias in (panel._stack_order or [])
            if alias in panel.cube_widgets
        ]
        ports.render_reconciler.reconcile_ordered_widgets(ordered_widgets)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="editor_insert_layout_repopulated",
            workflow_id=plan.request.workflow_id,
            cube_alias=plan.request.cube_alias,
            ordered_widget_aliases=[alias for alias, _widget in ordered_widgets],
            panel_widget_aliases=list(panel.cube_widgets),
            panel_section_aliases=list(panel.cube_sections),
            built_new_widget=plan.built_new_widget,
        )

    def _report_insert_complete(
        self,
        plan: EditorIncrementalInsertPlan,
        state: EditorIncrementalInsertCompletionState,
        *,
        phase: InsertCompletionPhase,
    ) -> None:
        """Notify callers once at the configured insertion completion phase."""

        request = plan.request
        if state.insert_completion_reported:
            return
        if phase != request.completion_phase:
            return
        state.insert_completion_reported = True
        self._ports.projection_completions.forget_pending_insert(
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            token=plan.build_token,
            reason="incremental_insert_reported",
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="editor_insert_report_complete",
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            reported_phase=phase,
            configured_completion_phase=request.completion_phase,
            built_new_widget=plan.built_new_widget,
        )
        if request.on_complete is not None:
            request.on_complete()

    def _finish_insert_first_usable(
        self,
        plan: EditorIncrementalInsertPlan,
        state: EditorIncrementalInsertCompletionState,
    ) -> None:
        """Notify callers once first-interaction controls are available."""

        request = plan.request
        ports = self._ports
        panel = ports.panel
        if state.first_usable_completed:
            return
        ports.render_reconciler.finalize_cube_widget_for_reveal(
            request.cube_alias,
            plan.cube_widget,
            reason="incremental_first_usable",
            workflow_id=request.workflow_id,
        )
        state.first_usable_completed = True
        ports.render_reconciler.set_cube_widget_update_wash(
            plan.cube_widget,
            visible=False,
        )
        state.motion_started = self._motion.present_cube(
            prepared=self._prepared_motion(plan),
            already_started=state.motion_started,
            cube_alias=request.cube_alias,
            cube_widget=plan.cube_widget,
        )
        log_timing(
            _LOGGER,
            "Inserted editor cube section reached first usable state",
            started_at=request.started_at,
            cube_alias=request.cube_alias,
            cube_section_count=len(panel._stack_order or []),
            built_new_widget=plan.built_new_widget,
            level="debug",
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="editor_insert_first_usable",
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            built_new_widget=plan.built_new_widget,
            completion_phase=request.completion_phase,
            panel_stack_order=list(panel._stack_order or []),
        )
        self._report_insert_complete(plan, state, phase="first_usable")

    def _finish_insert(
        self,
        plan: EditorIncrementalInsertPlan,
        state: EditorIncrementalInsertCompletionState,
    ) -> None:
        """Finish editor registries after any deferred card build completes."""

        request = plan.request
        ports = self._ports
        panel = ports.panel
        try:
            phase_started = perf_counter()
            panel.sync_prompt_editor_values_for_cube(request.cube_alias)
            panel.refresh_link_widgets_for_cube(request.cube_alias)
            log_timing(
                _LOGGER,
                "Refreshed editor cube-scoped widget registries after cube insert",
                started_at=phase_started,
                cube_alias=request.cube_alias,
                level="debug",
            )
            ports.projection_lifecycle.refresh_visibility(
                message=(
                    app_text(
                        "Failed to refresh editor visibility after incremental cube insert"
                    )
                ),
                reason="cube_added",
                use_cached_snapshot=True,
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_insert_visibility_refreshed",
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                built_new_widget=plan.built_new_widget,
                panel_stack_order=list(panel._stack_order or []),
            )
            self._finish_insert_first_usable(plan, state)
            ports.render_reconciler.finalize_cube_widget_for_reveal(
                request.cube_alias,
                plan.cube_widget,
                reason="incremental_complete",
                workflow_id=request.workflow_id,
            )
            state.motion_started = self._motion.present_node_cards(
                prepared=self._prepared_motion(plan),
                already_started=state.motion_started,
                cube_alias=request.cube_alias,
            )
            if plan.build_session is not None:
                ports.build_registry.mark_complete(
                    request.cube_alias,
                    plan.build_token,
                )
            log_timing(
                _LOGGER,
                "Inserted editor cube section incrementally",
                started_at=request.started_at,
                cube_alias=request.cube_alias,
                cube_section_count=len(panel._stack_order or []),
                built_new_widget=plan.built_new_widget,
                existing_widget_count=len(panel.cube_widgets),
                level="debug",
            )
            self._report_insert_complete(plan, state, phase="complete")
        finally:
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_insert_finish",
                workflow_id=request.workflow_id,
                cube_alias=request.cube_alias,
                built_new_widget=plan.built_new_widget,
                completion_phase=request.completion_phase,
                panel_widget_aliases=list(panel.cube_widgets),
                panel_section_aliases=list(panel.cube_sections),
            )
            ports.projection_preparation.end_behavior_transaction(
                plan.preparation,
                reason="cube_added",
            )

    def _cancel_incremental_insert(self, plan: EditorIncrementalInsertPlan) -> None:
        """Cancel one alias build session when its token is superseded."""

        request = plan.request
        self._motion.cancel()
        self._ports.build_registry.cancel(
            request.cube_alias,
            plan.build_token,
            "superseded_incremental_insert",
        )
        self._ports.projection_completions.cancel_pending_insert(
            workflow_id=request.workflow_id,
            cube_alias=request.cube_alias,
            token=plan.build_token,
            reason="superseded_incremental_insert",
            cancel_superseded=False,
        )
        self._ports.projection_preparation.end_behavior_transaction(
            plan.preparation,
            reason="cube_added",
        )
        self._ports.render_reconciler.set_cube_widget_update_wash(
            plan.cube_widget,
            visible=False,
        )

    @staticmethod
    def _prepared_motion(
        plan: EditorIncrementalInsertPlan,
    ) -> PreparedIncrementalInsertMotion:
        """Restore the immutable motion request carried by an insert plan."""

        return PreparedIncrementalInsertMotion(
            generation=plan.motion_generation,
            target=plan.motion_target,
        )
