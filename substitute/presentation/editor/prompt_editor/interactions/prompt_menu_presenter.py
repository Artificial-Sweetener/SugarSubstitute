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

"""Adapt prepared prompt feature snapshots into shell context-menu requests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.save_preset_dialog import (
    SavePresetDialog,
    preset_dialog_result,
)

from ..commands import PromptCommandSourceIdentity
from ..features import (
    PromptContextMenuActionController,
    PromptContextMenuActionSnapshot,
    PromptSegmentPresetController,
    PromptSegmentPresetDialogResult,
    PromptSegmentPresetSaveDialogRequest,
    PromptSegmentSelectionSnapshot,
)
from ..shell import (
    PromptShellContextMenuOpening,
    PromptShellPromptMenuRequest,
    PromptShellSelectionSnapshot,
)
from .trigger_word_action_adapter import PromptTriggerWordActionAdapter


class PromptMenuEditorHost(Protocol):
    """Describe editor host reads and writes needed by prompt menu presenters."""

    def textCursor(self) -> QTextCursor:  # noqa: N802
        """Return the source-backed cursor wrapper."""

    def setTextCursor(self, cursor: object) -> None:  # noqa: N802
        """Apply one source-backed cursor selection."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current prompt source text."""

    def window(self) -> QWidget:
        """Return the top-level Qt window for this host."""

    def parentWidget(self) -> QWidget | None:  # noqa: N802
        """Return this host's direct Qt parent."""


class PromptSegmentPresetHostAdapter:
    """Expose prompt segment host behavior without making PromptEditor the owner."""

    def __init__(
        self,
        *,
        host: PromptMenuEditorHost,
        source_identity_provider: Callable[[], PromptCommandSourceIdentity | None],
    ) -> None:
        """Store editor accessors used by prompt segment presentation logic."""

        self._host = host
        self._source_identity_provider = source_identity_provider

    def textCursor(self) -> QTextCursor:  # noqa: N802
        """Return the source-backed prompt cursor."""

        return self._host.textCursor()

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current prompt source text."""

        return self._host.toPlainText()

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity when available."""

        return self._source_identity_provider()

    def prompt_segment_dialog_parent(self) -> object:
        """Return the editor-panel parent for save-segment dialogs."""

        editor_panel = self._ancestor_editor_panel()
        if editor_panel is not None:
            return editor_panel
        host_widget = cast(QWidget, self._host)
        window = self._host.window()
        if isinstance(window, QWidget) and window is not host_widget:
            return window
        parent = self._host.parentWidget()
        if parent is not None:
            return parent
        return host_widget

    def restore_prompt_segment_selection(self, *, start: int, end: int) -> None:
        """Restore a prompt segment selection through the host cursor."""

        cursor = self._host.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self._host.setTextCursor(cursor)

    def _ancestor_editor_panel(self) -> QWidget | None:
        """Return the owning editor panel widget when this editor is panel-hosted."""

        parent = self._host.parentWidget()
        while parent is not None:
            if parent.__class__.__name__ == "EditorPanel":
                return parent
            parent = parent.parentWidget()
        return None


