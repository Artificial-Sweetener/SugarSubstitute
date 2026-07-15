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

"""Apply Output canvas source-tab rebuilds outside the widget host."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    source_tab_items,
    source_tab_removal_keys,
    source_tab_tooltip,
    source_tab_tooltip_refresh_items,
    source_tabs_rebuild_plan,
)

TooltipInstaller = Callable[[object, object, int], object]


@dataclass(frozen=True, slots=True)
class OutputCanvasSourceTabsController:
    """Own Output source-tab mutation and tooltip-filter application."""

    visible_sources: Callable[[], Iterable[OutputCanvasSourceGroup]]
    cached_signature: Callable[[], tuple[tuple[str, str], ...] | None]
    set_cached_signature: Callable[[tuple[tuple[str, str], ...]], None]
    set_preferred_width: Callable[[int], None]
    tabbar: Callable[[], object]
    on_tab_changed: Callable[[str], None]
    active_set_index: Callable[[], int]
    tooltip_filters: Callable[[], MutableMapping[str, object]]
    measure_preferred_width: Callable[[], int]
    sync_source_selector: Callable[[], None]
    install_tooltip_filter: TooltipInstaller

    def rebuild_source_tabs(self, *, active_source_key: str | None) -> None:
        """Rebuild source selector tabs from current source groups."""

        sources = tuple(self.visible_sources())
        tab_plan = source_tabs_rebuild_plan(
            sources,
            cached_signature=self.cached_signature(),
            active_source_key=active_source_key,
        )
        active_tabbar = self.tabbar()
        if not tab_plan.rebuild_required:
            if tab_plan.active_source_key is not None:
                self._set_current_item(active_tabbar, tab_plan.active_source_key)
            self.sync_source_selector()
            return

        self.set_cached_signature(tab_plan.signature)
        self.set_preferred_width(0)
        self._disconnect_tab_changed(active_tabbar)

        tab_items = _tab_items(active_tabbar)
        if tab_items is not None:
            self.tooltip_filters().clear()
            for key in source_tab_removal_keys(tab_items):
                self._remove_widget(active_tabbar, key)

        for source_tab in source_tab_items(sources):
            self._add_item(active_tabbar, source_tab.source_key, source_tab.label)
            added_tab_items = _tab_items(active_tabbar)
            tab_item = (
                added_tab_items.get(source_tab.source_key)
                if added_tab_items is not None
                else None
            )
            if tab_item is not None:
                self._configure_source_tab_tooltip(source_tab.source, tab_item)

        self._adjust_size(active_tabbar)
        self.set_preferred_width(self.measure_preferred_width())
        if tab_plan.active_source_key is not None:
            self._set_current_item(active_tabbar, tab_plan.active_source_key)
        self._connect_tab_changed(active_tabbar)
        self.sync_source_selector()

    def refresh_source_tab_tooltips(self) -> None:
        """Refresh source tab tooltip text after source/set selection changes."""

        active_tabbar = self.tabbar()
        tab_items = _tab_items(active_tabbar)
        if tab_items is None:
            return
        self.tooltip_filters().clear()
        for refresh_item in source_tab_tooltip_refresh_items(
            self.visible_sources(),
            tab_items,
        ):
            self._configure_source_tab_tooltip(
                refresh_item.source,
                refresh_item.tab_item,
            )

    def _configure_source_tab_tooltip(
        self,
        source: OutputCanvasSourceGroup,
        tab_item: object,
    ) -> None:
        """Attach qfluent tooltip behavior for one output source tab."""

        tooltip = source_tab_tooltip(
            source,
            active_set_index=self.active_set_index(),
        )
        set_tooltip = getattr(tab_item, "setToolTip", None)
        if not callable(set_tooltip):
            return
        set_tooltip(tooltip.text)
        if not tooltip.installs_hover_filter:
            return
        self.tooltip_filters()[tooltip.source_key] = self.install_tooltip_filter(
            tab_item,
            tab_item,
            600,
        )

    def _disconnect_tab_changed(self, tabbar: object) -> None:
        """Disconnect tab-change signal if currently connected."""

        signal = getattr(tabbar, "currentItemChanged", None)
        disconnect = getattr(signal, "disconnect", None)
        if not callable(disconnect):
            return
        try:
            disconnect(self.on_tab_changed)
        except RuntimeError:
            return

    def _connect_tab_changed(self, tabbar: object) -> None:
        """Connect tab-change signal when available."""

        signal = getattr(tabbar, "currentItemChanged", None)
        connect = getattr(signal, "connect", None)
        if callable(connect):
            connect(self.on_tab_changed)

    @staticmethod
    def _add_item(tabbar: object, key: str, label: str) -> None:
        """Add one source tab item when the tabbar supports it."""

        add_item = getattr(tabbar, "addItem", None)
        if callable(add_item):
            add_item(key, label)

    @staticmethod
    def _remove_widget(tabbar: object, key: str) -> None:
        """Remove one source tab item when the tabbar supports it."""

        remove_widget = getattr(tabbar, "removeWidget", None)
        if callable(remove_widget):
            remove_widget(key)

    @staticmethod
    def _adjust_size(tabbar: object) -> None:
        """Ask the tabbar to settle size hints when available."""

        adjust_size = getattr(tabbar, "adjustSize", None)
        if callable(adjust_size):
            adjust_size()

    @staticmethod
    def _set_current_item(tabbar: object, key: str) -> None:
        """Select one source tab when the tabbar supports it."""

        set_current_item = getattr(tabbar, "setCurrentItem", None)
        if callable(set_current_item):
            set_current_item(key)


def _tab_items(tabbar: object) -> Mapping[str, object] | None:
    """Return tabbar item mapping when exposed by the concrete widget."""

    items = getattr(tabbar, "items", None)
    return items if isinstance(items, Mapping) else None


__all__ = [
    "OutputCanvasSourceTabsController",
    "TooltipInstaller",
]
