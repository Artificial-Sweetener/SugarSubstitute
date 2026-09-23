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

"""Test syntax render-plan cache ownership."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.projection.syntax_cache import (
    PromptSyntaxRenderPlanCache,
)


def test_syntax_render_plan_cache_requires_a_positive_limit() -> None:
    """Reject cache configurations that cannot retain a completed plan."""

    with pytest.raises(ValueError, match="must be positive"):
        PromptSyntaxRenderPlanCache(limit=0)


def test_syntax_render_plan_cache_evicts_the_oldest_plan_at_its_capacity() -> None:
    """Bound render-plan reuse without retaining the oldest projected prompt."""

    render_plan_cache = PromptSyntaxRenderPlanCache()
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        cast(PromptWildcardCatalogGateway, object()),
        render_plan_cache=render_plan_cache,
    )
    syntax_profile = PromptSyntaxProfileService().build_profile(
        {"prompt_syntaxes": ["emphasis"]}
    )
    first_plan = syntax_service.build_render_plan(
        document_service.build_document_view("render cache 0"),
        syntax_profile,
    )

    for index in range(render_plan_cache.limit):
        syntax_service.build_render_plan(
            document_service.build_document_view(f"render cache {index + 1}"),
            syntax_profile,
        )

    assert render_plan_cache.size == render_plan_cache.limit
    assert all(
        render_plan is not first_plan for render_plan in render_plan_cache.values()
    )
