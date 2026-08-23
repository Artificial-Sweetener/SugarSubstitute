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

"""Verify Output navigation source-tab identity, rebuild, and tooltips."""

from __future__ import annotations


from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    SourceTabTooltip,
    SourceTabItem,
    SourceTabTooltipRefreshItem,
    SourceTabsRebuildPlan,
    source_tab_items,
    source_tab_removal_keys,
    source_tab_signature,
    source_tab_tooltip,
    source_tab_tooltip_refresh_items,
    source_tabs_rebuild_plan,
)


from tests.presentation.canvas.output.navigation.bar_support import (
    build_bar_image_item,
)


def test_source_tab_signature_uses_source_keys_and_labels() -> None:
    """Source-tab signatures should track only tab identity values."""

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert source_tab_signature(sources) == (
        ("wf:text", "Text"),
        ("wf:upscale", "Upscale"),
    )


def test_source_tab_signature_preserves_order() -> None:
    """Source-tab signatures should preserve visible source order."""

    sources = (
        OutputCanvasSourceGroup("wf:second", "Second", {}),
        OutputCanvasSourceGroup("wf:first", "First", {}),
    )

    assert source_tab_signature(sources) == (
        ("wf:second", "Second"),
        ("wf:first", "First"),
    )


def test_source_tabs_rebuild_plan_rebuilds_for_changed_signature() -> None:
    """Source-tab rebuild plans should request rebuilds for changed identities."""

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert source_tabs_rebuild_plan(
        sources,
        cached_signature=(("wf:text", "Text"),),
        active_source_key="wf:upscale",
    ) == SourceTabsRebuildPlan(
        signature=(("wf:text", "Text"), ("wf:upscale", "Upscale")),
        rebuild_required=True,
        active_source_key="wf:upscale",
    )


def test_source_tabs_rebuild_plan_skips_matching_signature() -> None:
    """Source-tab rebuild plans should preserve cached tabbar identities."""

    sources = (OutputCanvasSourceGroup("wf:text", "Text", {}),)

    assert source_tabs_rebuild_plan(
        sources,
        cached_signature=(("wf:text", "Text"),),
        active_source_key=None,
    ) == SourceTabsRebuildPlan(
        signature=(("wf:text", "Text"),),
        rebuild_required=False,
        active_source_key=None,
    )


def test_source_tab_items_preserve_visible_source_order() -> None:
    """Source-tab item plans should preserve tab ids, labels, and source DTOs."""

    text_source = OutputCanvasSourceGroup("wf:text", "Text", {})
    upscale_source = OutputCanvasSourceGroup("wf:upscale", "Upscale", {})

    assert source_tab_items((text_source, upscale_source)) == (
        SourceTabItem("wf:text", "Text", text_source),
        SourceTabItem("wf:upscale", "Upscale", upscale_source),
    )


def test_source_tab_removal_keys_preserve_existing_tab_order() -> None:
    """Source-tab removal plans should snapshot existing tab keys in order."""

    assert source_tab_removal_keys(
        {
            "wf:text": object(),
            "wf:upscale": object(),
            "wf:detail": object(),
        }
    ) == ("wf:text", "wf:upscale", "wf:detail")


def test_source_tab_tooltip_uses_active_set_metadata() -> None:
    """Source-tab tooltip plans should use the selected set's metadata."""

    source = OutputCanvasSourceGroup(
        "wf:text",
        "Text",
        {
            1: build_bar_image_item(
                width=512, height=512, duration_ms=1.0, set_index=1
            ),
            3: build_bar_image_item(
                width=1024, height=768, duration_ms=3080.0, set_index=3
            ),
        },
    )

    assert source_tab_tooltip(source, active_set_index=3) == SourceTabTooltip(
        source_key="wf:text",
        text="1024x768\n3.1s",
        installs_hover_filter=True,
    )


def test_source_tab_tooltip_skips_hover_filter_without_display_text() -> None:
    """Source-tab tooltip plans should avoid hover filters without useful text."""

    source = OutputCanvasSourceGroup(
        "wf:text",
        "Text",
        {
            1: build_bar_image_item(
                width=None, height=None, duration_ms=None, set_index=1
            )
        },
    )

    assert source_tab_tooltip(source, active_set_index=1) == SourceTabTooltip(
        source_key="wf:text",
        text="",
        installs_hover_filter=False,
    )


def test_source_tab_tooltip_refresh_items_skip_missing_tabs() -> None:
    """Source-tab tooltip refresh plans should include only existing tab widgets."""

    text_source = OutputCanvasSourceGroup("wf:text", "Text", {})
    upscale_source = OutputCanvasSourceGroup("wf:upscale", "Upscale", {})
    text_tab = object()

    assert source_tab_tooltip_refresh_items(
        (text_source, upscale_source),
        {"wf:text": text_tab},
    ) == (
        SourceTabTooltipRefreshItem(
            source_key="wf:text",
            source=text_source,
            tab_item=text_tab,
        ),
    )
