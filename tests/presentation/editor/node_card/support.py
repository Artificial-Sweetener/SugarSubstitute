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

"""Provide typed construction and inspection support for node-card tests."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    ResolvedFieldSpec,
)
from substitute.application.node_behavior.models import EditorBehaviorSnapshot
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionContentClip,
)
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter


class ActivationService:
    """Record node activation commands issued by title-row interactions."""

    def __init__(self) -> None:
        """Initialize an empty activation command log."""

        self.calls: list[tuple[object, str, bool | None]] = []

    def set_node_activation_override(
        self,
        cube_state: object,
        node_name: str,
        explicit_enabled: bool | None,
    ) -> None:
        """Record one explicit activation override command."""

        self.calls.append((cube_state, node_name, explicit_enabled))


class Gateway:
    """Return empty node definitions for deterministic builder tests."""

    @staticmethod
    def get_node_definition(node_class: str) -> dict[str, object]:
        """Return no optional live definition payload."""

        return Gateway.get_required_node_definition(node_class)

    @staticmethod
    def get_required_node_definition(_node_class: str) -> dict[str, object]:
        """Return no required live definition payload."""

        return {}


class DefinitionGateway:
    """Return configured live node definitions without external I/O."""

    def __init__(self, definitions: Mapping[str, object]) -> None:
        """Retain definitions keyed by node class."""

        self._definitions = dict(definitions)

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a Comfy-shaped cached payload for one class type."""

        definition = self._definitions.get(node_class)
        return {node_class: definition} if isinstance(definition, dict) else {}

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the same deterministic payload for required lookup paths."""

        return self.get_node_definition(node_class)


class Panel:
    """Provide non-widget state required by NodeCardBuilder helpers."""

    def __init__(self) -> None:
        """Initialize empty card and layout registries."""

        self.cube_id = "Base"
        self._stack_order: list[str] = []
        self._cube_states: dict[str, object] = {}
        self.row_widgets: dict[object, object] = {}
        self.col_widgets: dict[object, object] = {}

    @staticmethod
    def is_connection(_value: object) -> bool:
        """Return False for every concise test value."""

        return False


class WidgetPanel(QWidget):
    """Provide QWidget-backed state for full node-card construction tests."""

    def __init__(self) -> None:
        """Initialize state consumed by NodeCardBuilder."""

        super().__init__()
        self.cube_id = "Base"
        self._stack_order: list[str] = []
        self._cube_states: dict[str, object] = {}
        self.cube_widgets: dict[str, object] = {}
        self.row_widgets: dict[object, tuple[object | None, object | None]] = {}
        self.col_widgets: dict[
            object, tuple[object | None, object | None, object | None]
        ] = {}
        self.card_wrappers: dict[tuple[str, str], object] = {}
        self._hidden_field_keys: set[object] = set()
        self._field_search_active = False
        self._search_field_match_keys: set[object] | None = None
        self.advanced_field_keys: set[object] = set()
        self.shown_advanced_input_nodes: set[tuple[str, str]] = set()
        self._field_sync_controller = EditorPanelFieldSyncController(self)
        self.input_widgets_by_field_key: dict[tuple[str, str, str], QWidget] = {}
        self.node_behavior_service = ActivationService()
        self.refresh_reasons: list[str] = []

    @staticmethod
    def is_connection(_value: object) -> bool:
        """Return False for every concise test value."""

        return False

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return no active behavior snapshot for title-control tests."""

        return None

    def refresh_node_behavior_state(self, *, reason: str) -> None:
        """Record behavior refresh requests issued by title controls."""

        self.refresh_reasons.append(reason)

    @staticmethod
    def _build_behavior_snapshot(
        *,
        search_hidden_keys: set[object] | None = None,
        node_search_text: str | None = None,
    ) -> None:
        """Return no dynamic snapshot for direct synchronization tests."""

        _ = search_hidden_keys, node_search_text
        return None


class PromptDependencyPanel(WidgetPanel):
    """Record prompt-only dependency requests made while fields are built."""

    def __init__(self) -> None:
        """Initialize empty prompt dependency call logs."""

        super().__init__()
        self.scheduled_lora_calls: list[tuple[str | None, str, str]] = []
        self.prompt_feature_profile_calls: list[
            tuple[str | None, str, str, dict[str, object]]
        ] = []

    def scheduled_lora_resolver_for_prompt(
        self,
        alias: str | None,
        node_name: str,
        field_key: str,
    ) -> object:
        """Record one scheduled-LoRA resolver request."""

        self.scheduled_lora_calls.append((alias, node_name, field_key))
        return object()

    def prompt_feature_profile_for_prompt(
        self,
        alias: str | None,
        node_name: str,
        field_key: str,
        field_style: Mapping[str, object],
    ) -> object:
        """Record one prompt feature-profile request."""

        self.prompt_feature_profile_calls.append(
            (alias, node_name, field_key, dict(field_style))
        )
        return object()


