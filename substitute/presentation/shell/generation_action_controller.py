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

"""Project generation progress and titlebar action state for the shell."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Mapping
from typing import Any
from typing import cast

from substitute.application.generation import (
    GenerationQueueJob,
    GenerationQueueStateChange,
)
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import ProgressUpdate
from substitute.presentation.generation.queue_counts import (
    pending_generation_queue_job_count,
)
from substitute.presentation.shell.generation_action_projection import (
    project_generation_actions,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionState,
    GenerationSelectedMode,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.progress_projection import (
    ProgressProjectionMode,
    set_progress_bar_value,
)
from substitute.presentation.shell.progress_overlay_controller import (
    progress_overlay_controller_for,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info

_LOGGER = get_logger("presentation.shell.generation_action_controller")


class GenerationActionController:
    """Own generation progress and action projection for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose generation surfaces should be projected."""

        self._shell = shell

    def update_progress_labels(
        self,
        workflow_pct: float,
        sampler_pct: float | None,
    ) -> None:
        """Apply active progress percentages to overlay bars and taskbar progress."""

        progress_view = self._shell.progress_service.build_view_state(
            active=True,
            workflow_percent=workflow_pct,
            sampler_percent=sampler_pct,
        )
        self.apply_generation_progress_state(progress_view)

    def apply_generation_progress_state(
        self,
        progress_view: ProgressViewState,
        *,
        mode: ProgressProjectionMode = ProgressProjectionMode.LIVE_UPDATE,
    ) -> None:
        """Apply projected progress state to every shell progress surface."""

        progress_workflow_id = progress_view.workflow_id
        if progress_workflow_id:
            workflow_session_service = getattr(
                self._shell,
                "workflow_session_service",
                None,
            )
            active_workflow_id = getattr(
                workflow_session_service,
                "active_workflow_id",
                None,
            )
            if active_workflow_id is not None and progress_workflow_id != str(
                active_workflow_id
            ):
                self.project_active_workflow_progress()
                return

        progress_view_state = (
            progress_view.active,
            progress_view.show_overlay,
            progress_view.workflow_value,
            progress_view.sampler_value,
            progress_view.workflow_id,
            progress_view.generation_run_id,
            progress_view.prompt_id,
        )
        progress_registry = getattr(
            self._shell,
            "generation_progress_strip_registry",
            None,
        )
        apply_progress_view = getattr(progress_registry, "apply_progress_view", None)
        if callable(apply_progress_view):
            apply_progress_view(progress_view, mode=mode)
        if getattr(self._shell, "_last_progress_view_state", None) == (
            progress_view_state
        ):
            return
        self._shell._last_progress_view_state = progress_view_state

        if progress_view.show_overlay:
            self._position_progress_overlay()
            self._shell.progressOverlay.show()
        else:
            self._shell.progressOverlay.hide()

        set_progress_bar_value(
            self._shell.workflowOverlayBar,
            progress_view.workflow_value,
            mode=mode,
        )
        set_progress_bar_value(
            self._shell.samplerOverlayBar,
            progress_view.sampler_value,
            mode=mode,
        )
        if progress_view.show_overlay:
            self._shell._taskbar_progress_presenter.set_progress(
                progress_view.workflow_value
            )
        else:
            self._shell._taskbar_progress_presenter.clear_progress()
        log_debug(
            _LOGGER,
            "generation progress projected",
            workflow_id=progress_view.workflow_id,
            generation_run_id=progress_view.generation_run_id,
            prompt_id=progress_view.prompt_id,
            workflow_value=progress_view.workflow_value,
            sampler_value=progress_view.sampler_value,
            show_overlay=progress_view.show_overlay,
            mode=mode.value,
        )

    def _position_progress_overlay(self) -> None:
        """Ask the progress overlay owner to refresh progress geometry."""

        controller = getattr(self._shell, "progress_overlay_controller", None)
        position_progress_overlay = getattr(
            controller,
            "position_progress_overlay",
            None,
        )
        if callable(position_progress_overlay):
            position_progress_overlay()
            return
        progress_overlay_controller_for(self._shell).position_progress_overlay()

    def project_active_workflow_progress(self) -> None:
        """Project selected workflow progress onto shell progress surfaces."""

        workflow_session_service = getattr(
            self._shell,
            "workflow_session_service",
            None,
        )
        workflow_id = str(
            getattr(workflow_session_service, "active_workflow_id", "") or ""
        )
        workflow_progress_service = getattr(
            self._shell,
            "workflow_progress_service",
            None,
        )
        view_for_workflow = getattr(
            workflow_progress_service,
            "view_for_workflow",
            None,
        )
        if callable(view_for_workflow):
            progress_view = view_for_workflow(workflow_id)
        else:
            progress_view = ProgressViewState.hidden(workflow_id=workflow_id)
        self.apply_generation_progress_state(
            progress_view,
            mode=ProgressProjectionMode.SELECTION_REPLAY,
        )

    def clear_generation_progress(self) -> None:
        """Clear visible generation progress without synthesizing telemetry."""

        workflow_progress_service = getattr(
            self._shell,
            "workflow_progress_service",
            None,
        )
        clear_all = getattr(workflow_progress_service, "clear_all", None)
        if callable(clear_all):
            clear_all()
        self.apply_generation_progress_state(
            ProgressViewState.hidden(),
            mode=ProgressProjectionMode.CLEAR,
        )

    def apply_generation_progress(self, progress_update: ProgressUpdate) -> None:
        """Apply typed progress updates through existing progress presentation."""

        if (
            progress_update.sampler_percent is not None
            and progress_update.sampler_percent > 0
        ):
            generation_feedback_presenter_for(
                self._shell
            ).clear_model_field_progress_for_sampler_once()
        workflow_progress_service = getattr(
            self._shell,
            "workflow_progress_service",
            None,
        )
        apply_update = getattr(workflow_progress_service, "apply_update", None)
        progress_view = None
        if callable(apply_update):
            progress_view = apply_update(progress_update)
        workflow_session_service = getattr(
            self._shell,
            "workflow_session_service",
            None,
        )
        active_workflow_id = getattr(
            workflow_session_service,
            "active_workflow_id",
            None,
        )
        if (
            progress_update.workflow_id == active_workflow_id
            and progress_view is not None
        ):
            self.apply_generation_progress_state(
                progress_view,
                mode=ProgressProjectionMode.LIVE_UPDATE,
            )

    def set_generation_selected_mode(self, mode: str) -> None:
        """Set selected generation mode or refresh active-state visuals."""

        if mode == "generate":
            self._shell._current_generate_mode = "generate"
        elif mode == "continuous":
            self._shell._current_generate_mode = "continuous"
        else:
            raise ValueError(f"Unknown mode for generate button: {mode}")
        self.apply_generation_action_availability()

    def set_backend_state(self, state: str) -> None:
        """Apply the current Comfy backend availability state to shell actions."""

        if state not in {"starting", "ready", "unavailable"}:
            raise ValueError(f"Unknown backend state: {state}")
        previous_state = getattr(self._shell, "_backend_state", None)
        self._shell._backend_state = state
        if state == "ready":
            self._shell.workspace_generation_controller.set_backend_available(
                True,
                message=app_text("ComfyUI is ready."),
            )
        elif state == "starting":
            self._shell.workspace_generation_controller.set_backend_available(
                False,
                message=app_text("ComfyUI is still starting."),
            )
        else:
            self._shell.workspace_generation_controller.set_backend_available(
                False,
                message=app_text("ComfyUI is unavailable."),
            )
        log_info(
            _LOGGER,
            "generation backend state applied",
            backend_state=state,
        )
        state_signal = getattr(self._shell, "backend_state_changed", None)
        emit_state = getattr(state_signal, "emit", None)
        if previous_state != state and callable(emit_state):
            emit_state(state)
        self.apply_generation_action_availability()

    def handle_generation_queue_state_changed(
        self,
        event: GenerationQueueStateChange,
    ) -> None:
        """Refresh generation actions from the published queue state."""

        self.apply_generation_action_availability(queue_jobs=event.jobs)

    def apply_generation_action_availability(
        self,
        *,
        queue_jobs: tuple[GenerationQueueJob, ...] | None = None,
    ) -> None:
        """Project and apply shell generation action state."""

        if getattr(self._shell, "_detached_for_gui_reload", False):
            return
        registry = getattr(self._shell, "generation_titlebar_control_registry", None)
        apply_registry_presentation = getattr(
            registry,
            "apply_generation_presentation",
            None,
        )
        generation_action_cluster = getattr(
            self._shell,
            "generationActionCluster",
            None,
        )
        if (
            not callable(apply_registry_presentation)
            and generation_action_cluster is None
        ):
            return
        presentation = project_generation_actions(
            self.generation_action_state(queue_jobs=queue_jobs)
        )
        if callable(apply_registry_presentation):
            apply_registry_presentation(presentation)
        else:
            apply_cluster_presentation = getattr(
                generation_action_cluster,
                "apply_generation_presentation",
            )
            if callable(apply_cluster_presentation):
                apply_cluster_presentation(presentation)
        log_debug(
            _LOGGER,
            "generation action availability projected",
            backend_state=getattr(self._shell, "_backend_state", ""),
            selected_mode=getattr(self._shell, "_current_generate_mode", "generate"),
            play_enabled=presentation.play_enabled,
            skip_enabled=presentation.skip_enabled,
            stop_enabled=presentation.stop_enabled,
            queue_badge_count=presentation.queue_badge_count,
            queue_segment_visible=presentation.queue_segment_visible,
        )

    def generation_action_state(
        self,
        *,
        queue_jobs: tuple[GenerationQueueJob, ...] | None = None,
    ) -> GenerationActionState:
        """Collect shell state needed for generation action projection."""

        resolved_queue_jobs = (
            queue_jobs
            if queue_jobs is not None
            else self._shell.generation_job_queue_service.jobs()
        )
        selected_mode = cast(
            GenerationSelectedMode,
            getattr(self._shell, "_current_generate_mode", "generate"),
        )
        return GenerationActionState(
            selected_mode=selected_mode,
            continuous_active=(
                self._shell.workspace_generation_controller.is_continuous_active
            ),
            backend_ready=self._shell._backend_state == "ready",
            workflow_runnable=self.active_workflow_has_generation_source(),
            settings_route_active=(
                getattr(self._shell, "_active_workspace_route", None)
                == SETTINGS_WORKSPACE_ROUTE
            ),
            queue_has_active=self._shell.generation_job_queue_service.has_active_job(),
            queue_has_cancellable=(
                self._shell.generation_job_queue_service.has_cancellable_jobs()
            ),
            pending_queue_count=pending_generation_queue_job_count(resolved_queue_jobs),
            queue_has_visible_jobs=bool(resolved_queue_jobs),
            queue_panel_visible=(self._shell.generation_queue_controller.panel_visible),
        )

    def active_workflow_has_generation_source(self) -> bool:
        """Return whether the active workflow has one executable document source."""

        workflow_session_service = getattr(
            self._shell,
            "workflow_session_service",
            None,
        )
        workflow_id = getattr(workflow_session_service, "active_workflow_id", None)
        workflows = getattr(workflow_session_service, "workflows", None)
        if workflow_id is None or not isinstance(workflows, Mapping):
            return False
        workflow = workflows.get(workflow_id)
        if getattr(workflow, "direct_workflow", None) is not None:
            return True
        cubes = getattr(workflow, "cubes", None)
        return isinstance(cubes, Mapping) and bool(cubes)


def generation_action_controller_for(shell: Any) -> GenerationActionController:
    """Return the composed generation action controller for a shell."""

    controller = getattr(shell, "generation_action_controller", None)
    if isinstance(controller, GenerationActionController):
        return controller
    controller = GenerationActionController(shell)
    setattr(shell, "generation_action_controller", controller)
    return controller


__all__ = [
    "GenerationActionController",
    "generation_action_controller_for",
]
