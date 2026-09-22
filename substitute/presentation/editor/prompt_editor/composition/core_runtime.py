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

"""Compose the projection-through-interaction prompt-editor runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent

from substitute.application.prompt_editor.conditioning import PromptConditioningContext
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..commands.autocomplete_commands import PromptAutocompleteAcceptance
from ..commands.context_insertion import (
    PromptCommandContextInsertState,
    PromptContextInsertionService,
)
from ..commands.contracts import PromptCommandResult
from ..commands.diagnostic_commands import (
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
)
from ..external_input_facade import (
    PromptEditorExternalInputFacade,
    build_prompt_editor_external_input_facade,
)
from ..features import PromptDiagnosticsCursor, PromptDiagnosticsFeatureController
from ..interactions import (
    PromptDanbooruDialogRunner,
    PromptExternalUrlActionRunner,
    PromptInteractionEditor,
    PromptWheelScrollResult,
)
from ..interactions.weight_interaction import PromptWeightInteractionEditor
from ..key_router import PromptEditorKeyRouter, build_prompt_editor_key_router
from ..projection.undo_payload import PromptProjectionUndoPayload
from ..rendering_facade import (
    PromptEditorRenderingFacade,
    build_prompt_editor_rendering_facade,
)
from ..scene_facade import PromptEditorSceneFacade, build_prompt_editor_scene_facade
from ..shell import PromptEditorShellRuntime
from .autocomplete_factory import PromptEditorAutocompleteFactory
from .collaborator_bundle import (
    PromptEditorAutocompleteCollaborators,
    PromptEditorConstructionInputs,
)
from .context import PromptEditorCompositionContext
from .context_insertion_factory import build_context_insertion_service
from .danbooru_factory import PromptEditorDanbooruFactory
from .execution_factory import PromptEditorExecutionFactory
from .feature_collaborators import (
    PromptEditorServiceCollaborators,
    PromptEditorSyntaxCollaborators,
)
from .foundations import (
    build_external_url_action_runner,
    build_prompt_document_service,
)
from .projection_factory import (
    PromptEditorProjectionCollaborators,
    PromptEditorProjectionFactory,
)
from .service_factory import PromptEditorServiceFactory
from .syntax_factory import PromptEditorSyntaxFactory
from .wiring import (
    PromptEditorConstructionObserver,
)


@dataclass(frozen=True, slots=True)
class PromptEditorCoreRuntimeBindings:
    """Declare host operations consumed while composing core collaborators."""

    mount_projection: Callable[[PromptEditorProjectionCollaborators], None]
    context_insert_state: Callable[[], PromptCommandContextInsertState]
    restore_focus: Callable[[], None]
    complete_lora_autocomplete_replacement: Callable[[], None]
    execute_autocomplete_acceptance: Callable[
        [PromptAutocompleteAcceptance],
        PromptCommandResult[object],
    ]
    interaction_editor: PromptInteractionEditor
    weight_interaction_editor: PromptWeightInteractionEditor
    wheel_surface_scroll_allowed: Callable[[QWheelEvent], bool]
    wheel_surface_scroll_handler: Callable[[QWheelEvent], PromptWheelScrollResult]
    wheel_to_editor_panel: Callable[[QWheelEvent], None]
    publish_rich_rendering_changed: Callable[[bool], None]
    bind_diagnostics_signals: Callable[[PromptDiagnosticsFeatureController], None]


@dataclass(frozen=True, slots=True)
class PromptEditorCoreRuntime:
    """Carry the composed projection, service, autocomplete, and syntax graph."""

    projection: PromptEditorProjectionCollaborators
    services: PromptEditorServiceCollaborators
    autocomplete: PromptEditorAutocompleteCollaborators
    syntax: PromptEditorSyntaxCollaborators
    context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload]
    external_input: PromptEditorExternalInputFacade
    external_url_actions: PromptExternalUrlActionRunner
    danbooru_dialog: PromptDanbooruDialogRunner
    diagnostics: PromptDiagnosticsFeatureController
    scene: PromptEditorSceneFacade
    rendering: PromptEditorRenderingFacade
    key_router: PromptEditorKeyRouter


@dataclass(frozen=True, slots=True)
class _PromptDiagnosticsHostAdapter:
    """Route diagnostics to initialized command owners during composition."""

    restore_focus: Callable[[], None]
    source_text: Callable[[], str]
    cursor: Callable[[], PromptDiagnosticsCursor]
    source_identity: Callable[[], PromptSourceIdentity]
    execute_action: Callable[
        [PromptDiagnosticAction],
        PromptDiagnosticCommandResult[PromptProjectionUndoPayload],
    ]

    def setFocus(self) -> None:
        """Restore editor focus after an accepted diagnostic mutation."""

        self.restore_focus()

    def toPlainText(self) -> str:
        """Return the live source text used by diagnostics presentation."""

        return self.source_text()

    def textCursor(self) -> PromptDiagnosticsCursor:
        """Return the live source-backed diagnostics cursor."""

        return self.cursor()

    def prompt_command_source_identity(self) -> PromptSourceIdentity:
        """Return the projection command owner's current source identity."""

        return self.source_identity()

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one diagnostic action through the projection command owner."""

        return cast(PromptDiagnosticCommandResult[object], self.execute_action(action))


def build_prompt_editor_core_runtime(
    inputs: PromptEditorConstructionInputs,
    context: PromptEditorCompositionContext,
    shell: PromptEditorShellRuntime,
    bindings: PromptEditorCoreRuntimeBindings,
    observer: PromptEditorConstructionObserver,
    *,
    prompt_conditioning_context: PromptConditioningContext | None,
) -> PromptEditorCoreRuntime:
    """Compose all owners from projection editing through input interaction."""

    phase_started_at = observer.started_at()
    execution_factory = PromptEditorExecutionFactory(inputs, context)
    danbooru_factory = PromptEditorDanbooruFactory(context)
    projection = PromptEditorProjectionFactory(
        inputs,
        context,
        execution_factory,
    ).build(paste_completed=shell.paste_completion.complete)
    bindings.mount_projection(projection)
    external_input = build_prompt_editor_external_input_facade(
        context.editor,
        projection.surface,
        shell.paste_completion,
    )
    context.editor.setFocusProxy(projection.surface)
    context.editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    projection.shell_padding_fill_plane.lower()
    projection.fill_plane.lower()
    shell.chrome.configure_owned_fill_plane()
    shell.chrome.bind_theme_refresh()
    projection.surface.raise_()
    context_insertion = build_context_insertion_service(
        projection,
        cursor_provider=projection.surface.textCursor,
        context_insert_state_provider=bindings.context_insert_state,
        focus_restorer=bindings.restore_focus,
        source_text_provider=projection.surface.toPlainText,
    )
    observer.log_timing(
        "Initialized prompt editor projection surface",
        started_at=phase_started_at,
        has_thumbnail_repository=inputs.thumbnail_asset_repository is not None,
        level="debug",
    )

    phase_started_at = observer.started_at()
    external_url_actions = build_external_url_action_runner(inputs.open_url)
    services = PromptEditorServiceFactory(
        inputs,
        context,
        execution_factory,
        danbooru_factory,
    ).build(
        projection,
        context_insertion,
        cursor_provider=projection.surface.textCursor,
        cursor_setter=projection.surface.setTextCursor,
        external_url_actions=external_url_actions,
        source_text_provider=projection.surface.toPlainText,
    )
    danbooru_dialog = danbooru_factory.build_dialog_runner(
        action_controller=services.danbooru_action_controller,
        lookup_dispatcher_factory=inputs.danbooru_lookup_dispatcher_factory,
    )
    diagnostics = PromptDiagnosticsFeatureController(
        host=_PromptDiagnosticsHostAdapter(
            restore_focus=bindings.restore_focus,
            source_text=projection.surface.toPlainText,
            cursor=projection.surface.textCursor,
            source_identity=projection.source_commands.source_identity,
            execute_action=projection.diagnostic_commands.execute,
        ),
        surface=projection.surface.diagnostics,
        feature_profile=services.feature_profile_controller,
        wildcard_feature=services.wildcard_diagnostics_presentation,
        document_semantics=inputs.prompt_document_semantics,
        conditioning_context=prompt_conditioning_context,
        spellcheck_service=inputs.prompt_spellcheck_service,
        parent=context.editor,
        request_channel=cast(
            Any,
            execution_factory.build_request_channel(owner_label="prompt-diagnostics"),
        ),
        bind_signals=bindings.bind_diagnostics_signals,
    )
    projection.danbooru_paste_import_controller.configure_danbooru_url_import(
        services.danbooru_action_controller.url_import_service,
        enabled=services.danbooru_action_controller.url_import_enabled,
    )
    observer.log_timing(
        "Initialized prompt editor service state",
        started_at=phase_started_at,
        has_lora_catalog=inputs.prompt_lora_catalog_service is not None,
        has_spellcheck_service=inputs.prompt_spellcheck_service is not None,
        has_segment_presets=inputs.prompt_segment_preset_source is not None,
        level="debug",
    )

    phase_started_at = observer.started_at()
    document_service = build_prompt_document_service(inputs)
    autocomplete = PromptEditorAutocompleteFactory(inputs, context).build(
        projection,
        services,
        external_url_actions,
        document_service,
        autocomplete_cursor_position=(
            lambda: projection.surface.textCursor().position()
        ),
        autocomplete_focus_host=context.editor,
        complete_lora_autocomplete_replacement=(
            bindings.complete_lora_autocomplete_replacement
        ),
        cursor_rect=projection.surface.cursorRect,
        execute_autocomplete_acceptance=bindings.execute_autocomplete_acceptance,
        restore_autocomplete_focus=bindings.restore_focus,
        viewport=projection.surface.viewport,
    )
    scene = build_prompt_editor_scene_facade(
        context.editor,
        services.scene_context_publication,
        autocomplete.query_result_lifecycle,
    )
    feature_profile = services.feature_profile_controller
    observer.log_timing(
        "Initialized prompt editor autocomplete services",
        started_at=phase_started_at,
        has_lora_catalog=inputs.prompt_lora_catalog_service is not None,
        lora_autocomplete_enabled=feature_profile.lora_autocomplete_enabled,
        trigger_word_suggestions_enabled=feature_profile.lora_trigger_words_enabled,
        level="debug",
    )

    phase_started_at = observer.started_at()
    syntax = PromptEditorSyntaxFactory(inputs, execution_factory).build(
        projection,
        services,
        autocomplete.autocomplete,
        document_service,
        autocomplete.query_result_lifecycle,
        autocomplete_cursor_state=lambda: (
            (cursor := projection.surface.textCursor()).position(),
            cursor.hasSelection(),
        ),
        autocomplete_source_text=projection.surface.toPlainText,
        syntax_active_span=projection.surface.active_syntax_span,
        syntax_cursor_position=lambda: projection.surface.textCursor().position(),
        syntax_editor_session_id=id(context.editor),
        syntax_source_text=projection.surface.toPlainText,
        interaction_editor=bindings.interaction_editor,
        weight_interaction_editor=bindings.weight_interaction_editor,
        wheel_surface_scroll_allowed=bindings.wheel_surface_scroll_allowed,
        wheel_surface_scroll_handler=bindings.wheel_surface_scroll_handler,
        wheel_to_editor_panel=bindings.wheel_to_editor_panel,
    )
    rendering = build_prompt_editor_rendering_facade(
        projection.surface,
        syntax.interaction_controller,
        bindings.publish_rich_rendering_changed,
    )
    key_router = build_prompt_editor_key_router(
        syntax.interaction_controller,
        projection.surface,
    )
    shell.paste_completion.bind_interaction(syntax.interaction_controller)
    projection.surface.bind_canonical_semantic_preparer(
        syntax.syntax_state.prepare_prompt_state
    )
    observer.log_timing(
        "Initialized prompt editor syntax services",
        started_at=phase_started_at,
        spellcheck_feature_enabled=feature_profile.spellcheck_enabled,
        level="debug",
    )
    return PromptEditorCoreRuntime(
        projection=projection,
        services=services,
        autocomplete=autocomplete,
        syntax=syntax,
        context_insertion=context_insertion,
        external_input=external_input,
        external_url_actions=external_url_actions,
        danbooru_dialog=danbooru_dialog,
        diagnostics=diagnostics,
        scene=scene,
        rendering=rendering,
        key_router=key_router,
    )


__all__ = [
    "PromptEditorCoreRuntime",
    "PromptEditorCoreRuntimeBindings",
    "build_prompt_editor_core_runtime",
]
