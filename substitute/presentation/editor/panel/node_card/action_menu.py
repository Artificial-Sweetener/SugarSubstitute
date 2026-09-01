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
from substitute.presentation.editor.panel.node_card.advanced_input_binding import (
    AdvancedInputCardBinding,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)

_NODE_ACTIONS = "Node actions"
_SHOW_ADVANCED_INPUTS = app_text("Show advanced inputs")
_HIDE_ADVANCED_INPUTS = app_text("Hide advanced inputs")
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
    """Compose presets and advanced visibility into one title-bar menu."""

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
        binding = cls(
            title_row=title_row,
            preset_context=preset_context,
            preset_source=preset_source,
            dialog_parent=dialog_parent,
            is_connection=is_connection,
            advanced_inputs=advanced_inputs,
        )
        if binding.current_menu_model() is None:
            binding.deleteLater()
            return None
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
    ) -> None:
        """Retain action sources and create the menu's sole entry button."""

        super().__init__(title_row)
        self._title_row = title_row
        self._preset_context = preset_context
        self._preset_source = preset_source
        self._dialog_parent = dialog_parent
        self._is_connection = is_connection
        self._advanced_inputs = advanced_inputs
        self._active_menu: object | None = None
        self.button = NodeCardActionMenuButton(title_row)
        self.button.clicked.connect(self.show_menu)

    def show_menu(self) -> None:
        """Build current actions and open their Fluent menu below the gear."""

        model = self.current_menu_model()
        if model is None:
            return
        menu = QFluentMenuRenderer(parent=self.button).render(model)
        self._active_menu = menu
        menu.exec(self.button.mapToGlobal(QPoint(0, self.button.height())))

    def current_menu_model(self) -> MenuModel | None:
        """Return the current unified menu model, or no model when empty."""

        entries = self._entries()
        if not entries:
            return None
        return MenuModel(entries=entries, object_name="NodeCardActionMenu")

    def _entries(self) -> tuple[MenuEntry, ...]:
        """Return current preset entries followed by advanced visibility."""

        entries = list(
            node_input_preset_menu_entries(
                menu_parent=self._title_row,
                context=self._preset_context,
                preset_source=self._preset_source,
                dialog_parent=self._dialog_parent,
                is_connection=self._is_connection,
            )
        )
        if self._advanced_inputs is None:
            return tuple(entries)
        if entries:
            entries.append(MenuSeparator())
        entries.append(
            MenuItem(
                "node.advanced_inputs.toggle",
                (
                    _HIDE_ADVANCED_INPUTS
                    if self._advanced_inputs.shown
                    else _SHOW_ADVANCED_INPUTS
                ),
                callback=self._advanced_inputs.toggle,
            )
        )
        return tuple(entries)


__all__ = ["NodeCardActionMenuBinding", "NodeCardActionMenuButton"]
