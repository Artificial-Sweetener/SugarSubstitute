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

"""Build focused semantic refresh interaction scenarios."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptSemanticRefreshController,
    PromptStaleResultGuard,
)
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.debouncer import (
    FakeSemanticDebouncer,
)
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.host import (
    DeferredSemanticRefreshHost,
)
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.task_channel import (
    FakeSemanticRequestChannel,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    SyntaxRendererCoordinatorDouble,
    autocomplete_double,
    syntax_renderer_double,
    syntax_service,
)
from tests.presentation.editor.prompt_editor.interactions.support.controller import (
    prompt_interaction_controller,
)
from tests.presentation.editor.prompt_editor.interactions.support.editor import (
    ControllerEditorDouble,
    MenuCursorDouble,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile


def build_hosted_semantic_refresh_controller(
    *,
    controller_provider: Callable[[], Any],
    document_service: Any,
    syntax_profile: Any,
) -> PromptSemanticRefreshController:
    """Build a real semantic refresh controller for coordinator behavior tests."""

    return PromptSemanticRefreshController(
        host=cast(Any, DeferredSemanticRefreshHost(controller_provider)),
        document_service=cast(Any, document_service),
        syntax_service=cast(Any, syntax_service()),
        syntax_profile=cast(Any, syntax_profile),
        request_channel=FakeSemanticRequestChannel(),
        debouncer=FakeSemanticDebouncer(),
        stale_result_guard=PromptStaleResultGuard(),
    )


def build_semantic_refresh_controller(
    *,
    document_service: Any,
    syntax_service_: Any,
    syntax_profile: Any,
    request_channel: FakeSemanticRequestChannel | None = None,
    debouncer: FakeSemanticDebouncer | None = None,
) -> PromptSemanticRefreshController:
    """Build a semantic refresh controller with controllable async seams."""

    return PromptSemanticRefreshController(
        host=cast(Any, None),
        document_service=cast(Any, document_service),
        syntax_service=cast(Any, syntax_service_),
        syntax_profile=cast(Any, syntax_profile),
        request_channel=request_channel or FakeSemanticRequestChannel(),
        debouncer=debouncer or FakeSemanticDebouncer(),
        stale_result_guard=PromptStaleResultGuard(),
    )


def build_interaction_controller(
    editor: ControllerEditorDouble,
    *,
    semantic_refresh_controller: object,
    syntax_renderers: SyntaxRendererCoordinatorDouble | None = None,
    document_service: object | None = None,
    syntax_service_: object | None = None,
    syntax_profile: object | None = None,
) -> Any:
    """Build a prompt interaction controller for semantic-refresh tests."""

    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers or syntax_renderer_double(),
        document_service=cast(
            PromptDocumentService,
            document_service or PromptDocumentService(),
        ),
        mutation_service=PromptMutationService(),
        syntax_service_=cast(Any, syntax_service_ or syntax_service()),
        syntax_profile=cast(
            Any,
            syntax_profile or prompt_syntax_profile("emphasis", "wildcard"),
        ),
    )
    if hasattr(semantic_refresh_controller, "_host"):
        semantic_refresh_controller._host = controller._syntax_state
    return controller


def build_editor(text: str, *, position: int) -> ControllerEditorDouble:
    """Return an editor double with matching click and caret cursors."""

    return ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=position),
        current_cursor=MenuCursorDouble(text=text, position=position),
        text=text,
    )
