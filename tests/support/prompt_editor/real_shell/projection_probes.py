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

"""Probe projection routing and semantic settlement through a mounted editor."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.real_shell.input_driver import PromptEditorInputDriver
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorTraceAction,
    PromptFieldHandle,
    PromptProjectionTypingPathProbe,
    PromptSceneProjectionTimelineSample,
)
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


class PromptProjectionProbes:
    """Own real-input probes for production projection and semantic refresh paths."""

    def __init__(
        self,
        *,
        input_driver: PromptEditorInputDriver,
        trace_actions: list[PromptEditorTraceAction],
    ) -> None:
        """Bind path probes to one mounted prompt interaction session."""

        self._input = input_driver
        self._trace_actions = trace_actions

    def typed_scene(
        self,
        field: PromptFieldHandle,
        *,
        marker_text: str = "**Scene",
        settle_ms: int = 300,
    ) -> tuple[PromptSceneProjectionTimelineSample, ...]:
        """Probe scene projection after every real key and semantic settle boundary."""

        if settle_ms < 0:
            raise ValueError("Scene probe settle duration must not be negative.")
        target = self._input.focus_editor(field)
        started_at = perf_counter()
        samples = [
            scene_projection_sample(
                field.editor,
                label="before-input",
                started_at=started_at,
            )
        ]
        for character_index, character in enumerate(marker_text):
            QTest.keyClicks(target, character)
            samples.append(
                scene_projection_sample(
                    field.editor,
                    label=f"character-{character_index}:{character}",
                    started_at=started_at,
                )
            )
        wait_for_qt_condition(
            lambda: scene_projection_is_settled(field.editor),
            timeout_ms=max(1, settle_ms),
        )
        samples.append(
            scene_projection_sample(
                field.editor,
                label="settled",
                started_at=started_at,
            )
        )
        self._trace_actions.append(PromptEditorTraceAction("type_text", marker_text))
        return tuple(samples)

    def typed_paths(
        self,
        field: PromptFieldHandle,
        text: str,
    ) -> PromptProjectionTypingPathProbe:
        """Type through the real shell and record projection application paths."""

        def type_text(target: QWidget) -> None:
            """Send text through Qt's real key route."""

            QTest.keyClicks(target, text)

        probe = self._paths(field, input_label=text, input_action=type_text)
        self._trace_actions.append(PromptEditorTraceAction("type_text", text))
        return probe

    def key_path(
        self,
        field: PromptFieldHandle,
        *,
        key: Qt.Key,
        label: str,
    ) -> PromptProjectionTypingPathProbe:
        """Send one editing key and record the selected projection path."""

        def press_key(target: QWidget) -> None:
            """Send the editing key through Qt's real key route."""

            QTest.keyClick(target, key)

        probe = self._paths(field, input_label=label, input_action=press_key)
        self._trace_actions.append(PromptEditorTraceAction("key", label, key=int(key)))
        return probe

    def paste_paths(
        self,
        field: PromptFieldHandle,
        text: str,
    ) -> PromptProjectionTypingPathProbe:
        """Paste through the real clipboard and record projection paths."""

        QApplication.clipboard().setText(text)

        def paste(target: QWidget) -> None:
            """Send the platform paste shortcut through Qt's real key route."""

            QTest.keySequence(target, QKeySequence.StandardKey.Paste)

        probe = self._paths(field, input_label=text, input_action=paste)
        self._trace_actions.append(PromptEditorTraceAction("paste_text", text))
        return probe

    def undo_paths(self, field: PromptFieldHandle) -> PromptProjectionTypingPathProbe:
        """Undo through the real shortcut and record projection paths."""

        return self._history_paths(field, QKeySequence.StandardKey.Undo, "undo")

    def redo_paths(self, field: PromptFieldHandle) -> PromptProjectionTypingPathProbe:
        """Redo through the real shortcut and record projection paths."""

        return self._history_paths(field, QKeySequence.StandardKey.Redo, "redo")

    def _history_paths(
        self,
        field: PromptFieldHandle,
        standard_key: QKeySequence.StandardKey,
        label: str,
    ) -> PromptProjectionTypingPathProbe:
        """Send one history shortcut and record its production projection paths."""

        def restore_history(target: QWidget) -> None:
            """Send the requested history shortcut through Qt's real key route."""

            QTest.keySequence(target, standard_key)

        probe = self._paths(field, input_label=label, input_action=restore_history)
        self._trace_actions.append(PromptEditorTraceAction(label, ""))
        return probe

    def _paths(
        self,
        field: PromptFieldHandle,
        *,
        input_label: str,
        input_action: Callable[[QWidget], None],
    ) -> PromptProjectionTypingPathProbe:
        """Record the production path around one headless input action."""

        target = self._input.focus_editor(field)
        surface = cast(Any, field.editor)._surface
        edit_pipeline = surface._edit_pipeline
        original_rebuild = surface._rebuild_projection
        original_apply = edit_pipeline.apply
        canonical_rebuild_count = 0
        apply_paths: list[str] = []
        incremental_rejection_reasons: list[str] = []
        layout_rejection_reasons: list[str] = []

        def counted_rebuild() -> object:
            """Count and invoke one production canonical projection rebuild."""

            nonlocal canonical_rebuild_count
            canonical_rebuild_count += 1
            return original_rebuild()

        def recorded_apply(request: object) -> object:
            """Record the production path selected for one source change."""

            outcome = original_apply(request)
            apply_paths.append(str(outcome.apply_path.value))
            incremental_rejection_reasons.append(
                str(outcome.incremental_rejection_reason)
            )
            return outcome

        def record_layout_rejection(reason: str) -> None:
            """Record one rejected incremental frame transition."""

            layout_rejection_reasons.append(reason)

        surface._rebuild_projection = counted_rebuild
        edit_pipeline.apply = recorded_apply
        surface._layout.set_incremental_rejection_observer(record_layout_rejection)
        started_at = perf_counter()
        try:
            input_action(target)
            wait_for_queued_qt_turn()
        finally:
            surface._rebuild_projection = original_rebuild
            edit_pipeline.apply = original_apply
            surface._layout.set_incremental_rejection_observer(None)

        sample = scene_projection_sample(
            field.editor,
            label="typing-path-probe",
            started_at=started_at,
        )
        return PromptProjectionTypingPathProbe(
            typed_text=input_label,
            elapsed_ms=sample.elapsed_ms,
            canonical_rebuild_count=canonical_rebuild_count,
            apply_paths=tuple(apply_paths),
            incremental_rejection_reasons=tuple(incremental_rejection_reasons),
            layout_rejection_reasons=tuple(layout_rejection_reasons),
            source_text=sample.source_text,
            projection_text=sample.projection_text,
            scene_titles=sample.scene_titles,
        )


