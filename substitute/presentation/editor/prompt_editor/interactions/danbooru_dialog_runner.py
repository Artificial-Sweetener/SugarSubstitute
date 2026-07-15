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

"""Run prepared Danbooru wiki dialog requests outside the public editor widget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtWidgets import QWidget

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruWikiContentService,
)
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    DanbooruWikiDialog,
    DanbooruWikiLookupDispatcher,
)

from ..features import (
    PromptDanbooruActionController,
    PromptDanbooruActionHost,
    PromptDanbooruWikiDialogRequest,
)
from .external_url_action_runner import (
    PromptExternalUrlActionRunner,
    PromptExternalUrlOpener,
)


class PromptDanbooruDialogFactory(Protocol):
    """Create one native Danbooru wiki dialog for a prepared action request."""

    def __call__(
        self,
        *,
        wiki_service: DanbooruWikiContentService,
        image_preview_service: DanbooruImagePreviewService | None,
        recent_posts_service: DanbooruRecentPostsService | None,
        selection_text: str,
        open_url: PromptExternalUrlOpener,
        lookup_dispatcher: DanbooruWikiLookupDispatcher | None,
        parent: QWidget,
    ) -> object:
        """Return a dialog object exposing the Qt modal execution API."""


class PromptDanbooruExecutableDialog(Protocol):
    """Expose the modal execution method used by the runner."""

    def exec(self) -> int:
        """Execute the dialog modally and return the Qt result code."""


class PromptDanbooruDialogHostAdapter(PromptDanbooruActionHost):
    """Adapt editor composition callbacks to Danbooru action-controller host needs."""

    def __init__(
        self,
        *,
        source_identity_provider: Callable[[], object | None],
        dialog_parent_provider: Callable[[], QWidget],
        external_url_actions: PromptExternalUrlActionRunner,
    ) -> None:
        """Store host collaborators without depending on the concrete editor widget."""

        self._source_identity_provider = source_identity_provider
        self._dialog_parent_provider = dialog_parent_provider
        self._external_url_actions = external_url_actions

    def prompt_command_source_identity(self) -> object | None:
        """Return the current prompt command source identity when available."""

        return self._source_identity_provider()

    def danbooru_wiki_dialog_parent(self) -> object:
        """Return the parent object for native Danbooru wiki dialogs."""

        return self._dialog_parent_provider()

    def external_url_opener(self) -> PromptExternalUrlOpener:
        """Return the URL opener used by Danbooru wiki dialogs."""

        return self._external_url_actions.open_danbooru_external_url


class PromptDanbooruDialogRunner:
    """Execute prepared native Danbooru wiki dialog requests."""

    def __init__(
        self,
        *,
        action_controller: PromptDanbooruActionController,
        dialog_factory: PromptDanbooruDialogFactory | None = None,
        lookup_dispatcher_factory: Callable[[QWidget], DanbooruWikiLookupDispatcher]
        | None = None,
    ) -> None:
        """Store the feature owner and dialog factory used for execution."""

        self._action_controller = action_controller
        self._dialog_factory = dialog_factory or DanbooruWikiDialog
        self._lookup_dispatcher_factory = lookup_dispatcher_factory

    def open_wiki_for_selection(self, selection_text: str) -> bool:
        """Open a prepared wiki dialog for the exact selected prompt text."""

        return self._action_controller.open_wiki_for_selection(
            selection_text,
            dialog_runner=self.run_wiki_dialog,
        )

    def run_wiki_dialog(self, request: PromptDanbooruWikiDialogRequest) -> None:
        """Construct and execute the native Danbooru wiki dialog."""

        dialog = cast(
            PromptDanbooruExecutableDialog,
            self._dialog_factory(
                wiki_service=request.wiki_service,
                image_preview_service=request.image_preview_service,
                recent_posts_service=request.recent_posts_service,
                selection_text=request.selection_text,
                open_url=request.open_url,
                lookup_dispatcher=self._lookup_dispatcher(request.parent),
                parent=cast(QWidget, request.parent),
            ),
        )
        dialog.exec()

    def _lookup_dispatcher(
        self,
        parent: object,
    ) -> DanbooruWikiLookupDispatcher | None:
        """Return a dispatcher for one dialog parent when a factory is configured."""

        if self._lookup_dispatcher_factory is None:
            return None
        return self._lookup_dispatcher_factory(cast(QWidget, parent))
