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

"""Own prompt-editor context-menu routing and presentation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QContextMenuEvent, QTextCursor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    MenuAnimationType,
    RoundMenu,
)

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataMenuItem,
    model_metadata_menu_entries,
)
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)
from ..features.diagnostic_menu_actions import PromptContextMenuAction
from ..features.prompt_segment_preset_models import PromptSegmentPresetMenuModel

from .context_menu_catalog import PromptSemanticMenuCatalog, menu_item_from_qaction
from .menu_presentation import present_prompt_menu

PromptShellSelectionSnapshot = tuple[int, int, str]


class PromptShellTextMenuParent(Protocol):
    """Describe the text-editor API consumed by shell menu rows."""

    def textCursor(self) -> QTextCursor:
        """Return the current prompt text cursor."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current prompt source text."""

    def undo(self) -> None:
        """Undo one prompt edit."""

    def redo(self) -> None:
        """Redo one prompt edit."""

    def canUndo(self) -> bool:  # noqa: N802
        """Return whether undo is available."""

    def canRedo(self) -> bool:  # noqa: N802
        """Return whether redo is available."""

    def isReadOnly(self) -> bool:  # noqa: N802
        """Return whether source edits are disabled."""


class PromptShellClipboardActions(Protocol):
    """Expose prompt clipboard actions used by shell text-menu rows."""

    def copy(self) -> None:
        """Copy the active prompt selection."""

    def cut(self) -> None:
        """Cut the active prompt selection."""

    def paste(self) -> None:
        """Paste into the active prompt selection."""

    def select_all(self) -> None:
        """Select the full prompt source."""


@dataclass(frozen=True, slots=True)
class PromptShellContextInsertState:
    """Carry the active context-menu insertion target."""

    insert_position: int | None
    should_replace_selection: bool | None


@dataclass(frozen=True, slots=True)
class PromptShellContextMenuOpening:
    """Describe cheap per-open context state for feature action adaptation."""

    source_position: int
    selected_text: str
    selection_snapshot: PromptShellSelectionSnapshot | None


@dataclass(frozen=True, slots=True)
class PromptShellPromptMenuRequest:
    """Carry prepared prompt menu actions into shell presentation."""

    schedule_lora: Callable[[], None]
    schedule_lora_enabled: bool
    trigger_word_actions: tuple[QAction, ...]
    prompt_segment_model: PromptSegmentPresetMenuModel | None
    selected_prompt_text: str | None
    save_prompt_segment: Callable[[], None] | None
    lookup_danbooru_wiki: Callable[[], None] | None
    danbooru_wiki_lookup_enabled: bool
    insert_prompt_segment: Callable[[str], None] | None
    queue_scene_key: str | None
    queue_scene: Callable[[str], None] | None
    diagnostic_actions: tuple[PromptContextMenuAction, ...]
    rich_prompt_rendering_enabled: bool
    toggle_rich_prompt_rendering: Callable[[bool], None] | None


class PromptShellPromptMenuRequestProvider(Protocol):
    """Provide prepared prompt-menu inputs to the passive shell controller."""

    def prepare_prompt_menu_selection(
        self,
        *,
        selected_text: str,
        selection_snapshot: PromptShellSelectionSnapshot | None,
        reason: str,
    ) -> None:
        """Prepare selection-dependent prompt-menu state before menu open."""

    def prepared_prompt_menu_request(
        self,
        opening: PromptShellContextMenuOpening,
    ) -> PromptShellPromptMenuRequest:
        """Return prepared prompt-menu inputs for one shell opening."""

    def prepare_prompt_menu_opening(
        self,
        opening: PromptShellContextMenuOpening,
        *,
        reason: str,
    ) -> None:
        """Prepare source-position menu state before menu inputs are read."""


