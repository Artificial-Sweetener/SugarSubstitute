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

"""Probe production prompt context-menu behavior through the real Qt boundary."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter, thread_time
from typing import Any, cast

from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication, QPoint, Qt
from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorContextMenuTrace,
    PromptEditorTraceAction,
    PromptFieldHandle,
    PromptInlineLoraMenuProbe,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


class PromptContextMenuProbe:
    """Capture real menu presentation and LoRA-action behavior for one session."""

    def __init__(self, trace_actions: list[PromptEditorTraceAction]) -> None:
        """Write menu interactions into the owning session trace."""

        self._trace_actions = trace_actions

    def trace(
        self,
        field: PromptFieldHandle,
        *,
        clicked_text: str,
        trigger_first_lora_action: bool = False,
        trigger_lora_action_label: str | None = None,
        before_trigger_lora_action: Callable[[], None] | None = None,
        populate_lazy_submenus: bool = True,
    ) -> PromptEditorContextMenuTrace:
        """Open a real prompt context menu and capture LoRA trigger action state.

        Args:
            field: Mounted production prompt field to exercise.
            clicked_text: Visible source fragment that receives the right-click.
            trigger_first_lora_action: Trigger the first captured LoRA action.
            trigger_lora_action_label: Trigger the action whose visible or full label
                matches this value.
            before_trigger_lora_action: Run a lifecycle mutation after menu capture
                but before triggering the selected LoRA action.
            populate_lazy_submenus: Populate lazy QFluent submenus for inspection.
        """

        if trigger_first_lora_action and trigger_lora_action_label is not None:
            raise ValueError("choose either the first action or a named action")

        from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
            RoundMenu,
        )
        from substitute.presentation.editor.prompt_editor.shell import (
            context_menu_controller as prompt_context_menu_module,
        )

        editor = field.editor
        source_before = editor.toPlainText()
        local_pos = viewport_position_for_source_text(editor, clicked_text)
        viewport = editor.viewport()
        global_pos = viewport.mapToGlobal(local_pos)
        click_source_position = source_position_for_text(editor, clicked_text)
        snapshot_before = prepared_lora_action_snapshot(editor, source_before)
        cached_before = cached_scheduled_loras(editor, source_before)
        captured_menu_rows: list[str] = []
        captured_submenu_rows: list[tuple[str, tuple[str, ...]]] = []
        captured_trigger_actions: list[QAction] = []
        triggered_action_text: str | None = None
        original_exec = RoundMenu.exec
        text_menu_class = cast(
            Any, prompt_context_menu_module
        )._PromptEditorTextEditMenu
        original_text_menu_exec = text_menu_class.exec
        event_dispatch_elapsed_ms = 0.0
        menu_exec_elapsed_ms = 0.0
        text_menu_exec_elapsed_ms = 0.0

        def capture_exec(menu: object, *_args: object, **_kwargs: object) -> None:
            """Capture the real QFluent menu instead of showing a native popup."""

            nonlocal menu_exec_elapsed_ms
            nonlocal triggered_action_text
            started_at = thread_time()
            captured_menu_rows.extend(round_menu_rows(menu))
            if populate_lazy_submenus:
                populate_lazy_round_menu_submenus(menu)
            captured_submenu_rows.extend(round_menu_submenu_rows(menu))
            captured_trigger_actions.extend(round_menu_trigger_actions(menu))
            action = selected_trigger_action(
                tuple(captured_trigger_actions),
                trigger_first=trigger_first_lora_action,
                requested_label=trigger_lora_action_label,
            )
            if action is not None:
                if before_trigger_lora_action is not None:
                    before_trigger_lora_action()
                triggered_action_text = action.text()
                action.trigger()
            menu_exec_elapsed_ms += (thread_time() - started_at) * 1000.0

        def capture_text_menu_exec(
            menu: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            """Measure prompt menu population before the final RoundMenu boundary."""

            nonlocal text_menu_exec_elapsed_ms
            started_at = thread_time()
            try:
                return original_text_menu_exec(menu, *args, **kwargs)
            finally:
                text_menu_exec_elapsed_ms += (thread_time() - started_at) * 1000.0

        RoundMenu.exec = capture_exec
        text_menu_class.exec = capture_text_menu_exec
        try:
            started_at = perf_counter()
            press_event = QMouseEvent(
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QPointF(local_pos),
                QtCore.QPointF(global_pos),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QCoreApplication.sendEvent(viewport, press_event)
            context_event = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                local_pos,
                global_pos,
            )
            QCoreApplication.sendEvent(viewport, context_event)
            event_dispatch_elapsed_ms = (perf_counter() - started_at) * 1000.0
            wait_for_queued_qt_turn()
        finally:
            text_menu_class.exec = original_text_menu_exec
            RoundMenu.exec = original_exec

        source_after = editor.toPlainText()
        snapshot_after = prepared_lora_action_snapshot(editor, source_after)
        cached_after = cached_scheduled_loras(editor, source_after)
        self._trace_actions.append(
            PromptEditorTraceAction("context_menu", clicked_text)
        )
        return PromptEditorContextMenuTrace(
            source_before=source_before,
            source_after=source_after,
            clicked_text=clicked_text,
            click_source_position=click_source_position,
            menu_rows=tuple(captured_menu_rows),
            submenu_rows=tuple(captured_submenu_rows),
            trigger_action_texts=tuple(
                action.text() for action in captured_trigger_actions
            ),
            trigger_action_full_labels=tuple(
                str(action.property("promptFullTriggerWordsLabel"))
                for action in captured_trigger_actions
            ),
            triggered_action_text=triggered_action_text,
            lora_snapshot_readiness_before=snapshot_readiness(snapshot_before),
            lora_snapshot_unavailable_before=snapshot_unavailable_reason(
                snapshot_before
            ),
            lora_snapshot_action_count_before=snapshot_action_count(snapshot_before),
            lora_snapshot_readiness_after=snapshot_readiness(snapshot_after),
            lora_snapshot_unavailable_after=snapshot_unavailable_reason(snapshot_after),
            lora_snapshot_action_count_after=snapshot_action_count(snapshot_after),
            cached_scheduled_lora_count_before=(
                None if cached_before is None else len(cached_before)
            ),
            cached_scheduled_lora_count_after=(
                None if cached_after is None else len(cached_after)
            ),
            event_dispatch_elapsed_ms=event_dispatch_elapsed_ms,
            menu_exec_elapsed_ms=menu_exec_elapsed_ms,
            menu_population_elapsed_ms=max(
                0.0,
                text_menu_exec_elapsed_ms - menu_exec_elapsed_ms,
            ),
            captured_menu_row_count=len(captured_menu_rows),
            captured_submenu_row_count=sum(
                len(rows) for _title, rows in captured_submenu_rows
            ),
            captured_action_count=len(captured_trigger_actions),
        )

    def probe_inline_lora_menu(
        self,
        field: PromptFieldHandle,
    ) -> PromptInlineLoraMenuProbe:
        """Present the first projected LoRA token through its production presenter."""

        from qfluentwidgets.components.widgets.menu import (
            RoundMenu,
        )

        editor = field.editor
        surface = getattr(editor, "_surface")
        projection_document = surface.projection_document()
        token = next(
            (
                candidate
                for candidate in projection_document.tokens
                if getattr(getattr(candidate, "kind", None), "value", None) == "lora"
            ),
            None,
        )
        if token is None:
            raise AssertionError("mounted prompt has no projected LoRA token")
        captured_rows: list[str] = []
        captured_trigger_actions: list[QAction] = []
        original_exec = RoundMenu.exec

        def capture_exec(menu: object, *_args: object, **_kwargs: object) -> None:
            """Capture the rendered inline menu without displaying a popup."""

            captured_rows.extend(round_menu_rows(menu))
            captured_trigger_actions.extend(round_menu_trigger_actions(menu))

        RoundMenu.exec = capture_exec
        try:
            presenter = getattr(editor, "_inline_lora_menu_presenter")
            presenter.show_lora_context_menu(
                token,
                editor.viewport().mapToGlobal(editor.viewport().rect().center()),
            )
            wait_for_queued_qt_turn()
        finally:
            RoundMenu.exec = original_exec
        return PromptInlineLoraMenuProbe(
            menu_rows=tuple(captured_rows),
            trigger_action_texts=tuple(
                action.text() for action in captured_trigger_actions
            ),
            trigger_action_full_labels=tuple(
                str(action.property("promptFullTriggerWordsLabel"))
                for action in captured_trigger_actions
            ),
        )


def source_position_for_text(editor: PromptEditor, text: str) -> int:
    """Return the first source position occupied by visible text."""

    return editor.toPlainText().index(text)


def viewport_position_for_source_text(editor: PromptEditor, text: str) -> QPoint:
    """Return a viewport-local point centered on one source text fragment."""

    source_start = source_position_for_text(editor, text)
    fragments = editor.source_range_fragments(
        start=source_start,
        end=source_start + len(text),
    )
    if not fragments:
        raise AssertionError(f"no visible source fragment for {text!r}")
    point = fragments[0].center().toPoint()
    return QPoint(int(point.x()), int(point.y()))


def prepared_lora_action_snapshot(editor: PromptEditor, prompt_text: str) -> object:
    """Return the current prepared LoRA action snapshot without deriving it."""

    controller = getattr(editor, "_lora_trigger_word_controller")
    return controller.snapshot_for_prompt(prompt_text=prompt_text)


def cached_scheduled_loras(
    editor: PromptEditor,
    prompt_text: str,
) -> tuple[object, ...] | None:
    """Return cached scheduled LoRAs exposed by the production editor."""

    controller = getattr(editor, "_lora_trigger_word_controller", None)
    cached_scheduled_loras = getattr(controller, "cached_scheduled_loras", None)
    if not callable(cached_scheduled_loras):
        return None
    return cast(tuple[object, ...] | None, cached_scheduled_loras(prompt_text))


def snapshot_readiness(snapshot: object) -> str:
    """Return a compact readiness label for a LoRA action snapshot."""

    status = getattr(snapshot, "status", None)
    readiness = getattr(status, "readiness", None)
    return str(getattr(readiness, "value", readiness))


def snapshot_unavailable_reason(snapshot: object) -> str | None:
    """Return the unavailable reason from a LoRA action snapshot."""

    status = getattr(snapshot, "status", None)
    reason = getattr(status, "unavailable_reason", None)
    return None if reason is None else str(reason)


def snapshot_action_count(snapshot: object) -> int:
    """Return the number of prepared LoRA trigger-word actions."""

    return len(getattr(snapshot, "trigger_word_actions", ()))


def round_menu_rows(menu: object) -> tuple[str, ...]:
    """Return top-level QFluent menu action labels from one opened menu."""

    actions = getattr(menu, "menuActions", None)
    if not callable(actions):
        return ()
    return tuple(action.text() for action in actions() if isinstance(action, QAction))


def round_menu_submenu_rows(menu: object) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return submenu titles and action labels for one opened QFluent menu."""

    submenus = getattr(menu, "_subMenus", ())
    rows: list[tuple[str, tuple[str, ...]]] = []
    for submenu in submenus:
        title = getattr(submenu, "title", lambda: "")()
        rows.append((str(title), round_menu_rows(submenu)))
    return tuple(rows)