def scene_projection_is_settled(editor: PromptEditor) -> bool:
    """Return whether projection and semantic refresh have completed."""

    sample = scene_projection_sample(
        editor,
        label="settlement-check",
        started_at=perf_counter(),
    )
    return not (
        sample.projection_has_pending_update
        or sample.semantic_refresh_pending
        or sample.semantic_refresh_active
    )


def scene_projection_sample(
    editor: PromptEditor,
    *,
    label: str,
    started_at: float,
) -> PromptSceneProjectionTimelineSample:
    """Capture scene-relevant projection owners without draining events."""

    surface = cast(Any, editor)._surface
    interaction_controller = cast(Any, editor)._interaction_controller
    semantic_refresh = interaction_controller._semantic_refresh
    editor_state = surface.editor_state
    projection_document = editor_state.projection.document
    scene_titles = tuple(
        str(token.display_text)
        for token in projection_document.tokens
        if getattr(getattr(token, "kind", None), "value", None) == "scene"
    )
    return PromptSceneProjectionTimelineSample(
        label=label,
        elapsed_ms=(perf_counter() - started_at) * 1000.0,
        source_text=editor.toPlainText(),
        document_view_source_text=str(editor_state.semantic.document.source_text),
        projection_text=str(projection_document.projection_text),
        scene_titles=scene_titles,
        projection_freshness=str(surface._projection_freshness_controller.freshness),
        projection_has_pending_update=bool(
            surface._projection_freshness_controller.has_pending_update()
        ),
        semantic_refresh_pending=semantic_refresh._pending_request is not None,
        semantic_refresh_active=semantic_refresh._active_task_identity is not None,
        cursor_position=int(editor.textCursor().position()),
        focus_active=prompt_editor_focus_active(editor),
        focus_widget_path=object_path(QApplication.focusWidget()),
    )


def prompt_editor_focus_active(editor: PromptEditor) -> bool:
    """Return whether headless Qt retains prompt input ownership."""

    focused = QApplication.focusWidget()
    focus_proxy = editor.focusProxy()
    if editor.hasFocus() or focused is editor or focused is focus_proxy:
        return True
    if focused is not None and editor.isAncestorOf(focused):
        return True
    return focused is None and QGuiApplication.platformName().casefold() == "offscreen"


def object_path(widget: QWidget | None) -> str:
    """Return a stable diagnostic ancestry path for one Qt widget."""

    if widget is None:
        return "<none>"
    names: list[str] = []
    current: QWidget | None = widget
    while current is not None:
        object_name = current.objectName()
        names.append(
            type(current).__name__
            if not object_name
            else f"{type(current).__name__}#{object_name}"
        )
        current = current.parentWidget()
    return " <- ".join(names)
