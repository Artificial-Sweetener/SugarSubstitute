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

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QFontMetrics,
    QTextCursor,
)
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    MenuAnimationType,
    RoundMenu,
)

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataMenuItem,
    model_metadata_menu_entries,
)
from substitute.presentation.widgets.menu_icons import transparent_menu_icon
from substitute.presentation.widgets.menu_model import (
    LazyMenuSubmenu,
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

PromptShellSelectionSnapshot = tuple[int, int, str]

_TRIGGER_MENU_TEXT_WIDTH = 190
_PROMPT_SEGMENT_MENU_TEXT_WIDTH = 220


class PromptShellTextMenuParent(Protocol):
    """Describe the QFluent host operations needed by the text menu."""

    def textCursor(self) -> QTextCursor:
        """Return the current host text cursor."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current host source text."""

    def undo(self) -> None:
        """Undo one prompt edit."""

    def redo(self) -> None:
        """Redo one prompt edit."""

    def canUndo(self) -> bool:  # noqa: N802
        """Return whether undo is currently available."""

    def canRedo(self) -> bool:  # noqa: N802
        """Return whether redo is currently available."""

    def isReadOnly(self) -> bool:  # noqa: N802
        """Return whether the host is read-only."""


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


class PromptShellDiagnosticAction(Protocol):
    """Describe one prepared diagnostic menu action."""

    @property
    def label(self) -> str:
        """Return the menu label."""

    @property
    def enabled(self) -> bool:
        """Return whether the action is enabled."""

    @property
    def callback(self) -> Callable[[], None] | None:
        """Return the prepared action callback."""


class PromptShellSegmentPresetItem(Protocol):
    """Describe one prepared saved-segment insert action."""

    @property
    def label(self) -> str:
        """Return the menu label."""

    @property
    def text(self) -> str:
        """Return the insertion text."""

    @property
    def tooltip(self) -> str:
        """Return the action tooltip."""


class PromptShellSegmentPresetSection(Protocol):
    """Describe one prepared saved-segment menu section."""

    @property
    def title(self) -> str:
        """Return the section title."""

    @property
    def presets(self) -> tuple[PromptShellSegmentPresetItem, ...]:
        """Return prepared preset actions in this section."""


class PromptShellSegmentPresetMenuModel(Protocol):
    """Describe the prepared saved-segment menu model."""

    @property
    def sections(self) -> tuple[PromptShellSegmentPresetSection, ...]:
        """Return prepared menu sections."""


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
    prompt_segment_model: PromptShellSegmentPresetMenuModel | None
    selected_prompt_text: str | None
    save_prompt_segment: Callable[[], None] | None
    lookup_danbooru_wiki: Callable[[], None] | None
    danbooru_wiki_lookup_enabled: bool
    insert_prompt_segment: Callable[[str], None] | None
    queue_scene_key: str | None
    queue_scene: Callable[[str], None] | None
    diagnostic_actions: tuple[PromptShellDiagnosticAction, ...]
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
                _menu_item_from_qaction(
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
        prompt_segment_model: PromptShellSegmentPresetMenuModel | None = None,
        selected_prompt_text: str | None = None,
        save_prompt_segment: Callable[[], None] | None = None,
        lookup_danbooru_wiki: Callable[[], None] | None = None,
        danbooru_wiki_lookup_enabled: bool = False,
        insert_prompt_segment: Callable[[str], None] | None = None,
        queue_scene_key: str | None = None,
        queue_scene: Callable[[str], None] | None = None,
        diagnostic_actions: tuple[PromptShellDiagnosticAction, ...] = (),
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
        self._schedule_lora_callback = schedule_lora
        self._schedule_lora_enabled = schedule_lora_enabled
        self._trigger_word_actions = trigger_word_actions
        self._prompt_segment_model = prompt_segment_model
        self._selected_prompt_text = selected_prompt_text
        self._save_prompt_segment = save_prompt_segment
        self._lookup_danbooru_wiki = lookup_danbooru_wiki
        self._danbooru_wiki_lookup_enabled = danbooru_wiki_lookup_enabled
        self._insert_prompt_segment = insert_prompt_segment
        self._queue_scene_key = queue_scene_key
        self._queue_scene = queue_scene
        self._diagnostic_actions = diagnostic_actions
        self._rich_prompt_rendering_enabled = rich_prompt_rendering_enabled
        self._toggle_rich_prompt_rendering = toggle_rich_prompt_rendering

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
        return RoundMenu.exec(self, pos, ani, aniType)

    def _menu_entries(self) -> tuple[MenuEntry, ...]:
        """Return the complete prompt context-menu model in display order."""

        entries: list[MenuEntry] = []
        entries.extend(self._diagnostic_entries())
        if entries:
            entries.append(MenuSeparator())
        text_entries = self._qfluent_text_entries()
        entries.extend(text_entries)
        if not cast(PromptShellTextMenuParent, self.parent()).isReadOnly():
            mutation_entries = self._prompt_mutation_entries()
            if mutation_entries and entries:
                entries.append(MenuSeparator())
            entries.extend(mutation_entries)
        if entries:
            entries.append(MenuSeparator())
        entries.append(self._rich_prompt_rendering_entry())
        return tuple(entries)

    def _diagnostic_entries(self) -> tuple[MenuItem, ...]:
        """Return prompt diagnostic action rows for the shared renderer."""

        if cast(PromptShellTextMenuParent, self.parent()).isReadOnly():
            return ()
        return tuple(
            MenuItem(
                action_id=f"prompt.diagnostic.{index}",
                label=render_application_text(diagnostic_action.label),
                callback=diagnostic_action.callback,
                enabled=(
                    diagnostic_action.enabled and diagnostic_action.callback is not None
                ),
                icon=transparent_menu_icon(),
            )
            for index, diagnostic_action in enumerate(self._diagnostic_actions)
        )

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

    def _prompt_mutation_entries(self) -> tuple[MenuEntry, ...]:
        """Return scene, preset, trigger-word, and utility prompt rows."""

        entries: list[MenuEntry] = []
        queue_scene = self._queue_scene_entry()
        if queue_scene is not None:
            entries.append(queue_scene)
        segment_entry = self._prompt_segment_submenu_entry()
        if segment_entry is not None:
            entries.append(segment_entry)
        trigger_entry = self._trigger_word_menu_entry()
        if trigger_entry is not None:
            entries.append(trigger_entry)
        utility_entries = self._prompt_utility_entries()
        if utility_entries:
            if entries:
                entries.append(MenuSeparator())
            entries.extend(utility_entries)
        return tuple(entries)

    def _queue_scene_entry(self) -> MenuItem | None:
        """Return the scene queue row when the menu target is runnable."""

        if self._queue_scene is None or self._queue_scene_key is None:
            return None
        return MenuItem(
            "prompt.queue_scene",
            render_application_text(app_text("Queue this scene")),
            callback=self._queue_scene_for_key,
        )

    def _prompt_segment_submenu_entry(self) -> LazyMenuSubmenu | None:
        """Return a lazily populated saved segment submenu entry."""

        if self._insert_prompt_segment is None or self._prompt_segment_model is None:
            return None
        if not self._prompt_segment_model.sections:
            return None
        return LazyMenuSubmenu(
            render_application_text(app_text("Insert saved segment")),
            entries_factory=self._prompt_segment_entries,
        )

    def _prompt_segment_entries(self) -> tuple[MenuEntry, ...]:
        """Return saved prompt segment rows when the submenu opens."""

        assert self._prompt_segment_model is not None
        assert self._insert_prompt_segment is not None
        entries: list[MenuEntry] = []
        show_headers = len(self._prompt_segment_model.sections) > 1
        for section_index, section in enumerate(self._prompt_segment_model.sections):
            if section_index > 0:
                entries.append(MenuSeparator())
            section_entries = tuple(
                MenuItem(
                    action_id=f"prompt.segment.insert.{section_index}.{preset_index}",
                    label=self._prompt_segment_action_label(preset.label),
                    callback=self._insert_prompt_segment_callback(preset.text),
                    tooltip=preset.tooltip,
                )
                for preset_index, preset in enumerate(section.presets)
            )
            if show_headers:
                entries.append(
                    MenuSection(title=section.title, entries=section_entries)
                )
            else:
                entries.extend(section_entries)
        return tuple(entries)

    def _insert_prompt_segment_callback(self, text: str) -> Callable[[], None]:
        """Return a callback that inserts one saved prompt segment."""

        assert self._insert_prompt_segment is not None
        insert_prompt_segment = self._insert_prompt_segment
        return lambda: insert_prompt_segment(text)

    def _trigger_word_menu_entry(self) -> MenuEntry | None:
        """Return trigger-word insertion row or lazy submenu."""

        if not self._trigger_word_actions:
            return None
        return LazyMenuSubmenu(
            render_application_text(app_text("Insert trigger words")),
            entries_factory=self._trigger_word_entries,
        )

    def _trigger_word_entries(self) -> tuple[MenuItem, ...]:
        """Return trigger-word rows when the trigger submenu opens."""

        return tuple(
            self._menu_item_from_qaction(
                action,
                action_id=f"prompt.lora.trigger_words.{index}",
            )
            for index, action in enumerate(self._trigger_word_actions)
        )

    def _prompt_utility_entries(self) -> tuple[MenuItem, ...]:
        """Return prompt-specific utility actions in display order."""

        entries: list[MenuItem] = []
        if self._can_save_prompt_segment():
            entries.append(
                MenuItem(
                    "prompt.segment.save",
                    render_application_text(app_text("Save segment as...")),
                    callback=self._save_prompt_segment,
                    icon=FIF.SAVE.icon(),
                )
            )
        if self._can_lookup_danbooru_wiki():
            entries.append(
                MenuItem(
                    "prompt.danbooru.lookup",
                    render_application_text(app_text("Danbooru wiki lookup")),
                    callback=self._lookup_danbooru_wiki,
                    icon=FIF.DICTIONARY.icon(),
                )
            )
        if self._schedule_lora_enabled:
            entries.append(
                MenuItem(
                    "prompt.lora.schedule",
                    render_application_text(app_text("Schedule LoRA")),
                    callback=self._schedule_lora_callback,
                    icon=FIF.EDIT.icon(),
                )
            )
        return tuple(entries)

    def _rich_prompt_rendering_entry(self) -> MenuItem:
        """Return the rich prompt rendering check row."""

        return MenuItem(
            "prompt.rich_rendering.toggle",
            render_application_text(app_text("Rich prompt rendering")),
            checkable=True,
            checked=self._rich_prompt_rendering_enabled,
            checked_callback=self._toggle_rich_prompt_rendering,
            icon=(
                FIF.ACCEPT.icon()
                if self._rich_prompt_rendering_enabled
                else transparent_menu_icon()
            ),
        )

    def _menu_item_from_qaction(self, action: QAction, *, action_id: str) -> MenuItem:
        """Translate a prepared QAction into a shared menu item."""

        return _menu_item_from_qaction(action, action_id=action_id)

    def _can_lookup_danbooru_wiki(self) -> bool:
        """Return whether the menu can expose the Danbooru wiki lookup action."""

        return (
            self._danbooru_wiki_lookup_enabled
            and self._lookup_danbooru_wiki is not None
            and bool((self._selected_prompt_text or "").strip())
        )

    def _can_save_prompt_segment(self) -> bool:
        """Return whether the menu can expose the save-segment action."""

        if (
            self._save_prompt_segment is None
            or cast(PromptShellTextMenuParent, self.parent()).isReadOnly()
        ):
            return False
        selected_text = (
            self._selected_prompt_text
            if self._selected_prompt_text is not None
            else self._selected_text_from_parent_cursor()
        )
        return bool(selected_text.strip())

    def _selected_text_from_parent_cursor(self) -> str:
        """Return selected text from the host cursor for direct menu tests."""

        cursor = cast(PromptShellTextMenuParent, self.parent()).textCursor()
        return cursor.selectedText().replace("\u2029", "\n")

    def _queue_scene_for_key(self) -> None:
        """Emit the stored scene queue request."""

        if self._queue_scene is None or self._queue_scene_key is None:
            return
        self._queue_scene(self._queue_scene_key)

    def _prompt_segment_action_label(self, label: str) -> str:
        """Return a width-bounded label for saved prompt segment actions."""

        metrics = QFontMetrics(QApplication.font())
        return metrics.elidedText(
            label,
            Qt.TextElideMode.ElideRight,
            _PROMPT_SEGMENT_MENU_TEXT_WIDTH,
        )


def _menu_item_from_qaction(action: QAction, *, action_id: str) -> MenuItem:
    """Translate a prepared QAction into a shared menu item."""

    return MenuItem(
        action_id,
        action.text(),
        callback=action.trigger,
        enabled=action.isEnabled(),
        tooltip=action.toolTip() or None,
        icon=None if action.icon().isNull() else action.icon(),
        properties={
            name: value
            for name in ("promptFullTriggerWordsLabel",)
            if (value := action.property(name)) is not None
        },
        data=action.data(),
    )


__all__ = [
    "PromptShellContextInsertState",
    "PromptShellContextMenuController",
    "PromptShellContextMenuOpening",
    "PromptShellDiagnosticAction",
    "PromptShellPromptMenuRequest",
    "PromptShellPromptMenuRequestProvider",
    "PromptShellSelectionSnapshot",
    "PromptShellSegmentPresetMenuModel",
    "_PromptEditorTextEditMenu",
]
