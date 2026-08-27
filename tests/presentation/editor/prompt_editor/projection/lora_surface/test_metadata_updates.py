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

"""Verify scheduled LoRA metadata refresh and retry behavior."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.autocomplete_support import (
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_surface_support import (
    StaticPromptLoraCatalog,
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
    lora_catalog_item_with_banner,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    set_surface_prompt_state,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
    surface_source_commands,
)


def test_projection_surface_schedules_metadata_only_prompt_state(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged-source metadata refreshes should use the projection scheduler."""

    ensure_qapp()
    text = "<lora:midna:1>"
    surface = new_projection_surface()
    surface.resize(240, 180)
    widgets.append(surface)
    surface_source_commands(surface).set_source_text(text)
    document_view = PromptDocumentService().build_document_view(text)
    syntax_profile = prompt_syntax_profile("lora")
    initial_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    ).build_render_plan(document_view, syntax_profile)
    metadata_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(document_view, syntax_profile)
    set_surface_prompt_state(surface, document_view, initial_render_plan)
    surface.flush_pending_projection_update(reason="test_initial_metadata_state")
    surface.set_cursor_positions(
        cursor_position=len(text),
        anchor_position=len(text),
    )
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    set_surface_prompt_state(surface, document_view, metadata_render_plan)

    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    assert not surface.cursorRect().isNull()
    assert rebuild_count == 1
    assert surface.has_pending_projection_update() is False

    token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert rebuild_count == 1
    assert surface.has_pending_projection_update() is False
    assert token.thumbnail_variants


def test_projection_surface_scheduled_metadata_failure_remains_retryable(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed scheduled metadata applies should not mark the failed plan current."""

    ensure_qapp()
    text = "<lora:midna:1>, tail"
    surface = new_projection_surface()
    surface.resize(240, 180)
    widgets.append(surface)
    surface_source_commands(surface).set_source_text(text)
    document_view = PromptDocumentService().build_document_view(text)
    syntax_profile = prompt_syntax_profile("lora")
    original_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    ).build_render_plan(document_view, syntax_profile)
    metadata_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(document_view, syntax_profile)
    set_surface_prompt_state(surface, document_view, original_render_plan)
    surface.flush_pending_projection_update(reason="test_initial_metadata_state")
    surface.set_cursor_positions(
        cursor_position=len(text),
        anchor_position=len(text),
    )
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_attempts = 0

    def fail_rebuild() -> None:
        """Fail the first scheduled metadata projection apply."""

        nonlocal rebuild_attempts
        rebuild_attempts += 1
        raise RuntimeError("projection rebuild failed")

    monkeypatch.setattr(surface, "_rebuild_projection", fail_rebuild)
    monkeypatch.setattr(
        cast(Any, surface)._edit_pipeline._trailing_strategy,
        "can_apply_prompt_state_insert",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        cast(Any, surface)._prompt_state_applier._strategy,
        "try_incremental",
        lambda **_kwargs: False,
    )

    surface._projection_freshness_controller.schedule_metadata_update(  # noqa: SLF001
        snapshot=surface.editor_state.prepare_semantic(
            document_view,
            metadata_render_plan,
            source_identity=surface.editor_state.source_identity,
        ),
    )

    assert surface.has_pending_projection_update() is True

    flush_projection_update_scheduler(surface)

    assert rebuild_attempts == 1
    assert surface.editor_state.projection_semantic.render_plan == original_render_plan
    assert surface.has_pending_projection_update() is False

    monkeypatch.setattr(surface, "_rebuild_projection", original_rebuild_projection)
    monkeypatch.undo()
    set_surface_prompt_state(surface, document_view, metadata_render_plan)

    flush_projection_update_scheduler(surface)

    assert surface.editor_state.projection_semantic.render_plan == metadata_render_plan
    assert surface.has_pending_projection_update() is False
