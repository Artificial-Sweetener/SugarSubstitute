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

"""Own mounted prompt-editor document replacement and invalidation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.prompt_editor.conditioning import PromptConditioningContext
from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
    PromptDocumentSemanticsController,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)

from .commands.source_service import PromptSourceCommandService
from .features import (
    PromptDiagnosticsFeatureController,
    PromptLoraTriggerWordController,
)
from .interactions import PromptInteractionController
from .projection.undo_payload import PromptProjectionUndoPayload


@dataclass(frozen=True, slots=True)
class PromptEditorDocumentBindings:
    """Declare document commands and semantic invalidation operations."""

    set_plain_text: Callable[[str], None]
    set_source_text: Callable[[str], None]
    replace_baseline_text: Callable[..., None]
    replace_document_text: Callable[[str], None]
    replace_document_text_with_prompt_state: Callable[..., None]
    replace_semantics: Callable[[PromptDocumentSemantics], bool]
    replace_conditioning_context: Callable[[PromptConditioningContext], bool]
    publish_interaction_semantics_changed: Callable[[], None]
    publish_diagnostics_semantics_changed: Callable[[], None]
    publish_lora_source_changed: Callable[[], None]


@dataclass(frozen=True, slots=True)
class PromptEditorDocumentFacade:
    """Expose document commands with atomic semantic invalidation."""

    bindings: PromptEditorDocumentBindings

    def set_plain_text(self, text: str) -> None:
        """Replace the full normalized prompt source."""

        self.bindings.set_plain_text(text)

    def set_source_text(self, text: str) -> None:
        """Replace the full exact prompt source."""

        self.bindings.set_source_text(text)

    def replace_baseline_text(self, text: str, *, exact_source: bool = False) -> None:
        """Replace restored source and establish a new undo baseline."""

        self.bindings.replace_baseline_text(text, exact_source=exact_source)

    def replace_baseline_document(
        self,
        text: str,
        semantics: PromptDocumentSemantics,
    ) -> None:
        """Replace semantics and exact source as one invalidation transaction."""

        semantics_changed = self.bindings.replace_semantics(semantics)
        self.replace_baseline_text(text, exact_source=True)
        if not semantics_changed:
            return
        self.bindings.publish_interaction_semantics_changed()
        self.bindings.publish_diagnostics_semantics_changed()
        self.bindings.publish_lora_source_changed()

    def replace_conditioning_context(
        self,
        conditioning_context: PromptConditioningContext,
    ) -> bool:
        """Replace graph-derived conditioning semantics."""

        return self.bindings.replace_conditioning_context(conditioning_context)

    def replace_document_text(self, text: str) -> None:
        """Replace document text through one grouped edit."""

        self.bindings.replace_document_text(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace text using one already prepared semantic snapshot."""

        self.bindings.replace_document_text_with_prompt_state(
            text,
            document_view=document_view,
            render_plan=render_plan,
        )


def build_prompt_editor_document_facade(
    semantics: PromptDocumentSemanticsController,
    source_commands: PromptSourceCommandService[PromptProjectionUndoPayload],
    interaction: PromptInteractionController,
    diagnostics: PromptDiagnosticsFeatureController,
    lora_trigger_words: PromptLoraTriggerWordController,
) -> PromptEditorDocumentFacade:
    """Bind mounted document and dependent feature owners to one facade."""

    return PromptEditorDocumentFacade(
        PromptEditorDocumentBindings(
            set_plain_text=source_commands.set_plain_text,
            set_source_text=source_commands.set_source_text,
            replace_baseline_text=source_commands.replace_baseline_text,
            replace_document_text=source_commands.replace_document_text,
            replace_document_text_with_prompt_state=(
                source_commands.replace_document_text_with_prompt_state
            ),
            replace_semantics=semantics.replace,
            replace_conditioning_context=diagnostics.replace_conditioning_context,
            publish_interaction_semantics_changed=(
                interaction.handle_document_semantics_changed
            ),
            publish_diagnostics_semantics_changed=(
                diagnostics.handle_document_semantics_changed
            ),
            publish_lora_source_changed=lora_trigger_words.handle_source_changed,
        )
    )


__all__ = [
    "PromptEditorDocumentBindings",
    "PromptEditorDocumentFacade",
    "build_prompt_editor_document_facade",
]
