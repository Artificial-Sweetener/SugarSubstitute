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

"""Assemble immutable prompt projections from focused feature projectors."""

from __future__ import annotations

from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionTransientState,
)
from substitute.presentation.editor.prompt_editor.core.projection.mapping import (
    PromptProjectionMapping,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.caret_map_builder import (
    build_prompt_projection_caret_map,
)
from substitute.presentation.editor.prompt_editor.projection.collapse_models import (
    PromptProjectionCollapseCandidate,
)
from substitute.presentation.editor.prompt_editor.projection.emphasis_projection import (
    build_emphasis_collapse_candidates,
)
from substitute.presentation.editor.prompt_editor.projection.inline_preview_projection import (
    PromptInlinePreviewProjector,
)
from substitute.presentation.editor.prompt_editor.projection.lora_projection import (
    build_lora_collapse_candidates,
)
from substitute.presentation.editor.prompt_editor.projection.region_projection import (
    PromptRegionProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.run_builder import (
    PromptProjectionRunBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.scene_projection import (
    PromptSceneProjectionPlanner,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.projection.wildcard_projection import (
    build_wildcard_collapse_candidates,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)


class PromptProjectionBuilder:
    """Assemble one projection document from independently owned feature views."""

    def __init__(
        self,
        *,
        document_semantics: PromptDocumentSemantics | None = None,
    ) -> None:
        """Prepare the collaborators required for every projection build."""

        active_semantics = document_semantics or OrdinaryPromptDocumentSemantics()
        self._scene_projection = PromptSceneProjectionPlanner(active_semantics)
        self._region_projection = PromptRegionProjectionBuilder()
        self._run_builder = PromptProjectionRunBuilder()
        self._inline_preview_projector = PromptInlinePreviewProjector()

    def source_edit_requires_canonical_rebuild(
        self,
        previous_source_text: str,
        next_source_text: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one source-local edit changes scene topology."""

        return self._scene_projection.edit_requires_canonical_rebuild(
            previous_source_text,
            next_source_text,
            start=start,
            end=end,
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.PROJECTION_DOCUMENT_BUILD)
    def build_projection(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None = None,
        decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
        scene_error_keys: frozenset[str] = frozenset(),
        transient_state: PromptProjectionTransientState | None = None,
    ) -> PromptProjectionDocument:
        """Build the complete current projection for one prompt snapshot."""

        active_transient_state = transient_state or PromptProjectionTransientState()
        collapse_candidates = self._collapse_candidates(
            document_view,
            render_plan,
            display_mode=display_mode,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )
        tokens = tuple(candidate.token for candidate in collapse_candidates)
        source_text = document_view.source_text
        if display_mode is PromptProjectionDisplayMode.RAW:
            runs = self._run_builder.raw_runs(source_text)
        else:
            runs = self._run_builder.projected_runs(
                source_text,
                collapse_candidates=collapse_candidates,
            )
            region_projection = self._region_projection.build(
                runs,
                document_view.region_structure,
            )
            runs = region_projection.runs
            tokens = tuple(
                sorted(
                    (*tokens, *region_projection.tokens),
                    key=lambda token: (token.source_start, token.source_end),
                )
            )
        runs = self._inline_preview_projector.project(
            runs,
            source_length=len(source_text),
            preview=active_transient_state.autocomplete_preview,
        )
        projection_text = "".join(
            run.display_text
            if run.kind is PromptProjectionRunKind.TEXT
            else OBJECT_REPLACEMENT_CHARACTER
            for run in runs
        )
        mapping = PromptProjectionMapping(
            runs=runs,
            source_length=len(source_text),
            projection_length=len(projection_text),
        )
        caret_map = build_prompt_projection_caret_map(
            runs=runs,
            tokens=tokens,
            source_length=len(source_text),
            projection_length=len(projection_text),
        )
        return PromptProjectionDocument(
            display_mode=display_mode,
            source_text=source_text,
            projection_text=projection_text,
            runs=runs,
            tokens=tokens,
            mapping=mapping,
            caret_map=caret_map,
            region_structure=document_view.region_structure,
        )

    def _collapse_candidates(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> tuple[PromptProjectionCollapseCandidate, ...]:
        """Combine independent semantic feature candidates in source order."""

        all_supported_ranges = tuple(
            sorted((span.start, span.end) for span in render_plan.syntax_spans)
        )
        accent_ranges = frozenset(decoration_accent_ranges)
        candidates = [
            PromptProjectionCollapseCandidate(
                start=token.source_start,
                end=token.source_end,
                token=token,
            )
            for token in self._scene_projection.build_tokens(
                document_view.source_text,
                scene_error_keys=scene_error_keys,
            )
        ]
        candidates.extend(
            build_emphasis_collapse_candidates(
                document_view,
                render_plan,
                session=session,
                active_span_range=active_span_range,
                decoration_accent_ranges=accent_ranges,
            )
        )
        candidates.extend(
            build_wildcard_collapse_candidates(
                render_plan,
                session=session,
                active_span_range=active_span_range,
                decoration_accent_ranges=accent_ranges,
                all_supported_ranges=all_supported_ranges,
            )
        )
        candidates.extend(
            build_lora_collapse_candidates(
                document_view,
                render_plan,
                display_mode=display_mode,
                session=session,
                active_span_range=active_span_range,
                all_supported_ranges=all_supported_ranges,
            )
        )
        candidates.sort(key=lambda candidate: candidate.start)
        return tuple(candidates)


__all__ = ["PromptProjectionBuilder"]
