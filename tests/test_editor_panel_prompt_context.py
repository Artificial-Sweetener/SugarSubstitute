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

"""Tests for editor-panel prompt workflow context reuse."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
import os
from types import SimpleNamespace
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from substitute.application.node_behavior import NodeBehaviorService
from substitute.application.prompt_editor import (
    PromptFeatureProfileService,
    ScheduledLoraProvider,
)
from substitute.domain.prompt import PromptEditorFeature, PromptFeatureDecision
from substitute.domain.prompt.features import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.view import EditorPanel
from tests.execution_test_helpers import immediate_editor_panel_execution_factories
from tests.localization_testing import empty_node_presentation_service


class _EmptyNodeDefinitionGateway:
    """Return empty node definitions for editor-panel construction."""

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no live node definition data for the requested class."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no required live node definition data for the requested class."""

        _ = node_class
        return {}


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication used by editor-panel tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _editor_panel(
    prompt_feature_profile_service: PromptFeatureProfileService | None = None,
    scheduled_lora_provider: ScheduledLoraProvider | None = None,
) -> EditorPanel:
    """Build an editor panel with inert prompt collaborators."""

    node_definition_gateway = _EmptyNodeDefinitionGateway()
    return EditorPanel(
        node_definition_gateway=node_definition_gateway,
        prompt_autocomplete_gateway=SimpleNamespace(),
        prompt_wildcard_catalog_gateway=SimpleNamespace(),
        node_behavior_service=NodeBehaviorService(
            node_definition_gateway=node_definition_gateway
        ),
        node_presentation_service=empty_node_presentation_service(),
        scheduled_lora_provider=scheduled_lora_provider,
        prompt_feature_profile_service=prompt_feature_profile_service,
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )


