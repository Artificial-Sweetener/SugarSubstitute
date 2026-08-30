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

"""Build repeated node-card generations for registration tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    WidgetPanel,
    ensure_qapp,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object

WidgetFactory = Callable[..., QWidget]


@dataclass(slots=True)
class RebuildScenario:
    """Own one panel and builder across successive card generations."""

    panel: WidgetPanel
    builder: NodeCardBuilder
    cube_state: SimpleNamespace
    node_name: str
    node_type: str

    def build(
        self,
        *,
        inputs: dict[str, object],
        definitions: Mapping[str, Mapping[str, object]],
    ) -> QWidget:
        """Build one current card generation and require a wrapper result."""

        nodes = {
            self.node_name: {
                "class_type": self.node_type,
                "inputs": inputs,
            }
        }
        self.cube_state.buffer = {
            "nodes": nodes,
            "definitions": dict(definitions),
        }
        snapshot = build_behavior_snapshot(
            cube_states={"A": self.cube_state},
            stack_order=["A"],
            definitions_by_class=definitions,
        )
        wrapper = cast(
            QWidget | None,
            self.builder.build_node_card(
                node_name=self.node_name,
                inputs=inputs,
                node_type=self.node_type,
                field_specs=snapshot.field_specs_by_alias["A"][self.node_name],
                cube_state=self.cube_state,
                resolved_behavior=snapshot.resolved_nodes_by_alias["A"][self.node_name],
                display_decision=snapshot.card_decisions_by_alias["A"][self.node_name],
                alias="A",
            ),
        )
        if wrapper is None:
            raise AssertionError("Rebuild scenario did not produce a node card.")
        return wrapper

    def destroy(self, *wrappers: QWidget) -> None:
        """Destroy every produced generation and its panel synchronously."""

        for wrapper in wrappers:
            destroy_qt_object(wrapper)
        destroy_qt_object(self.panel)


def create_rebuild_scenario(
    monkeypatch: pytest.MonkeyPatch,
    *,
    node_name: str,
    node_type: str,
    widget_factory: WidgetFactory | None = None,
) -> RebuildScenario:
    """Create a builder whose field boundary is deterministic and local."""

    ensure_qapp()
    panel = WidgetPanel()
    cube_state = SimpleNamespace(buffer={"nodes": {}, "definitions": {}}, ui={})
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    builder = build_node_card_builder(panel, Gateway())
    factory = widget_factory or (lambda **_kwargs: QWidget(panel))
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        factory,
    )
    return RebuildScenario(
        panel=panel,
        builder=builder,
        cube_state=cube_state,
        node_name=node_name,
        node_type=node_type,
    )


def ksampler_definitions(
    *, include_scheduler: bool = True
) -> dict[str, dict[str, object]]:
    """Return the grouped KSampler definition used by rebuild contracts."""

    required: dict[str, object] = {
        "sampler_name": ["STRING"],
        "steps": ["INT"],
        "cfg": ["FLOAT"],
    }
    if include_scheduler:
        required["scheduler"] = ["STRING"]
    return {"KSampler": {"input": {"required": required}}}


def ksampler_inputs(*, include_scheduler: bool = True) -> dict[str, object]:
    """Return values matching the grouped KSampler rebuild definition."""

    inputs: dict[str, object] = {
        "sampler_name": "euler",
        "steps": 28,
        "cfg": 5.5,
    }
    if include_scheduler:
        inputs["scheduler"] = "normal"
    return inputs


__all__ = [
    "RebuildScenario",
    "create_rebuild_scenario",
    "ksampler_definitions",
    "ksampler_inputs",
]
