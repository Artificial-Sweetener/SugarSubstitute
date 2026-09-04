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

"""Measure responsive Output source navigation without mutating route state."""

from __future__ import annotations

from collections.abc import Callable, Mapping


class OutputCanvasNavigationMeasurement:
    """Provide source-tab measurement to the navigation layout controller."""

    canvas_width: Callable[[], int | None]
    tabbar: Callable[[], object]
    cached_source_tabbar_width: Callable[[], int]
    set_cached_source_tabbar_width: Callable[[int], None]

    def available_tabbar_container_width(self) -> int:
        """Return horizontal space available to the floating navigation bar."""

        width = self.canvas_width()
        if width is None:
            return 10_000
        return max(1, int(width) - 24)

    def preferred_tabbar_width(self) -> int:
        """Return full source tabbar preferred width even when it is hidden."""

        tabbar = self.tabbar()
        measured_width = self.measure_tabbar_preferred_width(tabbar)
        if measured_width > 0:
            self.set_cached_source_tabbar_width(measured_width)
            return measured_width
        cached_width = max(0, int(self.cached_source_tabbar_width() or 0))
        if cached_width > 0:
            return cached_width
        width = getattr(tabbar, "width", None)
        return int(width()) if callable(width) else 0

    @classmethod
    def measure_tabbar_preferred_width(cls, tabbar: object) -> int:
        """Measure the source tabbar's content width from current layout state."""

        ensure_polished = getattr(tabbar, "ensurePolished", None)
        if callable(ensure_polished):
            ensure_polished()
        layout_getter = getattr(tabbar, "layout", None)
        layout = layout_getter() if callable(layout_getter) else None
        if layout is not None:
            invalidate = getattr(layout, "invalidate", None)
            if callable(invalidate):
                invalidate()
            activate = getattr(layout, "activate", None)
            if callable(activate):
                activate()
        size_hint_width = cls.size_hint_width(tabbar)
        if size_hint_width > 0:
            return size_hint_width
        return cls.tabbar_item_width(tabbar, layout)

    @staticmethod
    def size_hint_width(widget: object) -> int:
        """Return a widget size-hint width when it reports a positive value."""

        size_hint = getattr(widget, "sizeHint", None)
        if not callable(size_hint):
            return 0
        hint = size_hint()
        width = getattr(hint, "width", None)
        if not callable(width):
            return 0
        return max(0, int(width()))

    @classmethod
    def tabbar_item_width(cls, tabbar: object, layout: object | None) -> int:
        """Calculate tabbar width from child item hints when parent hint is stale."""

        items = getattr(tabbar, "items", {})
        if not isinstance(items, Mapping):
            return 0
        item_widths = tuple(
            cls.tabbar_item_preferred_width(item) for item in items.values()
        )
        visible_item_widths = tuple(width for width in item_widths if width > 0)
        if not visible_item_widths:
            return 0
        spacing = cls.layout_spacing(layout)
        margins = cls.layout_horizontal_margins(layout)
        return (
            sum(visible_item_widths)
            + max(0, len(visible_item_widths) - 1) * spacing
            + margins
        )

    @classmethod
    def tabbar_item_preferred_width(cls, item: object) -> int:
        """Return a source-tab item width from settled or hinted geometry."""

        ensure_polished = getattr(item, "ensurePolished", None)
        if callable(ensure_polished):
            ensure_polished()
        adjust_size = getattr(item, "adjustSize", None)
        if callable(adjust_size):
            adjust_size()
        hinted_width = cls.size_hint_width(item)
        if hinted_width > 0:
            return hinted_width
        width = getattr(item, "width", None)
        return max(0, int(width())) if callable(width) else 0

    @staticmethod
    def layout_spacing(layout: object | None) -> int:
        """Return a layout's horizontal spacing when available."""

        if layout is None:
            return 0
        spacing = getattr(layout, "spacing", None)
        if not callable(spacing):
            return 0
        return max(0, int(spacing()))

    @staticmethod
    def layout_horizontal_margins(layout: object | None) -> int:
        """Return a layout's left and right margins when available."""

        if layout is None:
            return 0
        contents_margins = getattr(layout, "contentsMargins", None)
        if not callable(contents_margins):
            return 0
        margins = contents_margins()
        left = getattr(margins, "left", None)
        right = getattr(margins, "right", None)
        return (max(0, int(left())) if callable(left) else 0) + (
            max(0, int(right())) if callable(right) else 0
        )


__all__ = ["OutputCanvasNavigationMeasurement"]
