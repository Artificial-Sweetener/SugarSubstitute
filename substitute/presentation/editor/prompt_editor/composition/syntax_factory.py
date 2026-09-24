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

"""Own prompt syntax, interaction, reorder, and weight composition."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QWheelEvent

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)

from ..async_work import build_prompt_semantic_refresh_controller
from ..features import PromptAutocompleteQueryResultLifecycle
from ..interactions import (
    PromptAutocompleteInputPort,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
    PromptInteractionController,
    PromptInteractionEditor,
    PromptTokenWeightWheelIntentController,
    PromptWeightInteraction,
    PromptWheelController,
    PromptWheelScrollResult,
)
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from ..interactions.weight_interaction import PromptWeightInteractionEditor
from ..projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from ..syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from .collaborator_bundle import PromptEditorConstructionInputs
from .execution_factory import PromptEditorExecutionFactory
from .feature_collaborators import (
    PromptEditorServiceCollaborators,
    PromptEditorSyntaxCollaborators,
)
from .projection_factory import PromptEditorProjectionCollaborators
from .reorder_overlay_factory import PromptSegmentReorderOverlayFactory
from .token_weight_controls_factory import PromptTokenWeightControlsFactory


class PromptEditorSyntaxFactory:
    """Build the syntax and interaction graph against shared editor owners."""

    def __init__(
        self,
        inputs: PromptEditorConstructionInputs,
        execution: PromptEditorExecutionFactory,
    ) -> None:
        """Retain construction inputs and the shared async execution authority."""
        self._inputs = inputs
        self._execution = execution

    def build(
        self,
        projection_collaborators: PromptEditorProjectionCollaborators,
        service_collaborators: PromptEditorServiceCollaborators,
        autocomplete: PromptAutocompleteInputPort,
        document_service: PromptDocumentService,
        autocomplete_query_result_lifecycle: PromptAutocompleteQueryResultLifecycle,
        *,
        autocomplete_cursor_state: Callable[[], tuple[int, bool]],
        autocomplete_source_text: Callable[[], str],
        syntax_active_span: Callable[[], PromptSyntaxSpanView | None],
        syntax_cursor_position: Callable[[], int],
        syntax_editor_session_id: int,
        syntax_source_text: Callable[[], str],
        interaction_editor: PromptInteractionEditor,
        weight_interaction_editor: PromptWeightInteractionEditor,
        wheel_surface_scroll_allowed: Callable[[QWheelEvent], bool],
        wheel_surface_scroll_handler: Callable[[QWheelEvent], PromptWheelScrollResult],
        wheel_to_editor_panel: Callable[[QWheelEvent], None],
    ) -> PromptEditorSyntaxCollaborators:
        """Build syntax services, renderers, controls, and interaction owners."""
        semantics = self._inputs.prompt_document_semantics
        feature_profile = service_collaborators.feature_profile_controller
        mutation_service = PromptMutationService(document_semantics=semantics)
        syntax_profile = feature_profile.syntax_profile()
        syntax_service = PromptSyntaxService(
            self._inputs.prompt_wildcard_catalog_gateway,
            prompt_lora_catalog_service=self._inputs.prompt_lora_catalog_service,
            document_semantics=semantics,
        )
        reorder_projection = PromptReorderPreviewProjectionProvider(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )
        reorder_metrics = PromptReorderInteractionMetricsOwner()
        reorder_overlay_factory = PromptSegmentReorderOverlayFactory(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            geometry_owner=projection_collaborators.surface.reorder.geometry_owner,
            interaction_metrics=reorder_metrics,
        )
        renderers = PromptSyntaxRendererCoordinator((projection_collaborators.surface,))
        syntax_state = PromptSyntaxStateController(
            active_syntax_span=syntax_active_span,
            cursor_position=syntax_cursor_position,
            editor_session_id=syntax_editor_session_id,
            renderers=renderers,
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            state=projection_collaborators.surface.editor_state,
            source_text=syntax_source_text,
            source_changed_callback=lambda reason: reorder_projection.clear_cache(
                reason=reason
            ),
        )
        semantic_refresh = build_prompt_semantic_refresh_controller(
            host=syntax_state,
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            executor=self._execution.build_task_executor(owner_label="prompt-semantic"),
        )
        autocomplete_snapshots = PromptAutocompleteSourceSnapshotController(
            cursor_state=autocomplete_cursor_state,
            document_view_provider=lambda: syntax_state.document_view,
            feature_profile=feature_profile,
            source_identity=projection_collaborators.source_commands.source_identity,
            source_text=autocomplete_source_text,
        )
        autocomplete_timing = PromptAutocompleteTimingController(
            source_snapshots=autocomplete_snapshots,
            lifecycle_requester=autocomplete_query_result_lifecycle,
            lora_autocomplete_enabled=lambda: feature_profile.lora_autocomplete_enabled,
        )
        reorder_publication = PromptReorderPreviewPublicationOwner(
            clear_preview_state=projection_collaborators.surface.reorder.clear_preview_state,
            current_document_view=lambda: syntax_state.document_view,
            publish_preview_state=projection_collaborators.surface.reorder.set_preview_state,
            source_identity=projection_collaborators.source_commands.source_identity,
            viewport_width=lambda: projection_collaborators.surface.viewport().width(),
            document_service=document_service,
            projection_provider=reorder_projection,
            metrics=reorder_metrics,
            interval_ms=PromptReorderPreviewPublicationOwner.DEFAULT_INTERVAL_MS,
        )
        weight_interaction = PromptWeightInteraction(
            editor=weight_interaction_editor,
            autocomplete_timing=autocomplete_timing,
            syntax_state=syntax_state,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            feature_profile=feature_profile,
            semantic_refresh=semantic_refresh,
            projection=projection_collaborators.surface,
        )
        interaction_controller = PromptInteractionController(
            interaction_editor,
            autocomplete=autocomplete,
            autocomplete_timing_controller=autocomplete_timing,
            syntax_state=syntax_state,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            feature_profile=feature_profile,
            semantic_refresh_controller=semantic_refresh,
            reorder_overlay_factory=reorder_overlay_factory,
            reorder_preview_publication=reorder_publication,
            weight_interaction=weight_interaction,
        )
        wheel_intent = PromptTokenWeightWheelIntentController(
            projection_collaborators.surface
        )
        weight_controls = PromptTokenWeightControlsFactory(
            surface=projection_collaborators.surface,
            exact_edit_host=weight_interaction,
            wheel_intent_owner=wheel_intent,
        ).create_token_weight_controls()
        wheel_controller = PromptWheelController(
            allow_surface_scroll=wheel_surface_scroll_allowed,
            forward_to_editor_panel=wheel_to_editor_panel,
            handle_surface_scroll=wheel_surface_scroll_handler,
            token_weight_wheel_intent=wheel_intent,
            token_weight_wheel_handler=weight_controls.handle_host_wheel_event,
        )
        syntax_state.add_renderer(weight_controls)
        return PromptEditorSyntaxCollaborators(
            autocomplete_timing_controller=autocomplete_timing,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_profile=syntax_profile,
            syntax_service=syntax_service,
            token_weight_controls=weight_controls,
            weight_interaction=weight_interaction,
            wheel_controller=wheel_controller,
            syntax_renderer_coordinator=renderers,
            syntax_state=syntax_state,
            interaction_controller=interaction_controller,
        )