def populate_lazy_round_menu_submenus(menu: object) -> None:
    """Populate renderer-owned lazy QFluent submenus for inspection."""

    submenus = getattr(menu, "_subMenus", ())
    for submenu in submenus:
        populate = getattr(submenu, "populate_if_needed", None)
        if callable(populate):
            populate()


def round_menu_trigger_actions(menu: object) -> tuple[QAction, ...]:
    """Return LoRA trigger-word actions from a menu and any captured submenus."""

    actions = list(round_menu_actions(menu))
    submenus = getattr(menu, "_subMenus", ())
    for submenu in submenus:
        actions.extend(round_menu_actions(submenu))
    return tuple(
        action
        for action in actions
        if action.text().startswith("Trigger words:")
        or action.property("promptFullTriggerWordsLabel") is not None
    )


def round_menu_actions(menu: object) -> tuple[QAction, ...]:
    """Return QAction objects directly owned by one QFluent menu."""

    actions = getattr(menu, "menuActions", None)
    if not callable(actions):
        return ()
    return tuple(action for action in actions() if isinstance(action, QAction))


def selected_trigger_action(
    actions: tuple[QAction, ...],
    *,
    trigger_first: bool,
    requested_label: str | None,
) -> QAction | None:
    """Return the trigger action selected by one context-menu probe."""

    if trigger_first:
        return actions[0] if actions else None
    if requested_label is None:
        return None
    for action in actions:
        full_label = action.property("promptFullTriggerWordsLabel")
        if action.text() == requested_label or full_label == requested_label:
            return action
    return None
