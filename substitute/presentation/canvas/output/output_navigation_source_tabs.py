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

"""Plan Output source-tab identity, rebuilds, and tooltip refreshes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSourceGroup,
    output_source_label_text,
)
from substitute.presentation.canvas.output.output_source_tooltip_presenter import (
    source_tab_tooltip_text,
)

SourceTabSignature = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class SourceTabTooltip:
    """Describe the tooltip content and hover behavior for one source tab."""

    source_key: str
    text: str
    installs_hover_filter: bool


@dataclass(frozen=True, slots=True)
class SourceTabsRebuildPlan:
    """Describe whether source tabs need Qt reconstruction."""

    signature: SourceTabSignature
    rebuild_required: bool
    active_source_key: str | None


@dataclass(frozen=True, slots=True)
class SourceTabItem:
    """Describe one source tab to add to the Qt tabbar."""

    source_key: str
    label: str
    source: OutputCanvasSourceGroup


@dataclass(frozen=True, slots=True)
class SourceTabTooltipRefreshItem:
    """Describe one source tab whose tooltip should be refreshed."""

    source_key: str
    source: OutputCanvasSourceGroup
    tab_item: object


def source_tab_signature(
    sources: Iterable[OutputCanvasSourceGroup],
) -> SourceTabSignature:
    """Return stable source-tab identity values for rebuild cache checks."""

    return tuple(
        (source.source_key, render_application_text(output_source_label_text(source)))
        for source in sources
    )


def source_tabs_rebuild_plan(
    sources: Iterable[OutputCanvasSourceGroup],
    *,
    cached_signature: SourceTabSignature | None,
    active_source_key: str | None,
) -> SourceTabsRebuildPlan:
    """Return whether source tabs must be rebuilt from visible source identity."""

    signature = source_tab_signature(sources)
    return SourceTabsRebuildPlan(
        signature=signature,
        rebuild_required=signature != cached_signature,
        active_source_key=active_source_key,
    )


def source_tab_items(
    sources: Iterable[OutputCanvasSourceGroup],
) -> tuple[SourceTabItem, ...]:
    """Return source-tab add instructions in visible source order."""

    return tuple(
        SourceTabItem(
            source_key=source.source_key,
            label=render_application_text(output_source_label_text(source)),
            source=source,
        )
        for source in sources
    )


def source_tab_removal_keys(tab_items: Mapping[str, object]) -> tuple[str, ...]:
    """Return source-tab keys to remove using a stable key snapshot."""

    return tuple(tab_items.keys())


def source_tab_tooltip(
    source: OutputCanvasSourceGroup,
    *,
    active_set_index: int,
) -> SourceTabTooltip:
    """Return the tooltip plan for one source tab."""

    text = source_tab_tooltip_text(source, active_set_index=active_set_index)
    return SourceTabTooltip(
        source_key=source.source_key,
        text=text,
        installs_hover_filter=bool(text),
    )


def source_tab_tooltip_refresh_items(
    sources: Iterable[OutputCanvasSourceGroup],
    tab_items: Mapping[str, object],
) -> tuple[SourceTabTooltipRefreshItem, ...]:
    """Return visible source/tab pairs that can receive refreshed tooltips."""

    return tuple(
        SourceTabTooltipRefreshItem(
            source_key=source.source_key,
            source=source,
            tab_item=tab_item,
        )
        for source in sources
        if (tab_item := tab_items.get(source.source_key)) is not None
    )


__all__ = [
    "SourceTabItem",
    "SourceTabSignature",
    "SourceTabTooltip",
    "SourceTabTooltipRefreshItem",
    "SourceTabsRebuildPlan",
    "source_tab_items",
    "source_tab_removal_keys",
    "source_tab_signature",
    "source_tab_tooltip",
    "source_tab_tooltip_refresh_items",
    "source_tabs_rebuild_plan",
]