class PromptContextMenuRequestPresenter:
    """Build shell prompt-menu requests from prepared feature snapshots."""

    def __init__(
        self,
        *,
        action_snapshot_provider: PromptContextMenuActionController,
        segment_presets: PromptSegmentPresetController,
        trigger_word_action_adapter: PromptTriggerWordActionAdapter,
        schedule_lora: Callable[[], None],
        open_danbooru_wiki_for_selection: Callable[[str], object],
        queue_scene: Callable[[str], None],
        is_read_only: Callable[[], bool],
        rich_prompt_rendering_enabled: Callable[[], bool],
        toggle_rich_prompt_rendering: Callable[[bool], None],
    ) -> None:
        """Store feature and shell callbacks for prompt-menu request building."""

        self._action_snapshot_provider = action_snapshot_provider
        self._segment_presets = segment_presets
        self._trigger_word_action_adapter = trigger_word_action_adapter
        self._schedule_lora = schedule_lora
        self._open_danbooru_wiki_for_selection = open_danbooru_wiki_for_selection
        self._queue_scene = queue_scene
        self._is_read_only = is_read_only
        self._rich_prompt_rendering_enabled = rich_prompt_rendering_enabled
        self._toggle_rich_prompt_rendering = toggle_rich_prompt_rendering

    def prepare_prompt_menu_selection(
        self,
        *,
        selected_text: str,
        selection_snapshot: PromptShellSelectionSnapshot | None,
        reason: str,
    ) -> None:
        """Prepare selected-text menu state before shell opens the menu."""

        selection_range = (
            None
            if selection_snapshot is None
            else (selection_snapshot[0], selection_snapshot[1])
        )
        read_only = self._is_read_only()
        self._action_snapshot_provider.prepare_menu_selection(
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            reason=reason,
        )

    def prepare_prompt_menu_opening(
        self,
        opening: PromptShellContextMenuOpening,
        *,
        reason: str,
    ) -> None:
        """Prepare source-position menu state before shell reads menu actions."""

        self._action_snapshot_provider.prepare_menu_opening(
            source_position=opening.source_position,
            reason=reason,
        )

    def selected_prompt_text(self) -> str:
        """Return the exact currently selected source text."""

        return self._segment_presets.selected_prompt_text()

    def selected_prompt_range_and_text(self) -> PromptShellSelectionSnapshot | None:
        """Return the exact current selected source range and text."""

        selection_snapshot = self._segment_presets.selected_prompt_range_and_text()
        if selection_snapshot is None:
            return None
        return selection_snapshot.as_tuple()

    def restore_prompt_selection_snapshot(
        self,
        selection_snapshot: PromptShellSelectionSnapshot,
    ) -> None:
        """Restore a source selection captured before a context-menu side effect."""

        start, end, selected_text = selection_snapshot
        self._segment_presets.restore_selection_snapshot(
            PromptSegmentSelectionSnapshot(
                start=start,
                end=end,
                text=selected_text,
            )
        )

    def prepared_prompt_menu_request(
        self,
        opening: PromptShellContextMenuOpening,
    ) -> PromptShellPromptMenuRequest:
        """Adapt one menu opening into shell presentation inputs."""

        action_snapshot = (
            self._action_snapshot_provider.prepared_action_snapshot_for_menu(
                source_position=opening.source_position,
                selected_text=opening.selected_text,
                selection_range=(
                    None
                    if opening.selection_snapshot is None
                    else (opening.selection_snapshot[0], opening.selection_snapshot[1])
                ),
                read_only=self._is_read_only(),
                rich_prompt_rendering_enabled=self._rich_prompt_rendering_enabled(),
            )
        )
        return self._request_for_snapshot(opening, action_snapshot)

    def _request_for_snapshot(
        self,
        opening: PromptShellContextMenuOpening,
        action_snapshot: PromptContextMenuActionSnapshot,
    ) -> PromptShellPromptMenuRequest:
        """Return a shell request for one prepared action snapshot."""

        return PromptShellPromptMenuRequest(
            schedule_lora=self._schedule_lora,
            schedule_lora_enabled=action_snapshot.lora_picker_ready,
            trigger_word_actions=(
                self._trigger_word_action_adapter.actions_for_trigger_words(
                    action_snapshot.lora_trigger_word_actions
                )
            ),
            prompt_segment_model=action_snapshot.segment_snapshot.menu_model,
            selected_prompt_text=opening.selected_text,
            save_prompt_segment=self._save_prompt_segment_callback(
                opening,
                save_ready=action_snapshot.segment_snapshot.save_state.ready,
            ),
            lookup_danbooru_wiki=self._danbooru_wiki_callback(
                opening,
                action_ready=(
                    action_snapshot.danbooru_snapshot.wiki_lookup_action is not None
                    and action_snapshot.danbooru_snapshot.wiki_lookup_action.ready
                ),
            ),
            danbooru_wiki_lookup_enabled=bool(
                action_snapshot.danbooru_snapshot.wiki_lookup_action is not None
                and action_snapshot.danbooru_snapshot.wiki_lookup_action.ready
            ),
            insert_prompt_segment=(
                self._insert_prompt_segment
                if action_snapshot.segment_snapshot.insert_ready
                else None
            ),
            queue_scene_key=action_snapshot.queue_scene_key,
            queue_scene=self._queue_scene,
            diagnostic_actions=action_snapshot.diagnostic_actions,
            rich_prompt_rendering_enabled=(
                action_snapshot.rich_prompt_rendering_enabled
            ),
            toggle_rich_prompt_rendering=self._toggle_rich_prompt_rendering,
        )

    def _save_prompt_segment_callback(
        self,
        opening: PromptShellContextMenuOpening,
        *,
        save_ready: bool,
    ) -> Callable[[], None] | None:
        """Return the callback that saves the captured menu selection."""

        if not save_ready:
            return None

        def save_selected_prompt_segment() -> None:
            """Save the source selection captured before menu side effects."""

            if opening.selection_snapshot is not None:
                self.restore_prompt_selection_snapshot(opening.selection_snapshot)
            self._segment_presets.save_selected_segment_as_preset(
                opening.selected_text,
                dialog_runner=self._run_prompt_segment_save_dialog,
            )

        return save_selected_prompt_segment

    def _insert_prompt_segment(self, insertion_text: str) -> None:
        """Insert a saved prompt segment through the segment controller."""

        self._segment_presets.insert_saved_prompt_segment(insertion_text)

    def _danbooru_wiki_callback(
        self,
        opening: PromptShellContextMenuOpening,
        *,
        action_ready: bool,
    ) -> Callable[[], None] | None:
        """Return the callback that opens Danbooru lookup for captured text."""

        if not action_ready:
            return None

        def lookup_selected_danbooru_wiki() -> None:
            """Open the selected prompt text in the Danbooru wiki dialog."""

            if opening.selection_snapshot is not None:
                self.restore_prompt_selection_snapshot(opening.selection_snapshot)
            self._open_danbooru_wiki_for_selection(opening.selected_text)

        return lookup_selected_danbooru_wiki

    def _run_prompt_segment_save_dialog(
        self,
        request: PromptSegmentPresetSaveDialogRequest,
    ) -> PromptSegmentPresetDialogResult:
        """Run the Qt save-segment dialog for a prepared segment request."""

        return preset_dialog_result(
            SavePresetDialog(
                parent=cast(QWidget, request.parent),
                title=request.title,
                scopes=request.scopes,
            )
        )


__all__ = [
    "PromptContextMenuRequestPresenter",
    "PromptMenuEditorHost",
    "PromptSegmentPresetHostAdapter",
]
