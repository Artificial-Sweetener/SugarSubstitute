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

"""Compose production prompt interaction controllers for focused tests."""

from __future__ import annotations

import importlib
from typing import Any, cast

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
    PromptEditorState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features.feature_profile_controller import (
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_overlay_port import (
    PromptReorderOverlayFactory,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from substitute.presentation.editor.prompt_editor.syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    SyntaxRendererCoordinatorDouble,
    autocomplete_double,
    semantic_refresh_controller_double,
    syntax_service,
)
from tests.presentation.editor.prompt_editor.interactions.support.editor import (
    ControllerEditorDouble,
)
from tests.presentation.editor.prompt_editor.interactions.support.reorder_overlay import (
    OverlayFactoryDouble,
)
from tests.support.prompt_editor.autocomplete_support import (
    PromptAutocompleteTimingTestDouble,
    prompt_syntax_profile,
)


def prompt_interaction_controller(
    editor: Any,
    *,
    syntax_renderers: SyntaxRendererCoordinatorDouble,
    document_service: PromptDocumentService | None = None,
    mutation_service: PromptMutationService | None = None,
    syntax_service_: PromptSyntaxService | None = None,
    syntax_profile: PromptSyntaxProfile | None = None,
    autocomplete: object | None = None,
    semantic_refresh_controller: object | None = None,
    feature_profile: PromptFeatureProfileController | None = None,
    reorder_overlay_factory: PromptReorderOverlayFactory | None = None,
    reorder_interaction_metrics: PromptReorderInteractionMetricsOwner | None = None,
) -> Any:
    """Build a prompt interaction controller with a syntax-state owner."""

    interaction_module = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.controller"
    )
    weight_interaction_module = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.weight_interaction"
    )
    resolved_document_service = document_service or PromptDocumentService()
    resolved_syntax_service = syntax_service_ or syntax_service()
    resolved_syntax_profile = syntax_profile or prompt_syntax_profile(
        "emphasis",
        "wildcard",
    )
    resolved_mutation_service = mutation_service or PromptMutationService()
    initial_document = PromptDocumentService().build_document_view(editor.toPlainText())
    initial_render_plan = resolved_syntax_service.build_render_plan(
        initial_document,
        resolved_syntax_profile,
    )
    live_source = _LiveEditorSource(editor)
    state: PromptEditorState[
        PromptDocumentView,
        PromptSyntaxRenderPlan,
        PromptDocumentView,
        Any,
        Any,
    ] = PromptEditorState(
        source=live_source,
        semantic_document=initial_document,
        render_plan=initial_render_plan,
        projection_document=initial_document,
    )
    if isinstance(editor, ControllerEditorDouble):

        def publish_live_source() -> None:
            """Publish the changed test source through the revision owner."""

            state.publish_source(live_source)

        editor.bind_source_publication(publish_live_source)
    syntax_state = PromptSyntaxStateController(
        active_syntax_span=editor.active_syntax_span,
        cursor_position=lambda: editor.textCursor().position(),
        editor_session_id=id(editor),
        renderers=cast(PromptSyntaxRendererCoordinator, syntax_renderers),
        document_service=resolved_document_service,
        syntax_service=resolved_syntax_service,
        syntax_profile=resolved_syntax_profile,
        state=cast(
            PromptEditorDocumentState[
                PromptDocumentView,
                PromptSyntaxRenderPlan,
                PromptProjectionDocument,
            ],
            state,
        ),
        source_text=editor.toPlainText,
    )
    resolved_overlay_factory = reorder_overlay_factory or OverlayFactoryDouble(
        interaction_metrics=reorder_interaction_metrics,
    )
    preview_publication = PromptReorderPreviewPublicationOwner(
        clear_preview_state=editor.clear_reorder_preview_state,
        current_document_view=lambda: syntax_state.document_view,
        publish_preview_state=editor.set_reorder_preview_state,
        source_identity=editor.prompt_command_source_identity,
        viewport_width=lambda: 0,
        document_service=resolved_document_service,
        projection_provider=PromptReorderPreviewProjectionProvider(
            document_service=resolved_document_service,
            syntax_service=resolved_syntax_service,
            syntax_profile=resolved_syntax_profile,
        ),
        metrics=resolved_overlay_factory.interaction_metrics,
        interval_ms=PromptReorderPreviewPublicationOwner.DEFAULT_INTERVAL_MS,
    )
    resolved_autocomplete = cast(Any, autocomplete or autocomplete_double())
    resolved_semantic_refresh = (
        semantic_refresh_controller or semantic_refresh_controller_double()
    )
    resolved_feature_profile = (
        feature_profile or PromptFeatureProfileController.from_legacy_syntax(None)
    )
    weight_interaction = weight_interaction_module.PromptWeightInteraction(
        editor=editor,
        autocomplete_timing=cast(
            Any,
            PromptAutocompleteTimingTestDouble(
                on_clear=lambda: resolved_autocomplete.dismiss_autocomplete(
                    "incompatible_query"
                )
            ),
        ),
        syntax_state=syntax_state,
        document_service=resolved_document_service,
        mutation_service=resolved_mutation_service,
        syntax_service=resolved_syntax_service,
        syntax_profile=resolved_syntax_profile,
        feature_profile=resolved_feature_profile,
        semantic_refresh=cast(Any, resolved_semantic_refresh),
        projection=None,
    )
    return interaction_module.PromptInteractionController(
        editor,
        autocomplete=resolved_autocomplete,
        autocomplete_timing_controller=cast(
            Any,
            PromptAutocompleteTimingTestDouble(
                on_clear=lambda: resolved_autocomplete.dismiss_autocomplete(
                    "incompatible_query"
                )
            ),
        ),
        syntax_state=syntax_state,
        document_service=resolved_document_service,
        mutation_service=resolved_mutation_service,
        syntax_service=resolved_syntax_service,
        syntax_profile=resolved_syntax_profile,
        feature_profile=resolved_feature_profile,
        semantic_refresh_controller=resolved_semantic_refresh,
        reorder_overlay_factory=resolved_overlay_factory,
        weight_interaction=weight_interaction,
        reorder_preview_publication=preview_publication,
    )


class _LiveEditorSource:
    """Expose test-editor text as a monotonically revisioned source boundary."""

    def __init__(self, editor: Any) -> None:
        """Capture the initial editor text and revision."""

        self._editor = editor
        self._text = cast(str, editor.toPlainText())
        self._revision = 0
        self._identity = PromptSourceIdentity(0, len(self._text))

    @property
    def identity(self) -> PromptSourceIdentity:
        """Return the identity cached for the current test source."""

        self._sync()
        return self._identity

    @property
    def source_text(self) -> str:
        """Return current editor text after advancing its test revision."""

        self._sync()
        return self._text

    @property
    def source_revision(self) -> int:
        """Return the revision assigned to current editor text."""

        self._sync()
        return self._revision

    @property
    def source_length(self) -> int:
        """Return current editor text length."""

        self._sync()
        return len(self._text)

    def _sync(self) -> None:
        """Advance once whenever the editor exposes different source text."""

        text = cast(str, self._editor.toPlainText())
        if text == self._text:
            return
        self._text = text
        self._revision += 1
        self._identity = PromptSourceIdentity(self._revision, len(self._text))
