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

"""Compose the prompt editor's native editing and semantic menu rows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import MenuAnimationType  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.presentation.widgets.action_menu import ActionMenu
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

from ..features.diagnostic_menu_actions import PromptContextMenuAction
from ..features.prompt_segment_preset_models import PromptSegmentPresetMenuModel
from .context_menu_catalog import PromptSemanticMenuCatalog
from .menu_presentation import present_prompt_menu


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


class PromptTextMenu(ActionMenu):
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


__all__ = ["PromptTextMenu", "PromptShellTextMenuParent", "PromptShellClipboardActions"]
