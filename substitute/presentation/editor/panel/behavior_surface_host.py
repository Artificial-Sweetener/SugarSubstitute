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

"""Apply behavior snapshots and expose cube visibility menu callbacks."""

from __future__ import annotations

from typing import Any, cast

from substitute.shared.logging.logger import get_logger, log_debug, log_warning

from .behavior.panel_ports import behavior_applier_for_panel
from .behavior_context_host import EditorPanelBehaviorContextHost
from .projection_host import EditorPanelProjectionHost
from .projection_preparation import BehaviorRefreshReason
from .runtime_access import (
    cube_visibility_menu_controller_for_panel,
    current_behavior_snapshot_for_panel,
)

_LOGGER = get_logger("presentation.editor.panel.behavior_surface_host")

_BEHAVIOR_TRANSACTION_INVALIDATING_REASONS: frozenset[BehaviorRefreshReason] = (
    frozenset(
        {
            "cube_removed",
            "cube_renamed",
            "stack_reordered",
            "search_changed",
            "node_activation_changed",
            "node_link_changed",
            "prompt_link_changed",
            "node_definition_changed",
            "model_options_changed",
        }
    )
)
_PROJECTION_INVALIDATING_REASONS: frozenset[BehaviorRefreshReason] = frozenset(
    reason
    for reason in _BEHAVIOR_TRANSACTION_INVALIDATING_REASONS
    if reason != "model_options_changed"
)


class EditorPanelBehaviorSurfaceHost:
    """Provide behavior and visibility callbacks through the panel host API."""

    def _rebuild_all_cube_visibility_menus(self) -> None:
        """Delegate reveal-menu rebuilds to the visibility owner."""

        cube_visibility_menu_controller_for_panel(self).rebuild_all()

    def _on_cube_visibility_menu_triggered(self, action: object) -> None:
        """Delegate reveal-menu action routing to the visibility owner."""

        cube_visibility_menu_controller_for_panel(self).route_triggered_action(action)

    def _rebuild_cube_visibility_menu(self, alias: str) -> None:
        """Delegate one reveal-menu rebuild to the visibility owner."""

        cube_visibility_menu_controller_for_panel(self).rebuild(alias)

    def _on_cube_visibility_menu_toggled(
        self,
        alias: str,
        action: object,
    ) -> None:
        """Delegate reveal-menu toggle persistence to the visibility owner."""

        cube_visibility_menu_controller_for_panel(self).route_toggled_action(
            alias,
            action,
        )

    def refresh_node_behavior_state(
        self,
        search_hidden_keys: set[object] | None = None,
        override_hidden_field_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
        *,
        reason: BehaviorRefreshReason = "full_workflow_projection",
        use_cached_snapshot: bool = False,
    ) -> None:
        """Resolve and apply the latest node-behavior snapshot."""

        panel: Any = self
        if not panel._stack_order or not panel._cube_states:
            return
        if node_search_text is not None:
            panel._current_node_search_text = node_search_text
        if search_hidden_keys is not None:
            panel._current_search_hidden_keys = set(search_hidden_keys)
        if search_matching_nodes is not None:
            panel._current_search_matching_nodes = set(search_matching_nodes)
        if (
            not use_cached_snapshot
            and reason in _BEHAVIOR_TRANSACTION_INVALIDATING_REASONS
        ):
            EditorPanelBehaviorContextHost.invalidate_behavior_refresh_transaction(
                cast(EditorPanelBehaviorContextHost, self),
                reason=reason,
            )
        if not use_cached_snapshot and reason in _PROJECTION_INVALIDATING_REASONS:
            EditorPanelProjectionHost.invalidate_projection(
                cast(EditorPanelProjectionHost, self),
                reason=reason,
            )

        try:
            last_snapshot = current_behavior_snapshot_for_panel(self)
            if use_cached_snapshot and last_snapshot is not None:
                snapshot = last_snapshot
            else:
                snapshot_kwargs: dict[str, object] = {
                    "search_hidden_keys": search_hidden_keys,
                    "node_search_text": node_search_text,
                }
                if override_hidden_field_keys is not None:
                    snapshot_kwargs["override_hidden_field_keys"] = (
                        override_hidden_field_keys
                    )
                if search_matching_nodes is not None:
                    snapshot_kwargs["search_matching_nodes"] = search_matching_nodes
                snapshot = panel._build_behavior_snapshot(**snapshot_kwargs)
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to build editor behavior snapshot",
                reason=reason,
                use_cached_snapshot=use_cached_snapshot,
                search_hidden_keys=repr(search_hidden_keys),
                node_search_text_length=(
                    0 if node_search_text is None else len(node_search_text)
                ),
                search_matching_nodes=repr(search_matching_nodes),
                error_type=type(error).__name__,
            )
            snapshot = None

        applier = behavior_applier_for_panel(self)
        if snapshot is None:
            applier.restore_previous_state()
            return

        applier.apply_snapshot(snapshot)
        panel.refresh_prompt_scene_diagnostics()
        log_debug(
            _LOGGER,
            "Refreshed editor behavior state",
            reason=reason,
            use_cached_snapshot=use_cached_snapshot,
            cube_section_count=len(panel._stack_order or []),
        )


__all__ = ["EditorPanelBehaviorSurfaceHost"]