class PromptShellContextMenuController:
    """Route context-menu events and present prepared prompt actions."""

    def __init__(
        self,
        *,
        host: QWidget,
        finish_pending_key_edit_block: Callable[[str], None],
        has_text_selection: Callable[[], bool],
        selected_prompt_range_and_text: Callable[
            [], PromptShellSelectionSnapshot | None
        ],
        selected_prompt_text: Callable[[], str],
        restore_prompt_selection_snapshot: Callable[
            [PromptShellSelectionSnapshot], None
        ],
        source_position_for_global_pos: Callable[[QPoint], int],
        current_source_position: Callable[[], int],
        prompt_menu_requires_custom_actions: Callable[[], bool],
        show_native_context_menu: Callable[[QContextMenuEvent], None],
        clipboard_actions: PromptShellClipboardActions,
        prompt_menu_requests: PromptShellPromptMenuRequestProvider,
    ) -> None:
        """Store collaborators for shell-only context-menu behavior."""

        self._host = host
        self._finish_pending_key_edit_block = finish_pending_key_edit_block
        self._has_text_selection = has_text_selection
        self._selected_prompt_range_and_text = selected_prompt_range_and_text
        self._selected_prompt_text = selected_prompt_text
        self._restore_prompt_selection_snapshot = restore_prompt_selection_snapshot
        self._source_position_for_global_pos = source_position_for_global_pos
        self._current_source_position = current_source_position
        self._prompt_menu_requires_custom_actions = prompt_menu_requires_custom_actions
        self._show_native_context_menu = show_native_context_menu
        self._clipboard_actions = clipboard_actions
        self._prompt_menu_request_provider = prompt_menu_requests
        self._last_context_menu_global_pos: QPoint | None = None
        self._last_context_menu_insert_position: int | None = None
        self._last_context_menu_press_had_selection: bool | None = None
        self._last_context_menu_selection_snapshot: (
            PromptShellSelectionSnapshot | None
        ) = None
        self._context_menu_should_replace_selection: bool | None = None
        self._inline_lora_context_menu_global_pos: QPoint | None = None

    def record_context_menu_press(self) -> None:
        """Capture selection state before Qt changes it for context-menu routing."""

        self._last_context_menu_press_had_selection = self._has_text_selection()
        self._last_context_menu_selection_snapshot = (
            self._selected_prompt_range_and_text()
        )
        selection_snapshot = (
            self._last_context_menu_selection_snapshot
            if self._last_context_menu_press_had_selection
            else None
        )
        selected_prompt_text = (
            selection_snapshot[2]
            if selection_snapshot is not None
            else self._selected_prompt_text()
        )
        self._prompt_menu_request_provider.prepare_prompt_menu_selection(
            selected_text=selected_prompt_text,
            selection_snapshot=selection_snapshot,
            reason="context_menu_press",
        )

    def forward_context_menu_event_to_host(self, event: QContextMenuEvent) -> bool:
        """Forward one viewport-originated context menu into the host path."""

        if self._consume_inline_lora_context_menu_event(event.globalPos()):
            event.accept()
            return True
        host_local_pos = self._host.mapFromGlobal(event.globalPos())
        forwarded_event = QContextMenuEvent(
            event.reason(),
            host_local_pos,
            event.globalPos(),
            event.modifiers(),
        )
        if not self._prompt_menu_requires_custom_actions():
            self._show_native_context_menu(forwarded_event)
        else:
            self.show_prompt_context_menu(forwarded_event)
        event.accept()
        return True

    @prompt_editor_work_event(PromptEditorWorkEvent.CONTEXT_MENU_OPEN)
    def show_prompt_context_menu(self, event: QContextMenuEvent) -> None:
        """Show the QFluent prompt menu from prepared feature action state."""

        self._finish_pending_key_edit_block("context_menu")
        self._last_context_menu_global_pos = QPoint(event.globalPos())
        had_selection_before_context_click = (
            self._last_context_menu_press_had_selection
            if self._last_context_menu_press_had_selection is not None
            else self._has_text_selection()
        )
        selection_snapshot = (
            self._last_context_menu_selection_snapshot
            if had_selection_before_context_click
            else None
        )
        selected_prompt_text = (
            selection_snapshot[2]
            if selection_snapshot is not None
            else self._selected_prompt_text()
        )
        self._last_context_menu_press_had_selection = None
        self._last_context_menu_selection_snapshot = None
        if selection_snapshot is not None:
            self._restore_prompt_selection_snapshot(selection_snapshot)
        self._context_menu_should_replace_selection = had_selection_before_context_click
        context_source_position = self._source_position_for_global_pos(
            event.globalPos()
        )
        if selection_snapshot is not None:
            self._restore_prompt_selection_snapshot(selection_snapshot)
        self._last_context_menu_insert_position = (
            None if had_selection_before_context_click else context_source_position
        )
        opening = PromptShellContextMenuOpening(
            source_position=context_source_position,
            selected_text=selected_prompt_text,
            selection_snapshot=selection_snapshot,
        )
        self._prompt_menu_request_provider.prepare_prompt_menu_opening(
            opening,
            reason="context_menu_open",
        )
        request = self._prompt_menu_request_provider.prepared_prompt_menu_request(
            opening
        )
        menu = _PromptEditorTextEditMenu(
            self._host,
            schedule_lora=request.schedule_lora,
            clipboard_actions=self._clipboard_actions,
            schedule_lora_enabled=request.schedule_lora_enabled,
            trigger_word_actions=request.trigger_word_actions,
            prompt_segment_model=request.prompt_segment_model,
            selected_prompt_text=request.selected_prompt_text,
            save_prompt_segment=request.save_prompt_segment,
            lookup_danbooru_wiki=request.lookup_danbooru_wiki,
            danbooru_wiki_lookup_enabled=request.danbooru_wiki_lookup_enabled,
            insert_prompt_segment=request.insert_prompt_segment,
            queue_scene_key=request.queue_scene_key,
            queue_scene=request.queue_scene,
            diagnostic_actions=request.diagnostic_actions,
            rich_prompt_rendering_enabled=request.rich_prompt_rendering_enabled,
            toggle_rich_prompt_rendering=request.toggle_rich_prompt_rendering,
        )
        menu.exec(event.globalPos(), ani=True)

    @prompt_editor_work_event(PromptEditorWorkEvent.CONTEXT_MENU_OPEN)
    def field_action_entries(
        self,
        context: FieldActionContext,
    ) -> tuple[MenuEntry, ...]:
        """Return prompt-domain actions targeting the live caret or selection."""

        self._finish_pending_key_edit_block("node_action_menu")
        self._last_context_menu_global_pos = QPoint(context.anchor_global_position)
        selection_snapshot = self._selected_prompt_range_and_text()
        had_selection = selection_snapshot is not None
        selected_prompt_text = (
            selection_snapshot[2]
            if selection_snapshot is not None
            else self._selected_prompt_text()
        )
        self._prompt_menu_request_provider.prepare_prompt_menu_selection(
            selected_text=selected_prompt_text,
            selection_snapshot=selection_snapshot,
            reason="node_action_menu",
        )
        source_position = self._current_source_position()
        self._context_menu_should_replace_selection = had_selection
        self._last_context_menu_insert_position = (
            None if had_selection else source_position
        )
        opening = PromptShellContextMenuOpening(
            source_position=source_position,
            selected_text=selected_prompt_text,
            selection_snapshot=selection_snapshot,
        )
        self._prompt_menu_request_provider.prepare_prompt_menu_opening(
            opening,
            reason="node_action_menu",
        )
        request = self._prompt_menu_request_provider.prepared_prompt_menu_request(
            opening
        )
        return self._semantic_catalog(request).field_entries()

    def _semantic_catalog(
        self,
        request: PromptShellPromptMenuRequest,
    ) -> PromptSemanticMenuCatalog:
        """Build the semantic prompt catalog from one prepared request."""

        return PromptSemanticMenuCatalog(
            cast(PromptShellTextMenuParent, self._host),
            schedule_lora=request.schedule_lora,
            schedule_lora_enabled=request.schedule_lora_enabled,
            trigger_word_actions=request.trigger_word_actions,
            prompt_segment_model=request.prompt_segment_model,
            selected_prompt_text=request.selected_prompt_text,
            save_prompt_segment=request.save_prompt_segment,
            lookup_danbooru_wiki=request.lookup_danbooru_wiki,
            danbooru_wiki_lookup_enabled=request.danbooru_wiki_lookup_enabled,
            insert_prompt_segment=request.insert_prompt_segment,
            queue_scene_key=request.queue_scene_key,
            queue_scene=request.queue_scene,
            diagnostic_actions=request.diagnostic_actions,
            rich_prompt_rendering_enabled=request.rich_prompt_rendering_enabled,
            toggle_rich_prompt_rendering=request.toggle_rich_prompt_rendering,
        )

    def show_inline_lora_context_menu(
        self,
        *,
        global_pos: QPoint,
        trigger_action: QAction | None,
        metadata_menu_items: tuple[ModelMetadataMenuItem, ...],
    ) -> None:
        """Show prepared inline LoRA token context actions."""

        if not metadata_menu_items and trigger_action is None:
            return
        self._inline_lora_context_menu_global_pos = QPoint(global_pos)
        entries: list[MenuEntry] = []
        if trigger_action is not None:
            entries.append(
                menu_item_from_qaction(
                    trigger_action,
                    action_id="prompt.inline_lora.trigger_words",
                )
            )
        if metadata_menu_items:
            if entries:
                entries.append(MenuSeparator())
            entries.extend(model_metadata_menu_entries(metadata_menu_items))
        menu = QFluentMenuRenderer(parent=self._host).render(
            MenuModel(entries=tuple(entries))
        )
        menu.exec(global_pos)

    def last_context_menu_global_pos(self) -> QPoint | None:
        """Return the last prompt-menu opening position for popup placement."""

        if self._last_context_menu_global_pos is None:
            return None
        return QPoint(self._last_context_menu_global_pos)

    def consume_context_insert_state(self) -> PromptShellContextInsertState:
        """Return and clear context-menu insert targeting state."""

        insert_state = PromptShellContextInsertState(
            insert_position=self._last_context_menu_insert_position,
            should_replace_selection=self._context_menu_should_replace_selection,
        )
        self._last_context_menu_insert_position = None
        self._context_menu_should_replace_selection = None
        return insert_state

    def set_context_insert_state(
        self,
        *,
        insert_position: int | None,
        should_replace_selection: bool | None = None,
    ) -> None:
        """Set context-menu insert state for tests and delegated commands."""

        self._last_context_menu_insert_position = insert_position
        self._context_menu_should_replace_selection = should_replace_selection

    def set_selection_press_state(
        self,
        *,
        had_selection: bool | None,
        selection_snapshot: PromptShellSelectionSnapshot | None,
    ) -> None:
        """Set captured context-menu selection state for tests."""

        self._last_context_menu_press_had_selection = had_selection
        self._last_context_menu_selection_snapshot = selection_snapshot

    def _consume_inline_lora_context_menu_event(self, global_pos: QPoint) -> bool:
        """Suppress the host text menu generated by an inline LoRA right-click."""

        inline_global_pos = self._inline_lora_context_menu_global_pos
        if inline_global_pos is None:
            return False
        self._inline_lora_context_menu_global_pos = None
        return inline_global_pos == global_pos


