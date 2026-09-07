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

"""Own the single Fluent action menu exposed by a node-card title bar."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QObject, QPoint, QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import TransparentToolButton  # type: ignore[import-untyped]

from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetSource,
)
from substitute.presentation.editor.panel.menus.node_title_preset_actions import (
    NodeInputPresetContext,
    node_input_preset_menu_entries,
)
from substitute.presentation.editor.field_actions import (
    FieldActionContribution,
    FieldActionContext,
)
from substitute.presentation.editor.panel.node_card.advanced_input_binding import (
    AdvancedInputCardBinding,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.widgets.menu_button_controller import (
    MenuButtonController,
)
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.widgets.qfluent_submenu_interaction import (
    install_submenu_click_openers,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)

_NODE_ACTIONS = "Node actions"
_SHOW_ADVANCED_INPUTS = app_text("Show advanced inputs")
_BUTTON_SIZE = 28
_ICON_SIZE = 20


class NodeCardActionMenuButton(TransparentToolButton):  # type: ignore[misc]
    """Render the Fluent gear that owns all node-card menu actions."""

    def __init__(self, parent: QWidget) -> None:
        """Create a compact accessible gear button for the title bar."""

        super().__init__(parent)
        self.setIcon(AppIcon.SETTINGS_20_REGULAR)
        self.setObjectName("NodeCardActionMenuButton")
        self.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        self.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_localized_tooltip(self, _NODE_ACTIONS)
        set_localized_accessible_name(self, _NODE_ACTIONS)


class NodeCardActionMenuBinding(QObject):
    """Compose node and field actions directly into one title-bar menu."""

    @classmethod
    def create(
        cls,
        *,
        title_row: QWidget,
        title_layout: QHBoxLayout,
        preset_context: NodeInputPresetContext,
        preset_source: NodeInputPresetSource | None,
        dialog_parent: Callable[[], QWidget],
        is_connection: Callable[[object], bool] | None,
        advanced_inputs: AdvancedInputCardBinding | None,
        field_action_contributions: tuple[FieldActionContribution, ...] = (),
    ) -> NodeCardActionMenuBinding | None:
        """Create a gear only when the node currently exposes a menu action."""

        prepare_menu = getattr(
            preset_source,
            "prepare_node_input_preset_menu_model",
            None,
        )
        if callable(prepare_menu):
            prepare_menu(
                node_type=preset_context.node_type,
                reason="node_card_built",
            )
        node_preset_entries = node_input_preset_menu_entries(
            menu_parent=title_row,
            context=preset_context,
            preset_source=preset_source,
            dialog_parent=dialog_parent,
            is_connection=is_connection,
        )
        if not _has_available_actions(
            node_preset_entries=node_preset_entries,
            advanced_inputs=advanced_inputs,
            field_action_contributions=field_action_contributions,
        ):
            return None
        binding = cls(
            title_row=title_row,
            preset_context=preset_context,
            preset_source=preset_source,
            dialog_parent=dialog_parent,
            is_connection=is_connection,
            advanced_inputs=advanced_inputs,
            field_action_contributions=field_action_contributions,
        )
        title_layout.addWidget(binding.button)
        setattr(title_row, "_node_card_action_menu_binding", binding)
        return binding

    def __init__(
        self,
        *,
        title_row: QWidget,
        preset_context: NodeInputPresetContext,
        preset_source: NodeInputPresetSource | None,
        dialog_parent: Callable[[], QWidget],
        is_connection: Callable[[object], bool] | None,
        advanced_inputs: AdvancedInputCardBinding | None,
        field_action_contributions: tuple[FieldActionContribution, ...] = (),
    ) -> None:
        """Retain action sources and create the menu's sole entry button."""

        super().__init__(title_row)
        self._title_row = title_row
        self._preset_context = preset_context
        self._preset_source = preset_source
        self._dialog_parent = dialog_parent
        self._is_connection = is_connection
        self._advanced_inputs = advanced_inputs
        self._field_action_contributions = field_action_contributions
        self.button = NodeCardActionMenuButton(title_row)
        self._menu_controller = MenuButtonController(
            self.button,
            menu_position=self._menu_position,
        )
        self._menu_controller.set_menu_factory(self._build_menu)

    def _menu_position(self) -> QPoint:
        """Return the current global anchor below the node-card gear."""

        return cast(QPoint, self.button.mapToGlobal(QPoint(0, self.button.height())))

    def _build_menu(self) -> object | None:
        """Render the current node actions for one legitimate open request."""

        anchor_global_position = self._menu_position()
        model = self.current_menu_model(
            FieldActionContext(anchor_global_position=anchor_global_position)
        )
        if model is None:
            return None
        menu = QFluentMenuRenderer(parent=self.button).render(model)
        install_submenu_click_openers(menu)
        return cast(object, menu)

    def current_menu_model(
        self,
        context: FieldActionContext | None = None,
    ) -> MenuModel | None:
        """Return the current unified menu model, or no model when empty."""

        entries = self._entries(
            context
            or FieldActionContext(
                anchor_global_position=self.button.mapToGlobal(
                    QPoint(0, self.button.height())
                )
            )
        )
        if not entries:
            return None
        return MenuModel(entries=entries, object_name="NodeCardActionMenu")

    def _entries(self, context: FieldActionContext) -> tuple[MenuEntry, ...]:
        """Return current node, field, and advanced actions in stable order."""

        entries = list(self._node_preset_entries())
        for contribution in self._field_action_contributions:
            field_entries = contribution.entries(context)
            if not field_entries:
                continue
            if entries:
                entries.append(MenuSeparator())
            entries.extend(field_entries)
        if self._advanced_inputs is None:
            return tuple(entries)
        if entries:
            entries.append(MenuSeparator())
        entries.append(
            MenuItem(
                "node.advanced_inputs.toggle",
                _SHOW_ADVANCED_INPUTS,
                checkable=True,
                checked=self._advanced_inputs.shown,
                checked_callback=self._advanced_inputs.set_shown,
            )
        )
        return tuple(entries)

    def _node_preset_entries(self) -> tuple[MenuEntry, ...]:
        """Return node-owned preset actions available to the cog."""

        return node_input_preset_menu_entries(
            menu_parent=self._title_row,
            context=self._preset_context,
            preset_source=self._preset_source,
            dialog_parent=self._dialog_parent,
            is_connection=self._is_connection,
        )


def _has_available_actions(
    *,
    node_preset_entries: tuple[MenuEntry, ...],
    advanced_inputs: AdvancedInputCardBinding | None,
    field_action_contributions: tuple[FieldActionContribution, ...],
) -> bool:
    """Return whether constructing a node-card action button is warranted."""

    if node_preset_entries or advanced_inputs is not None:
        return True
    return any(
        contribution.is_available() for contribution in field_action_contributions
    )


__all__ = ["NodeCardActionMenuBinding", "NodeCardActionMenuButton"]
