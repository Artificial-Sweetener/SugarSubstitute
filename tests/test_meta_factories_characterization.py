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

"""Characterization tests for meta link-factory behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.overrides import ChoiceLinkFieldState, ChoiceLinkTarget
from substitute.domain.links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
)
from substitute.domain.node_behavior import NodeDisplayDecision, PromptRole
import substitute.presentation.editor.panel.factories.meta_factories as meta_factories
from substitute.presentation.editor.panel.node_card_builder import (
    _switch_override_for_next_state,
)


@pytest.fixture(autouse=True)
def _render_localized_combo_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render localized labels directly for non-Qt combo test doubles."""

    def set_item(combo: _FakeComboBox, index: int, text: str) -> None:
        combo.items[index] = render_source_application_text(text)

    monkeypatch.setattr(meta_factories, "set_localized_combo_item", set_item)


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


def test_enabled_switch_off_persists_explicit_false_for_default_disabled_node() -> None:
    """Turning off a revealed default-disabled node should keep activation explicit."""

    decision = NodeDisplayDecision(
        visible=True,
        enabled=True,
        reason="explicit:enabled",
        revealable=True,
        reveal_checked=True,
        show_enabled_switch=True,
        policy_default_enabled=False,
        explicit_override=True,
        explicit_revealed=True,
    )

    assert _switch_override_for_next_state(decision, False) is False


class _Signal:
    """Qt-like signal helper with connect/disconnect/emit."""

    def __init__(self) -> None:
        self._slots = []

    def connect(self, slot) -> None:
        """Register callback."""
        self._slots.append(slot)

    def disconnect(self) -> None:
        """Disconnect all callbacks."""
        self._slots.clear()

    def emit(self, *args) -> None:
        """Emit to registered callbacks."""
        for slot in list(self._slots):
            slot(*args)


class _FakeComboBox:
    """ComboBox stand-in used for meta factory behavior tests."""

    def __init__(self, _parent=None) -> None:
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

    def __init__(self, _parent=None) -> None:
        """Track shared preferred width applications."""

        super().__init__(_parent)
        self.shared_width: int | None = None

    def fontMetrics(self):
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
        self.widgets = []

    def addWidget(self, widget) -> None:
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
        self._hidden_field_keys = set()
        self.hidden_sets: list[set] = []
        self.all_buffers: dict[str, dict[str, object]] = {}
        self.node_selection_calls: list[tuple[str, str, str | None, str | None]] = []

    def set_hidden_field_keys(self, keys: set) -> None:
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


def test_setup_node_link_combobox_hides_first_prompt_endpoint(
    monkeypatch,
) -> None:
    """First prompt endpoint should use the generic selector and stay hidden."""
    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _Panel(["A", "B"])
    layout = _Layout()
    widgets = {}
    all_buffers = {
        "A": {"nodes": {"positive_prompt": {"inputs": {}}}},
        "B": {"nodes": {"positive_prompt": {"inputs": {}}}},
    }
    panel.all_buffers = all_buffers
    endpoint_index = _positive_node_link_index("A", "B")
    endpoint = endpoint_index.prompt_endpoint_for("A", PromptRole.POSITIVE)
    assert endpoint is not None

    combo, first = meta_factories.setup_node_link_combobox(
        panel,
        widgets,
        endpoint,
        endpoint_index,
        all_buffers,
        layout,
        lambda text: text,
        link_context=_node_link_context(panel),
    )

    assert first == "A"
    assert isinstance(combo, _FakeLinkSelectorComboBox)
    assert combo.hidden is True
    assert layout.widgets == [combo]
    assert widgets == {("A", endpoint.identity): combo}


def test_setup_node_link_combobox_updates_prompt_selection_through_canonical_node_link(
    monkeypatch,
) -> None:
    """Prompt link selection should store canonical node_link metadata."""
    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _RefreshPanel(["A", "B"])
    layout = _Layout()
    widgets = {}
    all_buffers = {
        "A": {"nodes": {"positive_prompt": {"inputs": {}}}},
        "B": {
            "nodes": {
                "positive_prompt": {
                    "inputs": {},
                    "node_link": {"from_cube": None, "from_node": None},
                }
            }
        },
    }
    panel.all_buffers = all_buffers
    endpoint_index = _positive_node_link_index("A", "B")
    endpoint = endpoint_index.prompt_endpoint_for("B", PromptRole.POSITIVE)
    assert endpoint is not None

    combo, first = meta_factories.setup_node_link_combobox(
        panel,
        widgets,
        endpoint,
        endpoint_index,
        all_buffers,
        layout,
        lambda text: text,
        link_context=_node_link_context(panel),
    )

    assert first == "A"
    assert isinstance(combo, _FakeLinkSelectorComboBox)
    assert combo.hidden is False
    assert combo.current_text == "Independent"

    combo.currentTextChanged.emit("🔗 A")
    assert panel.node_selection_calls == [
        ("B", "prompt:positive", "A", "positive_prompt")
    ]
    assert all_buffers["B"]["nodes"]["positive_prompt"]["node_link"] == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert panel.refresh_calls == ["node_link_changed"]

    combo.currentTextChanged.emit("Independent")
    assert panel.node_selection_calls[-1] == ("B", "prompt:positive", None, None)
    assert all_buffers["B"]["nodes"]["positive_prompt"]["node_link"] == {
        "from_cube": None,
        "from_node": None,
    }


