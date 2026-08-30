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

"""Verify pure Output navigation selection and activation planning."""

from __future__ import annotations


from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_policy import (
    OutputCanvasNavigationPolicy,
)


from tests.presentation.canvas.output.navigation.controller_support import (
    build_output_item,
    build_source,
    build_scene,
)


def test_source_fallback_item_prefers_exact_last_real_set() -> None:
    """Source fallback should preserve the user's exact concrete set when present."""

    first_item = build_output_item(set_index=1)
    exact_item = build_output_item(set_index=3)
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={1: first_item, 3: exact_item},
    )

    item = OutputCanvasNavigationPolicy.source_fallback_item(
        {"source-a": source},
        "source-a",
        last_real_set_index=3,
    )

    assert item is exact_item


def test_source_fallback_item_returns_none_for_unknown_source() -> None:
    """Missing sources should not produce a fallback activation item."""

    item = OutputCanvasNavigationPolicy.source_fallback_item(
        {},
        "missing-source",
        last_real_set_index=2,
    )

    assert item is None


def test_tab_change_action_ignores_suppressed_signal() -> None:
    """Suppressed tabbar changes should not trigger navigation work."""

    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=True,
        active_set_index=1,
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1,))},
    )

    assert action.kind == "none"
    assert action.source_key == "wf:text"
    assert action.item is None


def test_tab_change_action_activates_grid_for_grid_set() -> None:
    """Grid mode tab changes should keep source-grid activation when available."""

    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=False,
        active_set_index=0,
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_grid"
    assert action.source_key == "wf:text"


def test_tab_change_action_preserves_grid_for_single_image_source() -> None:
    """Grid mode tab changes should preserve hierarchy for a one-tile source."""

    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=False,
        active_set_index=0,
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1,))},
    )

    assert action.kind == "activate_grid"
    assert action.source_key == "wf:text"


def test_tab_change_action_returns_concrete_output_item() -> None:
    """Concrete set tab changes should resolve the selected source item."""

    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=False,
        active_set_index=2,
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_output_item"
    assert action.source_key == "wf:text"
    assert action.item is not None
    assert action.item.set_index == 2


def test_tab_change_action_rejects_missing_batch_within_selected_source() -> None:
    """Source tab changes must not substitute another batch for a missing one."""

    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key="wf:upscale",
        suppress_tab_change=False,
        active_set_index=2,
        source_groups_by_key={
            "wf:upscale": build_source("wf:upscale", set_indexes=(1,))
        },
    )

    assert action.kind == "missing_set"
    assert action.source_key == "wf:upscale"
    assert action.item is None


def test_tab_change_action_reports_unknown_source() -> None:
    """Concrete set tab changes should report unknown routes for widget logging."""

    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key="missing",
        suppress_tab_change=False,
        active_set_index=1,
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1,))},
    )

    assert action.kind == "unknown_source"
    assert action.source_key == "missing"
    assert action.item is None


def test_scene_selection_action_activates_scene_overview_for_all() -> None:
    """The All scene picker row should request scene-overview activation."""

    action = OutputCanvasNavigationPolicy.scene_selection_action("all")

    assert action.kind == "activate_scene_overview"
    assert action.scene_key == "all"


def test_scene_selection_action_activates_concrete_scene() -> None:
    """Concrete scene picker rows should request scoped scene activation."""

    action = OutputCanvasNavigationPolicy.scene_selection_action("portrait")

    assert action.kind == "activate_scene"
    assert action.scene_key == "portrait"


def test_set_selection_action_activates_grid_set() -> None:
    """Set index zero should request source-grid activation for the active source."""

    action = OutputCanvasNavigationPolicy.set_selection_action(
        set_index=0,
        active_source_key="wf:text",
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_grid"
    assert action.source_key == "wf:text"
    assert action.item is None


def test_set_selection_action_returns_active_source_item() -> None:
    """Concrete set selection should prefer the active source when available."""

    action = OutputCanvasNavigationPolicy.set_selection_action(
        set_index=2,
        active_source_key="wf:text",
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_output_item"
    assert action.source_key == "wf:text"
    assert action.item is not None
    assert action.item.set_index == 2


def test_set_selection_action_rejects_a_set_missing_from_active_source() -> None:
    """Concrete set selection must not switch CubeOutput sources implicitly."""

    action = OutputCanvasNavigationPolicy.set_selection_action(
        set_index=2,
        active_source_key="missing",
        source_groups_by_key={
            "wf:text": build_source("wf:text", set_indexes=(1,)),
            "wf:upscale": build_source("wf:upscale", set_indexes=(2,)),
        },
    )

    assert action.kind == "missing_set"
    assert action.source_key == "missing"
    assert action.item is None


def test_set_selection_action_returns_none_without_target() -> None:
    """Missing set targets should not ask the widget to mutate visible state."""

    action = OutputCanvasNavigationPolicy.set_selection_action(
        set_index=3,
        active_source_key="wf:text",
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=())},
    )

    assert action.kind == "missing_set"
    assert action.source_key == "wf:text"
    assert action.item is None


def test_scene_activation_plan_returns_none_for_unknown_scene() -> None:
    """Unknown scene activation should not ask the widget to mutate visible state."""

    plan = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key="missing",
        scene_groups_by_key={},
        was_scene_overview=False,
        active_source_key="wf:text",
    )

    assert plan is None


