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

"""Contract tests for speculative prompt projection incremental edits."""

from __future__ import annotations


import pytest

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import (
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection import (
    plain_text_document_editor,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
)
from substitute.presentation.editor.prompt_editor.projection.plain_text_document_editor import (
    PromptPlainTextDocumentEditor,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.mapping import (
    PromptProjectionMapping,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


from .support import _scene_projection_document


def test_incremental_plain_text_edit_rejects_invalid_projection_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid speculative incremental documents should fall back to full rebuild."""

    previous_text = "abc"
    next_text = "aXbc"
    run = PromptProjectionRun(
        run_id="run-1",
        kind=PromptProjectionRunKind.TEXT,
        source_start=0,
        source_end=len(previous_text),
        display_text=previous_text,
        source_positions=range(0, len(previous_text) + 1),
        projection_start=0,
        projection_end=len(previous_text),
    )
    previous_document = PromptProjectionDocument(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        source_text=previous_text,
        projection_text=previous_text,
        runs=(run,),
        tokens=(),
        mapping=PromptProjectionMapping(
            runs=(run,),
            source_length=len(previous_text),
            projection_length=len(previous_text),
        ),
        caret_map=PromptProjectionCaretMap(
            stops=tuple(
                PromptProjectionCaretStop(
                    visual_index=index,
                    projection_position=index,
                    state=PromptProjectionCaretState(
                        source_position=index,
                        placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                        run_id=run.run_id,
                    ),
                )
                for index in range(len(previous_text) + 1)
            ),
            tokens=(),
            source_length=len(previous_text),
            projection_length=len(previous_text),
        ),
        region_structure=PromptRegionStructureView.empty(len(previous_text)),
    )

    def fail_incremental_apply(
        *args: object, **kwargs: object
    ) -> PromptProjectionDocument:
        """Simulate a speculative document invariant failure."""

        raise ValueError("invalid source boundary count")

    monkeypatch.setattr(
        plain_text_document_editor,
        "apply_plain_text_document_edit",
        fail_incremental_apply,
    )
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=1,
            end=1,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is None
    assert editor.last_rejection_reason == "invalid_incremental_projection_document"


def test_incremental_plain_text_edit_rejects_region_topology_change() -> None:
    """A separator-invalidating newline deletion must use canonical projection."""

    previous_text = "global\n[SEP]\npink witch hat"
    next_text = "global[SEP]\npink witch hat"
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=7,
            replacement_text="",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_scene_projection_document(previous_text),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is None
    assert editor.last_rejection_reason == "region_structure_topology_changed"
