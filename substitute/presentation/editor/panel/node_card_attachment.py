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

"""Attach one realized node card to its section and wrapper registry."""

from __future__ import annotations

import weakref

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import DegradedNodeBehavior
from substitute.shared.logging.logger import get_logger, log_warning

from .cube_section_build_ports import CubeSectionBuildSessionPanelProtocol
from .node_card.variant import NodeCardVariant, column_span_for_node_card_variant
from .rendering.render_transaction import EditorRenderTransaction
from .widgets.masonry_grid_layout import MasonryGridLayout
from .widgets.degraded_node_card import build_degraded_node_card

_LOGGER = get_logger("presentation.editor.panel.node_card_attachment")


def attach_node_card(
    *,
    panel: CubeSectionBuildSessionPanelProtocol,
    cube_alias: str,
    node_name: str,
    card: QWidget,
    variant: NodeCardVariant,
    grid_layout: MasonryGridLayout,
) -> int:
    """Register, classify, and insert one node card exactly once."""

    setattr(card, "_current_cube_alias", cube_alias)
    panel.register_card_wrapper(cube_alias, node_name, card)
    _connect_registry_cleanup(
        panel=panel,
        cube_alias=cube_alias,
        node_name=node_name,
        card=card,
    )
    span = column_span_for_node_card_variant(variant)
    card.setProperty("column_span", span)
    card.setProperty("node_card_variant", variant.value)
    grid_layout.addWidget(card)
    if isinstance(panel, QWidget):
        with EditorRenderTransaction(panel) as transaction:
            transaction.attach_node_card(card)
    return span


def attach_degraded_node_card(
    *,
    panel: CubeSectionBuildSessionPanelProtocol,
    cube_alias: str,
    node: DegradedNodeBehavior,
    grid_layout: MasonryGridLayout,
    parent: QWidget,
) -> int:
    """Build and attach one truthful card for unavailable live metadata."""

    span = attach_node_card(
        panel=panel,
        cube_alias=cube_alias,
        node_name=node.node_name,
        card=build_degraded_node_card(node, parent=parent),
        variant=NodeCardVariant.RUNTIME_ISSUE,
        grid_layout=grid_layout,
    )
    log_warning(
        _LOGGER,
        "Rendered saved node with unavailable live definition",
        cube_alias=cube_alias,
        node_name=node.node_name,
        node_class_type=node.class_type,
        missing_node_classes=",".join(node.missing_definition_classes),
        missing_fields=",".join(node.missing_fields),
        column_span=span,
    )
    return span


def _connect_registry_cleanup(
    *,
    panel: CubeSectionBuildSessionPanelProtocol,
    cube_alias: str,
    node_name: str,
    card: QWidget,
) -> None:
    """Remove the wrapper registry entry when its exact card is destroyed."""

    try:
        card_ref = weakref.ref(card)

        def cleanup_card_wrapper(*_args: object) -> None:
            """Remove the wrapper only if it still owns the registry entry."""

            current_card = card_ref()
            if current_card is not None:
                panel.remove_card_wrapper_if_current(
                    cube_alias,
                    node_name,
                    current_card,
                )

        card.destroyed.connect(cleanup_card_wrapper)
    except (AttributeError, RuntimeError, TypeError) as error:
        log_warning(
            _LOGGER,
            "Failed to connect cube-section card cleanup",
            cube_alias=cube_alias,
            node_name=node_name,
            error_type=type(error).__name__,
        )


__all__ = ["attach_degraded_node_card", "attach_node_card"]
