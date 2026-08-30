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

"""Verify exact history geometry through its focused strategy owner."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.layout.checkpoints import (
    capture_layout_checkpoint,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    PromptProjectionFreshnessBlockers,
)
from substitute.presentation.editor.prompt_editor.projection.history_checkpoint_strategy import (
    PromptHistoryCheckpointStrategy,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for,
    projection_layout_for,
)


def _blockers(
    *,
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    reorder: bool = False,
    autocomplete: bool = False,
    exact_weight: bool = False,
    expanded_source: bool = False,
) -> PromptProjectionFreshnessBlockers:
    """Return explicit checkpoint eligibility state."""

    return PromptProjectionFreshnessBlockers(
        display_mode=display_mode,
        reorder_preview_active=reorder,
        autocomplete_preview_active=autocomplete,
        exact_weight_edit_active=exact_weight,
        expanded_source_range_active=expanded_source,
    )


def test_history_checkpoint_strategy_restores_matching_prepared_frame() -> None:
    """Restore shared immutable geometry without invoking canonical layout."""

    initial_text = "alpha, (beta:1.20), gamma"
    layout, initial_projection = projection_layout_for(initial_text)
    paint_input = layout.frame.paint_input
    checkpoint = capture_layout_checkpoint(
        layout.frame.output,
        palette_key=int(paint_input.palette.cacheKey()),
        semantic_palette=paint_input.semantic_palette,
    )
    assert checkpoint is not None
    next_document_view, next_projection = projection_document_for(
        "alpha, inserted, (beta:1.20), gamma"
    )
    layout.set_projection(next_projection, prompt_document_view=next_document_view)

    restored = PromptHistoryCheckpointStrategy(layout).try_restore(
        checkpoint,
        blockers=_blockers(),
        expected_source_text=initial_text,
    )

    assert restored is initial_projection
    assert layout.frame.output.projection_document is initial_projection
    assert layout.frame.output.snapshot is checkpoint.snapshot


@pytest.mark.parametrize(
    "blockers",
    (
        _blockers(display_mode=PromptProjectionDisplayMode.RAW),
        _blockers(reorder=True),
        _blockers(autocomplete=True),
        _blockers(exact_weight=True),
        _blockers(expanded_source=True),
    ),
)
def test_history_checkpoint_strategy_rejects_transient_projection_modes(
    blockers: PromptProjectionFreshnessBlockers,
) -> None:
    """Do not replace geometry owned by an active transient projection mode."""

    layout, _projection = projection_layout_for("alpha")
    paint_input = layout.frame.paint_input
    checkpoint = capture_layout_checkpoint(
        layout.frame.output,
        palette_key=int(paint_input.palette.cacheKey()),
        semantic_palette=paint_input.semantic_palette,
    )
    assert checkpoint is not None

    assert (
        PromptHistoryCheckpointStrategy(layout).try_restore(
            checkpoint,
            blockers=blockers,
            expected_source_text="alpha",
        )
        is None
    )


def test_history_checkpoint_strategy_rejects_source_or_geometry_mismatch() -> None:
    """Reject stale source identity and width-dependent checkpoint geometry."""

    layout, _projection = projection_layout_for("alpha", text_width=180.0)
    paint_input = layout.frame.paint_input
    checkpoint = capture_layout_checkpoint(
        layout.frame.output,
        palette_key=int(paint_input.palette.cacheKey()),
        semantic_palette=paint_input.semantic_palette,
    )
    assert checkpoint is not None
    strategy = PromptHistoryCheckpointStrategy(layout)

    assert (
        strategy.try_restore(
            checkpoint,
            blockers=_blockers(),
            expected_source_text="beta",
        )
        is None
    )
    layout.set_text_width(240.0)
    assert (
        strategy.try_restore(
            checkpoint,
            blockers=_blockers(),
            expected_source_text="alpha",
        )
        is None
    )
