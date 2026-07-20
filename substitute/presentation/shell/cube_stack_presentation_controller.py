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

"""Own cube-stack preference, document availability, chrome, and transitions."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    app_text,
    set_localized_accessible_name,
    set_localized_accessible_description,
    set_localized_tooltip,
)

from collections.abc import Callable, Iterable
from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QStackedWidget

from substitute.domain.workflow import WorkflowDocumentKind
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.app_orb_action_cluster import (
    AppOrbCubeStackButton,
)
from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPreference,
    CubeStackPresentationFrame,
    CubeStackPresentationInput,
    CubeStackPresentationMode,
    resolve_cube_stack_presentation_mode,
    target_frame_for_mode,
)
from substitute.presentation.shell.cube_stack_presentation_transition import (
    CubeStackPresentationTransition,
)
from substitute.presentation.shell.workspace_splitter_controller import (
    WorkspaceSplitterController,
)
from substitute.presentation.workflows.cube_stack_view import CubeStack
from substitute.shared.logging.logger import get_logger, log_debug

_UNAVAILABLE_LABEL: ApplicationMessage = app_text(
    "Cube stack unavailable for Comfy workflows"
)
_EXPAND_LABEL: ApplicationMessage = app_text("Expand cube stack")
_COLLAPSE_LABEL: ApplicationMessage = app_text("Collapse cube stack")
_LOGGER = get_logger("presentation.shell.cube_stack_presentation_controller")


class CubeStackMaterialSurface(Protocol):
    """Describe material mutations owned by cube-stack presentation."""

    def set_cube_stack_region_widget(self, widget: QStackedWidget | None) -> None:
        """Set the live region excluded from the workspace material wash."""

    def set_cube_stack_wash_opacity(self, opacity: float) -> None:
        """Set the material wash opacity over the cube-stack region."""


class CubeStackEditorSurface(Protocol):
    """Describe editor geometry driven by cube-stack availability progress."""

    def set_cube_stack_unavailable_progress(self, progress: float) -> None:
        """Apply interpolated direct-Comfy content spacing."""


class CubeStackExpansionLease:
    """Hold one cancellable request for temporary expanded presentation."""

    def __init__(
        self,
        *,
        release: Callable[[int], None],
        token: int,
    ) -> None:
        """Store the controller release port and unique lease identity."""

        self._release = release
        self._token = token
        self._active = True

    @property
    def active(self) -> bool:
        """Return whether this lease still influences presentation policy."""

        return self._active

    def release(self) -> None:
        """Release this lease exactly once."""

        if not self._active:
            return
        self._active = False
        self._release(self._token)

    def _cancel(self) -> None:
        """Mark this lease inactive after an explicit presentation override."""

        self._active = False

    def __enter__(self) -> CubeStackExpansionLease:
        """Return this lease for scoped use."""

        return self

    def __exit__(self, *_error: object) -> None:
        """Release the temporary expansion when a scope exits."""

        self.release()


class CubeStackPresentationController(QObject):
    """Provide one authoritative presentation path for cube and direct documents."""

    def __init__(
        self,
        *,
        container: QStackedWidget,
        stacks: Callable[[], Iterable[CubeStack]],
        mode_button: AppOrbCubeStackButton,
        material_surface: CubeStackMaterialSurface,
        active_editor_surface: Callable[[], CubeStackEditorSurface | None],
        splitter_controller: WorkspaceSplitterController,
        position_search_box: Callable[[], None],
        request_autosave: Callable[[], None],
        duration_resolver: Callable[[int], int] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Store narrow widget ports and initialize expanded cube presentation."""

        super().__init__(parent)
        self._container = container
        self._stacks = stacks
        self._mode_button = mode_button
        self._material_surface = material_surface
        self._active_editor_surface = active_editor_surface
        self._splitter_controller = splitter_controller
        self._position_search_box = position_search_box
        self._request_autosave = request_autosave
        self._preference = CubeStackPreference.EXPANDED
        self._document_kind = WorkflowDocumentKind.CUBE_STACK
        self._workflow_route_active = True
        self._mode = CubeStackPresentationMode.EXPANDED
        self._rendered_frame = target_frame_for_mode(
            self._mode,
            hidden_item_preference=self._preference,
        )
        self._lease_generation = 0
        self._active_leases: dict[int, CubeStackExpansionLease] = {}
        self._completion_callbacks: dict[int, Callable[[], None]] = {}
        transition_kwargs: dict[str, object] = {}
        if duration_resolver is not None:
            transition_kwargs["duration_resolver"] = duration_resolver
        self._transition = CubeStackPresentationTransition(
            read_frame=self.current_frame,
            apply_frame=self._apply_frame,
            parent=self,
            **transition_kwargs,  # type: ignore[arg-type]
        )
        self._transition.transitionFinished.connect(self._finish_transition)
        self._container.show()
        self._material_surface.set_cube_stack_region_widget(self._container)
        self._material_surface.set_cube_stack_wash_opacity(1.0)
        self._sync_chrome(self._mode)

    @property
    def preference(self) -> CubeStackPreference:
        """Return the durable cube-stack density preference."""

        return self._preference

    @property
    def mode(self) -> CubeStackPresentationMode:
        """Return the most recently requested derived presentation mode."""

        return self._mode

    @property
    def document_kind(self) -> WorkflowDocumentKind:
        """Return the active workflow's mutually exclusive document kind."""

        return self._document_kind

    @property
    def is_animating(self) -> bool:
        """Return whether a geometry transition is active."""

        return self._transition.is_animating

    @property
    def active_generation(self) -> int:
        """Return the identity of the latest presentation request."""

        return self._transition.active_generation

    @property
    def preferred_stack_width(self) -> int:
        """Return the visible width associated with the durable preference."""

        return target_frame_for_mode(
            CubeStackPresentationMode(self._preference.value),
            hidden_item_preference=self._preference,
        ).container_width

    def current_frame(self) -> CubeStackPresentationFrame:
        """Return the authoritative frame last applied to all presentation surfaces."""

        return self._rendered_frame

    def activate_document_kind(
        self,
        document_kind: WorkflowDocumentKind,
        *,
        animated: bool,
        on_complete: Callable[[], None] | None = None,
    ) -> int:
        """Derive and present availability for the newly active workflow document."""

        self._document_kind = document_kind
        return self._request_derived_mode(
            animated=animated,
            on_complete=on_complete,
            persist=False,
        )

    def request_preference(
        self,
        compact: bool,
        *,
        animated: bool = True,
        on_complete: Callable[[], None] | None = None,
    ) -> int:
        """Change durable cube presentation without overriding document availability."""

        self._cancel_expansion_leases()
        self._preference = (
            CubeStackPreference.COMPACT if compact else CubeStackPreference.EXPANDED
        )
        return self._request_derived_mode(
            animated=animated,
            on_complete=on_complete,
            persist=True,
        )

    def set_workflow_route_active(self, active: bool) -> None:
        """Publish route visibility without overriding document availability."""

        self._workflow_route_active = bool(active)
        if not active:
            self._material_surface.set_cube_stack_region_widget(None)
        elif self._mode is not CubeStackPresentationMode.UNAVAILABLE:
            self._material_surface.set_cube_stack_region_widget(self._container)
        self._sync_chrome(self._mode)

    def restore_preference(self, compact: bool) -> int:
        """Apply persisted preference immediately during startup or restore."""

        self._preference = (
            CubeStackPreference.COMPACT if compact else CubeStackPreference.EXPANDED
        )
        return self._request_derived_mode(animated=False, persist=False)

    def prepare_stack(self, stack: CubeStack) -> None:
        """Initialize a newly materialized cube stack from durable preference."""

        stack.setCompact(self._target_compact(self._mode))

    def acquire_expansion(
        self,
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> CubeStackExpansionLease:
        """Temporarily expand cube documents and return a cancellable lease."""

        self._lease_generation += 1
        token = self._lease_generation
        lease = CubeStackExpansionLease(release=self._release_lease, token=token)
        self._active_leases[token] = lease
        self._request_derived_mode(
            animated=True,
            on_complete=on_expanded,
            persist=False,
        )
        return lease

    def normalize_current_splitter_geometry(self) -> tuple[int, ...]:
        """Persist user sizing in the durable cube-preference coordinate space."""

        return self._splitter_controller.remember_user_geometry(
            effective_stack_width=self._rendered_frame.container_width,
            preferred_stack_width=self.preferred_stack_width,
        )

    def splitter_sizes_for_snapshot(self) -> tuple[int, ...]:
        """Return canonical sizes without persisting an animation frame."""

        return self._splitter_controller.sizes_for_snapshot(
            effective_stack_width=self._rendered_frame.container_width,
            preferred_stack_width=self.preferred_stack_width,
        )

    def stop(self) -> None:
        """Stop an in-flight transition during shell disposal."""

        self._transition.stop()
        self._completion_callbacks.clear()

    def _release_lease(self, token: int) -> None:
        """Remove one lease and restore the derived durable mode when last released."""

        if token not in self._active_leases:
            return
        self._active_leases.pop(token)
        self._request_derived_mode(animated=True, persist=False)

    def _cancel_expansion_leases(self) -> None:
        """Cancel temporary expansion before applying explicit user preference."""

        leases = tuple(self._active_leases.values())
        self._active_leases.clear()
        for lease in leases:
            lease._cancel()

    def _request_derived_mode(
        self,
        *,
        animated: bool,
        persist: bool,
        on_complete: Callable[[], None] | None = None,
    ) -> int:
        """Retarget all cube-stack surfaces from current live geometry."""

        mode = resolve_cube_stack_presentation_mode(
            CubeStackPresentationInput(
                document_kind=self._document_kind,
                preference=self._preference,
                temporary_expansion_count=len(self._active_leases),
            )
        )
        target = target_frame_for_mode(
            mode,
            hidden_item_preference=self._preference,
        )
        self._mode = mode
        self._sync_chrome(mode)
        if mode is not CubeStackPresentationMode.UNAVAILABLE:
            self._container.show()
            self._material_surface.set_cube_stack_region_widget(self._container)
        self._begin_stack_transition()
        self._splitter_controller.begin_stack_width_transition(
            self._rendered_frame.container_width
        )
        generation = self._transition.transition_to(mode, target, animated=animated)
        self._completion_callbacks.clear()
        if on_complete is not None:
            if self._transition.is_animating:
                self._completion_callbacks[generation] = on_complete
            else:
                on_complete()
        if persist:
            self._request_autosave()
        log_debug(
            _LOGGER,
            "Cube-stack presentation requested",
            mode=mode.value,
            preference=self._preference.value,
            document_kind=self._document_kind.value,
            generation=generation,
            animated=animated,
        )
        return generation

    def _begin_stack_transition(self) -> None:
        """Prepare all cached cube stacks for the preference endpoint."""

        target_compact = self._target_compact(self._mode)
        for stack in self._stacks():
            stack.beginCompactTransition(target_compact)

    def _apply_frame(self, frame: CubeStackPresentationFrame) -> None:
        """Apply one typed frame to container, stacks, material, splitter, and overlay."""

        self._rendered_frame = frame
        self._container.setFixedWidth(frame.container_width)
        for stack in self._stacks():
            stack.applyCompactTransition(
                stack_width=frame.container_width,
                item_width=frame.item_width,
                compact_progress=frame.compact_progress,
            )
        self._material_surface.set_cube_stack_wash_opacity(
            1.0 - frame.material_progress
        )
        editor_surface = self._active_editor_surface()
        if editor_surface is not None:
            editor_surface.set_cube_stack_unavailable_progress(
                frame.editor_gutter_progress
            )
        self._splitter_controller.apply_stack_width_frame(frame.container_width)
        self._position_search_box()

    def _finish_transition(self, mode_value: object, generation: int) -> None:
        """Commit only the current request's endpoint and run its callback."""

        mode = CubeStackPresentationMode(str(mode_value))
        if generation != self._transition.active_generation or mode is not self._mode:
            return
        self._apply_endpoint_state(mode)
        callback = self._completion_callbacks.pop(generation, None)
        self._completion_callbacks.clear()
        if callback is not None:
            callback()

    def _apply_endpoint_state(self, mode: CubeStackPresentationMode) -> None:
        """Commit visibility and stable stack geometry after an exact endpoint."""

        compact = self._target_compact(mode)
        for stack in self._stacks():
            stack.finishCompactTransition(compact)
        if mode is CubeStackPresentationMode.UNAVAILABLE:
            self._container.hide()
            self._material_surface.set_cube_stack_region_widget(None)
        else:
            self._container.show()
            self._material_surface.set_cube_stack_region_widget(self._container)
        self._splitter_controller.finish_stack_width_transition()
        self._sync_chrome(mode)
        self._position_search_box()

    def _sync_chrome(self, mode: CubeStackPresentationMode) -> None:
        """Synchronize checked, enabled, icon, tooltip, and accessible button state."""

        unavailable = mode is CubeStackPresentationMode.UNAVAILABLE
        compact = (
            self._preference is CubeStackPreference.COMPACT
            if unavailable
            else mode is CubeStackPresentationMode.COMPACT
        )
        blocked = self._mode_button.blockSignals(True)
        try:
            self._mode_button.setChecked(compact)
        finally:
            self._mode_button.blockSignals(blocked)
        self._mode_button.setEnabled(self._workflow_route_active and not unavailable)
        if unavailable:
            label = _UNAVAILABLE_LABEL
            set_localized_tooltip(self._mode_button, label)
            set_localized_accessible_name(self._mode_button, label)
            set_localized_accessible_description(
                self._mode_button, "Direct Comfy workflows contain no cube stack."
            )
            return
        label = _EXPAND_LABEL if compact else _COLLAPSE_LABEL
        icon = (
            AppIcon.PANEL_LEFT_20_REGULAR if compact else AppIcon.PANEL_LEFT_20_FILLED
        )
        self._mode_button.setIcon(icon)
        set_localized_tooltip(self._mode_button, label)
        set_localized_accessible_name(self._mode_button, label)
        set_localized_accessible_description(
            self._mode_button, "Toggle between expanded and compact cube cards."
        )

    def _target_compact(self, mode: CubeStackPresentationMode) -> bool:
        """Return stable card density for one visible or hidden endpoint."""

        if mode is CubeStackPresentationMode.COMPACT:
            return True
        if mode is CubeStackPresentationMode.EXPANDED:
            return False
        return self._preference is CubeStackPreference.COMPACT


__all__ = [
    "CubeStackEditorSurface",
    "CubeStackExpansionLease",
    "CubeStackMaterialSurface",
    "CubeStackPresentationController",
]
