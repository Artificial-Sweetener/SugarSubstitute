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

"""Apply linked and independent presentation modes to existing node cards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Mapping

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import NodeDisplayDecision
from .accordion_motion import (
    AccordionChevronWidget,
    AccordionMotionController,
    set_accordion_surface_attachment,
)
from .body_layout import (
    ensure_card_body_layout_state,
    resolve_card_body_expanded_height,
    set_card_body_forced_collapsed,
)


@dataclass(frozen=True)
class NodeCardModeBinding:
    """Collect the existing widgets that linked-mode refreshes may alter."""

    wrapper: QWidget
    title_row: QWidget
    content_body: QWidget | None
    content_layout: QVBoxLayout | None
    chevron: AccordionChevronWidget | None
    enabled_switch_wrapper: QWidget | None
    enabled_switch: Any | None
    accordion_controller: AccordionMotionController | None
    collapsible: bool
    has_rows: bool
    allow_unbounded_content_height: bool


class NodeCardModeController:
    """Own per-card linked-mode presentation without rebuilding cube sections."""

    def __init__(self) -> None:
        """Initialize an empty card-binding registry."""

        self._bindings: dict[tuple[str, str], NodeCardModeBinding] = {}

    def register(
        self,
        alias: str | None,
        node_name: str,
        binding: NodeCardModeBinding,
    ) -> None:
        """Register one card binding when it has a concrete cube alias."""

        if alias is None:
            return
        self._bindings[(alias, node_name)] = binding

    def clear(self) -> None:
        """Forget all registered bindings after the panel layout is cleared."""

        self._bindings.clear()

    def rename_alias(self, old_alias: str, new_alias: str) -> None:
        """Migrate registered card bindings after a cube alias changes."""

        for key, binding in list(self._bindings.items()):
            alias, node_name = key
            if alias != old_alias:
                continue
            new_key = (new_alias, node_name)
            self._bindings[new_key] = self._bindings.pop(key)
            set_property = getattr(binding.wrapper, "setProperty", None)
            if callable(set_property):
                set_property("cube_alias", new_alias)

    def bindings_for_alias(self, alias: str) -> tuple[NodeCardModeBinding, ...]:
        """Return live card-mode bindings currently registered for one cube alias."""

        return tuple(
            binding
            for (registered_alias, _node_name), binding in self._bindings.items()
            if registered_alias == alias and self._is_live_widget(binding.wrapper)
        )

    def apply_decisions(
        self,
        decisions_by_alias: Mapping[str, Mapping[str, NodeDisplayDecision]],
    ) -> None:
        """Apply linked/independent mode for every currently registered card."""

        for alias, per_node in decisions_by_alias.items():
            for node_name, decision in per_node.items():
                binding = self._bindings.get((alias, node_name))
                if binding is None or not self._is_live_widget(binding.wrapper):
                    continue
                self._apply_binding(binding, decision)

    def _apply_binding(
        self,
        binding: NodeCardModeBinding,
        decision: NodeDisplayDecision,
    ) -> None:
        """Apply one behavior decision to one existing card binding."""

        linked = decision.node_link_active
        self._sync_enabled_switch(binding, decision)
        self._set_widget_visible(
            binding.enabled_switch_wrapper,
            decision.show_enabled_switch and not linked,
        )
        self._set_widget_visible(
            binding.chevron,
            binding.collapsible and binding.has_rows and not linked,
        )
        self._set_title_interaction(binding, linked=linked)
        self._set_body_mode(binding, linked=linked)
        self._refresh_owner_cube_height(binding.wrapper)

    @classmethod
    def _sync_enabled_switch(
        cls,
        binding: NodeCardModeBinding,
        decision: NodeDisplayDecision,
    ) -> None:
        """Update the switch checked state without emitting activation changes."""

        switch = binding.enabled_switch
        if switch is None or not cls._is_live_widget(switch):
            return
        block_signals = getattr(switch, "blockSignals", None)
        set_checked = getattr(switch, "setChecked", None)
        if not callable(block_signals) or not callable(set_checked):
            return
        was_blocked = bool(block_signals(True))
        try:
            set_checked(bool(decision.enabled))
        finally:
            block_signals(was_blocked)

    @classmethod
    def _set_widget_visible(cls, widget: object | None, visible: bool) -> None:
        """Set widget visibility when the widget is still valid."""

        if not cls._is_live_widget(widget):
            return
        set_visible = getattr(widget, "setVisible", None)
        if callable(set_visible):
            set_visible(bool(visible))

    def _set_title_interaction(
        self,
        binding: NodeCardModeBinding,
        *,
        linked: bool,
    ) -> None:
        """Enable or suppress title-row accordion interaction."""

        if not self._is_live_widget(binding.title_row):
            return
        if linked:
            apply_title_row_interaction(
                title_row=binding.title_row,
                accordion_callback=None,
                enabled_switch=None,
                enabled_switch_wrapper=None,
            )
            return
        if binding.collapsible and binding.accordion_controller is not None:
            controller = binding.accordion_controller

            def toggle_card() -> None:
                """Toggle the bound accordion controller."""

                controller.toggle()

            apply_title_row_interaction(
                title_row=binding.title_row,
                accordion_callback=toggle_card,
                enabled_switch=binding.enabled_switch,
                enabled_switch_wrapper=binding.enabled_switch_wrapper,
            )
            return
        apply_title_row_interaction(
            title_row=binding.title_row,
            accordion_callback=None,
            enabled_switch=binding.enabled_switch,
            enabled_switch_wrapper=binding.enabled_switch_wrapper,
        )

    def _set_body_mode(
        self,
        binding: NodeCardModeBinding,
        *,
        linked: bool,
    ) -> None:
        """Collapse or restore the card body without destroying row widgets."""

        content_body = binding.content_body
        content_layout = binding.content_layout
        if (
            content_body is None
            or content_layout is None
            or not self._is_live_widget(content_body)
        ):
            return
        expanded_height = resolve_card_body_expanded_height(
            content_layout=content_layout,
            allow_unbounded_height=binding.allow_unbounded_content_height,
        )
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=expanded_height,
        )
        if linked:
            set_card_body_forced_collapsed(
                content_body=content_body,
                state=state,
                forced_collapsed=True,
                allow_unbounded_height=binding.allow_unbounded_content_height,
            )
            self._sync_surface_attachment(binding, attached=False)
            return
        set_card_body_forced_collapsed(
            content_body=content_body,
            state=state,
            forced_collapsed=False,
            allow_unbounded_height=binding.allow_unbounded_content_height,
        )
        self._sync_surface_attachment(
            binding,
            attached=not state.collapsed and binding.has_rows,
        )

    def _sync_surface_attachment(
        self,
        binding: NodeCardModeBinding,
        *,
        attached: bool,
    ) -> None:
        """Synchronize optional split-surface corner state after mode changes."""

        content_body = binding.content_body
        if content_body is None or not self._is_live_widget(content_body):
            return
        set_accordion_surface_attachment(
            card_title=binding.title_row,
            content_body=content_body,
            attached=attached,
        )

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
    def _refresh_owner_cube_height(widget: QWidget) -> None:
        """Ask the nearest cube section parent to recompute its height."""

        parent = widget.parentWidget()
        while parent is not None:
            defer_update = getattr(parent, "defer_update_cube_height", None)
            if callable(defer_update):
                defer_update()
                return
            update = getattr(parent, "update_cube_height", None)
            if callable(update):
                update()
                return
            parent = parent.parentWidget()


def apply_title_row_interaction(
    *,
    title_row: QWidget,
    accordion_callback: Callable[[], None] | None,
    enabled_switch: object | None,
    enabled_switch_wrapper: QWidget | None,
) -> None:
    """Apply title-row activation precedence to a header surface when supported."""

    if accordion_callback is not None:
        _set_title_row_activation(title_row, accordion_callback)
        return
    switch_callback = _enabled_switch_toggle_callback(
        enabled_switch=enabled_switch,
        enabled_switch_wrapper=enabled_switch_wrapper,
    )
    if switch_callback is not None:
        _set_title_row_activation(title_row, switch_callback)
        return
    _clear_title_row_activation(title_row)


def _set_title_row_activation(
    title_row: QWidget,
    callback: Callable[[], None],
) -> None:
    """Enable title-row activation through the row-owned API when present."""

    set_activation = getattr(title_row, "set_row_activation", None)
    if callable(set_activation):
        set_activation(callback)
        return
    title_row.setCursor(Qt.CursorShape.PointingHandCursor)


def _clear_title_row_activation(title_row: QWidget) -> None:
    """Clear title-row activation through the row-owned API when present."""

    clear_activation = getattr(title_row, "clear_row_activation", None)
    if callable(clear_activation):
        clear_activation()
        return
    title_row.setCursor(Qt.CursorShape.ArrowCursor)


def _enabled_switch_toggle_callback(
    *,
    enabled_switch: object | None,
    enabled_switch_wrapper: QWidget | None,
) -> Callable[[], None] | None:
    """Return a row callback that delegates to an enabled switch when available."""

    if not _is_live_object(enabled_switch):
        return None
    if _is_hidden(enabled_switch_wrapper) or _is_hidden(enabled_switch):
        return None
    is_checked = getattr(enabled_switch, "isChecked", None)
    set_checked = getattr(enabled_switch, "setChecked", None)
    if not callable(is_checked) or not callable(set_checked):
        return None

    def toggle_switch() -> None:
        """Toggle the existing switch so its signal remains authoritative."""

        set_checked(not bool(is_checked()))

    return toggle_switch


def _is_hidden(widget: object | None) -> bool:
    """Return whether a live widget has been explicitly hidden."""

    if not _is_live_object(widget):
        return False
    is_hidden = getattr(widget, "isHidden", None)
    return bool(is_hidden()) if callable(is_hidden) else False


def _is_live_object(widget: object | None) -> bool:
    """Return whether a Qt object reference can still be used."""

    if widget is None:
        return False
    try:
        return bool(shiboken6.isValid(widget))
    except TypeError:
        return True


__all__ = [
    "NodeCardModeBinding",
    "NodeCardModeController",
    "apply_title_row_interaction",
]
