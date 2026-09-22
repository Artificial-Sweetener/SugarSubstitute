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

"""Expose prompt-editor composition construction data types."""

from __future__ import annotations

from .collaborator_bundle import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorCollaborators,
    PromptEditorConstructionInputs,
    PromptEditorTaskExecutorFactory,
)
from .autocomplete_factory import PromptEditorAutocompleteFactory
from .bundle_factory import build_resize_handle, bundle_collaborators
from .context import PromptEditorCompositionContext
from .execution_factory import PromptEditorExecutionFactory
from .foundations import (
    build_external_url_action_runner,
    build_prompt_document_service,
)
from .context_insertion_factory import build_context_insertion_service
from .danbooru_factory import PromptEditorDanbooruFactory
from .projection_factory import PromptEditorProjectionFactory
from .syntax_factory import PromptEditorSyntaxFactory
from .menu_factory import PromptEditorMenuFactory
from .menu_runtime import (
    PromptEditorMenuActionBindings,
    PromptEditorMenuFeatureOwners,
    PromptEditorMenuHostBindings,
    PromptEditorMenuRuntime,
    build_prompt_editor_menu_runtime,
)
from .service_factory import PromptEditorServiceFactory
from .signal_bindings import (
    PromptEditorDiagnosticsControllerBinding,
    PromptEditorSignalHost,
    bind_prompt_editor_diagnostics_signals,
    bind_prompt_editor_signals,
)
from .wiring import (
    PromptEditorConstructionLifecycleHost,
    PromptEditorConstructionObserver,
    PromptEditorInitialLayoutHost,
    PromptEditorLifecycleWiringResult,
    apply_prompt_editor_initial_layout,
    is_deleted_qt_object_error,
    qt_object_is_alive,
    wire_prompt_editor_construction_lifecycle,
)

__all__ = [
    "DanbooruWikiLookupDispatcherFactory",
    "PromptEditorCollaborators",
    "PromptEditorAutocompleteFactory",
    "PromptEditorCompositionContext",
    "PromptEditorDanbooruFactory",
    "PromptEditorExecutionFactory",
    "PromptEditorMenuFactory",
    "PromptEditorMenuActionBindings",
    "PromptEditorMenuFeatureOwners",
    "PromptEditorMenuHostBindings",
    "PromptEditorMenuRuntime",
    "PromptEditorProjectionFactory",
    "PromptEditorServiceFactory",
    "PromptEditorSyntaxFactory",
    "PromptEditorConstructionInputs",
    "PromptEditorConstructionLifecycleHost",
    "PromptEditorConstructionObserver",
    "PromptEditorTaskExecutorFactory",
    "PromptEditorDiagnosticsControllerBinding",
    "PromptEditorInitialLayoutHost",
    "PromptEditorLifecycleWiringResult",
    "PromptEditorSignalHost",
    "apply_prompt_editor_initial_layout",
    "bind_prompt_editor_diagnostics_signals",
    "bind_prompt_editor_signals",
    "build_context_insertion_service",
    "build_external_url_action_runner",
    "build_prompt_document_service",
    "build_prompt_editor_menu_runtime",
    "build_resize_handle",
    "bundle_collaborators",
    "is_deleted_qt_object_error",
    "qt_object_is_alive",
    "wire_prompt_editor_construction_lifecycle",
]