def ensure_qapp() -> QApplication:
    """Return the process QApplication used by node-card widget tests."""

    application = QApplication.instance()
    if application is None:
        return QApplication([])
    if not isinstance(application, QApplication):
        raise RuntimeError("Node-card tests require a QApplication dispatcher.")
    return application


def content_layout_for(viewport: QWidget) -> QVBoxLayout:
    """Return the row layout hosted on an accordion content surface."""

    assert isinstance(viewport, AccordionContentClip)
    content_layout = viewport.content_widget().layout()
    assert isinstance(content_layout, QVBoxLayout)
    return content_layout


def accordion_content_attached(widget: QWidget) -> bool:
    """Return the split-surface attachment state."""

    attached = getattr(widget, "accordion_content_attached", None)
    assert callable(attached)
    return bool(attached())


def node_card_for(wrapper: QWidget) -> QWidget:
    """Return the node-card surface hosted by one builder wrapper."""

    layout = wrapper.layout()
    assert layout is not None
    node_card_item = layout.itemAt(0)
    assert node_card_item is not None
    node_card = node_card_item.widget()
    assert node_card is not None
    return node_card


def title_row_for(wrapper: QWidget) -> QWidget:
    """Return the title row hosted by one builder wrapper."""

    node_card = node_card_for(wrapper)
    card_layout = node_card.layout()
    assert card_layout is not None
    title_row_item = card_layout.itemAt(0)
    assert title_row_item is not None
    title_row = title_row_item.widget()
    assert title_row is not None
    return title_row


def card_title_text(wrapper: QWidget) -> str:
    """Return the sole visible node-card title."""

    title_labels = title_row_for(wrapper).findChildren(CaptionLabel)
    assert len(title_labels) == 1
    return str(title_labels[0].text())


def title_body_divider_for(wrapper: QWidget) -> QWidget:
    """Return the divider between the title row and first body row."""

    content_layout = content_layout_for(content_body_for(wrapper))
    divider_item = content_layout.itemAt(0)
    assert divider_item is not None
    divider = divider_item.widget()
    assert divider is not None
    return divider


def content_body_for(wrapper: QWidget) -> AccordionContentClip:
    """Return the accordion content clip hosted by one card wrapper."""

    node_card = node_card_for(wrapper)
    card_layout = node_card.layout()
    assert card_layout is not None
    content_body_item = card_layout.itemAt(1)
    assert content_body_item is not None
    content_body = content_body_item.widget()
    assert isinstance(content_body, AccordionContentClip)
    return content_body


def row_activation_enabled(title_row: QWidget) -> bool:
    """Return whether a title row exposes row-level activation."""

    enabled = getattr(title_row, "row_activation_enabled", None)
    assert callable(enabled)
    return bool(enabled())


def release_title_row(title_row: QWidget) -> None:
    """Deliver a deterministic row-release event to a title row."""

    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(4, 4),
        QPointF(4, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    title_row.mouseReleaseEvent(event)


def has_ancestor(widget: QWidget, expected_ancestor: QWidget) -> bool:
    """Return whether a widget is parented below the expected ancestor."""

    parent = widget.parentWidget()
    while parent is not None:
        if parent is expected_ancestor:
            return True
        parent = parent.parentWidget()
    return False


def title_switch(title_row: QWidget) -> QWidget:
    """Return the enabled switch attached to a title row."""

    switch = getattr(title_row, "_enabled_switch_widget", None)
    assert isinstance(switch, QWidget)
    return switch


def editor_tooltip_filter(widget: QWidget) -> FluentToolTipFilter | None:
    """Return the editor-owned QFluent tooltip filter on a widget."""

    tooltip_filter = getattr(widget, "_editor_tooltip_filter", None)
    if tooltip_filter is None:
        return None
    assert isinstance(tooltip_filter, FluentToolTipFilter)
    return tooltip_filter


def resolved_field_spec(
    *,
    presentation: FieldPresentation,
    value: object = 1,
) -> ResolvedFieldSpec:
    """Return a minimal resolved field spec for field-factory tests."""

    field_key = "text" if presentation == FieldPresentation.PROMPT_BOX else "steps"
    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="node",
        class_type="TestNode",
        field_key=field_key,
        field_type="STRING" if presentation == FieldPresentation.PROMPT_BOX else "INT",
        constraints={},
        meta_info={},
        field_info=None,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            presentation=presentation,
            style=(
                {"prompt_syntaxes": ["wildcard"]}
                if presentation == FieldPresentation.PROMPT_BOX
                else {}
            ),
        ),
    )


__all__ = [
    "ActivationService",
    "DefinitionGateway",
    "Gateway",
    "Panel",
    "PromptDependencyPanel",
    "WidgetPanel",
    "accordion_content_attached",
    "card_title_text",
    "content_body_for",
    "content_layout_for",
    "editor_tooltip_filter",
    "ensure_qapp",
    "has_ancestor",
    "node_card_for",
    "release_title_row",
    "resolved_field_spec",
    "row_activation_enabled",
    "title_body_divider_for",
    "title_row_for",
    "title_switch",
]
