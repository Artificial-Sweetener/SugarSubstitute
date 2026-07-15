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

"""Manage editor link-widget maps, cleanup, and refresh orchestration."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping, Sequence
from typing import Any, cast

from shiboken6 import isValid

from substitute.application.overrides import (
    SamplerSchedulerLinkSnapshot,
    SamplerSchedulerLinkStateService,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.workflows import NodeLinkEndpointIndex, NodeLinkIdentity
from .factories.meta_factories import (
    setup_node_link_combobox,
    setup_sampler_link_combobox,
    setup_scheduler_link_combobox,
)
from substitute.application.display_labels import beautify_label
from .node_link_widget_controller import NodeLinkWidgetController


def _expected_widget_keys(
    endpoint_index: NodeLinkEndpointIndex,
) -> tuple[tuple[str, NodeLinkIdentity], ...]:
    """Return endpoint-backed node-link widget keys expected in the registry."""

    keys: list[tuple[str, NodeLinkIdentity]] = []
    for endpoint in endpoint_index.endpoints:
        if endpoint_index.endpoint_for(endpoint.cube_alias, endpoint.identity) is None:
            continue
        key = (endpoint.cube_alias, endpoint.identity)
        if key not in keys:
            keys.append(key)
    return tuple(keys)


class MetaRegistry:
    """
    Responsible for managing widget link cleanup and updates for EditorPanel.
    This will be expanded as we migrate logic in later steps.
    """

    def __init__(self, panel: Any) -> None:
        self.panel = panel
        self._sampler_scheduler_link_state_service = SamplerSchedulerLinkStateService()
        self._node_link_widget_controller = NodeLinkWidgetController(
            panel,
            setup_node_link_combobox,
        )

    @property
    def _node_definition_gateway(self) -> NodeDefinitionGateway:
        """Expose the panel-owned live node-definition gateway."""

        return cast(NodeDefinitionGateway, self.panel.node_definition_gateway)

    def _cleanup_dead_widgets(
        self,
        widget_map: MutableMapping[tuple[Any, ...], Any],
    ) -> None:
        """
        Remove any ComboBox references from a widget mapping whose underlying C++ objects are deleted.
        """
        for key, combo in list(widget_map.items()):
            if not combo or not isValid(combo) or combo.parent() is None:
                widget_map.pop(key, None)

    def _all_buffers(self) -> dict[str, dict[str, Any]]:
        """Return workflow buffers keyed by cube alias for link option refreshes."""

        if not self.panel._cube_states or not self.panel._stack_order:
            return {}
        return {
            alias: self.panel._cube_states[alias].buffer
            for alias in self.panel._stack_order
            if alias in self.panel._cube_states
        }

    def _ordered_aliases(self) -> list[str]:
        """Return the current panel stack order as the width-planning order."""

        stack_order = getattr(self.panel, "_stack_order", None)
        if isinstance(stack_order, Sequence) and not isinstance(
            stack_order,
            (str, bytes),
        ):
            return list(stack_order)
        return []

    def _update_link_widgets(
        self,
        widget_map: MutableMapping[tuple[Any, ...], Any],
        setup_func: Callable[..., Any],
        add_label: bool = False,
    ) -> None:
        """
        Generalized updater for link ComboBoxes.
        """
        self._cleanup_dead_widgets(widget_map)

        all_buffers = self._all_buffers()
        if not all_buffers:
            return

        for key, combo in list(widget_map.items()):
            if not combo or not isValid(combo) or combo.parent() is None:
                widget_map.pop(key, None)
                continue

            args = list(key)
            setup_func(
                self.panel,
                widget_map,
                *args,
                all_buffers,
                combo.parentWidget().layout() if combo.parentWidget() else None,
                *([beautify_label] if add_label else []),
                node_definition_gateway=self._node_definition_gateway,
            )

    # Public wrappers for each mapping type

    def cleanup_dead_node_link_widgets(self) -> None:
        self._cleanup_dead_widgets(self.panel.node_link_widgets)

    def register_node_link_title_surface(
        self,
        *,
        cube_alias: str | None,
        node_name: str,
        identity: NodeLinkIdentity,
        title_layout: Any,
        title_controls: Sequence[Any],
    ) -> None:
        """Register a card title row that can host a generic node-link selector."""

        self._node_link_widget_controller.register_title_surface(
            cube_alias=cube_alias,
            node_name=node_name,
            identity=identity,
            title_layout=title_layout,
            title_controls=title_controls,
        )

    def rename_node_link_alias(self, old_alias: str, new_alias: str) -> None:
        """Migrate node-link selector projection maps after alias rename."""

        self._node_link_widget_controller.rename_alias(old_alias, new_alias)

    def remove_node_link_cube(self, cube_alias: str) -> None:
        """Remove node-link selector projection state for a closed cube."""

        self._node_link_widget_controller.remove_cube(cube_alias)

    def clear_node_link_title_surfaces(self) -> None:
        """Clear registered node-link title surfaces after layout disposal."""

        self._node_link_widget_controller.clear()

    def cleanup_dead_sampler_link_widgets(self) -> None:
        self._cleanup_dead_widgets(self.panel.sampler_link_widgets)

    def cleanup_dead_scheduler_link_widgets(self) -> None:
        self._cleanup_dead_widgets(self.panel.scheduler_link_widgets)

    def update_node_link_widgets(self) -> None:
        """Refresh generic node-link widgets from the current node endpoint index."""

        widget_map = self.panel.node_link_widgets
        keys_before_cleanup = tuple(widget_map.keys())
        self._cleanup_dead_widgets(widget_map)
        all_buffers = self._all_buffers()
        if not all_buffers:
            _ = keys_before_cleanup
            return
        behavior_snapshot = self.panel.current_behavior_snapshot()
        if behavior_snapshot is None:
            return
        self._node_link_widget_controller.reconcile_all(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            ordered_aliases=self._ordered_aliases(),
            node_definition_gateway=self._node_definition_gateway,
        )

    def update_node_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh whole-node link widgets owned by one cube alias."""

        widget_map = self.panel.node_link_widgets
        keys_before_cleanup = tuple(widget_map.keys())
        self._cleanup_dead_widgets(widget_map)
        all_buffers = self._all_buffers()
        if not all_buffers:
            _ = keys_before_cleanup
            return
        behavior_snapshot = self.panel.current_behavior_snapshot()
        if behavior_snapshot is None:
            return
        self._node_link_widget_controller.reconcile_cube(
            cube_alias=cube_alias,
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            ordered_aliases=self._ordered_aliases(),
            node_definition_gateway=self._node_definition_gateway,
        )

    def update_sampler_link_widgets(self) -> None:
        self._update_choice_link_widgets(
            self.panel.sampler_link_widgets,
            setup_sampler_link_combobox,
            "sampler",
        )

    def update_sampler_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh sampler link widgets owned by one cube alias."""

        self._update_choice_link_widgets_for_cube(
            self.panel.sampler_link_widgets,
            setup_sampler_link_combobox,
            cube_alias,
            "sampler",
        )

    def update_scheduler_link_widgets(self) -> None:
        self._update_choice_link_widgets(
            self.panel.scheduler_link_widgets,
            setup_scheduler_link_combobox,
            "scheduler",
        )

    def update_scheduler_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh scheduler link widgets owned by one cube alias."""

        self._update_choice_link_widgets_for_cube(
            self.panel.scheduler_link_widgets,
            setup_scheduler_link_combobox,
            cube_alias,
            "scheduler",
        )

    def _sampler_scheduler_link_snapshot(
        self,
    ) -> tuple[dict[str, dict[str, Any]], SamplerSchedulerLinkSnapshot] | None:
        """Return resolved sampler/scheduler link state when editor state is ready."""

        all_buffers = self._all_buffers()
        if not all_buffers:
            return None
        current_behavior_snapshot = getattr(
            self.panel,
            "current_behavior_snapshot",
            None,
        )
        if not callable(current_behavior_snapshot):
            return None
        behavior_snapshot = current_behavior_snapshot()
        if behavior_snapshot is None:
            return None
        link_snapshot = self._sampler_scheduler_link_state_service.build_snapshot(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            stack_order=self._ordered_aliases(),
        )
        return all_buffers, link_snapshot

    def _update_choice_link_widgets(
        self,
        widget_map: MutableMapping[tuple[Any, ...], Any],
        setup_func: Callable[..., Any],
        field_family: str,
    ) -> None:
        """Refresh sampler/scheduler value-link widgets from resolved field state."""

        self._cleanup_dead_widgets(widget_map)
        snapshot_payload = self._sampler_scheduler_link_snapshot()
        if snapshot_payload is None:
            return
        all_buffers, link_snapshot = snapshot_payload
        field_states = _field_states_for_family(link_snapshot, field_family)

        for key, combo in list(widget_map.items()):
            if not combo or not isValid(combo) or combo.parent() is None:
                widget_map.pop(key, None)
                continue

            cube_alias, node_name = key
            setup_func(
                self.panel,
                widget_map,
                cube_alias,
                node_name,
                all_buffers,
                combo.parentWidget().layout() if combo.parentWidget() else None,
                node_definition_gateway=self._node_definition_gateway,
                field_state=field_states.get((cube_alias, node_name)),
            )

    def _update_choice_link_widgets_for_cube(
        self,
        widget_map: MutableMapping[tuple[Any, ...], Any],
        setup_func: Callable[..., Any],
        cube_alias: str,
        field_family: str,
    ) -> None:
        """Refresh sampler/scheduler value-link widgets owned by one cube alias."""

        self._cleanup_dead_widgets(widget_map)
        snapshot_payload = self._sampler_scheduler_link_snapshot()
        if snapshot_payload is None:
            return
        all_buffers, link_snapshot = snapshot_payload
        field_states = _field_states_for_family(link_snapshot, field_family)

        for key, combo in list(widget_map.items()):
            if not key or key[0] != cube_alias:
                continue
            if not combo or not isValid(combo) or combo.parent() is None:
                widget_map.pop(key, None)
                continue

            _, node_name = key
            setup_func(
                self.panel,
                widget_map,
                cube_alias,
                node_name,
                all_buffers,
                combo.parentWidget().layout() if combo.parentWidget() else None,
                node_definition_gateway=self._node_definition_gateway,
                field_state=field_states.get((cube_alias, node_name)),
            )

    def _update_link_widgets_for_cube(
        self,
        widget_map: MutableMapping[tuple[Any, ...], Any],
        setup_func: Callable[..., Any],
        cube_alias: str,
        add_label: bool = False,
    ) -> None:
        """Refresh generic link widgets owned by one cube alias."""

        self._cleanup_dead_widgets(widget_map)
        all_buffers = self._all_buffers()
        if not all_buffers:
            return

        for key, combo in list(widget_map.items()):
            if not key or key[0] != cube_alias:
                continue
            if not combo or not isValid(combo) or combo.parent() is None:
                widget_map.pop(key, None)
                continue

            args = list(key)
            setup_func(
                self.panel,
                widget_map,
                *args,
                all_buffers,
                combo.parentWidget().layout() if combo.parentWidget() else None,
                *([beautify_label] if add_label else []),
                node_definition_gateway=self._node_definition_gateway,
            )


def _field_states_for_family(
    link_snapshot: SamplerSchedulerLinkSnapshot,
    field_family: str,
) -> dict[tuple[str, str], Any]:
    """Return sampler or scheduler field states from a combined snapshot."""

    if field_family == "sampler":
        return link_snapshot.sampler_fields
    return link_snapshot.scheduler_fields
