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

"""Reconcile whole-node link selector widgets from behavior snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any, TypeAlias, cast

import shiboken6

from substitute.application.node_behavior import EditorBehaviorSnapshot, TitleControl
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.workflows import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
    NodeLinkIdentity,
)
from substitute.presentation.editor.panel.factories.link_selector_widths import (
    node_link_width_labels_by_identity,
)
from substitute.application.display_labels import beautify_label
from .factories.meta_factories import NodeLinkComboContext

NodeLinkSelectorKey: TypeAlias = tuple[str, NodeLinkIdentity]
NodeLinkWidgetMap: TypeAlias = MutableMapping[NodeLinkSelectorKey, Any]
NodeLinkSetupFunc: TypeAlias = Callable[..., tuple[Any, str | None]]


@dataclass(frozen=True, slots=True)
class NodeLinkTitleSurface:
    """Describe where one node-link title selector can be attached."""

    cube_alias: str
    node_name: str
    identity: NodeLinkIdentity
    title_layout: Any
    title_controls: tuple[TitleControl, ...]


@dataclass(frozen=True, slots=True)
class NodeLinkReconciliationResult:
    """Summarize one node-link widget reconciliation pass."""

    expected_keys: tuple[NodeLinkSelectorKey, ...]
    created_keys: tuple[NodeLinkSelectorKey, ...]
    refreshed_keys: tuple[NodeLinkSelectorKey, ...]
    deleted_keys: tuple[NodeLinkSelectorKey, ...]
    missing_surface_keys: tuple[NodeLinkSelectorKey, ...]


class NodeLinkWidgetController:
    """Own creation, refresh, cleanup, and alias migration for node-link selectors."""

    def __init__(
        self,
        panel: Any,
        setup_node_link_combobox: NodeLinkSetupFunc,
    ) -> None:
        """Bind the controller to the panel projection maps it reconciles."""

        self._panel = panel
        self._setup_node_link_combobox = setup_node_link_combobox
        self._ensure_title_surface_map()

    def register_title_surface(
        self,
        *,
        cube_alias: str | None,
        node_name: str,
        identity: NodeLinkIdentity,
        title_layout: Any,
        title_controls: Sequence[TitleControl],
    ) -> None:
        """Register an existing card title row that can host a selector."""

        if cube_alias is None or not (
            TitleControl.NODE_LINK_SELECTOR in title_controls
            or TitleControl.PROMPT_LINK_SELECTOR in title_controls
        ):
            return
        key = (cube_alias, identity)
        self._title_surfaces()[key] = NodeLinkTitleSurface(
            cube_alias=cube_alias,
            node_name=node_name,
            identity=identity,
            title_layout=title_layout,
            title_controls=tuple(title_controls),
        )

    def rename_alias(self, old_alias: str, new_alias: str) -> None:
        """Migrate node-link selector projection state after a cube alias changes."""

        widget_map = self._widget_map()
        for key, combo in list(widget_map.items()):
            cube_alias, identity = key
            if cube_alias != old_alias:
                continue
            new_key = (new_alias, identity)
            if new_key in widget_map and widget_map[new_key] is not combo:
                self._delete_widget(combo)
                widget_map.pop(key, None)
                continue
            widget_map[new_key] = widget_map.pop(key)

        surface_map = self._title_surfaces()
        for key, surface in list(surface_map.items()):
            cube_alias, identity = key
            if cube_alias != old_alias:
                continue
            new_key = (new_alias, identity)
            surface_map[new_key] = self._title_surface_with_alias(surface, new_alias)
            surface_map.pop(key, None)

    def remove_cube(self, cube_alias: str) -> None:
        """Remove selector widgets and title surfaces for one closed cube."""

        widget_map = self._widget_map()
        for key, combo in list(widget_map.items()):
            if key[0] != cube_alias:
                continue
            widget_map.pop(key, None)
            self._delete_widget(combo)

        surface_map = self._title_surfaces()
        removed_surface_keys = tuple(key for key in surface_map if key[0] == cube_alias)
        for key in removed_surface_keys:
            surface_map.pop(key, None)

    def clear(self) -> None:
        """Forget registered title surfaces after the editor layout is cleared."""

        self._title_surfaces().clear()

    def reconcile_all(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        all_buffers: Mapping[str, Mapping[str, Any]],
        ordered_aliases: Sequence[str],
        node_definition_gateway: NodeDefinitionGateway,
    ) -> NodeLinkReconciliationResult:
        """Reconcile every node-link selector from the current behavior snapshot."""

        return self._reconcile(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            ordered_aliases=ordered_aliases,
            node_definition_gateway=node_definition_gateway,
            cube_alias=None,
        )

    def reconcile_cube(
        self,
        *,
        cube_alias: str,
        behavior_snapshot: EditorBehaviorSnapshot,
        all_buffers: Mapping[str, Mapping[str, Any]],
        ordered_aliases: Sequence[str],
        node_definition_gateway: NodeDefinitionGateway,
    ) -> NodeLinkReconciliationResult:
        """Reconcile node-link selectors owned by one cube alias."""

        return self._reconcile(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            ordered_aliases=ordered_aliases,
            node_definition_gateway=node_definition_gateway,
            cube_alias=cube_alias,
        )

    def _reconcile(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        all_buffers: Mapping[str, Mapping[str, Any]],
        ordered_aliases: Sequence[str],
        node_definition_gateway: NodeDefinitionGateway,
        cube_alias: str | None,
    ) -> NodeLinkReconciliationResult:
        """Apply one complete reconciliation pass to the widget map."""

        endpoint_index = behavior_snapshot.node_link_endpoint_index
        expected = self._expected_endpoints(
            endpoint_index=endpoint_index,
            behavior_snapshot=behavior_snapshot,
            cube_alias=cube_alias,
        )
        expected_keys = tuple(expected.keys())
        deleted_keys = self._cleanup_stale_widgets(expected_keys, cube_alias)
        shared_width_labels_by_identity = node_link_width_labels_by_identity(
            endpoint_index,
            list(ordered_aliases),
        )
        created_keys: list[NodeLinkSelectorKey] = []
        refreshed_keys: list[NodeLinkSelectorKey] = []
        missing_surface_keys: list[NodeLinkSelectorKey] = []
        widget_map = self._widget_map()

        for key, endpoint in expected.items():
            combo = widget_map.get(key)
            title_layout = self._layout_for_existing_combo(combo)
            if title_layout is None:
                title_layout = self._title_layout_for_key(key)
            if title_layout is None:
                missing_surface_keys.append(key)
                continue
            existed_before = key in widget_map
            self._setup_node_link_combobox(
                self._panel,
                widget_map,
                endpoint,
                endpoint_index,
                all_buffers,
                title_layout,
                beautify_label,
                shared_width_labels=shared_width_labels_by_identity.get(
                    endpoint.identity
                ),
                node_definition_gateway=node_definition_gateway,
                link_context=NodeLinkComboContext(
                    ordered_aliases=ordered_aliases,
                    apply_manual_node_link_selection=(
                        self._panel.apply_manual_node_link_selection
                    ),
                    notify_node_link_changed=self._notify_node_link_changed,
                ),
            )
            if existed_before:
                refreshed_keys.append(key)
            else:
                created_keys.append(key)

        result = NodeLinkReconciliationResult(
            expected_keys=expected_keys,
            created_keys=tuple(created_keys),
            refreshed_keys=tuple(refreshed_keys),
            deleted_keys=tuple(deleted_keys),
            missing_surface_keys=tuple(missing_surface_keys),
        )
        return result

    def _expected_endpoints(
        self,
        *,
        endpoint_index: NodeLinkEndpointIndex,
        behavior_snapshot: EditorBehaviorSnapshot,
        cube_alias: str | None,
    ) -> dict[NodeLinkSelectorKey, NodeLinkEndpoint]:
        """Return eligible endpoint widgets keyed by cube alias and identity."""

        expected: dict[NodeLinkSelectorKey, NodeLinkEndpoint] = {}
        for endpoint in endpoint_index.endpoints:
            if cube_alias is not None and endpoint.cube_alias != cube_alias:
                continue
            candidate = endpoint_index.endpoint_for_node(
                endpoint.cube_alias,
                endpoint.node_name,
                endpoint.identity,
            )
            if candidate is None:
                continue
            if not self._endpoint_uses_node_link_selector(
                behavior_snapshot,
                endpoint,
            ):
                continue
            expected.setdefault((endpoint.cube_alias, endpoint.identity), candidate)
        return expected

    @staticmethod
    def _endpoint_uses_node_link_selector(
        behavior_snapshot: EditorBehaviorSnapshot,
        endpoint: NodeLinkEndpoint,
    ) -> bool:
        """Return whether endpoint metadata declares the generic node-link selector."""

        resolved_nodes_by_alias = getattr(
            behavior_snapshot,
            "resolved_nodes_by_alias",
            None,
        )
        if not isinstance(resolved_nodes_by_alias, Mapping):
            return True
        per_cube = resolved_nodes_by_alias.get(endpoint.cube_alias)
        if not isinstance(per_cube, Mapping):
            return False
        resolved_behavior = per_cube.get(endpoint.node_name)
        card = getattr(resolved_behavior, "card", None)
        title_controls = getattr(card, "title_controls", ())
        return (
            TitleControl.NODE_LINK_SELECTOR in title_controls
            or TitleControl.PROMPT_LINK_SELECTOR in title_controls
        )

    def _cleanup_stale_widgets(
        self,
        expected_keys: Sequence[NodeLinkSelectorKey],
        cube_alias: str | None,
    ) -> tuple[NodeLinkSelectorKey, ...]:
        """Delete widgets that no longer correspond to eligible endpoints."""

        expected = set(expected_keys)
        deleted_keys: list[NodeLinkSelectorKey] = []
        widget_map = self._widget_map()
        for key, combo in list(widget_map.items()):
            if cube_alias is not None and key[0] != cube_alias:
                continue
            if key in expected and self._is_live_parented_widget(combo):
                continue
            widget_map.pop(key, None)
            self._delete_widget(combo)
            deleted_keys.append(key)
        return tuple(deleted_keys)

    def _ensure_title_surface_map(self) -> None:
        """Create the panel title-surface registry when absent."""

        if not hasattr(self._panel, "node_link_title_surfaces"):
            self._panel.node_link_title_surfaces = {}

    def _title_surfaces(self) -> MutableMapping[NodeLinkSelectorKey, Any]:
        """Return the mutable title-surface registry from the panel."""

        self._ensure_title_surface_map()
        surfaces = self._panel.node_link_title_surfaces
        if not isinstance(surfaces, MutableMapping):
            replacement: dict[NodeLinkSelectorKey, Any] = {}
            self._panel.node_link_title_surfaces = replacement
            return replacement
        return cast(MutableMapping[NodeLinkSelectorKey, Any], surfaces)

    def _notify_node_link_changed(self) -> None:
        """Refresh behavior state after a manual node-link selection."""

        self._panel.refresh_node_behavior_state(reason="node_link_changed")

    def _widget_map(self) -> NodeLinkWidgetMap:
        """Return the panel-owned node-link widget projection map."""

        return cast(NodeLinkWidgetMap, self._panel.node_link_widgets)

    def _title_layout_for_key(self, key: NodeLinkSelectorKey) -> Any | None:
        """Return the registered title layout for a selector key."""

        surface = self._title_surfaces().get(key)
        if surface is None:
            return None
        title_layout = getattr(surface, "title_layout", None)
        return title_layout

    @staticmethod
    def _layout_for_existing_combo(combo: object | None) -> Any | None:
        """Return an existing combo's parent layout when it is still attached."""

        if combo is None:
            return None
        parent_widget = getattr(combo, "parentWidget", None)
        if not callable(parent_widget):
            return None
        widget = parent_widget()
        layout = getattr(widget, "layout", None)
        if not callable(layout):
            return None
        return layout()

    @classmethod
    def _is_live_parented_widget(cls, widget: object | None) -> bool:
        """Return whether a widget reference is valid and still parented."""

        if widget is None or not cls._is_live_widget(widget):
            return False
        parent = getattr(widget, "parent", None)
        if callable(parent):
            return parent() is not None
        return True

    @staticmethod
    def _is_live_widget(widget: object | None) -> bool:
        """Return whether one Qt object reference can still be manipulated."""

        if widget is None:
            return False
        try:
            return bool(shiboken6.isValid(widget))
        except TypeError:
            return True

    @staticmethod
    def _delete_widget(widget: object | None) -> None:
        """Detach and schedule deletion for a widget-like object."""

        if widget is None:
            return
        set_parent = getattr(widget, "setParent", None)
        if callable(set_parent):
            set_parent(None)
        delete_later = getattr(widget, "deleteLater", None)
        if callable(delete_later):
            delete_later()

    @staticmethod
    def _title_surface_with_alias(surface: object, new_alias: str) -> object:
        """Return a title-surface object carrying the renamed cube alias."""

        if isinstance(surface, NodeLinkTitleSurface):
            return replace(surface, cube_alias=new_alias)
        values = dict(getattr(surface, "__dict__", {}))
        values["cube_alias"] = new_alias
        return SimpleNamespace(**values)


__all__ = [
    "NodeLinkReconciliationResult",
    "NodeLinkSelectorKey",
    "NodeLinkTitleSurface",
    "NodeLinkWidgetController",
]
