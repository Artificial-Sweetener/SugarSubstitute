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

"""Build prompt-specific semantic menu entries independently of menu chrome."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFontMetrics, QTextCursor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.presentation.widgets.menu_icons import transparent_menu_icon
from substitute.presentation.widgets.menu_model import (
    LazyMenuSubmenu,
    MenuEntry,
    MenuItem,
    MenuSection,
    MenuSeparator,
)

from ..features.diagnostic_menu_actions import PromptContextMenuAction
from ..features.prompt_segment_preset_models import PromptSegmentPresetMenuModel

_PROMPT_SEGMENT_MENU_TEXT_WIDTH = 220


class PromptSemanticMenuHost(Protocol):
    """Describe prompt state needed to derive semantic action availability."""

    def textCursor(self) -> QTextCursor:  # noqa: N802
        """Return the current prompt text cursor."""

    def isReadOnly(self) -> bool:  # noqa: N802
        """Return whether source edits are disabled."""


class PromptSemanticMenuCatalog:
    """Own the reusable prompt-domain action catalog for all menu surfaces."""

    def __init__(
        self,
        host: PromptSemanticMenuHost,
        *,
        schedule_lora: Callable[[], None],
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
        """Store prepared prompt actions and the live editor state they require."""

        self._host = host
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

    def field_entries(self) -> tuple[MenuEntry, ...]:
        """Return prompt-domain entries suitable for an aggregate node menu."""

        groups = (
            self.diagnostic_entries(),
            self.mutation_entries(),
            self.rendering_entries(),
        )
        entries: list[MenuEntry] = []
        for group in groups:
            if not group:
                continue
            if entries:
                entries.append(MenuSeparator())
            entries.extend(group)
        return tuple(entries)

    def diagnostic_entries(self) -> tuple[MenuItem, ...]:
        """Return prompt diagnostic actions for the current source position."""

        if self._host.isReadOnly():
            return ()
        return tuple(
            MenuItem(
                action_id=f"prompt.diagnostic.{index}",
                label=render_application_text(action.label),
                callback=action.callback,
                enabled=action.enabled and action.callback is not None,
                icon=transparent_menu_icon(),
            )
            for index, action in enumerate(self._diagnostic_actions)
        )

    def mutation_entries(self) -> tuple[MenuEntry, ...]:
        """Return scene, preset, trigger-word, and utility prompt actions."""

        if self._host.isReadOnly():
            return ()
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

    def rendering_entries(self) -> tuple[MenuItem, ...]:
        """Return prompt presentation controls available on every menu surface."""

        return (
            MenuItem(
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
            ),
        )

    def _queue_scene_entry(self) -> MenuItem | None:
        """Return the scene queue action when the target is runnable."""

        if self._queue_scene is None or self._queue_scene_key is None:
            return None
        return MenuItem(
            "prompt.queue_scene",
            render_application_text(app_text("Queue this scene")),
            callback=self._queue_scene_for_key,
        )

    def _prompt_segment_submenu_entry(self) -> LazyMenuSubmenu | None:
        """Return the lazily populated saved-segment submenu."""

        if self._insert_prompt_segment is None or self._prompt_segment_model is None:
            return None
        if not self._prompt_segment_model.sections:
            return None
        return LazyMenuSubmenu(
            render_application_text(app_text("Insert saved segment")),
            entries_factory=self._prompt_segment_entries,
        )

    def _prompt_segment_entries(self) -> tuple[MenuEntry, ...]:
        """Return saved prompt segments grouped by their stored scope."""

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

    def _trigger_word_menu_entry(self) -> LazyMenuSubmenu | None:
        """Return the lazily populated trigger-word submenu when available."""

        if not self._trigger_word_actions:
            return None
        return LazyMenuSubmenu(
            render_application_text(app_text("Insert trigger words")),
            entries_factory=self._trigger_word_entries,
        )

    def _trigger_word_entries(self) -> tuple[MenuItem, ...]:
        """Return actions that insert prepared LoRA trigger words."""

        return tuple(
            menu_item_from_qaction(
                action,
                action_id=f"prompt.lora.trigger_words.{index}",
            )
            for index, action in enumerate(self._trigger_word_actions)
        )

    def _prompt_utility_entries(self) -> tuple[MenuItem, ...]:
        """Return selection and LoRA utilities in display order."""

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

    def _can_lookup_danbooru_wiki(self) -> bool:
        """Return whether the selected prompt text supports a wiki lookup."""

        return (
            self._danbooru_wiki_lookup_enabled
            and self._lookup_danbooru_wiki is not None
            and bool((self._selected_prompt_text or "").strip())
        )

    def _can_save_prompt_segment(self) -> bool:
        """Return whether selected text may be persisted as a segment."""

        if self._save_prompt_segment is None or self._host.isReadOnly():
            return False
        selected_text = (
            self._selected_prompt_text
            if self._selected_prompt_text is not None
            else self._selected_text_from_host_cursor()
        )
        return bool(selected_text.strip())

    def _selected_text_from_host_cursor(self) -> str:
        """Return selected text directly from the live host cursor."""

        return self._host.textCursor().selectedText().replace("\u2029", "\n")

    def _queue_scene_for_key(self) -> None:
        """Emit the stored scene queue request."""

        if self._queue_scene is None or self._queue_scene_key is None:
            return
        self._queue_scene(self._queue_scene_key)

    def _prompt_segment_action_label(self, label: str) -> str:
        """Return a width-bounded label for saved prompt segments."""

        return QFontMetrics(QApplication.font()).elidedText(
            label,
            Qt.TextElideMode.ElideRight,
            _PROMPT_SEGMENT_MENU_TEXT_WIDTH,
        )


def menu_item_from_qaction(action: QAction, *, action_id: str) -> MenuItem:
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
    "PromptSemanticMenuCatalog",
    "PromptSemanticMenuHost",
    "menu_item_from_qaction",
]
