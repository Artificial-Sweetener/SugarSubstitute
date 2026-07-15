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
from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QTimer
import pytest

import substitute.presentation.editor.panel.prompt_scene_diagnostics_controller as mod


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


def test_prompt_scene_diagnostics_signal_configuration_is_idempotent() -> None:
    """Prompt editors should only receive scene diagnostics signal wiring once."""

    editor = _PromptEditorDouble()
    prompt_editor = cast(mod.PromptSceneEditorProtocol, editor)
    controller = mod.EditorPanelPromptSceneDiagnosticsController(
        cast(
            mod.EditorPanelPromptSceneDiagnosticsHost,
            SimpleNamespace(findChildren=lambda _type: []),
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
            SimpleNamespace(findChildren=lambda _type: []),
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
    )
    controller = mod.EditorPanelPromptSceneDiagnosticsController(
        cast(mod.EditorPanelPromptSceneDiagnosticsHost, host)
    )

    controller.refresh_prompt_scene_diagnostics()

    assert editor.error_key_calls == [frozenset()]
    assert editor.autocomplete_title_calls == [()]
    assert editor.queueable_key_calls == [frozenset()]
    assert controller.last_snapshot is None
