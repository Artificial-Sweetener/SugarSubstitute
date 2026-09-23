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

"""Own native Danbooru dialog and host-adapter composition."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
)

from ..features import PromptDanbooruActionController
from ..interactions import (
    PromptDanbooruDialogHostAdapter,
    PromptDanbooruDialogRunner,
    PromptExternalUrlActionRunner,
)
from .context import PromptEditorCompositionContext


def _dialog_parent(editor: QWidget) -> QWidget:
    """Return the top-level parent used for large browsing dialogs."""
    window = editor.window()
    if isinstance(window, QWidget) and window is not editor:
        return window
    parent = editor.parentWidget()
    if parent is not None:
        return parent
    return editor


class PromptEditorDanbooruFactory:
    """Build Danbooru action hosts and their native dialog runner."""

    def __init__(self, context: PromptEditorCompositionContext) -> None:
        """Retain the shell context that owns dialog parenting."""
        self._context = context

    def build_host_adapter(
        self,
        *,
        source_identity_provider: Callable[[], object | None],
        external_url_actions: PromptExternalUrlActionRunner,
    ) -> PromptDanbooruDialogHostAdapter:
        """Build the Danbooru action host without depending on PromptEditor."""
        return PromptDanbooruDialogHostAdapter(
            source_identity_provider=source_identity_provider,
            dialog_parent_provider=lambda: _dialog_parent(self._context.editor),
            external_url_actions=external_url_actions,
        )

    def build_dialog_runner(
        self,
        *,
        action_controller: PromptDanbooruActionController,
        lookup_dispatcher_factory: Callable[[QWidget], QtDanbooruWikiLookupDispatcher]
        | None,
    ) -> PromptDanbooruDialogRunner:
        """Build the native Danbooru wiki dialog execution boundary."""
        if lookup_dispatcher_factory is None:
            return PromptDanbooruDialogRunner(action_controller=action_controller)
        return PromptDanbooruDialogRunner(
            action_controller=action_controller,
            lookup_dispatcher_factory=lookup_dispatcher_factory,
        )
