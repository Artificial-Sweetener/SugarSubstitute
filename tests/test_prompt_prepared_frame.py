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

"""Verify prepared-frame publication and paint-only validation ownership."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintState,
)
from tests.prompt_projection_layout_test_helpers import projection_layout_for


def test_prepared_frame_reuses_projection_reference_index_for_paint_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep repeated paint-only validation independent of document size."""

    layout, projection = projection_layout_for("(cat:1.05), suffix")
    token_id = projection.tokens[0].token_id
    paint_state = PromptProjectionPaintState(active_token_ids=frozenset((token_id,)))
    original_references_only = PromptProjectionPaintState.references_only
    observed_indexes: list[tuple[frozenset[str], frozenset[str]]] = []

    def record_indexes(
        state: PromptProjectionPaintState,
        *,
        token_ids: frozenset[str],
        run_ids: frozenset[str],
    ) -> bool:
        """Record the immutable indexes supplied by the prepared frame."""

        observed_indexes.append((token_ids, run_ids))
        typed_original: Callable[..., bool] = original_references_only
        return typed_original(state, token_ids=token_ids, run_ids=run_ids)

    monkeypatch.setattr(
        PromptProjectionPaintState,
        "references_only",
        record_indexes,
    )

    assert layout.frame.try_set_paint_state(paint_state)
    assert layout.frame.try_set_paint_state(paint_state)

    assert observed_indexes[0][0] is observed_indexes[1][0]
    assert observed_indexes[0][1] is observed_indexes[1][1]


def test_prepared_frame_reuses_base_text_styles_for_paint_only_updates() -> None:
    """Keep document-wide font and color preparation off paint-state changes."""

    layout, projection = projection_layout_for("(cat:1.05), suffix")
    run_id = projection.runs[0].run_id
    base_styles = layout.frame.paint_input.base_text_styles

    layout.frame.set_paint_state(
        PromptProjectionPaintState(active_run_ids=frozenset((run_id,)))
    )

    assert layout.frame.paint_input.base_text_styles is base_styles