def test_setup_node_link_combobox_uses_behavior_refresh_for_prompt_changes(
    monkeypatch,
) -> None:
    """Prompt link changes should use the generic node-link behavior refresh."""

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _RefreshPanel(["A", "B"])
    layout = _Layout()
    widgets = {}
    all_buffers = {
        "A": {"nodes": {"positive_prompt": {"inputs": {}}}},
        "B": {
            "nodes": {
                "positive_prompt": {
                    "inputs": {},
                    "node_link": {"from_cube": None, "from_node": None},
                }
            }
        },
    }
    panel.all_buffers = all_buffers
    endpoint_index = _positive_node_link_index("A", "B")
    endpoint = endpoint_index.prompt_endpoint_for("B", PromptRole.POSITIVE)
    assert endpoint is not None

    combo, _first = meta_factories.setup_node_link_combobox(
        panel,
        widgets,
        endpoint,
        endpoint_index,
        all_buffers,
        layout,
        lambda text: text,
        link_context=_node_link_context(panel),
    )
    panel.refresh_calls.clear()

    combo.currentTextChanged.emit("🔗 A")

    assert panel.refresh_calls == ["node_link_changed"]
    assert not hasattr(panel, "rebuild_cube_section_for_link_change")


def test_setup_node_link_combobox_applies_shared_width_labels_to_prompt_selector(
    monkeypatch,
) -> None:
    """Prompt selectors should receive shared widths through the node-link setup."""

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _Panel(["A", "B"])
    layout = _Layout()
    widgets = {}
    all_buffers = {
        "A": {"nodes": {"positive_prompt": {"inputs": {}}}},
        "B": {"nodes": {"positive_prompt": {"inputs": {}}}},
    }
    panel.all_buffers = all_buffers
    endpoint_index = _positive_node_link_index("A", "B")
    endpoint = endpoint_index.prompt_endpoint_for("B", PromptRole.POSITIVE)
    assert endpoint is not None

    combo, _first = meta_factories.setup_node_link_combobox(
        panel,
        widgets,
        endpoint,
        endpoint_index,
        all_buffers,
        layout,
        lambda text: text,
        shared_width_labels=("Independent", "🔗 SDXL/Text to Image"),
        link_context=_node_link_context(panel),
    )

    assert combo.shared_width == len("🔗 SDXL/Text to Image") * 10 + 51


def test_setup_node_link_combobox_updates_vectorscope_selection(monkeypatch) -> None:
    """Generic node-link selection should store source cube and source node."""

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _RefreshPanel(["A", "B"])
    layout = _Layout()
    widgets = {}
    all_buffers = {
        "A": {"nodes": {"vectorscopecc": {"inputs": {"brightness": 0.25}}}},
        "B": {
            "nodes": {
                "vectorscopecc": {
                    "inputs": {"brightness": 0.75},
                    "node_link": {"from_cube": None, "from_node": None},
                }
            }
        },
    }
    panel.all_buffers = all_buffers
    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (
            NodeLinkEndpoint(
                cube_alias="A",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
                editable_value_keys=("brightness",),
            ),
            NodeLinkEndpoint(
                cube_alias="B",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
                editable_value_keys=("brightness",),
            ),
        )
    )
    identity = endpoint_index.identities_for_cube("B")[0]
    endpoint = endpoint_index.endpoint_for("B", identity)
    assert endpoint is not None

    combo, first = meta_factories.setup_node_link_combobox(
        panel,
        widgets,
        endpoint,
        endpoint_index,
        all_buffers,
        layout,
        lambda text: text,
        link_context=_node_link_context(panel),
    )

    assert first == "A"
    assert isinstance(combo, _FakeLinkSelectorComboBox)
    assert combo.hidden is False
    assert combo.items == ["Independent", "🔗 A"]
    combo.currentTextChanged.emit("🔗 A")
    assert panel.node_selection_calls == [("B", "vectorscopecc", "A", "vectorscopecc")]
    assert all_buffers["B"]["nodes"]["vectorscopecc"]["node_link"] == {
        "from_cube": "A",
        "from_node": "vectorscopecc",
    }
    assert panel.refresh_calls == ["node_link_changed"]
    assert not hasattr(panel, "rebuild_cube_section_for_link_change")

    combo.currentTextChanged.emit("Independent")
    assert panel.node_selection_calls[-1] == ("B", "vectorscopecc", None, None)
    assert all_buffers["B"]["nodes"]["vectorscopecc"]["node_link"] == {
        "from_cube": None,
        "from_node": None,
    }
    assert panel.refresh_calls[-1] == "node_link_changed"