def test_workflow_prompt_context_reuses_context_for_unchanged_refresh_state() -> None:
    """Repeated prompt context requests should share one refresh-scoped object."""

    _ensure_qapp()
    panel = _editor_panel()
    cube_state = SimpleNamespace(buffer={"nodes": {}})
    panel._cube_states = {"Cube": cube_state}
    panel._stack_order = ["Cube"]

    try:
        first = panel.workflow_prompt_context()
        second = panel.workflow_prompt_context()

        assert first is second
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_workflow_prompt_context_changes_when_refresh_state_changes() -> None:
    """A stack change should create a new prompt workflow context."""

    _ensure_qapp()
    panel = _editor_panel()
    panel._cube_states = {
        "Cube": SimpleNamespace(buffer={"nodes": {}}),
        "Second": SimpleNamespace(buffer={"nodes": {}}),
    }
    panel._stack_order = ["Cube"]

    try:
        first = panel.workflow_prompt_context()
        panel._stack_order = ["Cube", "Second"]
        second = panel.workflow_prompt_context()

        assert first is not second
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_workflow_prompt_context_changes_when_cube_buffer_changes() -> None:
    """A restored cube buffer replacement should create a fresh prompt context."""

    _ensure_qapp()
    panel = _editor_panel()
    cube_state = SimpleNamespace(buffer={"nodes": {}})
    panel._cube_states = {"Cube": cube_state}
    panel._stack_order = ["Cube"]

    try:
        first = panel.workflow_prompt_context()
        cube_state.buffer = {
            "nodes": {
                "schedule": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {"positive_prompt": "cat"},
                }
            }
        }
        second = panel.workflow_prompt_context()

        assert first is not second
        assert second.cube_states["Cube"] is cube_state
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_feature_profile_cache_reuses_same_prompt_request() -> None:
    """Repeated prompt profile requests in one render scope should call service once."""

    _ensure_qapp()
    service = _PromptFeatureProfileService()
    panel = _editor_panel(cast(PromptFeatureProfileService, service))
    panel._cube_states = {"Cube": SimpleNamespace(buffer={"nodes": {}})}
    panel._stack_order = ["Cube"]

    try:
        first = panel.prompt_feature_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {"prompt_syntaxes": ["wildcard"]},
        )
        second = panel.prompt_feature_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {"prompt_syntaxes": ["wildcard"]},
        )

        assert first is second
        assert len(service.calls) == 1
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_feature_profile_cache_separates_field_identity_and_style() -> None:
    """Prompt profile cache keys should include field identity and field style."""

    _ensure_qapp()
    service = _PromptFeatureProfileService()
    panel = _editor_panel(cast(PromptFeatureProfileService, service))
    panel._cube_states = {"Cube": SimpleNamespace(buffer={"nodes": {}})}
    panel._stack_order = ["Cube"]

    try:
        panel.prompt_feature_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {"prompt_syntaxes": ["wildcard"]},
        )
        panel.prompt_feature_profile_for_prompt(
            "Cube",
            "negative_prompt",
            "value",
            {"prompt_syntaxes": ["wildcard"]},
        )
        panel.prompt_feature_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {"prompt_syntaxes": ["emphasis"]},
        )

        assert len(service.calls) == 3
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_feature_profile_cache_resets_when_prompt_context_changes() -> None:
    """Prompt profile cache should not survive a changed workflow render scope."""

    _ensure_qapp()
    service = _PromptFeatureProfileService()
    panel = _editor_panel(cast(PromptFeatureProfileService, service))
    panel._cube_states = {
        "Cube": SimpleNamespace(buffer={"nodes": {}}),
        "Second": SimpleNamespace(buffer={"nodes": {}}),
    }
    panel._stack_order = ["Cube"]

    try:
        panel.prompt_feature_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {},
        )
        panel._stack_order = ["Cube", "Second"]
        panel.prompt_feature_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {},
        )

        assert len(service.calls) == 2
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_feature_profile_returns_none_without_service() -> None:
    """Panels without a prompt feature service should preserve fallback behavior."""

    _ensure_qapp()
    panel = _editor_panel()

    try:
        assert (
            panel.prompt_feature_profile_for_prompt(
                "Cube",
                "positive_prompt",
                "value",
                {},
            )
            is None
        )
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_field_profile_uses_fallback_without_service() -> None:
    """Prepared prompt field profiles should cover service-absent panels."""

    _ensure_qapp()
    panel = _editor_panel()

    try:
        decision = panel.prompt_field_profile_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
            {"prompt_syntaxes": ["wildcard"]},
        )

        assert decision.feature_profile.supports(PromptEditorFeature.WILDCARD_SYNTAX)
        assert decision.syntax_profile.enabled_syntaxes == ("wildcard",)
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_scheduled_lora_resolver_uses_configured_panel_provider() -> None:
    """Scheduled-LoRA prompt contexts should read the provider from panel services."""

    _ensure_qapp()
    provider = _ScheduledLoraProvider()
    panel = _editor_panel(scheduled_lora_provider=cast(ScheduledLoraProvider, provider))
    panel._cube_states = {"Cube": SimpleNamespace(buffer={"nodes": {}})}
    panel._stack_order = ["Cube"]

    try:
        resolver = panel.scheduled_lora_resolver_for_prompt(
            "Cube",
            "positive_prompt",
            "value",
        )

        assert resolver is not None
        assert resolver("cat") == ()
        assert provider.calls == [("Cube", "positive_prompt", "value", "cat")]
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_projection_prompt_context_snapshots_cube_buffers() -> None:
    """Projection prompt context should not observe later live buffer mutation."""

    _ensure_qapp()
    panel = _editor_panel()
    cube_state = SimpleNamespace(
        cube_id="cube.id",
        version="1.0",
        display_name="Cube",
        ui={"source": {"kind": "catalog"}},
        buffer={
            "nodes": {
                "positive_prompt": {
                    "inputs": {"value": "before"},
                },
            },
        },
    )

    try:
        panel.begin_projection_prompt_context(
            cube_states={"Cube": cube_state},
            stack_order=["Cube"],
            reason="test_projection",
        )
        cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["value"] = "after"

        context = panel._prompt_workflow_context_for_feature_profiles()
        snapshot = context.cube_states["Cube"]
        nodes = cast(
            dict[str, dict[str, dict[str, str]]],
            snapshot.buffer["nodes"],
        )

        assert nodes["positive_prompt"]["inputs"]["value"] == "before"
    finally:
        panel.clear_projection_prompt_context(reason="test_cleanup")
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_feature_profile_uses_projection_context_while_active() -> None:
    """Prompt profile resolution should share the projection context during restore."""

    _ensure_qapp()
    service = _PromptFeatureProfileService()
    panel = _editor_panel(cast(PromptFeatureProfileService, service))
    cube_state = SimpleNamespace(
        cube_id="cube.id",
        version="1.0",
        display_name="Cube",
        ui=None,
        buffer={"nodes": {}},
    )

    try:
        panel.begin_projection_prompt_context(
            cube_states={"Cube": cube_state},
            stack_order=["Cube"],
            reason="test_projection",
        )
        panel.prompt_feature_profile_for_prompt("Cube", "positive_prompt", "value", {})
        panel.prompt_feature_profile_for_prompt("Cube", "negative_prompt", "value", {})

        assert len(service.contexts) == 2
        projection_context = panel._prompt_context_controller.projection_prompt_context
        assert service.contexts[0] is projection_context
        assert service.contexts[1] is projection_context
    finally:
        panel.clear_projection_prompt_context(reason="test_cleanup")
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_clearing_projection_prompt_context_returns_to_live_context() -> None:
    """Projection-scoped profiles should not be reused after projection clears."""

    _ensure_qapp()
    service = _PromptFeatureProfileService()
    panel = _editor_panel(cast(PromptFeatureProfileService, service))
    cube_state = SimpleNamespace(
        cube_id="cube.id",
        version="1.0",
        display_name="Cube",
        ui=None,
        buffer={"nodes": {}},
    )
    panel._cube_states = {"Cube": cube_state}
    panel._stack_order = ["Cube"]

    try:
        panel.begin_projection_prompt_context(
            cube_states={"Cube": cube_state},
            stack_order=["Cube"],
            reason="test_projection",
        )
        panel.prompt_feature_profile_for_prompt("Cube", "positive_prompt", "value", {})
        projection_context = service.contexts[-1]
        panel.clear_projection_prompt_context(reason="test_complete")
        panel.prompt_feature_profile_for_prompt("Cube", "positive_prompt", "value", {})

        assert len(service.contexts) == 2
        assert service.contexts[0] is projection_context
        assert service.contexts[1] is panel.workflow_prompt_context()
        assert service.contexts[1] is not projection_context
    finally:
        panel.clear_projection_prompt_context(reason="test_cleanup")
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_changing_projection_prompt_context_resets_profile_cache() -> None:
    """Starting a new projection scope should clear prior projection profiles."""

    _ensure_qapp()
    service = _PromptFeatureProfileService()
    panel = _editor_panel(cast(PromptFeatureProfileService, service))
    cube_state = SimpleNamespace(
        cube_id="cube.id",
        version="1.0",
        display_name="Cube",
        ui=None,
        buffer={"nodes": {}},
    )
    second_state = SimpleNamespace(
        cube_id="second.id",
        version="1.0",
        display_name="Second",
        ui=None,
        buffer={"nodes": {}},
    )

    try:
        panel.begin_projection_prompt_context(
            cube_states={"Cube": cube_state},
            stack_order=["Cube"],
            reason="test_projection",
        )
        panel.prompt_feature_profile_for_prompt("Cube", "positive_prompt", "value", {})
        panel.begin_projection_prompt_context(
            cube_states={"Cube": cube_state, "Second": second_state},
            stack_order=["Cube", "Second"],
            reason="test_projection",
        )
        panel.prompt_feature_profile_for_prompt("Cube", "positive_prompt", "value", {})

        assert len(service.calls) == 2
        assert service.contexts[0] is not service.contexts[1]
    finally:
        panel.clear_projection_prompt_context(reason="test_cleanup")
        panel.deleteLater()
        _ensure_qapp().processEvents()


