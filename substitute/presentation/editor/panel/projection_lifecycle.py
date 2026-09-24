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

"""Own panel projection lifecycle cleanup and runtime issue integration."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast

from substitute.application.workflows import (
    update_node_link_references_on_rename,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_timing,
    log_warning,
)

from .factories.meta_factories import (
    update_prompt_link_references_on_rename,
    update_sampler_link_references_on_rename,
    update_scheduler_link_references_on_rename,
)
from .projection_preparation import (
    BehaviorRefreshReason,
)
from .projection_registry_cleanup import (
    ProjectionRegistryCleanup,
    ProjectionRegistryPanelPort,
)
from .projection_session_models import ActiveProjectionSession

_LOGGER = get_logger("presentation.editor.panel.projection_lifecycle")


class ProjectionBuildRegistryPort(Protocol):
    """Describe build-registry cleanup used by lifecycle transitions."""

    def forget(self, alias: str) -> object | None:
        """Forget one alias-scoped build record."""

    def clear(self) -> None:
        """Clear all build records."""


class ProjectionCompletionPort(Protocol):
    """Describe pending insert cancellation used during layout clearing."""

    def cancel_all_pending_inserts(self, *, reason: str) -> None:
        """Cancel pending insert completions for the supplied reason."""


class VisibleProjectionCommitPort(Protocol):
    """Describe visible commit cleanup used during layout clearing."""

    def discard_pending_visible_projection_commit(self, *, reason: str) -> None:
        """Discard any deferred visible projection commit."""


class RenderReconcilerPort(Protocol):
    """Describe layout reconciliation used by stack reorder."""

    def clear_layout(self) -> None:
        """Detach managed root-layout widgets."""

    def append_cube_widget_to_layout(self, cube_widget: object) -> None:
        """Append one cube widget to the root cube layout."""


class ProjectionLifecyclePanelPort(Protocol):
    """Describe panel state and operations owned by projection lifecycle."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]
    cube_headers: dict[str, object]
    card_wrappers: dict[object, object]
    input_widgets_by_field_key: dict[object, object]
    row_widgets: dict[object, object]
    col_widgets: dict[object, object]
    meta_registry: object

    def sanitize_prompt_link_state(self) -> None:
        """Sanitize prompt-link state after structural cube changes."""

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Refresh sampler and scheduler link state."""

    def _refresh_link_widgets(self) -> None:
        """Refresh visible link widgets."""

    def refresh_node_behavior_state(
        self,
        *,
        reason: BehaviorRefreshReason,
        use_cached_snapshot: bool = False,
    ) -> None:
        """Refresh behavior-derived visibility state."""


@dataclass(frozen=True, slots=True)
class EditorProjectionLifecyclePorts:
    """Group collaborators used by projection lifecycle transitions."""

    panel: ProjectionLifecyclePanelPort
    build_registry: ProjectionBuildRegistryPort
    projection_completions: ProjectionCompletionPort
    visible_commits: VisibleProjectionCommitPort
    render_reconciler: RenderReconcilerPort
    active_projection_session: Callable[[], ActiveProjectionSession | None]
    cancel_active_projection_session: Callable[[ActiveProjectionSession, str], None]
    invalidate_projection: Callable[[str], None]


class EditorProjectionLifecyclePipeline:
    """Own remove, rename, reorder, and clear projection lifecycle orchestration."""

    def __init__(self, ports: EditorProjectionLifecyclePorts) -> None:
        """Store explicit lifecycle collaborators without owning the coordinator."""

        self._ports = ports
        self._registry_cleanup = ProjectionRegistryCleanup(
            cast(ProjectionRegistryPanelPort, ports.panel),
            ports.build_registry,
        )

    def remove_cube(self, cube_alias: str) -> None:
        """Remove one cube from projection state and refresh derived visibility."""

        panel = self._ports.panel
        clear_issue = getattr(panel, "clear_cube_runtime_issues", None)
        if callable(clear_issue):
            clear_issue(cube_alias)
        self.discard_cube_widget(cube_alias, reason="cube_removed")
        self.refresh_visibility(
            message=app_text("Failed to refresh editor visibility after cube removal"),
            reason="cube_removed",
        )
        self._ports.invalidate_projection("cube_removed")

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Rename one cube and refresh projection-derived link state."""

        panel = self._ports.panel
        rename_alias = self._cube_registry_rename()
        if rename_alias is not None:
            rename_alias(old_alias, new_alias)
        rename_node_link_alias = getattr(
            getattr(panel, "meta_registry", None),
            "rename_node_link_alias",
            None,
        )
        if callable(rename_node_link_alias):
            rename_node_link_alias(old_alias, new_alias)

        if panel._cube_states and panel._stack_order:
            all_buffers = {
                alias: cast(
                    dict[str, Any], getattr(panel._cube_states[alias], "buffer")
                )
                for alias in panel._stack_order
                if alias in panel._cube_states
            }
            update_prompt_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            update_node_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            update_sampler_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            update_scheduler_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            panel.sanitize_prompt_link_state()
            panel._refresh_sampler_scheduler_link_state()

        panel._refresh_link_widgets()
        self.refresh_visibility(
            message=app_text("Failed to refresh editor visibility after cube rename"),
            reason="cube_renamed",
        )
        self._ports.invalidate_projection("cube_renamed")

    def reorder_cube_widgets(self) -> None:
        """Reattach cube widgets in stack order and refresh link widgets once."""

        panel = self._ports.panel
        if not panel._stack_order:
            return
        refresh_started_at = perf_counter()

        panel.sanitize_prompt_link_state()
        panel._refresh_sampler_scheduler_link_state()
        self._ports.render_reconciler.clear_layout()

        for alias in panel._stack_order:
            widget = panel.cube_widgets.get(alias)
            if widget is None:
                continue
            self._ports.render_reconciler.append_cube_widget_to_layout(widget)

        panel._refresh_link_widgets()
        self.refresh_visibility(
            message=app_text("Failed to refresh editor visibility after cube reorder"),
            reason="stack_reordered",
        )
        log_timing(
            _LOGGER,
            "Reordered editor cube widgets",
            started_at=refresh_started_at,
            cube_section_count=len(panel._stack_order),
            existing_widget_count=len(panel.cube_widgets),
            level="debug",
        )

    def clear_layout(self) -> None:
        """Dispose rendered projection widgets and clear projection lifecycle state."""

        panel = self._ports.panel
        clear_model_progress = getattr(panel, "clear_model_field_load_progress", None)
        if callable(clear_model_progress):
            clear_model_progress()
        log_debug(
            _LOGGER,
            "Clearing editor panel layout",
            card_wrapper_count=len(panel.card_wrappers),
            cube_position_count=len(getattr(panel, "cube_positions", {})),
            cube_visibility_button_count=len(
                getattr(panel, "_cube_visibility_btns", {}),
            ),
            cube_visibility_menu_count=len(
                getattr(panel, "_cube_visibility_menus", {}),
            ),
            cube_widget_count=len(panel.cube_widgets),
            cube_header_count=len(panel.cube_headers),
            node_link_widget_count=len(getattr(panel, "node_link_widgets", {})),
        )

        active_session = self._ports.active_projection_session()
        if active_session is not None:
            self._ports.cancel_active_projection_session(
                active_session,
                "layout_cleared",
            )
        self._ports.visible_commits.discard_pending_visible_projection_commit(
            reason="layout_cleared",
        )
        self._ports.projection_completions.cancel_all_pending_inserts(
            reason="layout_cleared",
        )
        self._ports.build_registry.clear()

        self._registry_cleanup.clear_mounted_surface()
        self._ports.invalidate_projection("layout_cleared")
        log_debug(
            _LOGGER,
            "Cleared editor panel layout",
            card_wrapper_count=len(panel.card_wrappers),
            cube_position_count=len(getattr(panel, "cube_positions", {})),
            cube_visibility_button_count=len(
                getattr(panel, "_cube_visibility_btns", {}),
            ),
            cube_visibility_menu_count=len(
                getattr(panel, "_cube_visibility_menus", {}),
            ),
            cube_widget_count=len(panel.cube_widgets),
            cube_header_count=len(panel.cube_headers),
            node_link_widget_count=len(getattr(panel, "node_link_widgets", {})),
        )

    def remove_closed_aliases(self, current_aliases: set[str]) -> None:
        """Dispose widgets and runtime issues for aliases no longer present."""

        panel = self._ports.panel
        for alias in list(panel.cube_widgets.keys()):
            if alias in current_aliases:
                continue
            clear_issue = getattr(panel, "clear_cube_runtime_issues", None)
            if callable(clear_issue):
                clear_issue(alias)
            self.discard_cube_widget(alias, reason="closed_alias")

    def discard_cube_widget(self, cube_alias: str, *, reason: str) -> None:
        """Remove one rendered cube widget and its projection ownership record."""

        self._registry_cleanup.discard_cube_widget(cube_alias, reason=reason)

    def clear_alias_scoped_panel_registries(self, cube_alias: str) -> None:
        """Clear editor registries whose entries belong to one cube alias."""

        self._registry_cleanup.clear_alias(cube_alias)

    def refresh_visibility(
        self,
        *,
        message: str,
        reason: BehaviorRefreshReason,
        use_cached_snapshot: bool = False,
    ) -> None:
        """Run an immediate behavior refresh and log failures with shared context."""

        try:
            self._ports.panel.refresh_node_behavior_state(
                reason=reason,
                use_cached_snapshot=use_cached_snapshot,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                message,
                reason=reason,
                error_type=type(error).__name__,
            )

    def _cube_registry_rename(self) -> Callable[[str, str], None] | None:
        """Return the cube-registry rename hook supplied by the panel."""

        panel = self._ports.panel
        registry_controller = getattr(panel, "_cube_registry_controller", None)
        registry = registry_controller() if callable(registry_controller) else None
        if registry is None:
            registry = getattr(panel, "_cube_registry", None)
        rename_alias = getattr(registry, "rename_cube_alias", None)
        return rename_alias if callable(rename_alias) else None
