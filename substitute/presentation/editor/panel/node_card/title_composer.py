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

"""Compose node-card title presentation and interactive controls."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import IconWidget

try:
    from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - test-stub fallback only

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
        """Provide a no-op font helper when qfluentwidgets is unavailable."""


from substitute.application.node_behavior import (
    NodeDisplayDecision,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
    TitleControl,
)
from substitute.domain.localization import NodePresentation
from substitute.presentation.editor.field_actions import FieldActionContribution
from substitute.presentation.editor.panel.factories.meta_factories import (
    build_enabled_switch,
)
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetSource,
)
from substitute.presentation.editor.panel.menus.node_title_preset_actions import (
    NodeInputPresetContext,
)
from substitute.presentation.editor.panel.node_card.action_menu import (
    NodeCardActionMenuBinding,
)
from substitute.presentation.editor.panel.node_card.activation_control import (
    apply_node_activation_change,
)
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
)
from substitute.presentation.editor.panel.node_card.advanced_input_binding import (
    AdvancedInputCardBinding,
)
from substitute.presentation.editor.panel.node_card.mode_controller import (
    apply_title_row_interaction,
)
from substitute.presentation.editor.panel.node_card.panel_snapshot import (
    NodePanelSnapshot,
)
from substitute.presentation.editor.panel.node_card.title_link_resolver import (
    resolve_title_node_link_endpoint,
)
from substitute.presentation.editor.panel.node_presentation_binding import (
    NodeTitleTextTarget,
)
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle
from substitute.presentation.editor.panel.widgets.field_row_geometry import (
    EDITOR_ROW_HORIZONTAL_MARGINS,
    EDITOR_ROW_SPACING,
)
from substitute.presentation.editor.panel.widgets.node_card import (
    NODE_CARD_TITLE_HEIGHT,
    NODE_CARD_TITLE_ICON_SIZE,
    NODE_CARD_TITLE_ICON_SLOT_SIZE,
    _NODE_CARD_SURFACE_VERTICAL_PADDING,
    _NodeCardHeaderSurface,
)
from substitute.presentation.qt_label_text import literal_label_text
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.widgets.tooltips import (
    bind_fluent_tooltip,
    normalized_tooltip,
)


class NodeCardTitleComposer:
    """Build localized node-card headers and their title-owned interactions."""

    ICONS = {
        "application": FIF.APPLICATION,
        "edit": FIF.EDIT,
        "eraser": AppIcon.ERASER_20_REGULAR,
        "folder": FIF.FOLDER,
        "model": AppIcon.BRAIN_CIRCUIT_20_REGULAR,
        "palette": FIF.PALETTE,
        "photo": FIF.PHOTO,
    }

    def __init__(
        self,
        panel: Any,
        services: EditorPanelServiceBundle,
        node_input_preset_source: NodeInputPresetSource | None,
    ) -> None:
        """Capture title presentation, behavior, and preset collaborators."""

        self._panel = panel
        self._services = services
        self._node_input_preset_source = node_input_preset_source

    def create(
        self,
        *,
        node_name: str,
        resolved_behavior: ResolvedNodeBehavior,
        display_decision: NodeDisplayDecision | None,
        snapshot: NodePanelSnapshot,
        no_chevron: bool,
        cube_state: Any,
        parent: QWidget | None,
        node_type: str,
        inputs: Mapping[str, object],
        field_specs: Mapping[str, ResolvedFieldSpec],
        node_presentation: NodePresentation,
        advanced_input_binding: AdvancedInputCardBinding | None,
        field_action_contributions: tuple[FieldActionContribution, ...],
    ) -> tuple[QWidget, AccordionChevronWidget | None]:
        """Build a complete title row from resolved presentation and behavior."""

        card_parent = parent if parent is not None else self._panel
        card_title = _NodeCardHeaderSurface(card_parent)
        card_title.setFixedHeight(NODE_CARD_TITLE_HEIGHT)
        title_layout = QHBoxLayout(card_title)
        title_layout.setContentsMargins(
            EDITOR_ROW_HORIZONTAL_MARGINS[0],
            _NODE_CARD_SURFACE_VERTICAL_PADDING,
            EDITOR_ROW_HORIZONTAL_MARGINS[2],
            _NODE_CARD_SURFACE_VERTICAL_PADDING,
        )
        title_layout.setSpacing(EDITOR_ROW_SPACING)

        title_icon = self._build_icon(
            self._resolve_icon(resolved_behavior.card.icon_name),
            parent=card_title,
        )
        title_layout.addWidget(title_icon)
        title_label = CaptionLabel(literal_label_text(node_presentation.title))
        setFont(title_label, 14, QFont.Weight.DemiBold)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        bind_fluent_tooltip(
            card_title,
            normalized_tooltip(node_presentation.card_tooltip),
            card_title,
            title_icon,
            title_label,
            show_delay_ms=600,
        )
        card_title.set_interactive_targets((title_icon, title_label))
        setattr(
            card_title,
            "_node_title_text_target",
            NodeTitleTextTarget(
                owner=card_title,
                label=title_label,
                tooltip_targets=(card_title, title_icon, title_label),
            ),
        )
        self._register_link_surface(
            card_title=card_title,
            title_layout=title_layout,
            node_name=node_name,
            resolved_behavior=resolved_behavior,
            snapshot=snapshot,
        )
        enabled_switch_wrapper = self._build_enabled_switch(
            card_title=card_title,
            title_layout=title_layout,
            node_name=node_name,
            display_decision=display_decision,
            snapshot=snapshot,
            cube_state=cube_state,
        )
        setattr(card_title, "_enabled_switch_wrapper", enabled_switch_wrapper)
        setattr(
            card_title,
            "_enabled_switch_widget",
            getattr(enabled_switch_wrapper, "_enabled_switch_widget", None),
        )
        apply_title_row_interaction(
            title_row=card_title,
            accordion_callback=None,
            enabled_switch=getattr(card_title, "_enabled_switch_widget", None),
            enabled_switch_wrapper=enabled_switch_wrapper,
        )
        self._bind_action_menu(
            card_title=card_title,
            title_layout=title_layout,
            snapshot=snapshot,
            node_name=node_name,
            node_type=node_type,
            inputs=inputs,
            field_specs=field_specs,
            cube_state=cube_state,
            advanced_input_binding=advanced_input_binding,
            field_action_contributions=field_action_contributions,
        )
        if no_chevron:
            return card_title, None
        chevron = AccordionChevronWidget(card_title)
        title_layout.addWidget(chevron)
        card_title.set_interactive_targets((title_icon, title_label, chevron))
        return card_title, chevron

    def _register_link_surface(
        self,
        *,
        card_title: QWidget,
        title_layout: QHBoxLayout,
        node_name: str,
        resolved_behavior: ResolvedNodeBehavior,
        snapshot: NodePanelSnapshot,
    ) -> None:
        """Register a title-level node-link selector when behavior requests one."""

        title_controls = resolved_behavior.card.title_controls
        if not (
            TitleControl.NODE_LINK_SELECTOR in title_controls
            or TitleControl.PROMPT_LINK_SELECTOR in title_controls
        ):
            return
        behavior_snapshot = self._panel.current_behavior_snapshot()
        endpoint_index = (
            behavior_snapshot.node_link_endpoint_index
            if behavior_snapshot is not None
            else None
        )
        if endpoint_index is None or snapshot.current_alias is None:
            return
        endpoint = resolve_title_node_link_endpoint(
            endpoint_index=endpoint_index,
            cube_alias=snapshot.current_alias,
            node_name=node_name,
            resolved_behavior=resolved_behavior,
        )
        if endpoint is None:
            return
        meta_registry = getattr(self._panel, "meta_registry", None)
        register = getattr(meta_registry, "register_node_link_title_surface", None)
        if callable(register):
            register(
                cube_alias=snapshot.current_alias,
                node_name=node_name,
                identity=endpoint.identity,
                title_layout=title_layout,
                title_controls=title_controls,
            )
        refresh = getattr(meta_registry, "update_node_link_widgets_for_cube", None)
        if callable(refresh):
            refresh(snapshot.current_alias)

    def _build_enabled_switch(
        self,
        *,
        card_title: QWidget,
        title_layout: QHBoxLayout,
        node_name: str,
        display_decision: NodeDisplayDecision | None,
        snapshot: NodePanelSnapshot,
        cube_state: Any,
    ) -> QWidget | None:
        """Build and append the behavior-owned activation switch when requested."""

        if display_decision is None or not display_decision.show_enabled_switch:
            return None
        wrapper = build_enabled_switch(
            card_title,
            snapshot.current_alias,
            node_name,
            cube_state,
            display_decision,
            checked_changed_callback=partial(
                apply_node_activation_change,
                self._panel,
                self._services,
                cube_state,
                node_name,
                display_decision,
            ),
        )
        title_layout.addWidget(wrapper)
        return wrapper

    def _bind_action_menu(
        self,
        *,
        card_title: QWidget,
        title_layout: QHBoxLayout,
        snapshot: NodePanelSnapshot,
        node_name: str,
        node_type: str,
        inputs: Mapping[str, object],
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: Any,
        advanced_input_binding: AdvancedInputCardBinding | None,
        field_action_contributions: tuple[FieldActionContribution, ...],
    ) -> None:
        """Bind presets, advanced inputs, and contributed actions to the title."""

        input_widgets = getattr(self._panel, "input_widgets_by_field_key", {})
        if not isinstance(input_widgets, Mapping):
            input_widgets = {}
        is_connection = getattr(self._panel, "is_connection", None)
        NodeCardActionMenuBinding.create(
            title_row=card_title,
            title_layout=title_layout,
            preset_context=NodeInputPresetContext(
                cube_alias=snapshot.current_alias,
                node_name=node_name,
                node_type=node_type,
                inputs=inputs,
                field_specs=field_specs,
                cube_state=cube_state,
                input_widgets_by_field_key=input_widgets,
            ),
            preset_source=self._node_input_preset_source,
            dialog_parent=self._preset_dialog_parent,
            is_connection=is_connection if callable(is_connection) else None,
            advanced_inputs=advanced_input_binding,
            field_action_contributions=field_action_contributions,
        )

    def _build_icon(self, icon_enum: Any | None, *, parent: QWidget) -> QWidget:
        """Return a fixed title-icon slot with the icon centered inside it."""

        slot = QWidget(parent)
        slot.setObjectName("NodeCardTitleIconSlot")
        slot.setFixedSize(
            NODE_CARD_TITLE_ICON_SLOT_SIZE,
            NODE_CARD_TITLE_ICON_SLOT_SIZE,
        )
        if icon_enum is None:
            return slot
        icon = IconWidget(icon_enum, slot)
        icon.setObjectName("NodeCardTitleIcon")
        icon.setFixedSize(NODE_CARD_TITLE_ICON_SIZE, NODE_CARD_TITLE_ICON_SIZE)
        slot_layout = QHBoxLayout(slot)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(0)
        slot_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
        return slot

    def _resolve_icon(self, icon_name: str | None) -> Any | None:
        """Return the mapped Fluent icon for one behavior icon name."""

        return self.ICONS.get(icon_name) if isinstance(icon_name, str) else None

    def _preset_dialog_parent(self) -> QWidget:
        """Return the widget that should own node preset save modals."""

        return self._panel if isinstance(self._panel, QWidget) else QWidget()


__all__ = ["NodeCardTitleComposer"]
