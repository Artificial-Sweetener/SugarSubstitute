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

"""Provide local typed doubles for meta-link factory contracts."""

from __future__ import annotations

from __future__ import annotations
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, TypeAlias
import pytest
from sugarsubstitute_shared.localization import render_source_application_text
from substitute.application.overrides import ChoiceLinkFieldState, ChoiceLinkTarget
from substitute.domain.links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
)
import substitute.presentation.editor.panel.factories.meta_factories as meta_factories

_Buffers: TypeAlias = dict[str, Any]
_SignalSlot: TypeAlias = Callable[..., None]


class _FakeNodeDefinitionGateway:
    """Return deterministic node definitions for meta-factory link tests."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store per-class payloads for lookup assertions."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured definition payload for the requested class."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured required definition payload for the requested class."""

        return self._definitions.get(node_class, {})


class _Signal:
    """Qt-like signal helper with connect/disconnect/emit."""

    def __init__(self) -> None:
        self._slots: list[_SignalSlot] = []

    def connect(self, slot: _SignalSlot) -> None:
        """Register callback."""
        self._slots.append(slot)

    def disconnect(self) -> None:
        """Disconnect all callbacks."""
        self._slots.clear()

    def emit(self, *args: object) -> None:
        """Emit to registered callbacks."""
        for slot in list(self._slots):
            slot(*args)


class _FakeComboBox:
    """ComboBox stand-in used for meta factory behavior tests."""

    def __init__(self, _parent: object | None = None) -> None:
        self.items: list[str] = []
        self.current_text = ""
        self.hidden = False
        self.enabled = True
        self.currentTextChanged = _Signal()

    def blockSignals(self, _blocked: bool) -> None:
        """No-op signal blocker."""
        return

    def clear(self) -> None:
        """Clear all items."""
        self.items.clear()
        self.current_text = ""

    def addItem(self, text: str) -> None:
        """Append one item."""
        self.items.append(text)

    def addItems(self, texts: list[str]) -> None:
        """Append many items."""
        self.items.extend(texts)

    def setCurrentText(self, text: str) -> None:
        """Set current text."""
        self.current_text = text

    def setCurrentIndex(self, index: int) -> None:
        """Set current text by index when valid."""
        if 0 <= index < len(self.items):
            self.current_text = self.items[index]

    def hide(self) -> None:
        """Mark hidden."""
        self.hidden = True

    def show(self) -> None:
        """Mark visible."""
        self.hidden = False

    def setEnabled(self, enabled: bool) -> None:
        """Record enabled state."""

        self.enabled = enabled


class _FakeLinkSelectorComboBox(_FakeComboBox):
    """Specialized stand-in used to verify prompt/node link widget scoping."""

    def __init__(self, _parent: object | None = None) -> None:
        """Track shared preferred width applications."""

        super().__init__(_parent)
        self.shared_width: int | None = None

    def fontMetrics(self) -> SimpleNamespace:
        """Return deterministic text measurement for width tests."""

        return SimpleNamespace(horizontalAdvance=lambda text: len(text) * 10)

    def setSharedPreferredWidth(self, width: int | None) -> None:
        """Record the shared preferred width applied by the factory."""

        self.shared_width = width

    def _closed_display_control_width_for_text_width(self, text_width: int) -> int:
        """Return deterministic closed-control width for factory tests."""

        return text_width + 51


class _Layout:
    """Title-layout test double that records added widgets."""

    def __init__(self) -> None:
        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        """Record appended widget."""
        self.widgets.append(widget)


def _field_state(
    *,
    literal_key: str,
    link_key: str,
    literal_options: tuple[str, ...],
    link_targets: tuple[ChoiceLinkTarget, ...] = (),
    options_resolved: bool = True,
) -> ChoiceLinkFieldState:
    """Build one resolved value-link field state for meta-factory tests."""

    return ChoiceLinkFieldState(
        cube_alias="B",
        node_name="sampler",
        literal_key=literal_key,
        link_key=link_key,
        literal_options=literal_options,
        link_targets=link_targets,
        active_link=None,
        options_resolved=options_resolved,
    )


class _Panel:
    """Minimal panel with hidden-key behavior used by prompt link setup."""

    def __init__(self, stack_order: list[str]) -> None:
        self._stack_order = stack_order
        self._hidden_field_keys: set[object] = set()
        self.hidden_sets: list[set[object]] = []
        self.all_buffers: _Buffers = {}
        self.node_selection_calls: list[tuple[str, str, str | None, str | None]] = []

    def set_hidden_field_keys(self, keys: set[object]) -> None:
        """Store hidden keys and call history."""
        self._hidden_field_keys = set(keys)
        self.hidden_sets.append(set(keys))

    def apply_manual_node_link_selection(
        self,
        cube_alias: str,
        identity: object,
        from_cube: str | None,
        from_node: str | None,
    ) -> None:
        """Apply generic node-link mutations the way the real panel delegates them."""

        family = getattr(identity, "family", "")
        node_name = (
            "positive_prompt" if family == "prompt:positive" else "vectorscopecc"
        )
        self.node_selection_calls.append((cube_alias, family, from_cube, from_node))
        node = self.all_buffers[cube_alias]["nodes"][node_name]
        node["node_link"] = {"from_cube": from_cube, "from_node": from_node}


class _RefreshPanel(_Panel):
    """Panel double that records behavior refresh calls instead of rebuilding."""

    def __init__(self, stack_order: list[str]) -> None:
        """Initialize refresh recording alongside normal link mutation state."""

        super().__init__(stack_order)
        self.refresh_calls: list[str] = []

    def refresh_node_behavior_state(self, *, reason: str) -> None:
        """Record one behavior refresh reason."""

        self.refresh_calls.append(reason)


def _node_link_context(panel: _Panel) -> meta_factories.NodeLinkComboContext:
    """Return explicit node-link setup context for factory tests."""

    notify = None
    if isinstance(panel, _RefreshPanel):

        def notify() -> None:
            """Record a node-link behavior refresh for this test panel."""

            panel.refresh_node_behavior_state(reason="node_link_changed")

    return meta_factories.NodeLinkComboContext(
        ordered_aliases=panel._stack_order,
        apply_manual_node_link_selection=panel.apply_manual_node_link_selection,
        notify_node_link_changed=notify,
    )


def _positive_node_link_index(*aliases: str) -> NodeLinkEndpointIndex:
    """Return canonical positive prompt node-link endpoints for test buffers."""

    return NodeLinkEndpointIndex.from_endpoints(
        NodeLinkEndpoint(
            cube_alias=alias,
            node_name="positive_prompt",
            class_type="PrimitiveStringMultiline",
            family="prompt:positive",
            editable_value_keys=("prompt_template",),
        )
        for alias in aliases
    )


def configure_localized_combo_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render localized labels directly for deterministic non-Qt combo doubles."""

    def set_item(combo: _FakeComboBox, index: int, text: str) -> None:
        """Assign rendered text through the fake combo's observable item state."""

        combo.items[index] = render_source_application_text(text)

    monkeypatch.setattr(meta_factories, "set_localized_combo_item", set_item)