def test_setup_node_link_combobox_applies_shared_width_labels(monkeypatch) -> None:
    """Node link setup should convert shared labels into preferred control width."""

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _Panel(["A", "B"])
    layout = _Layout()
    widgets = {}
    all_buffers = {
        "A": {"nodes": {"vectorscopecc": {"inputs": {"brightness": 0.25}}}},
        "B": {"nodes": {"vectorscopecc": {"inputs": {"brightness": 0.75}}}},
    }
    panel.all_buffers = all_buffers
    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (
            NodeLinkEndpoint(
                cube_alias="A",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
                editable_value_keys=("brightness",),
            ),
            NodeLinkEndpoint(
                cube_alias="B",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
                editable_value_keys=("brightness",),
            ),
        )
    )
    endpoint = endpoint_index.endpoint_for(
        "B",
        endpoint_index.identities_for_cube("B")[0],
    )
    assert endpoint is not None

    combo, _first = meta_factories.setup_node_link_combobox(
        panel,
        widgets,
        endpoint,
        endpoint_index,
        all_buffers,
        layout,
        lambda text: text,
        shared_width_labels=("Independent", "🔗 SDXL/Automask Detailer"),
        link_context=_node_link_context(panel),
    )

    assert combo.shared_width == len("🔗 SDXL/Automask Detailer") * 10 + 51


def test_sampler_scheduler_factories_remain_on_shared_combo_box(monkeypatch) -> None:
    """Sampler and scheduler link widgets should not switch to the specialized subclass."""

    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {
                        "required": {
                            "sampler_name": [["euler", "heun"]],
                            "scheduler": [["normal", "karras"]],
                        }
                    }
                }
            }
        }
    )

    sampler_combo = _FakeComboBox()
    scheduler_combo = _FakeComboBox()
    buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "euler", "scheduler": "normal"},
                    "sampler_links": [],
                    "scheduler_links": [],
                }
            }
        }
    }

    meta_factories.setup_sampler_link_combobox(
        parent=SimpleNamespace(),
        sampler_link_widgets={("B", "sampler"): sampler_combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="sampler_name",
            link_key="sampler_link",
            literal_options=("euler", "heun"),
        ),
    )
    meta_factories.setup_scheduler_link_combobox(
        parent=SimpleNamespace(),
        scheduler_link_widgets={("B", "sampler"): scheduler_combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="scheduler",
            link_key="scheduler_link",
            literal_options=("normal", "karras"),
        ),
    )

    assert type(sampler_combo) is _FakeComboBox
    assert type(scheduler_combo) is _FakeComboBox


def test_setup_sampler_link_combobox_resets_stale_link_to_first_literal(
    monkeypatch,
) -> None:
    """Sampler combobox should fall back to first literal option when link is stale."""
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {"required": {"sampler_name": [["euler", "heun"]]}}
                }
            }
        }
    )

    combo = _FakeComboBox()
    buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "invalid"},
                    "sampler_links": [
                        {"from_cube": "A", "from_node": "ksampler", "label": "link:A"}
                    ],
                    "sampler_link": {"from_cube": "A", "from_node": "missing"},
                }
            }
        }
    }

    meta_factories.setup_sampler_link_combobox(
        parent=SimpleNamespace(),
        sampler_link_widgets={("B", "sampler"): combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="sampler_name",
            link_key="sampler_link",
            literal_options=("euler", "heun"),
            link_targets=(
                ChoiceLinkTarget(
                    from_cube="A",
                    from_node="ksampler",
                    label="link:A",
                ),
            ),
        ),
    )

    assert combo.items == ["link:A", "euler", "heun"]
    assert combo.current_text == "euler"
    assert buffers["B"]["nodes"]["sampler"]["inputs"]["sampler_name"] == "euler"


def test_setup_scheduler_link_combobox_resets_invalid_literal_to_first_option(
    monkeypatch,
) -> None:
    """Scheduler combobox should normalize invalid literal values to first option."""
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {"required": {"scheduler": [["normal", "karras"]]}}
                }
            }
        }
    )

    combo = _FakeComboBox()
    buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {"scheduler": "invalid"},
                    "scheduler_links": [],
                }
            }
        }
    }

    meta_factories.setup_scheduler_link_combobox(
        parent=SimpleNamespace(),
        scheduler_link_widgets={("B", "sampler"): combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="scheduler",
            link_key="scheduler_link",
            literal_options=("normal", "karras"),
        ),
    )

    assert combo.current_text == "normal"
    assert buffers["B"]["nodes"]["sampler"]["inputs"]["scheduler"] == "normal"


