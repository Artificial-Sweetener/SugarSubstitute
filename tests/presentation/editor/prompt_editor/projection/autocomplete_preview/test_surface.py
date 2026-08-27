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

"""Contracts for active prompt projection autocomplete preview surfaces."""

from __future__ import annotations


from typing import Any, cast

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryState,
)
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_surface_support import (
    StaticPromptLoraCatalog,
    lora_catalog_item_with_banner,
    projection_token_kinds,
)
from tests.support.prompt_editor.projection_surface_support import (  # noqa: F401
    projection_surface_widgets as _projection_surface_widgets,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)


def test_surface_keeps_committed_projection_separate_from_active_preview(
    widgets: list[QWidget],
) -> None:
    """Surface preview state should affect active layout, not committed projection."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, 1g, omega",
        width=180,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len("alpha, 1g"), QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=9,
            suffix_text="irl",
        )
    )
    process_events(app)

    assert surface.projection_document().source_text == "alpha, 1g, omega"
    assert surface.projection_document().projection_text == "alpha, 1g, omega"
    assert surface.active_projection_document().projection_text == (
        "alpha, 1girl, omega"
    )
    assert box.toPlainText() == "alpha, 1g, omega"


def test_lora_autocomplete_accept_materializes_chip_immediately(
    widgets: list[QWidget],
) -> None:
    """Accepting a LoRA completion should publish projection state immediately."""

    app = ensure_qapp()
    prompt_name = r"Pony\Style\[Dave Cheung] Extracurricular ArtistCG Art Style PonyXL"
    host = QWidget()
    host.resize(760, 220)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_syntax_profile=prompt_syntax_profile("lora"),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(prompt_name=prompt_name),)
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setGeometry(20, 20, 700, box.minimumEditorHeight())
    host.show()
    box.show()
    box.setFocus()
    box.setPlainText(r"<lora:Pony\Style\[Dave")
    process_events(app)
    widgets.extend([host, box])

    query = PromptDocumentService().lora_autocomplete_query_at_cursor(
        text=box.toPlainText(),
        cursor_position=len(box.toPlainText()),
        has_selection=False,
    )
    assert query is not None
    query_lifecycle = cast(Any, box)._autocomplete_query_result_lifecycle
    query_lifecycle.refresh_results_for_query_state(
        PromptAutocompleteQueryState(
            source_revision=0,
            source_length=len(box.toPlainText()),
            source_text=box.toPlainText(),
            cursor_position=len(box.toPlainText()),
            has_selection=False,
            lora_query=query,
        )
    )

    cast(Any, box)._autocomplete.accept_lora_selection()

    assert box.toPlainText() == f"<lora:{prompt_name}:1.00>"
    assert PromptProjectionTokenKind.LORA in projection_token_kinds(surface_for(box))