def test_scene_activation_plan_prefers_representative_from_overview() -> None:
    """Leaving overview should prefer the scene representative source."""

    plan = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key="portrait",
        scene_groups_by_key={
            "portrait": build_scene(
                "portrait",
                sources=(
                    build_source("wf:text", set_indexes=(1,)),
                    build_source("wf:upscale", set_indexes=(1, 2)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        was_scene_overview=True,
        active_source_key="wf:text",
    )

    assert plan is not None
    assert plan.scene_key == "portrait"
    assert plan.active_source_key == "wf:upscale"
    assert plan.set_count == 2
    assert plan.followup == "activate_grid"


def test_scene_activation_plan_uses_batch_grid_before_single_representative() -> None:
    """Scene entry must not skip a sibling batch grid for a terminal single output."""

    plan = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key="portrait",
        scene_groups_by_key={
            "portrait": build_scene(
                "portrait",
                sources=(
                    build_source("wf:text", set_indexes=(1, 2, 3)),
                    build_source("wf:upscale", set_indexes=(1,)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        was_scene_overview=True,
        active_source_key=None,
    )

    assert plan is not None
    assert plan.scene_key == "portrait"
    assert plan.active_source_key == "wf:text"
    assert plan.set_count == 3
    assert plan.followup == "activate_grid"


def test_scene_activation_plan_preserves_previous_source_when_possible() -> None:
    """Scene activation should preserve the active source outside overview."""

    plan = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key="portrait",
        scene_groups_by_key={
            "portrait": build_scene(
                "portrait",
                sources=(
                    build_source("wf:text", set_indexes=(1,)),
                    build_source("wf:upscale", set_indexes=(1,)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        was_scene_overview=False,
        active_source_key="wf:text",
    )

    assert plan is not None
    assert plan.active_source_key == "wf:text"
    assert plan.set_count == 1
    assert plan.followup == "activate_grid"


def test_scene_activation_plan_reports_no_followup_without_sources() -> None:
    """Empty scenes should activate without requesting source follow-up."""

    plan = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key="empty",
        scene_groups_by_key={"empty": build_scene("empty", sources=())},
        was_scene_overview=False,
        active_source_key=None,
    )

    assert plan is not None
    assert plan.active_source_key is None
    assert plan.set_count == 0
    assert plan.followup == "none"


def test_grid_activation_plan_uses_explicit_grid_source() -> None:
    """Explicit source-grid activation should accept sources with multiple sets."""

    plan = OutputCanvasNavigationPolicy.grid_activation_plan(
        source_key="wf:text",
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1, 2))},
    )

    assert plan is not None
    assert plan.source_key == "wf:text"


def test_grid_activation_plan_uses_first_grid_source_when_missing() -> None:
    """Missing source input should fall back to the first source that can grid."""

    plan = OutputCanvasNavigationPolicy.grid_activation_plan(
        source_key=None,
        source_groups_by_key={
            "wf:text": build_source("wf:text", set_indexes=(1,)),
            "wf:upscale": build_source("wf:upscale", set_indexes=(1, 2)),
        },
    )

    assert plan is not None
    assert plan.source_key == "wf:upscale"


def test_grid_activation_plan_preserves_requested_single_item_source() -> None:
    """Explicit grid selection should preserve the requested one-tile source."""

    plan = OutputCanvasNavigationPolicy.grid_activation_plan(
        source_key="wf:upscale",
        source_groups_by_key={
            "wf:text": build_source("wf:text", set_indexes=(1, 2, 3)),
            "wf:upscale": build_source("wf:upscale", set_indexes=(1,)),
        },
    )

    assert plan is not None
    assert plan.source_key == "wf:upscale"


def test_grid_activation_plan_rejects_unknown_source() -> None:
    """Unknown source-grid activation should not mutate visible state."""

    assert (
        OutputCanvasNavigationPolicy.grid_activation_plan(
            source_key="missing",
            source_groups_by_key={
                "wf:text": build_source("wf:text", set_indexes=(1, 2))
            },
        )
        is None
    )


def test_grid_activation_plan_accepts_single_item_source() -> None:
    """A one-item source can render its batch hierarchy as a one-tile grid."""

    plan = OutputCanvasNavigationPolicy.grid_activation_plan(
        source_key="wf:text",
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1,))},
    )

    assert plan is not None
    assert plan.source_key == "wf:text"


def test_scene_overview_activation_plan_rejects_single_scene() -> None:
    """All-scenes overview should activate only when multiple scenes exist."""

    assert (
        OutputCanvasNavigationPolicy.scene_overview_activation_plan(scene_count=1)
        is None
    )


def test_scene_overview_activation_plan_sets_overview_navigation_state() -> None:
    """All-scenes overview activation should expose the existing overview defaults."""

    plan = OutputCanvasNavigationPolicy.scene_overview_activation_plan(
        scene_count=2,
    )

    assert plan is not None
    assert plan.active_set_index == 1
    assert plan.active_source_key is None
    assert plan.set_count == 0


def test_item_activation_plan_uses_item_identity_and_set() -> None:
    """Concrete output item activation should expose item-derived state."""

    item = build_output_item(set_index=3)

    plan = OutputCanvasNavigationPolicy.item_activation_plan(
        source_key="wf:upscale",
        item=item,
    )

    assert plan.source_key == "wf:upscale"
    assert plan.active_set_index == 3
    assert plan.last_real_set_index == 3
    assert plan.image_id == item.image_id