def test_setup_choice_link_combobox_keeps_existing_items_when_options_unresolved(
    monkeypatch,
) -> None:
    """Unresolved literal options must not become a link-only complete dropdown."""

    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    combo = _FakeComboBox()
    combo.addItems(["previous"])
    combo.setCurrentText("previous")
    buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {},
                    "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
                }
            }
        }
    }

    meta_factories.setup_sampler_link_combobox(
        parent=SimpleNamespace(),
        sampler_link_widgets={("B", "sampler"): combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        field_state=_field_state(
            literal_key="sampler_name",
            link_key="sampler_link",
            literal_options=(),
            link_targets=(
                ChoiceLinkTarget(
                    from_cube="A",
                    from_node="ksampler",
                    label="link:A",
                ),
            ),
            options_resolved=False,
        ),
    )

    assert combo.items == ["previous"]
    assert combo.current_text == "previous"
    assert combo.enabled is False


def test_sanitize_link_selections_preserve_linked_values_and_reset_invalid_literals() -> (
    None
):
    """Sanitizers should skip linked fields and repair only invalid literal selections."""
    all_buffers = {
        "A": {
            "nodes": {
                "s1": {
                    "inputs": {"sampler_name": "invalid"},
                    "sampler_links": [],
                    "sampler_link": None,
                },
                "s2": {
                    "inputs": {"sampler_name": "invalid"},
                    "sampler_links": [],
                    "sampler_link": {"from_cube": "X", "from_node": "Y"},
                },
                "k1": {
                    "inputs": {"scheduler": "bad"},
                    "scheduler_links": [],
                    "scheduler_link": None,
                },
            }
        }
    }

    meta_factories.sanitize_sampler_link_selection(
        all_buffers,
        {("A", "s1"): ["euler"], ("A", "s2"): ["heun"]},
    )
    meta_factories.sanitize_scheduler_link_selection(
        all_buffers,
        {("A", "k1"): ["normal"]},
    )

    assert all_buffers["A"]["nodes"]["s1"]["inputs"]["sampler_name"] == "euler"
    assert all_buffers["A"]["nodes"]["s2"]["inputs"]["sampler_name"] == "invalid"
    assert all_buffers["A"]["nodes"]["k1"]["inputs"]["scheduler"] == "normal"


def test_sanitize_link_selections_preserve_literals_when_options_are_unavailable() -> (
    None
):
    """Unavailable live choices should not erase restored sampler or scheduler values."""
    all_buffers = {
        "A": {
            "nodes": {
                "sampler": {
                    "inputs": {
                        "sampler_name": "euler_ancestral",
                        "scheduler": "normal",
                    },
                    "sampler_links": [],
                    "sampler_link": None,
                    "scheduler_links": [],
                    "scheduler_link": None,
                },
            },
        },
    }

    meta_factories.sanitize_sampler_link_selection(
        all_buffers,
        {("A", "sampler"): []},
    )
    meta_factories.sanitize_scheduler_link_selection(
        all_buffers,
        {("A", "sampler"): []},
    )

    inputs = all_buffers["A"]["nodes"]["sampler"]["inputs"]
    assert inputs["sampler_name"] == "euler_ancestral"
    assert inputs["scheduler"] == "normal"


def test_update_link_references_on_rename_updates_only_matching_aliases() -> None:
    """Rename propagation should rewrite only links targeting the renamed alias."""
    all_buffers = {
        "A": {
            "nodes": {
                "p": {"prompt_link": {"from_cube": "Old"}},
                "n": {"node_link": {"from_cube": "Old", "from_node": "vectorscopecc"}},
                "s": {"sampler_link": {"from_cube": "Old", "from_node": "K"}},
                "k": {"scheduler_link": {"from_cube": "Old", "from_node": "K"}},
                "x": {"prompt_link": {"from_cube": "Other"}},
            }
        }
    }

    meta_factories.update_prompt_link_references_on_rename(all_buffers, "Old", "New")
    meta_factories.update_sampler_link_references_on_rename(all_buffers, "Old", "New")
    meta_factories.update_scheduler_link_references_on_rename(all_buffers, "Old", "New")

    assert all_buffers["A"]["nodes"]["p"]["prompt_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["n"]["node_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["s"]["sampler_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["k"]["scheduler_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["x"]["prompt_link"]["from_cube"] == "Other"
