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

"""Compose prompt-editor execution routes from the application runtime."""

from __future__ import annotations

from itertools import count
from typing import Protocol, cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from substitute.application.execution import TaskSubmitter
from substitute.infrastructure.execution.thread_pool_lane import CompletionDispatcher
from substitute.presentation.editor.panel.execution_factories import (
    DanbooruWikiLookupDispatcherFactory,
    EditorPanelExecutionFactories,
    ModelPickerThumbnailPreloadRouteFactory,
    PromptEditorTaskExecutorFactory,
)
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher


class RuntimePromptEditorSubmitter(TaskSubmitter, Protocol):
    """Describe a runtime submitter with explicit dispatcher-route cleanup."""

    def close(self) -> None:
        """Release this runtime submitter route."""


class PromptEditorExecutionRuntime(Protocol):
    """Describe the runtime surface needed for editor execution routes."""

    def submitter(
        self,
        lane_name: str,
        *,
        owner_id: str,
        dispatcher: CompletionDispatcher,
    ) -> RuntimePromptEditorSubmitter:
        """Create one owner-scoped runtime submitter."""


def create_editor_panel_execution_factories(
    execution_runtime: PromptEditorExecutionRuntime,
) -> EditorPanelExecutionFactories:
    """Return editor-panel execution factories backed by the shared runtime."""

    danbooru_request_ids = count(1)

    def create_prompt_task_executor(
        owner: object,
        owner_id: str,
    ) -> object:
        """Create one prompt task executor for a Qt owner object."""

        from substitute.presentation.editor.prompt_editor.async_work import (
            build_prompt_editor_executor,
        )
        from substitute.presentation.editor.prompt_editor.async_work.main_thread_dispatcher import (
            QtPromptEditorMainThreadDispatcher,
        )
        from substitute.presentation.editor.prompt_editor.async_work.task_executor import (
            PromptEditorTaskExecutorRoute,
        )

        if not isinstance(owner, QObject):
            raise TypeError("prompt task execution owner must be a QObject.")
        submitter = execution_runtime.submitter(
            "prompt_editor",
            owner_id=owner_id,
            dispatcher=QtPromptEditorMainThreadDispatcher(owner),
        )
        return build_prompt_editor_executor(
            route=PromptEditorTaskExecutorRoute(
                submitter=submitter,
                close=submitter.close,
            )
        )

    def create_danbooru_lookup_dispatcher(
        parent: QWidget,
    ) -> object:
        """Create one runtime-backed Danbooru lookup dispatcher."""

        from substitute.presentation.dialogs.danbooru_wiki_dialog import (
            QtDanbooruWikiLookupDispatcher,
        )

        request_id = next(danbooru_request_ids)
        submitter = execution_runtime.submitter(
            "danbooru_refresh",
            owner_id=f"danbooru_wiki_dialog_{id(parent):x}_{request_id}",
            dispatcher=QtOwnerThreadDispatcher(parent),
        )
        return QtDanbooruWikiLookupDispatcher(
            parent,
            submitter=submitter,
            close_submitter=submitter.close,
        )

    def create_model_picker_thumbnail_route(
        receiver: QWidget,
    ) -> object:
        """Create one model-picker thumbnail preload route."""

        from substitute.presentation.widgets.model_picker import (
            ModelPickerThumbnailPreloadRoute,
        )

        submitter = execution_runtime.submitter(
            "thumbnail_decode",
            owner_id=f"model_picker_thumbnail_{id(receiver):x}",
            dispatcher=QtOwnerThreadDispatcher(receiver),
        )
        return ModelPickerThumbnailPreloadRoute(
            submitter=submitter,
            close=submitter.close,
        )

    return EditorPanelExecutionFactories(
        prompt_task_executor_factory=cast(
            PromptEditorTaskExecutorFactory,
            create_prompt_task_executor,
        ),
        danbooru_lookup_dispatcher_factory=cast(
            DanbooruWikiLookupDispatcherFactory,
            create_danbooru_lookup_dispatcher,
        ),
        model_picker_thumbnail_preload_route_factory=cast(
            ModelPickerThumbnailPreloadRouteFactory,
            create_model_picker_thumbnail_route,
        ),
    )


__all__ = [
    "EditorPanelExecutionFactories",
    "PromptEditorExecutionRuntime",
    "RuntimePromptEditorSubmitter",
    "create_editor_panel_execution_factories",
]
