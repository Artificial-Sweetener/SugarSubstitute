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

"""Apply a resolved Output projection plan to visible widget state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    consume_final_output_preview_retirement,
    output_revision_cache_binding,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    OutputCanvasInteractionController,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_grid_for_source,
    activate_output_scene_overview,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
    output_revision_cache,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
)
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresenter,
)
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    OutputCompareProjectionPresenter,
    _store_visible_output_compare_state,
)
from substitute.presentation.canvas.output.output_image_route_controller import (
    OutputImageRouteController,
)
from substitute.presentation.canvas.output.output_projection_presentation_plan import (
    OutputProjectionMode,
    resolve_output_projection_presentation,
)
from substitute.presentation.canvas.output.output_route_binding_controller import (
    OutputRouteBindingController,
)


@dataclass(frozen=True, slots=True)
class OutputProjectionChromeCallbacks:
    """Refresh navigation chrome after projection state changes."""

    sync_scene_selector: Callable[[], None]
    sync_set_selector: Callable[[], None]
    sync_source_selector: Callable[[], None]
    update_tabbar: Callable[[], None]


@dataclass(frozen=True, slots=True)
class OutputProjectionPresenter:
    """Own visible Output mutation and exactly-one-mode presentation."""

    view: Any
    route_binding: OutputRouteBindingController
    image_routes: OutputImageRouteController
    compare_route_presenter: OutputComparePresenter
    compare_projection_presenter: OutputCompareProjectionPresenter
    source_tabs: OutputCanvasSourceTabsController
    interaction: OutputCanvasInteractionController
    present_current_grid: Callable[[], bool]
    cancel_grid: Callable[[], None]
    chrome: OutputProjectionChromeCallbacks

    def present_session(
        self,
        session: OutputCanvasSession,
        *,
        retire_completed_preview_slot: Callable[[PreviewSlotKey, str, str], None],
    ) -> None:
        """Bind one session and present its single authorized visible mode."""

        view = self.view
        cache_binding = output_revision_cache_binding(
            output_preview_registry(view),
            session,
            current_cache_key=getattr(view, "_revision_cache_key", None),
        )
        if cache_binding is not None:
            view._revision_cache_key = cache_binding.cache_key
            view._revision_cache = cache_binding.cache
        view._output_session = session
        view._projection_workflow_id = session.workflow_id.value
        projection = session.projection
        view._output_projection = projection
        self.route_binding.bind_projection_session(session)
        view.scene_count = projection.scene_count
        plan = resolve_output_projection_presentation(
            projection,
            scene_groups=output_scene_groups_by_key(output_route_state_snapshot(view)),
        )
        _store_visible_output_compare_state(view, plan.compare_state)
        if plan.compare_state != projection.compare_state:
            signal = getattr(view, "activeOutputCompareChanged", None)
            emit = getattr(signal, "emit", None)
            if callable(emit):
                emit(plan.compare_state)

        if plan.mode is OutputProjectionMode.COMPARE:
            self.cancel_grid()
            self.compare_projection_presenter.present(
                projection,
                plan.compare_state,
            )
            return

        self.compare_route_presenter.present(
            projection=projection,
            state=plan.compare_state,
            route_blocked=True,
        )
        if plan.mode is OutputProjectionMode.SCENE_OVERVIEW:
            self._present_scene_overview(plan.scene_groups)
            return

        self._prepare_source_state(plan.source_groups)
        if plan.mode is OutputProjectionMode.SOURCE_GRID:
            self._present_source_grid(plan.source_groups)
        elif (
            plan.mode is OutputProjectionMode.IMAGE
            and plan.active_image_id is not None
            and plan.active_image_entry is not None
        ):
            self._present_image(
                session,
                plan.active_image_id,
                plan.active_image_entry,
                retire_completed_preview_slot,
            )
        else:
            self.cancel_grid()
            view.active_set_index = (
                0
                if OutputCanvasRouteModel.grid_available_for_current_source(
                    plan.source_groups,
                    view.active_source_key,
                )
                else 1
            )
        self._finish_standard_chrome()

    def _present_scene_overview(
        self,
        scene_groups: Mapping[str, OutputCanvasSceneGroup],
    ) -> None:
        """Mutate navigation state and immediately present the scene grid."""

        view = self.view
        view.active_scene_key = (
            view._output_projection.active_scene_key
            if view._output_projection.active_scene_key in scene_groups
            else next(iter(scene_groups), None)
        )
        view.active_scene_overview = True
        view.active_source_key = None
        view.active_set_index = 1
        view.set_count = 0
        self.source_tabs.rebuild_source_tabs(active_source_key=None)
        self.chrome.sync_scene_selector()
        self.chrome.sync_set_selector()
        self.chrome.sync_source_selector()
        self.chrome.update_tabbar()
        activate_output_scene_overview(
            view,
            update_tabbar_container=self.chrome.update_tabbar,
        )
        self.present_current_grid()

    def _prepare_source_state(
        self,
        source_groups: Mapping[str, OutputCanvasSourceGroup],
    ) -> None:
        """Apply projection scene/source/set selection before route presentation."""

        view = self.view
        projection = view._output_projection
        view.active_scene_key = projection.active_scene_key
        view.active_scene_overview = projection.active_scene_overview
        view.active_source_key = projection.active_source_key
        view.active_set_index = projection.active_set_index
        if view.active_set_index > 0:
            view.last_real_set_index = view.active_set_index
        view.set_count = OutputCanvasRouteModel.set_count_for_sources(
            tuple(source_groups.values())
        )
        self.source_tabs.rebuild_source_tabs(active_source_key=view.active_source_key)
        self.chrome.sync_scene_selector()

    def _present_source_grid(
        self,
        source_groups: Mapping[str, OutputCanvasSourceGroup],
    ) -> None:
        """Activate and present the selected source-batch grid."""

        view = self.view
        if activate_output_grid_for_source(
            view,
            view.active_source_key,
            source_groups_by_key=source_groups,
            update_tabbar_container=self.chrome.update_tabbar,
        ):
            self.present_current_grid()

    def _present_image(
        self,
        session: OutputCanvasSession,
        image_id: UUID,
        active_entry: tuple[str, OutputCanvasImageItem],
        retire: Callable[[PreviewSlotKey, str, str], None],
    ) -> None:
        """Apply a final image and retire its completed preview slot."""

        source_key, item = active_entry
        view = self.view
        view.active_set_index = view._output_projection.active_set_index
        view.last_real_set_index = view.active_set_index
        self.cancel_grid()
        self.interaction.set_grid_interaction_locked(False)
        self.image_routes.apply_projection_image(session, image_id)
        retirement = consume_final_output_preview_retirement(
            image_id=image_id,
            pending_final_preview_retire_ids=(
                output_revision_cache(view).pending_final_preview_retire_ids
            ),
            source_key=source_key,
            image_meta=item.image_meta,
            set_index=item.set_index,
        )
        if retirement is not None:
            retire(
                retirement.slot_key,
                retirement.source_label,
                "final_output_selected",
            )

    def _finish_standard_chrome(self) -> None:
        """Refresh standard Output chrome after non-compare presentation."""

        view = self.view
        self.chrome.sync_set_selector()
        if hasattr(view, "tabbar"):
            self.source_tabs.refresh_source_tab_tooltips()
        self.chrome.sync_scene_selector()
        self.chrome.sync_source_selector()
        self.chrome.update_tabbar()


__all__ = ["OutputProjectionChromeCallbacks", "OutputProjectionPresenter"]
