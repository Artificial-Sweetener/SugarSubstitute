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

"""Verify node-link selector factory behavior."""

from __future__ import annotations

from __future__ import annotations
import pytest
from substitute.domain.links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
)
from substitute.domain.node_behavior import PromptRole
import substitute.presentation.editor.panel.factories.meta_factories as meta_factories

from .link_test_support import (
    _FakeLinkSelectorComboBox,
    _Layout,
    _Panel,
    _RefreshPanel,
    _Buffers,
    _node_link_context,
    _positive_node_link_index,
    configure_localized_combo_items,
)


def test_setup_node_link_combobox_hides_first_prompt_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First prompt endpoint should use the generic selector and stay hidden."""

    configure_localized_combo_items(monkeypatch)
    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _Panel(["A", "B"])
    layout = _Layout()
    widgets: dict[tuple[str, object], _FakeLinkSelectorComboBox] = {}
    all_buffers: _Buffers = {
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt link selection should store canonical node_link metadata."""

    configure_localized_combo_items(monkeypatch)
    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _RefreshPanel(["A", "B"])
    layout = _Layout()
    widgets: dict[tuple[str, object], _FakeLinkSelectorComboBox] = {}
    all_buffers: _Buffers = {
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt link changes should use the generic node-link behavior refresh."""

    configure_localized_combo_items(monkeypatch)

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _RefreshPanel(["A", "B"])
    layout = _Layout()
    widgets: dict[tuple[str, object], _FakeLinkSelectorComboBox] = {}
    all_buffers: _Buffers = {
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt selectors should receive shared widths through the node-link setup."""

    configure_localized_combo_items(monkeypatch)

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _Panel(["A", "B"])
    layout = _Layout()
    widgets: dict[tuple[str, object], _FakeLinkSelectorComboBox] = {}
    all_buffers: _Buffers = {
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


def test_setup_node_link_combobox_updates_vectorscope_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic node-link selection should store source cube and source node."""

    configure_localized_combo_items(monkeypatch)

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _RefreshPanel(["A", "B"])
    layout = _Layout()
    widgets: dict[tuple[str, object], _FakeLinkSelectorComboBox] = {}
    all_buffers: _Buffers = {
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


def test_setup_node_link_combobox_applies_shared_width_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node link setup should convert shared labels into preferred control width."""

    configure_localized_combo_items(monkeypatch)

    monkeypatch.setattr(
        meta_factories, "LinkSelectorComboBox", _FakeLinkSelectorComboBox
    )
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)

    panel = _Panel(["A", "B"])
    layout = _Layout()
    widgets: dict[tuple[str, object], _FakeLinkSelectorComboBox] = {}
    all_buffers: _Buffers = {
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
