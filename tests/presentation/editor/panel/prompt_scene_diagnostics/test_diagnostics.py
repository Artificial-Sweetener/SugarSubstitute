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

"""Tests for editor-panel prompt scene diagnostics ownership."""

from __future__ import annotations

from collections.abc import Callable
import importlib
from types import ModuleType, SimpleNamespace
from typing import cast

from PySide6.QtCore import QTimer
import pytest

import substitute.presentation.editor.panel.prompt.scene_diagnostics as mod
from substitute.application.node_behavior import PromptRole
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex


class _SignalDouble:
    """Record callbacks connected to a Qt-like signal."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self.callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Record one connected callback."""

        self.callbacks.append(callback)


class _PromptEditorDouble:
    """Minimal prompt editor scene API used by the diagnostics controller."""

    def __init__(self, metadata: dict[str, str] | None = None) -> None:
        """Initialize metadata, signals, and publication call logs."""

        self._properties: dict[str, object] = {}
        if metadata is not None:
            self._properties["input_metadata"] = metadata
        self.textChanged = _SignalDouble()
        self.sceneQueueRequested = _SignalDouble()
        self.error_key_calls: list[frozenset[str]] = []
        self.autocomplete_title_calls: list[tuple[str, ...]] = []
        self.queueable_key_calls: list[frozenset[str]] = []

    def property(self, name: str) -> object:
        """Return one dynamic property value."""

        return self._properties.get(name)

    def setProperty(self, name: str, value: object) -> None:
        """Store one dynamic property value."""

        self._properties[name] = value

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Record published scene error keys."""

        self.error_key_calls.append(scene_error_keys)

    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Record published scene autocomplete titles."""

        self.autocomplete_title_calls.append(titles)

    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None:
        """Record published queueable scene keys."""

        self.queueable_key_calls.append(scene_keys)


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_prompt_scene_diagnostics_signal_configuration_is_idempotent() -> None:
    """Prompt editors should only receive scene diagnostics signal wiring once."""

    editor = _PromptEditorDouble()
    prompt_editor = cast(mod.PromptSceneEditorProtocol, editor)
    controller = mod.EditorPanelPromptSceneDiagnosticsController(
        cast(
            mod.EditorPanelPromptSceneDiagnosticsHost,
            SimpleNamespace(
                findChildren=lambda _type: [],
                current_behavior_snapshot=lambda: None,
            ),
        )
    )

    controller.configure_prompt_scene_diagnostics(prompt_editor)
    controller.configure_prompt_scene_diagnostics(prompt_editor)

    assert editor.property("promptSceneDiagnosticsTracked") is True
    assert editor.textChanged.callbacks == [
        controller.schedule_prompt_scene_diagnostics
    ]
    assert editor.sceneQueueRequested.callbacks == [
        controller.handle_prompt_scene_queue_requested
    ]