class _ScheduledLoraProvider:
    """Record scheduled-LoRA prompt-context resolution requests."""

    def __init__(self) -> None:
        """Initialize an empty request log."""

        self.calls: list[tuple[str | None, str, str, str]] = []

    def scheduled_loras_for_prompt_context(
        self,
        *,
        workflow_context: Any,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        prompt_text: str,
    ) -> tuple[()]:
        """Record one resolution request and return no scheduled LoRAs."""

        _ = workflow_context
        self.calls.append((cube_alias, prompt_node_name, prompt_field_key, prompt_text))
        return ()


class _PromptFeatureProfileService:
    """Record prompt profile requests and return stable profile instances."""

    def __init__(self) -> None:
        """Initialize the service test double."""

        self.calls: list[tuple[str | None, str, str, dict[str, object]]] = []
        self.contexts: list[object] = []
        self._profiles: dict[
            tuple[str | None, str, str, tuple[tuple[str, object], ...]],
            PromptEditorFeatureProfile,
        ] = {}

    def build_profile(
        self,
        *,
        field_style: MappingABC[str, object],
        workflow_context: object,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptEditorFeatureProfile:
        """Record one call and return a stable profile for the request key."""

        copied_style = dict(field_style)
        self.calls.append(
            (cube_alias, prompt_node_name, prompt_field_key, copied_style)
        )
        self.contexts.append(workflow_context)
        key = (
            cube_alias,
            prompt_node_name,
            prompt_field_key,
            tuple((key, repr(value)) for key, value in sorted(copied_style.items())),
        )
        profile = self._profiles.get(key)
        if profile is None:
            profile = PromptEditorFeatureProfile(
                decisions=(
                    PromptFeatureDecision(
                        feature=PromptEditorFeature.EMPHASIS,
                        enabled=True,
                    ),
                )
            )
            self._profiles[key] = profile
        return profile
