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

"""Route typed prompt syntax actions to their mutation-family owners."""

from __future__ import annotations

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.editing.emphasis_mutations import (
    PromptEmphasisMutationService,
)
from substitute.application.prompt_editor.editing.lora_mutations import (
    PromptLoraMutationService,
)
from substitute.application.prompt_editor.editing.mutation_result import (
    PromptMutation,
    PromptMutationProjector,
)
from substitute.application.prompt_editor.editing.structured_syntax import (
    PromptLogicalSyntaxMutation,
    PromptStructuredSyntaxMutationAdapter,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
    PromptAdjustEmphasisContentAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptConsumeSyntaxAction,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
    PromptSyntaxAction,
)
from substitute.application.prompt_editor.editing.wildcard_mutations import (
    PromptWildcardMutationService,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.prompt_editor.editing.syntax_action_router")


class PromptSyntaxActionRouter:
    """Dispatch syntax actions while preserving structured-value boundaries."""

    def __init__(
        self,
        *,
        document_semantics: PromptDocumentSemantics,
        mutation_projector: PromptMutationProjector,
        emphasis_mutations: PromptEmphasisMutationService,
        lora_mutations: PromptLoraMutationService,
        wildcard_mutations: PromptWildcardMutationService,
    ) -> None:
        """Store syntax-family owners and the structured-value adapter."""

        self._document_semantics = document_semantics
        self._mutation_projector = mutation_projector
        self._emphasis_mutations = emphasis_mutations
        self._lora_mutations = lora_mutations
        self._wildcard_mutations = wildcard_mutations
        self._structured_mutations = PromptStructuredSyntaxMutationAdapter(
            document_semantics
        )

    def apply(self, text: str, action: PromptSyntaxAction) -> PromptMutation | None:
        """Apply one typed syntax action to ordinary or structured prompt text."""

        if not self._document_semantics.uses_structured_prompt_values:
            return self._apply_unscoped(text, action)
        mutation = self._structured_mutations.apply(
            text,
            action,
            apply_logical_action=self._apply_logical,
        )
        if mutation is None:
            return None
        return self._mutation_projector.project_text(
            text=mutation.text,
            selection_start=mutation.selection_start,
            selection_end=mutation.selection_end,
        )

    def _apply_logical(
        self,
        text: str,
        action: PromptSyntaxAction,
    ) -> PromptLogicalSyntaxMutation | None:
        """Return coordinate fields from one ordinary logical mutation."""

        mutation = self._apply_unscoped(text, action)
        if mutation is None:
            return None
        return PromptLogicalSyntaxMutation(
            text=mutation.text,
            selection_start=mutation.selection_start,
            selection_end=mutation.selection_end,
        )

    def _apply_unscoped(
        self,
        text: str,
        action: PromptSyntaxAction,
    ) -> PromptMutation | None:
        """Apply one syntax action to an ordinary logical prompt string."""

        if isinstance(action, PromptAdjustEmphasisAction):
            mutation = self._emphasis_mutations.adjust_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                delta=action.delta,
            )
            _log_missing_target(mutation, text=text, action=action, reason="stale")
            return mutation
        if isinstance(action, PromptAdjustEmphasisContentAction):
            return self._emphasis_mutations.adjust(
                text,
                selection_start=action.content_start,
                selection_end=action.content_end,
                delta=action.delta,
            )
        if isinstance(action, PromptSetEmphasisWeightAction):
            mutation = self._emphasis_mutations.set_weight_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                weight=action.weight,
            )
            _log_missing_target(mutation, text=text, action=action, reason="stale")
            return mutation
        if isinstance(action, PromptSetEmphasisWeightContentAction):
            return self._emphasis_mutations.set_weight(
                text,
                selection_start=action.content_start,
                selection_end=action.content_end,
                weight=action.weight,
            )
        if isinstance(action, PromptAdjustLoraWeightAction):
            mutation = self._lora_mutations.adjust_weight_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                delta=action.delta,
            )
            _log_missing_target(mutation, text=text, action=action, reason="stale")
            return mutation
        if isinstance(action, PromptSetLoraWeightAction):
            mutation = self._lora_mutations.set_weight_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                weight=action.weight,
            )
            _log_missing_target(mutation, text=text, action=action, reason="stale")
            return mutation
        if isinstance(action, PromptSetWildcardTagAction):
            mutation = self._wildcard_mutations.set_tag_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                tag=action.tag,
            )
            _log_missing_target(
                mutation,
                text=text,
                action=action,
                reason="stale or invalid",
            )
            return mutation
        if isinstance(action, PromptAdjustWildcardTagAction):
            mutation = self._wildcard_mutations.adjust_numeric_tag_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                current_display_tag=action.current_display_tag,
                delta=action.delta,
            )
            _log_missing_target(
                mutation,
                text=text,
                action=action,
                reason="stale or not numeric",
            )
            return mutation
        if isinstance(action, PromptConsumeSyntaxAction):
            return None
        log_warning(
            _LOGGER,
            "Unsupported prompt syntax action.",
            action_type=type(action).__name__,
            syntax_kind=getattr(action, "syntax_kind", "unknown"),
            prompt_length=len(text),
        )
        return None


def _log_missing_target(
    mutation: PromptMutation | None,
    *,
    text: str,
    action: PromptSyntaxAction,
    reason: str,
) -> None:
    """Log a rejected action with its stale or invalid source coordinates."""

    if mutation is not None:
        return
    log_debug(
        _LOGGER,
        f"Prompt syntax action target is {reason}.",
        action_type=type(action).__name__,
        syntax_kind=getattr(action, "syntax_kind", "unknown"),
        outer_start=getattr(action, "outer_start", None),
        outer_end=getattr(action, "outer_end", None),
        prompt_length=len(text),
    )


__all__ = ["PromptSyntaxActionRouter"]
