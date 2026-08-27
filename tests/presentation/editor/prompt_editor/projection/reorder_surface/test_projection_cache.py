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

"""Verify reorder projection-cache identity and invalidation."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from tests.presentation.editor.prompt_editor.projection.reorder_surface.support import (
    _build_reorder_preview_state,
)
from tests.support.prompt_editor.projection_surface_support import (
    install_lora_wildcard_prompt_state,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
)


def test_projection_surface_reuses_stable_reorder_projections(
    widgets: list[QWidget],
) -> None:
    """Stable preview and base-drag projections should not rebuild repeatedly."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    assert preview_state.base_drag_snapshot is not None

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    after_first_set = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    after_second_set = surface.reorder_geometry_cache_counters()

    assert after_first_set["projection_snapshot_rebuild_count"] == 2
    assert after_second_set["projection_snapshot_rebuild_count"] == 2
    assert after_second_set["preview_projection_active_cache_hit_count"] == 1


def test_projection_surface_reorder_projection_context_includes_active_target_identity(
    widgets: list[QWidget],
) -> None:
    """Surface delegation should pass preview target identity into service cache keys."""

    surface = new_projection_surface()
    widgets.append(surface)
    install_lora_wildcard_prompt_state(surface, "alpha, beta, gamma")
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    changed_target_state = replace(
        preview_state,
        active_drop_target_identity=("line", 0, 2),
    )

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    before_changed_target = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(changed_target_state)
    after_changed_target = surface.reorder_geometry_cache_counters()

    assert cast(int, after_changed_target["projection_snapshot_rebuild_count"]) == (
        cast(int, before_changed_target["projection_snapshot_rebuild_count"]) + 1
    )


def test_projection_surface_reuses_reorder_preview_projection_lru_for_revisited_targets(
    widgets: list[QWidget],
) -> None:
    """Revisited preview targets should reuse cached projection layouts."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    assert preview_state_a.base_drag_snapshot is not None
    assert preview_state_b.base_drag_snapshot is not None

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    before_revisit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    after_revisit = surface.reorder_geometry_cache_counters()

    assert before_revisit["projection_snapshot_rebuild_count"] == 3
    assert after_revisit["projection_snapshot_rebuild_count"] == 3
    assert after_revisit["preview_projection_lru_cache_hit_count"] == 1


def test_projection_surface_reorder_preview_projection_lru_invalidates_on_clear(
    widgets: list[QWidget],
) -> None:
    """Clearing reorder preview state should discard cached preview layouts."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    surface.clear_reorder_preview_state()
    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    counters = surface.reorder_geometry_cache_counters()

    assert counters["projection_snapshot_rebuild_count"] == 2
    assert counters["preview_projection_cache_miss_count"] == 1


def test_projection_surface_reorder_preview_projection_lru_survives_scroll_geometry_clear(
    widgets: list[QWidget],
) -> None:
    """Scroll-only geometry invalidation should keep preview projection entries."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    surface.refresh_scroll()
    before_revisit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    after_revisit = surface.reorder_geometry_cache_counters()

    assert (
        after_revisit["projection_snapshot_rebuild_count"]
        == before_revisit["projection_snapshot_rebuild_count"]
    )
    assert cast(int, after_revisit["preview_projection_lru_cache_hit_count"]) == (
        cast(int, before_revisit["preview_projection_lru_cache_hit_count"]) + 1
    )


def test_projection_surface_reorder_preview_projection_lru_invalidates_on_display_mode_change(
    widgets: list[QWidget],
) -> None:
    """Display-mode changes should discard cached preview projection layouts."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    surface.set_display_mode(PromptProjectionDisplayMode.RAW)
    before_revisit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    after_revisit = surface.reorder_geometry_cache_counters()

    assert cast(int, after_revisit["projection_snapshot_rebuild_count"]) == (
        cast(int, before_revisit["projection_snapshot_rebuild_count"]) + 1
    )
