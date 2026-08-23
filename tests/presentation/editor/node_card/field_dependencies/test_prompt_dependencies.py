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

"""Verify prompt-only dependencies at the public card-build boundary."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import FieldPresentation
from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContext,
    PromptConditioningMode,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptFieldProfileDecision,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    PromptDependencyPanel,
    ensure_qapp,
    resolved_field_spec,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


def test_non_prompt_field_skips_prompt_only_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omit prompt services from ordinary scalar field construction."""

    scenario = _FieldDependencyScenario(monkeypatch)
    wrapper = scenario.build(
        field_key="steps",
        field_presentation=FieldPresentation.STANDARD,
    )
    try:
        assert scenario.panel.scheduled_lora_calls == []
        assert scenario.panel.prompt_feature_profile_calls == []
        assert scenario.captured["scheduled_lora_resolver"] is None
        assert scenario.captured["prompt_feature_profile"] is None
        assert scenario.captured["prompt_syntax_profile"] is None
    finally:
        scenario.destroy(wrapper)


def test_prompt_field_receives_prepared_prompt_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward prepared prompt collaborators without requesting panel fallbacks."""

    prompt_feature_profile = PromptEditorFeatureProfile.enabled_profile(())
    prompt_syntax_profile = PromptSyntaxProfile(enabled_syntaxes=())
    prompt_field_profile = PanelPromptFieldProfileDecision(
        feature_profile=prompt_feature_profile,
        syntax_profile=prompt_syntax_profile,
    )
    conditioning_context = PromptConditioningContext(
        mode=PromptConditioningMode.REGIONAL,
        endpoint=PromptEndpoint(
            cube_alias="A",
            role=PromptRole.POSITIVE,
            node_name="node",
            field_key="text",
        ),
    )

    def scheduled_lora_resolver(_text: str) -> tuple[PromptScheduledLora, ...]:
        """Return no scheduled LoRAs for the prepared resolver sentinel."""

        return ()

    scenario = _FieldDependencyScenario(monkeypatch)
    wrapper = scenario.build(
        field_key="text",
        field_presentation=FieldPresentation.PROMPT_BOX,
        value="prompt text",
        prompt_field_inputs={
            "text": NodeCardPromptFieldInputs(
                scheduled_lora_resolver=scheduled_lora_resolver,
                prompt_field_profile=prompt_field_profile,
                conditioning_context=conditioning_context,
            )
        },
    )
    try:
        assert scenario.panel.scheduled_lora_calls == []
        assert scenario.panel.prompt_feature_profile_calls == []
        assert scenario.captured["scheduled_lora_resolver"] is scheduled_lora_resolver
        assert scenario.captured["prompt_feature_profile"] is prompt_feature_profile
        assert scenario.captured["prompt_syntax_profile"] is prompt_syntax_profile
        assert scenario.captured["prompt_conditioning_context"] is conditioning_context
    finally:
        scenario.destroy(wrapper)


class _FieldDependencyScenario:
    """Own one public node-card build and its captured factory arguments."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create a deterministic card builder and capture its field boundary."""

        ensure_qapp()
        self.panel = PromptDependencyPanel()
        self.builder = build_node_card_builder(self.panel, Gateway())
        self.captured: dict[str, object] = {}

        def capture_factory(**kwargs: object) -> QWidget:
            """Capture arguments and return a minimal real field widget."""

            self.captured.update(kwargs)
            return QWidget(self.panel)

        monkeypatch.setattr(
            "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
            capture_factory,
        )

    def build(
        self,
        *,
        field_key: str,
        field_presentation: FieldPresentation,
        value: object = 1,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None = None,
    ) -> QWidget:
        """Build a one-field card through the builder's public boundary."""

        inputs = {field_key: value}
        nodes = {"node": {"class_type": "TestNode", "inputs": inputs}}
        cube_state = SimpleNamespace(
            buffer={"nodes": nodes, "definitions": {}},
            ui={},
        )
        self.panel._stack_order = ["A"]
        self.panel._cube_states = {"A": cube_state}
        snapshot = build_behavior_snapshot(
            cube_states={"A": cube_state},
            stack_order=["A"],
        )
        wrapper = cast(
            QWidget | None,
            self.builder.build_node_card(
                node_name="node",
                inputs=inputs,
                node_type="TestNode",
                field_specs={
                    field_key: resolved_field_spec(
                        presentation=field_presentation,
                        value=value,
                    )
                },
                cube_state=cube_state,
                resolved_behavior=snapshot.resolved_nodes_by_alias["A"]["node"],
                display_decision=snapshot.card_decisions_by_alias["A"]["node"],
                alias="A",
                prompt_field_inputs=prompt_field_inputs,
            ),
        )
        if wrapper is None:
            raise AssertionError("Field dependency scenario did not produce a card.")
        return wrapper

    def destroy(self, wrapper: QWidget) -> None:
        """Destroy the card and panel synchronously."""

        destroy_qt_object(wrapper)
        destroy_qt_object(self.panel)
