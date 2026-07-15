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

"""Build prompt semantic refresh snapshots away from presentation widgets."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)


@dataclass(frozen=True, slots=True)
class PromptSemanticRefreshResult:
    """Carry a prepared semantic prompt snapshot from background execution."""

    document_view: PromptDocumentView
    render_plan: PromptSyntaxRenderPlan


def build_semantic_refresh_result(
    *,
    source_text: str,
    document_service: PromptDocumentService,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
) -> PromptSemanticRefreshResult:
    """Build one document view and render plan for semantic refresh publication."""

    document_view = document_service.build_document_view(source_text)
    render_plan = syntax_service.build_render_plan(document_view, syntax_profile)
    return PromptSemanticRefreshResult(
        document_view=document_view,
        render_plan=render_plan,
    )


__all__ = [
    "PromptSemanticRefreshResult",
    "build_semantic_refresh_result",
]
