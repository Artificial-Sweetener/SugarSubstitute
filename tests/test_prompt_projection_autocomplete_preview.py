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

"""Tests for projection-owned autocomplete ghost text."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionInlinePreview,
    PromptProjectionRunKind,
    PromptProjectionTokenKind,
    PromptProjectionTransientState,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory
from tests.prompt_projection_surface_test_helpers import (
    lora_catalog_item_with_banner,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    projection_token_kinds,
    StaticPromptLoraCatalog,
)

_SKIP_SURFACE_TEST_UNDER_XDIST = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="projection surface tests require non-xdist execution on Windows",
)


def test_builder_inserts_autocomplete_preview_as_non_source_backed_run() -> None:
    """Builder-owned ghost runs should reserve projection text without source text."""

    projection = _build_projection(
        "alpha omega",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=len("alpha "),
                suffix_text="bright ",
            )
        ),
    )

    assert projection.source_text == "alpha omega"
    assert projection.projection_text == "alpha bright omega"
    assert [run.display_text for run in projection.runs] == [
        "alpha ",
        "bright ",
        "omega",
    ]
    ghost_run = projection.runs[1]
    assert ghost_run.ghosted is True
    assert ghost_run.source_backed is False
    assert ghost_run.source_start == len("alpha ")
    assert ghost_run.source_end == len("alpha ")
    assert tuple(ghost_run.source_positions) == (6,) * (len("bright ") + 1)


def test_builder_caret_map_skips_autocomplete_preview_text() -> None:
    """Ghost text should not create editable projection caret positions."""

    projection = _build_projection(
        "omega",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=0,
                suffix_text="bright ",
            )
        ),
    )

    caret_state = projection.caret_map.state_for_source_position(0)
    assert projection.projection_text == "bright omega"
    assert projection.caret_map.projection_position_for_state(caret_state) == 0
    assert not projection.caret_map.has_projection_position(len("bright "))


def test_builder_preserves_downstream_token_runs_after_preview() -> None:
    """Autocomplete preview insertion should not rewrite unrelated token runs."""

    projection = _build_projection(
        "alpha (cat:1.05) omega",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=len("alpha "),
                suffix_text="bright ",
            )
        ),
    )

    assert projection.projection_text == (
        "alpha bright "
        + OBJECT_REPLACEMENT_CHARACTER
        + "cat"
        + OBJECT_REPLACEMENT_CHARACTER
        + " omega"
    )
    assert projection.runs[2].kind is PromptProjectionRunKind.INLINE_OBJECT
    assert projection.runs[2].renderer_key == "emphasis_prefix"


def test_builder_omits_preview_inside_collapsed_token() -> None:
    """Collapsed inline objects should not receive parallel ghost placement."""

    projection = _build_projection(
        r"<lora:Unknown\Thing:0.8>",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=len("<lora:Unknown"),
                suffix_text=r"\Thing",
            )
        ),
    )

    assert projection.projection_text == OBJECT_REPLACEMENT_CHARACTER
    assert all(not run.ghosted for run in projection.runs)


@_SKIP_SURFACE_TEST_UNDER_XDIST
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


@_SKIP_SURFACE_TEST_UNDER_XDIST
def test_lora_autocomplete_accept_materializes_chip_immediately(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
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
    autocomplete = cast(Any, box)._autocomplete
    monkeypatch.setattr(autocomplete, "_present_panel", lambda: None)
    monkeypatch.setattr(
        autocomplete, "_publish_inline_completion_preview", lambda: None
    )
    autocomplete.refresh_for_lora_query(query)

    autocomplete.accept_lora_selection()

    assert box.toPlainText() == f"<lora:{prompt_name}:1.00>"
    assert PromptProjectionTokenKind.LORA in projection_token_kinds(surface_for(box))


def _build_projection(
    text: str,
    *,
    transient_state: PromptProjectionTransientState | None = None,
) -> PromptProjectionDocument:
    """Build a projected document with optional active transient state."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    return PromptProjectionBuilder().build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        transient_state=transient_state,
    )
