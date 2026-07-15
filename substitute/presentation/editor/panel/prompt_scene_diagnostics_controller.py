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

"""Own editor-panel prompt scene diagnostics scheduling and publication."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QTimer

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.prompt_editor import (
    PromptSceneAnalysisService,
    PromptSceneWorkflowCube,
    WorkflowSceneAnalysis,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.prompt_scene_diagnostics_controller")


class SignalConnectorProtocol(Protocol):
    """Describe a Qt-like signal that accepts connected callables."""

    def connect(self, callback: Callable[..., object]) -> None:
        """Connect one callback to the signal."""


class SignalEmitterProtocol(Protocol):
    """Describe a Qt-like signal that can emit one scene key."""

    def emit(self, scene_key: str) -> object:
        """Emit one normalized scene key."""


class PromptSceneEditorProtocol(Protocol):
    """Describe prompt editor scene APIs used by the panel controller."""

    textChanged: SignalConnectorProtocol
    sceneQueueRequested: SignalConnectorProtocol

    def property(self, name: str) -> object:
        """Return one dynamic Qt property."""

    def setProperty(self, name: str, value: object) -> object:
        """Set one dynamic Qt property."""

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Publish normalized scene keys that should render as errors."""

    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Publish scene titles available for line-start autocomplete."""

    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None:
        """Publish scene keys available for queue actions."""


class PromptSceneAnalysisServiceProtocol(Protocol):
    """Describe workflow prompt-scene analysis used by the controller."""

    def analyze(
        self,
        *,
        workflow: EditorPromptSceneWorkflow,
        endpoint_index: object,
    ) -> WorkflowSceneAnalysis:
        """Analyze one workflow and endpoint index for scene diagnostics."""


class EditorPanelPromptSceneDiagnosticsHost(Protocol):
    """Describe panel state needed for prompt scene diagnostics."""

    promptSceneQueueRequested: SignalEmitterProtocol
    _cube_states: Mapping[str, object] | None
    _stack_order: Sequence[str] | None
    _last_behavior_snapshot: EditorBehaviorSnapshot | None

    def findChildren(
        self,
        child_type: type[PromptEditor],
    ) -> list[PromptSceneEditorProtocol]:
        """Return child prompt editors hosted by the panel."""


@dataclass(frozen=True, slots=True)
class EditorPromptSceneWorkflow:
    """Adapt editor-panel cube state to the prompt scene analysis protocol."""

    stack_order: tuple[str, ...]
    cubes: Mapping[str, PromptSceneWorkflowCube]


@dataclass(frozen=True, slots=True)
class PromptSceneDiagnosticsSnapshot:
    """Capture scene diagnostics prepared for live prompt editors."""

    context_key: tuple[Hashable, ...]
    authority_endpoint_key: tuple[str, str, str] | None
    scene_titles: tuple[str, ...]
    queueable_scene_keys: frozenset[str]
    diagnostics_by_endpoint_key: Mapping[tuple[str, str, str], frozenset[str]]


class EditorPanelPromptSceneDiagnosticsController:
    """Coordinate panel-level scene diagnostics and queue action readiness."""

    def __init__(
        self,
        host: EditorPanelPromptSceneDiagnosticsHost,
        *,
        analysis_service: PromptSceneAnalysisServiceProtocol | None = None,
    ) -> None:
        """Store the host and initialize deferred-refresh state."""

        self._host = host
        self._analysis_service = analysis_service or PromptSceneAnalysisService()
        self._refresh_pending = False
        self._last_snapshot: PromptSceneDiagnosticsSnapshot | None = None

    @property
    def refresh_pending(self) -> bool:
        """Return whether a deferred diagnostics refresh is queued."""

        return self._refresh_pending

    @property
    def last_snapshot(self) -> PromptSceneDiagnosticsSnapshot | None:
        """Return the most recent prepared scene diagnostics snapshot."""

        return self._last_snapshot

    def configure_prompt_scene_diagnostics(
        self,
        prompt_editor: PromptSceneEditorProtocol,
    ) -> None:
        """Attach workflow-scene diagnostics refresh to one prompt editor."""

        if prompt_editor.property("promptSceneDiagnosticsTracked") is True:
            return
        prompt_editor.setProperty("promptSceneDiagnosticsTracked", True)
        prompt_editor.textChanged.connect(self.schedule_prompt_scene_diagnostics)
        prompt_editor.sceneQueueRequested.connect(
            self.handle_prompt_scene_queue_requested
        )

    def schedule_prompt_scene_diagnostics(self) -> None:
        """Defer scene diagnostics until prompt text has reached workflow buffers."""

        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self.refresh_scheduled_prompt_scene_diagnostics)

    def refresh_scheduled_prompt_scene_diagnostics(self) -> None:
        """Apply one deferred prompt-scene diagnostics refresh."""

        self._refresh_pending = False
        self.refresh_prompt_scene_diagnostics()

    def refresh_prompt_scene_diagnostics(self) -> None:
        """Push current workflow scene diagnostics into all live prompt editors."""

        snapshot = self.build_prompt_scene_diagnostics_snapshot()
        if snapshot is None:
            self._last_snapshot = None
            self.clear_prompt_scene_diagnostics()
            return
        self._last_snapshot = snapshot
        for prompt_editor in self._prompt_editors():
            self._apply_snapshot_to_prompt_editor(snapshot, prompt_editor)

    def clear_prompt_scene_diagnostics(self) -> None:
        """Clear scene diagnostics from all live prompt editors."""

        for prompt_editor in self._prompt_editors():
            prompt_editor.set_scene_error_keys(frozenset())
            prompt_editor.set_scene_autocomplete_titles(())
            prompt_editor.set_queueable_scene_keys(frozenset())

    def current_prompt_scene_analysis(self) -> WorkflowSceneAnalysis | None:
        """Return current workflow scene analysis when editor state is ready."""

        snapshot = self._current_behavior_snapshot()
        if (
            snapshot is None
            or not self._host._cube_states
            or not self._host._stack_order
        ):
            return None
        return self._analysis_service.analyze(
            workflow=EditorPromptSceneWorkflow(
                stack_order=tuple(self._host._stack_order),
                cubes=cast(
                    Mapping[str, PromptSceneWorkflowCube],
                    self._host._cube_states,
                ),
            ),
            endpoint_index=snapshot.prompt_endpoint_index,
        )

    def build_prompt_scene_diagnostics_snapshot(
        self,
    ) -> PromptSceneDiagnosticsSnapshot | None:
        """Prepare a scene diagnostics snapshot for the current panel state."""

        analysis = self.current_prompt_scene_analysis()
        if analysis is None:
            return None
        authority_endpoint = analysis.authority_endpoint
        authority_endpoint_key = (
            (
                authority_endpoint.cube_alias,
                authority_endpoint.node_name,
                authority_endpoint.field_key,
            )
            if authority_endpoint is not None
            else None
        )
        return PromptSceneDiagnosticsSnapshot(
            context_key=self._scene_context_key(analysis),
            authority_endpoint_key=authority_endpoint_key,
            scene_titles=tuple(scene.title for scene in analysis.scenes),
            queueable_scene_keys=frozenset(scene.key for scene in analysis.scenes),
            diagnostics_by_endpoint_key={
                (endpoint.cube_alias, endpoint.node_name, endpoint.field_key): (
                    diagnostics.orphan_scene_keys
                )
                for endpoint, diagnostics in analysis.diagnostics_by_endpoint.items()
            },
        )

    def handle_prompt_scene_queue_requested(self, scene_key: str) -> None:
        """Forward one prompt scene queue request when the scene is runnable."""

        analysis = self.current_prompt_scene_analysis()
        if analysis is None:
            return
        if scene_key not in {scene.key for scene in analysis.scenes}:
            log_warning(
                _LOGGER,
                "Ignored non-runnable prompt scene queue request",
                scene_key=scene_key,
            )
            return
        self._host.promptSceneQueueRequested.emit(scene_key)

    def _apply_snapshot_to_prompt_editor(
        self,
        snapshot: PromptSceneDiagnosticsSnapshot,
        prompt_editor: PromptSceneEditorProtocol,
    ) -> None:
        """Publish one scene diagnostics snapshot to a prompt editor."""

        metadata = prompt_editor.property("input_metadata")
        if not isinstance(metadata, dict):
            prompt_editor.set_scene_error_keys(frozenset())
            prompt_editor.set_scene_autocomplete_titles(())
            prompt_editor.set_queueable_scene_keys(frozenset())
            return
        prompt_editor.set_queueable_scene_keys(snapshot.queueable_scene_keys)
        raw_endpoint_key = (
            metadata.get("cube_alias"),
            metadata.get("node_name"),
            metadata.get("key"),
        )
        endpoint_key = (
            cast(tuple[str, str, str], raw_endpoint_key)
            if all(isinstance(value, str) for value in raw_endpoint_key)
            else None
        )
        prompt_editor.set_scene_autocomplete_titles(
            ()
            if endpoint_key == snapshot.authority_endpoint_key
            else snapshot.scene_titles
        )
        prompt_editor.set_scene_error_keys(
            snapshot.diagnostics_by_endpoint_key.get(endpoint_key, frozenset())
            if endpoint_key is not None
            else frozenset()
        )

    def _current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest behavior snapshot from the host or test double."""

        current_behavior_snapshot = getattr(
            self._host,
            "current_behavior_snapshot",
            None,
        )
        if callable(current_behavior_snapshot):
            snapshot = current_behavior_snapshot()
            return cast(EditorBehaviorSnapshot | None, snapshot)
        return cast(
            EditorBehaviorSnapshot | None,
            getattr(self._host, "_last_behavior_snapshot", None),
        )

    def _prompt_editors(self) -> tuple[PromptSceneEditorProtocol, ...]:
        """Return live prompt editors from the host panel."""

        return tuple(self._host.findChildren(PromptEditor))

    def _scene_context_key(
        self,
        analysis: WorkflowSceneAnalysis,
    ) -> tuple[Hashable, ...]:
        """Return the identity key used to describe the prepared scene snapshot."""

        stack_order = tuple(self._host._stack_order or ())
        cube_states = self._host._cube_states or {}
        authority_endpoint = analysis.authority_endpoint
        authority_key: tuple[str, str, str] | None = (
            (
                authority_endpoint.cube_alias,
                authority_endpoint.node_name,
                authority_endpoint.field_key,
            )
            if authority_endpoint is not None
            else None
        )
        scene_keys = tuple(scene.key for scene in analysis.scenes)
        return (
            id(self._current_behavior_snapshot()),
            tuple((alias, id(cube_states.get(alias))) for alias in stack_order),
            authority_key,
            scene_keys,
        )


__all__ = [
    "EditorPanelPromptSceneDiagnosticsController",
    "EditorPanelPromptSceneDiagnosticsHost",
    "EditorPromptSceneWorkflow",
    "PromptSceneEditorProtocol",
    "PromptSceneDiagnosticsSnapshot",
    "SignalConnectorProtocol",
    "SignalEmitterProtocol",
]