def test_prompt_scene_diagnostics_scheduling_coalesces_until_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple prompt text changes should queue one deferred scene refresh."""

    scheduled_callbacks: list[Callable[[], None]] = []

    def record_single_shot(_delay: int, callback: Callable[[], None]) -> None:
        """Record one deferred callback instead of scheduling through Qt."""

        scheduled_callbacks.append(callback)

    monkeypatch.setattr(QTimer, "singleShot", record_single_shot)
    controller = mod.EditorPanelPromptSceneDiagnosticsController(
        cast(
            mod.EditorPanelPromptSceneDiagnosticsHost,
            SimpleNamespace(
                findChildren=lambda _type: [],
                current_behavior_snapshot=lambda: None,
            ),
        )
    )

    controller.schedule_prompt_scene_diagnostics()
    controller.schedule_prompt_scene_diagnostics()

    assert controller.refresh_pending is True
    assert scheduled_callbacks == [
        controller.refresh_scheduled_prompt_scene_diagnostics
    ]

    scheduled_callbacks[0]()

    assert controller.refresh_pending is False


def test_prompt_scene_diagnostics_clear_when_analysis_unavailable() -> None:
    """Unavailable panel scene analysis should clear stale prompt editor state."""

    editor = _PromptEditorDouble()
    host = SimpleNamespace(
        _last_behavior_snapshot=None,
        _stack_order=[],
        _cube_states={},
        findChildren=lambda _type: [editor],
        current_behavior_snapshot=lambda: None,
    )
    controller = mod.EditorPanelPromptSceneDiagnosticsController(
        cast(mod.EditorPanelPromptSceneDiagnosticsHost, host)
    )

    controller.refresh_prompt_scene_diagnostics()

    assert editor.error_key_calls == [frozenset()]
    assert editor.autocomplete_title_calls == [()]
    assert editor.queueable_key_calls == [frozenset()]
    assert controller.last_snapshot is None


def test_refresh_prompt_scene_diagnostics_scopes_errors_and_autocomplete() -> None:
    """Scene diagnostics should keep duplicate and authority autocomplete scope local."""

    panel_module = _panel_module()
    authority_editor = _PromptEditorDouble(
        {
            "cube_alias": "Text",
            "node_name": "positive_prompt",
            "key": "text",
        }
    )
    negative_editor = _PromptEditorDouble(
        {
            "cube_alias": "Text",
            "node_name": "negative_prompt",
            "key": "text",
        }
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="text",
            ),
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.NEGATIVE,
                node_name="negative_prompt",
                field_key="text",
            ),
        )
    )
    behavior_snapshot = SimpleNamespace(prompt_endpoint_index=endpoint_index)
    panel = SimpleNamespace(
        _last_behavior_snapshot=behavior_snapshot,
        _stack_order=["Text"],
        _cube_states={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {
                                "text": "**portrait\none\n**Portrait\nduplicate\n**cafe\ncafe"
                            }
                        },
                        "negative_prompt": {
                            "inputs": {"text": "generic\n**hands\nbad hands"}
                        },
                    }
                }
            )
        },
        _clear_prompt_scene_diagnostics=lambda: None,
        findChildren=lambda _class: [authority_editor, negative_editor],
        current_behavior_snapshot=lambda: behavior_snapshot,
    )
    panel._prompt_scene_diagnostics_controller = (
        panel_module.EditorPanelPromptSceneDiagnosticsController(panel)
    )

    panel_module.EditorPanel.refresh_prompt_scene_diagnostics(panel)

    assert authority_editor.autocomplete_title_calls == [()]
    assert authority_editor.error_key_calls == [frozenset()]
    assert authority_editor.queueable_key_calls == [frozenset({"portrait", "cafe"})]
    assert negative_editor.autocomplete_title_calls == [("portrait", "cafe")]
    assert negative_editor.error_key_calls == [frozenset({"hands"})]
    assert negative_editor.queueable_key_calls == [frozenset({"portrait", "cafe"})]


def test_prompt_scene_queue_request_forwards_only_runnable_scene_keys() -> None:
    """EditorPanel should forward only scene keys from the authority scene list."""

    panel_module = _panel_module()
    emitted_keys: list[str] = []
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="text",
            ),
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.NEGATIVE,
                node_name="negative_prompt",
                field_key="text",
            ),
        )
    )
    behavior_snapshot = SimpleNamespace(prompt_endpoint_index=endpoint_index)
    panel = SimpleNamespace(
        _last_behavior_snapshot=behavior_snapshot,
        _stack_order=["Text"],
        _cube_states={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {"text": "**portrait\none\n**cafe\ncafe"}
                        },
                        "negative_prompt": {
                            "inputs": {"text": "generic\n**hands\nbad hands"}
                        },
                    }
                }
            )
        },
        promptSceneQueueRequested=SimpleNamespace(emit=emitted_keys.append),
        current_behavior_snapshot=lambda: behavior_snapshot,
    )
    panel._prompt_scene_diagnostics_controller = (
        panel_module.EditorPanelPromptSceneDiagnosticsController(panel)
    )

    panel_module.EditorPanel._handle_prompt_scene_queue_requested(panel, "portrait")
    panel_module.EditorPanel._handle_prompt_scene_queue_requested(panel, "hands")

    assert emitted_keys == ["portrait"]


def test_prompt_scene_queue_request_without_analysis_is_suppressed() -> None:
    """EditorPanel should not forward scene queue requests before analysis is ready."""

    panel_module = _panel_module()
    emitted_keys: list[str] = []
    panel = SimpleNamespace(
        _last_behavior_snapshot=None,
        _stack_order=[],
        _cube_states={},
        promptSceneQueueRequested=SimpleNamespace(emit=emitted_keys.append),
        current_behavior_snapshot=lambda: None,
    )
    panel._prompt_scene_diagnostics_controller = (
        panel_module.EditorPanelPromptSceneDiagnosticsController(panel)
    )

    panel_module.EditorPanel._handle_prompt_scene_queue_requested(panel, "portrait")

    assert emitted_keys == []
