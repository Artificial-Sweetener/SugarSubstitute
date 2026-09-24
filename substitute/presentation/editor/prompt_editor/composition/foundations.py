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

"""Build foundational prompt-editor services with no feature-state coupling."""

from __future__ import annotations

from substitute.application.prompt_editor.autocomplete.query_service import (
    PromptAutocompleteQueryService,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService

from ..interactions import PromptExternalUrlActionRunner, PromptExternalUrlOpener
from .collaborator_bundle import PromptEditorConstructionInputs


def build_external_url_action_runner(
    open_url: PromptExternalUrlOpener | None,
) -> PromptExternalUrlActionRunner:
    """Build the prompt-editor external URL action runner."""
    return PromptExternalUrlActionRunner(open_url=open_url)


def build_prompt_document_service(
    inputs: PromptEditorConstructionInputs,
) -> PromptDocumentService:
    """Build the shared document-query authority before feature composition."""
    return PromptDocumentService(
        autocomplete_query_service=PromptAutocompleteQueryService(
            document_semantics=inputs.prompt_document_semantics
        ),
        document_semantics=inputs.prompt_document_semantics,
    )
