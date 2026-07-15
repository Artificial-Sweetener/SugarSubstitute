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
from .factory import (
    PromptEditorCompositionContext,
    PromptEditorCompositionFactory,
    build_external_url_action_runner,
)
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
    "PromptEditorCompositionContext",
    "PromptEditorCompositionFactory",
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
    "build_external_url_action_runner",
    "is_deleted_qt_object_error",
    "qt_object_is_alive",
    "wire_prompt_editor_construction_lifecycle",
]
