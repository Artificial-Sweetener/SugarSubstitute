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

"""Settle cube-section height and child width-group geometry."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QLayout, QWidget
from shiboken6 import isValid

from substitute.presentation.editor.panel.node_card.body_layout import (
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
    resolve_card_body_expanded_height,
)
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    MasonryGridLayout,
)
from substitute.shared.logging.logger import get_logger, log_timing, log_warning

_LOGGER = get_logger("presentation.editor.panel.widgets.cube_section")
_QT_WIDGET_MAXIMUM_SIZE = 16_777_215


def is_live_widget(widget: object) -> bool:
    """Return whether one Qt object can still be safely inspected."""

    try:
        return bool(isValid(widget))
    except TypeError:
        return True


class CubeSectionLayoutController:
    """Own one cube section's synchronous and deferred layout settlement."""

    def __init__(
        self,
        *,
        section: QWidget,
        content_container: QWidget,
        grid_layout: MasonryGridLayout,
        height_changed: Callable[[], None],
    ) -> None:
        """Store the mounted section geometry surfaces."""

        self._section = section
        self._content_container = content_container
        self._grid_layout = grid_layout
        self._height_changed = height_changed
        self._resolved_height: int | None = None
        self._string_width_sync_pending = False

    @property
    def resolved_height(self) -> int | None:
        """Return the latest authoritative section height."""

        return self._resolved_height

    def update_height(self) -> None:
        """Set minimum height from the grid layout hint plus style padding."""

        if not is_live_widget(self._grid_layout):
            return
        try:
            self._grid_layout.invalidate()
            grid_height = self._grid_layout.sizeHint().height()
            content_layout = self._content_container.layout()
            content_height = (
                content_layout.sizeHint().height() if content_layout is not None else 0
            )
            height = max(grid_height + 36, content_height)
        except RuntimeError:
            return
        self._resolved_height = height
        self._section.setMinimumHeight(height)
        section_layout = self._section.layout()
        if section_layout is not None:
            section_layout.invalidate()
        self._section.updateGeometry()
        self._height_changed()

    def defer_height_update(self) -> None:
        """Defer a height recompute until the next event-loop turn."""

        QTimer.singleShot(0, self.update_height)

    def defer_string_width_sync(self) -> None:
        """Defer shared string line-edit width sync until layout has settled."""

        if not is_live_widget(self._section) or self._string_width_sync_pending:
            return
        self._string_width_sync_pending = True
        QTimer.singleShot(0, self.sync_string_width_group)

    def sync_string_width_group(self) -> None:
        """Apply one shared width cap to visible single-line string inputs."""

        self._string_width_sync_pending = False
        if not is_live_widget(self._section):
            return
        fields = self._string_width_group_fields()
        if len(fields) < 2:
            self._release_string_width_caps(fields)
            return
        self._release_string_width_caps(fields)
        self._activate_width_layouts(fields)
        visible_fields = [
            field
            for field in fields
            if is_live_widget(field)
            and field.isVisibleTo(self._section)
            and field.width() > 0
        ]
        if len(visible_fields) < 2:
            return
        shared_width = min(field.width() for field in visible_fields)
        for field in visible_fields:
            field.setMinimumWidth(shared_width)
            field.setMaximumWidth(shared_width)
            self._set_field_alignment(
                field,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            field.updateGeometry()
        self._activate_width_layouts(visible_fields)

    def finalize(self, *, reason: str) -> None:
        """Apply the authoritative section-local layout pass."""

        if not is_live_widget(self._section):
            log_warning(
                _LOGGER,
                "Skipped cube-section layout finalization for deleted widget",
                cube_alias="",
                reason=reason,
            )
            return
        cube_alias = self._cube_alias()
        width_before = self._section.width()
        height_before = self._section.height()
        started_at = perf_counter()
        try:
            content_layout = self._content_container.layout()
            self._invalidate_and_activate_layout(content_layout)
            refreshed_body_count = self._refresh_card_body_layouts()
            synced_picker_count = self._sync_model_picker_width_groups()
            self.sync_string_width_group()
            self._grid_layout.invalidate()
            self._invalidate_and_activate_layout(content_layout)
            self._invalidate_and_activate_layout(self._grid_layout)
            self.update_height()
            self._warn_if_suspicious_masonry_geometry(reason=reason)
        except RuntimeError as error:
            log_warning(
                _LOGGER,
                "Failed cube-section layout finalization",
                cube_alias=cube_alias,
                reason=reason,
                width_before=width_before,
                height_before=height_before,
                error_type=type(error).__name__,
            )
            raise
        log_timing(
            _LOGGER,
            "Finalized cube-section layout",
            started_at=started_at,
            level="debug",
            cube_alias=cube_alias,
            reason=reason,
            width_before=width_before,
            height_before=height_before,
            resolved_height=self._resolved_height,
            masonry_item_count=self._grid_layout.count(),
            refreshed_body_count=refreshed_body_count,
            synced_model_picker_card_count=synced_picker_count,
            visible=self._section.isVisible(),
        )

    def _string_width_group_fields(self) -> list[QWidget]:
        """Return live node-card single-line string inputs under this cube."""

        return [
            widget
            for widget in self._section.findChildren(QWidget)
            if self._is_string_width_group_field(widget)
        ]

    @staticmethod
    def _is_string_width_group_field(widget: QWidget) -> bool:
        """Return whether one widget participates in cube string width grouping."""

        metadata = widget.property("input_metadata")
        return (
            widget.__class__.__name__ == "LineEdit"
            and isinstance(metadata, Mapping)
            and metadata.get("type") == "STRING"
        )

    def _release_string_width_caps(self, fields: list[QWidget]) -> None:
        """Remove prior shared caps so wider layouts can be measured."""

        for field in fields:
            if not is_live_widget(field):
                continue
            field.setMinimumWidth(0)
            field.setMaximumWidth(_QT_WIDGET_MAXIMUM_SIZE)
            self._set_field_alignment(field, Qt.AlignmentFlag.AlignVCenter)
            field.updateGeometry()

    @staticmethod
    def _set_field_alignment(field: QWidget, alignment: Qt.AlignmentFlag) -> None:
        """Set parent-layout alignment for a grouped string line edit."""

        parent = field.parentWidget()
        if parent is None or not is_live_widget(parent):
            return
        layout = parent.layout()
        if layout is not None:
            layout.setAlignment(field, alignment)

    def _activate_width_layouts(self, fields: list[QWidget]) -> None:
        """Ask affected layouts to recompute before measuring field widths."""

        layouts: list[QLayout] = []
        seen_layout_ids: set[int] = set()
        for widget in (self._section, self._content_container, *fields):
            if not is_live_widget(widget):
                continue
            current: QWidget | None = widget
            while current is not None and is_live_widget(current):
                layout = current.layout()
                if layout is not None and id(layout) not in seen_layout_ids:
                    seen_layout_ids.add(id(layout))
                    layouts.append(layout)
                if current is self._section:
                    break
                current = current.parentWidget()
        self._grid_layout.invalidate()
        for layout in layouts:
            layout.invalidate()
        for layout in reversed(layouts):
            layout.activate()

    def _refresh_card_body_layouts(self) -> int:
        """Resolve registered card-body heights without changing collapse state."""

        refreshed = 0
        for binding in self._registered_card_mode_bindings():
            content_body = getattr(binding, "content_body", None)
            content_layout = getattr(binding, "content_layout", None)
            if (
                content_body is None
                or content_layout is None
                or not is_live_widget(content_body)
            ):
                continue
            content_layout.invalidate()
            allow_unbounded = bool(
                getattr(binding, "allow_unbounded_content_height", False)
            )
            expanded_height = resolve_card_body_expanded_height(
                content_layout=content_layout,
                allow_unbounded_height=allow_unbounded,
            )
            state = ensure_card_body_layout_state(
                content_body=content_body,
                expanded_height=expanded_height,
            )
            apply_card_body_layout_state(
                content_body=content_body,
                state=state,
                allow_unbounded_height=allow_unbounded,
                preserve_animation_height=True,
            )
            content_body.updateGeometry()
            refreshed += 1
        return refreshed

    def _sync_model_picker_width_groups(self) -> int:
        """Synchronously settle card-local model-picker width groups."""

        synced = 0
        for widget in self._section.findChildren(QWidget):
            sync_width_group = getattr(widget, "sync_model_picker_width_group", None)
            if callable(sync_width_group) and is_live_widget(widget):
                sync_width_group()
                synced += 1
        return synced

    def _registered_card_mode_bindings(self) -> tuple[object, ...]:
        """Return registered node-card mode bindings for this cube section."""

        alias = self._cube_alias()
        if not alias:
            return ()
        current: QWidget | None = self._section
        while current is not None and is_live_widget(current):
            controller = getattr(current, "_node_card_mode_controller", None)
            bindings_for_alias = getattr(controller, "bindings_for_alias", None)
            if callable(bindings_for_alias):
                return tuple(bindings_for_alias(alias))
            current = current.parentWidget()
        return ()

    def _cube_alias(self) -> str:
        """Return the cube alias assigned to this section when available."""

        alias = self._section.property("cube_alias")
        if isinstance(alias, str) and alias:
            return alias
        object_name = self._section.objectName()
        prefix = "CubePanel-"
        return object_name[len(prefix) :] if object_name.startswith(prefix) else ""

    @staticmethod
    def _invalidate_and_activate_layout(layout: QLayout | None) -> None:
        """Invalidate and synchronously activate one live Qt layout."""

        if layout is not None and is_live_widget(layout):
            layout.invalidate()
            layout.activate()

    def _warn_if_suspicious_masonry_geometry(self, *, reason: str) -> None:
        """Log visible masonry geometry that still resembles overlap."""

        seen: set[tuple[int, int, int, int]] = set()
        duplicates = 0
        visible_count = 0
        for index in range(self._grid_layout.count()):
            item = self._grid_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is None or not is_live_widget(widget) or not widget.isVisible():
                continue
            visible_count += 1
            geometry = widget.geometry()
            signature = (
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
            )
            if geometry.width() <= 0 or geometry.height() <= 0:
                continue
            if signature in seen:
                duplicates += 1
            seen.add(signature)
        if duplicates:
            log_warning(
                _LOGGER,
                "Detected duplicate visible masonry card geometry after finalization",
                cube_alias=self._cube_alias(),
                reason=reason,
                visible_item_count=visible_count,
                duplicate_geometry_count=duplicates,
            )
        if visible_count and self._resolved_height == 0:
            log_warning(
                _LOGGER,
                "Resolved zero-height cube section with visible masonry cards",
                cube_alias=self._cube_alias(),
                reason=reason,
                visible_item_count=visible_count,
            )


__all__ = ["CubeSectionLayoutController", "is_live_widget"]
