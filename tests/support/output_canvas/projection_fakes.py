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

"""Build Output projection and source-tab test collaborators."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
)


def install_fake_output_compare_presenter(fake: Any) -> None:
    """Install the composed compare presenter expected by widget seams."""

    if not hasattr(fake, "_compare_presenter"):
        fake._compare_presenter = SimpleNamespace(present=lambda **_kwargs: None)


def install_fake_output_source_tabs_controller(output_mod: Any, fake: Any) -> None:
    """Install the composed source-tabs controller expected by widget seams."""

    if hasattr(fake, "_source_tabs_controller"):
        return
    from .host_fakes import install_fake_output_projection_chrome  # noqa: PLC0415

    install_fake_output_projection_chrome(fake)
    if not hasattr(fake, "_source_tab_tooltip_filters"):
        fake._source_tab_tooltip_filters = {}
    if not hasattr(fake, "_source_tab_cache_signature"):
        fake._source_tab_cache_signature = None
    if not hasattr(fake, "_source_tabbar_preferred_width"):
        fake._source_tabbar_preferred_width = 0
    fake._source_tabs_controller = OutputCanvasSourceTabsController(
        visible_sources=lambda: tuple(
            output_mod.visible_output_source_groups_by_key(
                output_mod.output_route_state_snapshot(fake)
            ).values()
        ),
        cached_signature=lambda: getattr(fake, "_source_tab_cache_signature", None),
        set_cached_signature=lambda signature: setattr(
            fake, "_source_tab_cache_signature", signature
        ),
        set_preferred_width=lambda width: setattr(
            fake, "_source_tabbar_preferred_width", width
        ),
        tabbar=lambda: fake.tabbar,
        on_tab_changed=getattr(fake, "_on_tab_changed", lambda _route: None),
        active_set_index=lambda: int(getattr(fake, "active_set_index", 1)),
        tooltip_filters=lambda: fake._source_tab_tooltip_filters,
        measure_preferred_width=lambda: (
            OutputCanvasNavigationController.measure_tabbar_preferred_width(fake.tabbar)
        ),
        sync_source_selector=getattr(
            fake, "_sync_source_selector_button", lambda: None
        ),
        install_tooltip_filter=lambda _tab_item, _parent, _delay: object(),
    )


__all__ = [
    "install_fake_output_compare_presenter",
    "install_fake_output_source_tabs_controller",
]
