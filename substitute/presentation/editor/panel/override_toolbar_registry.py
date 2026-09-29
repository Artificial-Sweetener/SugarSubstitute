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

"""Own mounted global-override toolbar controls and their layout order."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.panel.overrides_controller")


class OverrideToolbarRegistry:
    """Keep mounted control identity, signatures, and layout attachment atomic."""

    def __init__(
        self,
        mainwindow: Any,
        dropdown_button: Callable[[], object | None],
    ) -> None:
        """Store the toolbar layout boundary and dynamic insertion anchor."""

        self._mainwindow = mainwindow
        self._dropdown_button = dropdown_button
        self.controls: dict[str, tuple[Any, Any]] = {}
        self._control_signatures: dict[str, tuple[object, ...]] = {}
        self.active_signature: tuple[tuple[object, ...], ...] | None = None

    def control(self, override_key: str) -> tuple[Any, Any] | None:
        """Return one mounted label/control pair."""

        return self.controls.get(override_key)

    def control_signature(self, override_key: str) -> tuple[object, ...] | None:
        """Return the realization signature for one mounted control."""

        return self._control_signatures.get(override_key)

    def register(
        self,
        override_key: str,
        label_widget: Any,
        widget: Any,
        signature: tuple[object, ...],
    ) -> None:
        """Publish one realized label/control pair and its signature."""

        self.controls[override_key] = (label_widget, widget)
        self._control_signatures[override_key] = signature

    def remove(self, override_key: str) -> bool:
        """Remove and dispose one toolbar label/control pair when present."""

        control = self.controls.pop(override_key, None)
        if control is None:
            return False
        label_widget, widget = control
        self._control_signatures.pop(override_key, None)
        self.active_signature = None
        layout = self._mainwindow.menu_bar_layout
        layout.removeWidget(label_widget)
        self._hide_widget(label_widget)
        label_widget.deleteLater()
        layout.removeWidget(widget)
        self._hide_widget(widget)
        widget.deleteLater()
        return True

    def detach(self) -> None:
        """Detach cached controls from the shared menu bar without disposal."""

        layout = self._mainwindow.menu_bar_layout
        for label_widget, widget in self.controls.values():
            if layout.indexOf(label_widget) >= 0:
                layout.removeWidget(label_widget)
            self._hide_widget(label_widget)
            if layout.indexOf(widget) >= 0:
                layout.removeWidget(widget)
            self._hide_widget(widget)

    def clear(self) -> None:
        """Dispose every mounted override control and reset signatures."""

        for override_key in list(self.controls):
            self.remove(override_key)
        self.controls.clear()
        self._control_signatures.clear()
        self.active_signature = None

    def insert(
        self,
        *,
        override_key: str,
        label_widget: Any,
        widget: Any,
        active_keys: tuple[str, ...],
    ) -> None:
        """Insert one label/control pair in semantic active-control order."""

        layout = self._mainwindow.menu_bar_layout
        for existing_widget in (label_widget, widget):
            if layout.indexOf(existing_widget) >= 0:
                layout.removeWidget(existing_widget)
        base_index = self._insert_base_index(layout)
        preceding_keys = (
            active_keys[: active_keys.index(override_key)]
            if override_key in active_keys
            else ()
        )
        insert_index = base_index
        for existing_key in preceding_keys:
            existing_control = self.controls.get(existing_key)
            if existing_control is None:
                continue
            insert_index = max(insert_index, layout.indexOf(existing_control[1]) + 1)
        log_debug(
            _LOGGER,
            "insert override widget",
            override_key=override_key,
            base_index=base_index,
            insert_index=insert_index,
            active_keys=active_keys,
            preceding_keys=preceding_keys,
            label_widget_type=type(label_widget).__name__,
            widget_type=type(widget).__name__,
        )
        layout.insertWidget(insert_index, label_widget)
        layout.insertWidget(insert_index + 1, widget)
        self._show_widget(label_widget)
        self._show_widget(widget)

    def all_attached(self, active_by_key: Mapping[str, object]) -> bool:
        """Return whether all active cached controls are mounted."""

        layout = self._mainwindow.menu_bar_layout
        for override_key in active_by_key:
            existing_control = self.controls.get(override_key)
            if existing_control is None:
                return False
            label_widget, widget = existing_control
            if layout.indexOf(label_widget) < 0 or layout.indexOf(widget) < 0:
                return False
        return True

    def _insert_base_index(self, layout: Any) -> int:
        """Return the first layout index available for override controls."""

        dropdown_button = self._dropdown_button()
        anchor_widget = None
        if dropdown_button is not None:
            property_getter = getattr(dropdown_button, "property", None)
            if callable(property_getter):
                anchor_widget = property_getter("layoutAnchorWidget")
        for candidate in (anchor_widget, dropdown_button):
            if candidate is None:
                continue
            index = int(layout.indexOf(candidate))
            if index >= 0:
                return index + 1
        return 0

    @staticmethod
    def _hide_widget(widget: Any) -> None:
        """Hide a detached toolbar widget when supported."""

        hide = getattr(widget, "hide", None)
        if callable(hide):
            hide()

    @staticmethod
    def _show_widget(widget: Any) -> None:
        """Show a mounted toolbar widget when supported."""

        show = getattr(widget, "show", None)
        if callable(show):
            show()


__all__ = ["OverrideToolbarRegistry"]
