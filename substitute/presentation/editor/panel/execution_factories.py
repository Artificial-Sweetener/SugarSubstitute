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

"""Define lightweight editor-panel execution factory containers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from substitute.presentation.dialogs.danbooru_wiki_dialog import (
        QtDanbooruWikiLookupDispatcher,
    )
    from substitute.presentation.editor.prompt_editor.async_work import (
        PromptEditorTaskExecutor,
    )
    from substitute.presentation.widgets.model_picker import (
        ModelPickerThumbnailPreloadRoute,
    )

PromptEditorTaskExecutorFactory: TypeAlias = Callable[
    [object, str],
    "PromptEditorTaskExecutor",
]
DanbooruWikiLookupDispatcherFactory: TypeAlias = Callable[
    ["QWidget"],
    "QtDanbooruWikiLookupDispatcher",
]
ModelPickerThumbnailPreloadRouteFactory: TypeAlias = Callable[
    ["QWidget"],
    "ModelPickerThumbnailPreloadRoute",
]


@dataclass(frozen=True, slots=True)
class EditorPanelExecutionFactories:
    """Carry execution factories consumed by editor-panel construction."""

    prompt_task_executor_factory: PromptEditorTaskExecutorFactory
    danbooru_lookup_dispatcher_factory: DanbooruWikiLookupDispatcherFactory
    model_picker_thumbnail_preload_route_factory: (
        ModelPickerThumbnailPreloadRouteFactory
    )


__all__ = [
    "DanbooruWikiLookupDispatcherFactory",
    "EditorPanelExecutionFactories",
    "ModelPickerThumbnailPreloadRouteFactory",
    "PromptEditorTaskExecutorFactory",
]
