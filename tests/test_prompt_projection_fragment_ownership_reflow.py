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

"""Test canonical prompt reflow ownership edits."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.projection.fragment_ownership_reflow import (
    PromptProjectionReflowEdit,
    reflow_edit_including_fragment_identity_changes,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
)


def test_reflow_edit_preserves_unchanged_fragment_owner_prefix() -> None:
    """Keep the requested edit when earlier run ownership is unchanged."""

    previous = _document("alpha beta", run_id="plain")
    projection = _document("alpha Xbeta", run_id="plain")

    edit = reflow_edit_including_fragment_identity_changes(
        previous,
        projection,
        start=6,
        end=6,
        replacement_text="X",
    )

    assert edit == PromptProjectionReflowEdit(6, 6, "X")


def test_reflow_edit_widens_equivalently_over_changed_fragment_owner() -> None:
    """Rebind an earlier changed owner without changing the source delta."""

    previous = _document("alpha beta", run_id="optimistic")
    projection = _document("alpha Xbeta", run_id="canonical")

    edit = reflow_edit_including_fragment_identity_changes(
        previous,
        projection,
        start=6,
        end=6,
        replacement_text="X",
    )

    assert edit == PromptProjectionReflowEdit(0, 6, "alpha X")
    assert len(edit.replacement_text) - (edit.end - edit.start) == 1


def _document(text: str, *, run_id: str) -> PromptProjectionDocument:
    """Return one internally consistent plain-text projection document."""

    run = PromptProjectionRun(
        run_id=run_id,
        kind=PromptProjectionRunKind.TEXT,
        source_start=0,
        source_end=len(text),
        display_text=text,
        source_positions=range(len(text) + 1),
        projection_start=0,
        projection_end=len(text),
    )
    return PromptProjectionDocument(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        source_text=text,
        projection_text=text,
        runs=(run,),
        tokens=(),
        mapping=PromptProjectionMapping(
            runs=(run,),
            source_length=len(text),
            projection_length=len(text),
        ),
        caret_map=PromptProjectionCaretMap(
            stops=tuple(
                PromptProjectionCaretStop(
                    visual_index=index,
                    projection_position=index,
                    state=PromptProjectionCaretState(
                        source_position=index,
                        placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                        run_id=run_id,
                    ),
                )
                for index in range(len(text) + 1)
            ),
            tokens=(),
            source_length=len(text),
            projection_length=len(text),
        ),
    )