class _PromptEditorTextEditMenu(RoundMenu):  # type: ignore[misc]
    """Present prompt-editor actions with one shared clipboard command owner."""

    def __init__(
        self,
        parent: QWidget,
        *,
        schedule_lora: Callable[[], None],
        clipboard_actions: PromptShellClipboardActions | None = None,
        schedule_lora_enabled: bool = True,
        trigger_word_actions: tuple[QAction, ...] = (),
        prompt_segment_model: PromptSegmentPresetMenuModel | None = None,
        selected_prompt_text: str | None = None,
        save_prompt_segment: Callable[[], None] | None = None,
        lookup_danbooru_wiki: Callable[[], None] | None = None,
        danbooru_wiki_lookup_enabled: bool = False,
        insert_prompt_segment: Callable[[str], None] | None = None,
        queue_scene_key: str | None = None,
        queue_scene: Callable[[str], None] | None = None,
        diagnostic_actions: tuple[PromptContextMenuAction, ...] = (),
        rich_prompt_rendering_enabled: bool = True,
        toggle_rich_prompt_rendering: Callable[[bool], None] | None = None,
    ) -> None:
        """Create a QFluent text menu that can schedule LoRAs."""

        super().__init__("", parent)
        self._clipboard_actions = (
            clipboard_actions
            if clipboard_actions is not None
            else cast(Any, parent)._clipboard_history_controller
        )
        self._semantic_catalog = PromptSemanticMenuCatalog(
            cast(PromptShellTextMenuParent, parent),
            schedule_lora=schedule_lora,
            schedule_lora_enabled=schedule_lora_enabled,
            trigger_word_actions=trigger_word_actions,
            prompt_segment_model=prompt_segment_model,
            selected_prompt_text=selected_prompt_text,
            save_prompt_segment=save_prompt_segment,
            lookup_danbooru_wiki=lookup_danbooru_wiki,
            danbooru_wiki_lookup_enabled=danbooru_wiki_lookup_enabled,
            insert_prompt_segment=insert_prompt_segment,
            queue_scene_key=queue_scene_key,
            queue_scene=queue_scene,
            diagnostic_actions=diagnostic_actions,
            rich_prompt_rendering_enabled=rich_prompt_rendering_enabled,
            toggle_rich_prompt_rendering=toggle_rich_prompt_rendering,
        )

    def exec(
        self,
        pos: object,
        ani: bool = True,
        aniType: MenuAnimationType = MenuAnimationType.DROP_DOWN,
    ) -> object:
        """Show the prompt menu from a shared batched menu model."""

        self.clear()
        model = MenuModel(entries=self._menu_entries())
        QFluentMenuRenderer(parent=cast(QWidget, self.parent())).populate_menu(
            self,
            model.entries,
        )
        if self.view.count() == 0:
            return None
        return present_prompt_menu(self, pos, ani, aniType)

    def _menu_entries(self) -> tuple[MenuEntry, ...]:
        """Return the complete prompt context-menu model in display order."""

        entries: list[MenuEntry] = []
        entries.extend(self._semantic_catalog.diagnostic_entries())
        if entries:
            entries.append(MenuSeparator())
        text_entries = self._qfluent_text_entries()
        entries.extend(text_entries)
        if not cast(PromptShellTextMenuParent, self.parent()).isReadOnly():
            mutation_entries = self._semantic_catalog.mutation_entries()
            if mutation_entries and entries:
                entries.append(MenuSeparator())
            entries.extend(mutation_entries)
        if entries:
            entries.append(MenuSeparator())
        entries.extend(self._semantic_catalog.rendering_entries())
        return tuple(entries)

    def _qfluent_text_entries(self) -> tuple[MenuEntry, ...]:
        """Return undo/redo plus standard clipboard command rows."""

        parent = cast(PromptShellTextMenuParent, self.parent())
        entries: list[MenuEntry] = []
        if parent.canUndo():
            entries.append(
                MenuItem(
                    "prompt.undo",
                    render_application_text(app_text("Undo")),
                    callback=parent.undo,
                    shortcut="Ctrl+Z",
                    icon=FIF.RETURN.icon(),
                )
            )
        if parent.canRedo():
            entries.append(
                MenuItem(
                    "prompt.redo",
                    render_application_text(app_text("Redo")),
                    callback=parent.redo,
                    shortcut="Ctrl+Y",
                    icon=FIF.ROTATE.icon(),
                )
            )
        edit_entries = tuple(entries)
        clipboard_entries: tuple[MenuItem, ...] = (
            MenuItem(
                "prompt.cut",
                render_application_text(app_text("Cut")),
                callback=self._clipboard_actions.cut,
                shortcut="Ctrl+X",
                icon=FIF.CUT.icon(),
            ),
            MenuItem(
                "prompt.copy",
                render_application_text(app_text("Copy")),
                callback=self._clipboard_actions.copy,
                shortcut="Ctrl+C",
                icon=FIF.COPY.icon(),
            ),
            MenuItem(
                "prompt.paste",
                render_application_text(app_text("Paste")),
                callback=self._clipboard_actions.paste,
                shortcut="Ctrl+V",
                icon=FIF.PASTE.icon(),
            ),
            MenuItem(
                "prompt.select_all",
                render_application_text(app_text("Select all")),
                callback=self._clipboard_actions.select_all,
                shortcut="Ctrl+A",
            ),
        )
        if edit_entries:
            return edit_entries + (MenuSeparator(),) + clipboard_entries
        return clipboard_entries


__all__ = [
    "PromptShellContextInsertState",
    "PromptShellContextMenuController",
    "PromptShellContextMenuOpening",
    "PromptShellPromptMenuRequest",
    "PromptShellPromptMenuRequestProvider",
    "PromptShellSelectionSnapshot",
    "_PromptEditorTextEditMenu",
]
