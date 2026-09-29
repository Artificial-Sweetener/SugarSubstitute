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

"""Dispose cube projection widgets and their alias-scoped registry entries."""

from __future__ import annotations

from typing import Protocol

from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.editor.panel.projection_lifecycle")


class ProjectionBuildRegistryPort(Protocol):
    """Describe build-registry cleanup used during widget disposal."""

    def forget(self, alias: str) -> object | None:
        """Forget one alias-scoped build record."""


class _LayoutItemPort(Protocol):
    """Describe layout-item access used by root cleanup."""

    def widget(self) -> object | None:
        """Return the contained widget, when present."""

    def layout(self) -> object | None:
        """Return the nested layout, when present."""


class _LayoutPort(Protocol):
    """Describe root layout removal operations."""

    def count(self) -> int:
        """Return the number of root layout items."""

    def takeAt(self, index: int) -> _LayoutItemPort:
        """Remove one root layout item."""


class ProjectionRegistryPanelPort(Protocol):
    """Describe mounted projection registries and root layout."""

    _layout: _LayoutPort
    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]
    cube_headers: dict[str, object]
    card_wrappers: dict[object, object]
    input_widgets_by_field_key: dict[object, object]
    row_widgets: dict[object, object]
    col_widgets: dict[object, object]
    meta_registry: object


class ProjectionRegistryCleanup:
    """Own complete and alias-scoped mounted projection disposal."""

    def __init__(
        self,
        panel: ProjectionRegistryPanelPort,
        build_registry: ProjectionBuildRegistryPort,
    ) -> None:
        """Store mounted registries and their build ownership."""

        self._panel = panel
        self._build_registry = build_registry

    def discard_cube_widget(self, cube_alias: str, *, reason: str) -> None:
        """Remove one rendered cube and its projection ownership record."""

        widget = self._panel.cube_widgets.pop(cube_alias, None)
        self._panel.cube_sections.pop(cube_alias, None)
        self._panel.cube_headers.pop(cube_alias, None)
        self._build_registry.forget(cube_alias)
        self.clear_alias(cube_alias)
        if widget is None:
            return
        hide = getattr(widget, "hide", None)
        if callable(hide):
            hide()
        remove_widget = getattr(self._panel, "_remove_cube_widget_from_layout", None)
        if callable(remove_widget):
            remove_widget(widget)
        else:
            set_parent = getattr(widget, "setParent", None)
            if callable(set_parent):
                set_parent(None)
        log_info(
            _LOGGER,
            "Discarded editor cube section widget",
            cube_alias=cube_alias,
            reason=reason,
        )

    def clear_alias(self, cube_alias: str) -> None:
        """Clear every mounted registry entry owned by one cube alias."""

        field_registry = getattr(self._panel, "_field_registry", None)
        remove_registered_cube = getattr(field_registry, "remove_cube", None)
        if callable(remove_registered_cube):
            remove_registered_cube(cube_alias)
        else:
            _remove_alias_keyed_entries(
                getattr(self._panel, "input_widgets_by_field_key", None),
                cube_alias,
            )
        _remove_alias_keyed_entries(
            getattr(self._panel, "row_widgets", None),
            cube_alias,
        )
        _remove_alias_keyed_entries(
            getattr(self._panel, "col_widgets", None),
            cube_alias,
        )
        _remove_alias_keyed_entries(
            getattr(self._panel, "_last_card_decisions", None),
            cube_alias,
        )
        hidden_keys = getattr(self._panel, "_last_hidden_field_keys", None)
        if isinstance(hidden_keys, set):
            setattr(
                self._panel,
                "_last_hidden_field_keys",
                {key for key in hidden_keys if not _alias_key_matches(key, cube_alias)},
            )
        meta_registry = getattr(self._panel, "meta_registry", None)
        remove_node_link_cube = getattr(meta_registry, "remove_node_link_cube", None)
        if callable(remove_node_link_cube):
            remove_node_link_cube(cube_alias)
        card_wrappers = getattr(self._panel, "card_wrappers", None)
        if isinstance(card_wrappers, dict):
            for key in [
                key for key in card_wrappers if _alias_key_matches(key, cube_alias)
            ]:
                card_wrappers.pop(key, None)

    def clear_mounted_surface(self) -> None:
        """Clear cube, link, child, and root-layout projection ownership."""

        self._panel.cube_widgets.clear()
        self._panel.cube_sections.clear()
        self._clear_link_registries()
        self._clear_child_widget_registries()
        self._clear_root_layout()
        getattr(self._panel, "cube_positions", {}).clear()

    def _clear_link_registries(self) -> None:
        """Clear link registries while preserving meta-registry cleanup hooks."""

        cleanup_dead = getattr(
            self._panel.meta_registry,
            "cleanup_dead_node_link_widgets",
            None,
        )
        if callable(cleanup_dead):
            cleanup_dead()
        clear_titles = getattr(
            self._panel.meta_registry,
            "clear_node_link_title_surfaces",
            None,
        )
        if callable(clear_titles):
            clear_titles()
        for attribute_name in ("node_link_widgets", "node_link_title_surfaces"):
            mapping = getattr(self._panel, attribute_name, None)
            if isinstance(mapping, dict):
                mapping.clear()

    def _clear_child_widget_registries(self) -> None:
        """Clear cube-scoped child registries after layout disposal starts."""

        self._panel.row_widgets = {}
        self._panel.col_widgets = {}
        field_registry = getattr(self._panel, "_field_registry", None)
        clear_fields = getattr(field_registry, "clear", None)
        if callable(clear_fields):
            clear_fields()
            self._panel.input_widgets_by_field_key = getattr(
                field_registry,
                "widget_map",
                {},
            )
        else:
            self._panel.input_widgets_by_field_key = {}
        card_modes = getattr(self._panel, "_node_card_mode_controller", None)
        clear_card_modes = getattr(card_modes, "clear", None)
        if callable(clear_card_modes):
            clear_card_modes()
        self._panel.card_wrappers.clear()
        getattr(self._panel, "_cube_visibility_btns", {}).clear()
        getattr(self._panel, "_cube_visibility_menus", {}).clear()
        self._panel.cube_headers.clear()

    def _clear_root_layout(self) -> None:
        """Dispose every root layout item through recursive panel cleanup."""

        while self._panel._layout.count():
            item = self._panel._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                delete_later = getattr(widget, "deleteLater", None)
                if callable(delete_later):
                    delete_later()
                continue
            nested_layout = item.layout()
            clear_nested = getattr(self._panel, "_clear_layout_recursive", None)
            if nested_layout is not None and callable(clear_nested):
                clear_nested(nested_layout)


def _remove_alias_keyed_entries(mapping: object, cube_alias: str) -> None:
    """Remove tuple-keyed entries scoped to one cube alias."""

    if not isinstance(mapping, dict):
        return
    for key in [key for key in mapping if _alias_key_matches(key, cube_alias)]:
        mapping.pop(key, None)


def _alias_key_matches(key: object, cube_alias: str) -> bool:
    """Return whether one registry key belongs to the supplied cube alias."""

    return isinstance(key, tuple) and bool(key) and key[0] == cube_alias


__all__ = [
    "ProjectionBuildRegistryPort",
    "ProjectionRegistryCleanup",
    "ProjectionRegistryPanelPort",
]
