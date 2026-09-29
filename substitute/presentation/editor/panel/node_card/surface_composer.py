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

"""Compose and mount one node-card surface around its realized rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from substitute.application.localization import NodePresentationService
from substitute.domain.localization import NodePresentationRequest
from substitute.presentation.editor.panel.node_presentation_binding import (
    NodeCardPresentationBinding,
    NodeTitleTextTarget,
)
from substitute.presentation.editor.panel.widgets.node_card import (
    NODE_CARD_BODY_BOTTOM_PADDING,
    NODE_CARD_BODY_ROW_SPACING,
    NODE_CARD_BODY_TOP_PADDING,
    _NodeCardContentSurface,
    _NodeCardSurface,
    NodeCardWidget,
)
from substitute.presentation.editor.utils.create_vbox import create_vbox

from .accordion_motion import (
    AccordionChevronWidget,
    AccordionContentClip,
    AccordionMotionController,
    set_accordion_surface_attachment,
)
from .accordion_section_layout import AccordionSectionLayoutBinding
from .mode_controller import NodeCardModeBinding, apply_title_row_interaction


@dataclass(frozen=True, slots=True)
class NodeCardSurfaceMetadata:
    """Carry searchable and diagnostic properties for one mounted card."""

    cube_alias: str | None
    node_name: str
    node_class_type: str
    variant: str
    has_title_controls: bool
    has_advanced_input_action: bool


@dataclass(frozen=True, slots=True)
class NodeCardSurfaceAssembly:
    """Expose the mutable card surfaces needed while body rows are realized."""

    wrapper: NodeCardWidget
    card: _NodeCardSurface
    card_layout: QVBoxLayout
    content_body: AccordionContentClip
    content_layout: QVBoxLayout
    presentation_binding: NodeCardPresentationBinding
    show_immediately: bool


class NodeCardSurfaceComposer:
    """Own card surface construction, accordion attachment, and mode registration."""

    def __init__(
        self,
        *,
        panel: Any,
        node_presentation_service: NodePresentationService,
        divider_factory: Callable[[QWidget], QWidget],
        reconcile_separators: Callable[[], None],
    ) -> None:
        """Capture mounted-surface collaborators without owning field realization."""

        self._panel = panel
        self._node_presentation_service = node_presentation_service
        self._divider_factory = divider_factory
        self._reconcile_separators = reconcile_separators

    def create(
        self,
        *,
        parent: QWidget,
        presentation_request: NodePresentationRequest,
        show_immediately: bool,
    ) -> NodeCardSurfaceAssembly:
        """Create an unattached wrapper, card, and collapsible body surface."""

        wrapper = NodeCardWidget(parent)
        presentation_binding = NodeCardPresentationBinding(
            owner=wrapper,
            service=self._node_presentation_service,
            request=presentation_request,
        )
        setattr(wrapper, "_node_presentation_binding", presentation_binding)
        card = _NodeCardSurface(wrapper)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        card_layout = create_vbox(
            parent=card,
            margins=(0, 0, 0, 0),
            spacing=0,
        )
        content_body = AccordionContentClip(
            parent=card,
            content_surface_factory=_NodeCardContentSurface,
        )
        content_body.setObjectName("NodeCardContentClip")
        content_layout = create_vbox(
            parent=content_body.content_widget(),
            margins=(0, NODE_CARD_BODY_TOP_PADDING, 0, NODE_CARD_BODY_BOTTOM_PADDING),
            spacing=NODE_CARD_BODY_ROW_SPACING,
        )
        return NodeCardSurfaceAssembly(
            wrapper=wrapper,
            card=card,
            card_layout=card_layout,
            content_body=content_body,
            content_layout=content_layout,
            presentation_binding=presentation_binding,
            show_immediately=show_immediately,
        )

    def mount(
        self,
        *,
        assembly: NodeCardSurfaceAssembly,
        title_row: QWidget,
        title_target: NodeTitleTextTarget | None,
        chevron: AccordionChevronWidget | None,
        metadata: NodeCardSurfaceMetadata,
        has_rows: bool,
        collapsible: bool,
        allow_unbounded_content_height: bool,
    ) -> None:
        """Attach the title/body surface and publish its live mode binding."""

        if title_target is not None:
            assembly.presentation_binding.set_title_target(title_target)
        assembly.card_layout.addWidget(title_row)
        accordion_controller = self._attach_body(
            assembly=assembly,
            title_row=title_row,
            chevron=chevron,
            has_rows=has_rows,
            collapsible=collapsible,
        )
        wrapper_layout = QVBoxLayout(assembly.wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(assembly.card)
        self._register_mode_binding(
            metadata=metadata,
            assembly=assembly,
            title_row=title_row,
            chevron=chevron,
            accordion_controller=accordion_controller,
            collapsible=collapsible,
            has_rows=has_rows,
            allow_unbounded_content_height=allow_unbounded_content_height,
        )
        self._apply_metadata(assembly.wrapper, metadata)
        assembly.presentation_binding.retranslate()
        assembly.wrapper.setVisible(assembly.show_immediately)
        assembly.card.defer_model_picker_width_group_sync()

    def _attach_body(
        self,
        *,
        assembly: NodeCardSurfaceAssembly,
        title_row: QWidget,
        chevron: AccordionChevronWidget | None,
        has_rows: bool,
        collapsible: bool,
    ) -> AccordionMotionController | None:
        """Attach populated body rows and optional accordion behavior."""

        if not has_rows:
            return None
        divider = self._divider_factory(assembly.content_body.content_widget())
        divider.setObjectName("NodeCardTitleBodyDivider")
        divider.setProperty("title_body_divider", True)
        assembly.content_layout.insertWidget(0, divider)
        self._reconcile_separators()
        assembly.content_body.set_content_height(
            assembly.content_layout.sizeHint().height()
        )
        assembly.card_layout.addWidget(assembly.content_body)
        if collapsible:
            return self._setup_collapsible_animation(
                card_title=title_row,
                content_body=assembly.content_body,
                content_layout=assembly.content_layout,
                chevron=chevron,
            )
        set_accordion_surface_attachment(
            card_title=title_row,
            content_body=assembly.content_body,
            attached=True,
        )
        return None

    def _register_mode_binding(
        self,
        *,
        metadata: NodeCardSurfaceMetadata,
        assembly: NodeCardSurfaceAssembly,
        title_row: QWidget,
        chevron: AccordionChevronWidget | None,
        accordion_controller: AccordionMotionController | None,
        collapsible: bool,
        has_rows: bool,
        allow_unbounded_content_height: bool,
    ) -> None:
        """Register the mounted widgets with the panel's card-mode owner."""

        controller = getattr(self._panel, "_node_card_mode_controller", None)
        register = getattr(controller, "register", None)
        if not callable(register):
            return
        enabled_switch_wrapper = getattr(title_row, "_enabled_switch_wrapper", None)
        register(
            metadata.cube_alias,
            metadata.node_name,
            NodeCardModeBinding(
                wrapper=assembly.wrapper,
                title_row=title_row,
                content_body=assembly.content_body if has_rows else None,
                content_layout=assembly.content_layout if has_rows else None,
                chevron=chevron,
                enabled_switch_wrapper=(
                    enabled_switch_wrapper
                    if isinstance(enabled_switch_wrapper, QWidget)
                    else None
                ),
                enabled_switch=getattr(title_row, "_enabled_switch_widget", None),
                accordion_controller=accordion_controller,
                collapsible=collapsible,
                has_rows=has_rows,
                allow_unbounded_content_height=allow_unbounded_content_height,
            ),
        )

    def _setup_collapsible_animation(
        self,
        *,
        card_title: QWidget,
        content_body: AccordionContentClip,
        content_layout: QVBoxLayout,
        chevron: AccordionChevronWidget | None,
    ) -> AccordionMotionController | None:
        """Attach accordion motion and title-row interaction when available."""

        if chevron is None:
            return None
        section_layout = AccordionSectionLayoutBinding(card_title)
        controller = AccordionMotionController(
            owner=self._panel,
            card_title=card_title,
            content_body=content_body,
            content_layout=content_layout,
            divider_below_title=None,
            chevron=chevron,
            transition_started=section_layout.preserve_transition_geometry,
            transition_finished=section_layout.finalize_transition_geometry,
        )
        setattr(content_body, "_accordion_motion_controller", controller)
        apply_title_row_interaction(
            title_row=card_title,
            accordion_callback=controller.toggle,
            enabled_switch=getattr(card_title, "_enabled_switch_widget", None),
            enabled_switch_wrapper=getattr(
                card_title,
                "_enabled_switch_wrapper",
                None,
            ),
        )
        return controller

    @staticmethod
    def _apply_metadata(
        wrapper: NodeCardWidget,
        metadata: NodeCardSurfaceMetadata,
    ) -> None:
        """Publish stable card identity and presentation properties."""

        wrapper.setProperty("cube_alias", metadata.cube_alias)
        wrapper.setProperty("node_name", metadata.node_name)
        wrapper.setProperty("node_class_type", metadata.node_class_type)
        wrapper.setProperty("node_card_variant", metadata.variant)
        wrapper.setProperty("has_title_controls", metadata.has_title_controls)
        wrapper.setProperty(
            "has_advanced_input_action",
            metadata.has_advanced_input_action,
        )
        wrapper.setProperty("base_card_visible", True)


__all__ = [
    "NodeCardSurfaceAssembly",
    "NodeCardSurfaceComposer",
    "NodeCardSurfaceMetadata",
]
