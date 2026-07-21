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

"""Define hostile display-mode, highlight, caret, and selection paint workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseActionKind, PromptAbuseScenario

_UNIT = (
    "masterpiece, (detailed face:1.20), {lighting/day}, "
    "<lora:detail_booster:0.80>, cinematic background, "
)


def display_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact transient-rendering and mode-switch torture scenarios."""

    source = _UNIT * 36
    return (
        _raw_rich_toggle_scenario(source),
        _search_highlight_scenario(source),
        _caret_selection_paint_scenario(source),
    )


def _raw_rich_toggle_scenario(source: str) -> PromptAbuseScenario:
    """Repeatedly toggle exact-source and projected rendering with paints."""

    cursor = len(source) // 2
    actions: list[PromptAbuseAction] = []
    for _cycle in range(12):
        for mode in ("raw", "rich"):
            actions.extend(
                (
                    _stable_action(
                        "display_mode",
                        source,
                        cursor,
                        value=mode,
                    ),
                    _stable_action("request_paint", source, cursor),
                    _stable_action("event_turn", source, cursor),
                )
            )
    return PromptAbuseScenario(
        name="raw-rich-toggle-churn",
        initial_text=source,
        actions=tuple(actions),
        expected_text=source,
        cursor_position=cursor,
        viewport_size=(420, 280),
    )


def _search_highlight_scenario(source: str) -> PromptAbuseScenario:
    """Churn many visible and offscreen search ranges through paint and scroll."""

    cursor = len(source) // 2
    ranges = tuple(
        (index, index + len("masterpiece"))
        for index in _substring_indexes(source, "masterpiece")
    )
    actions: list[PromptAbuseAction] = []
    for active_index, scroll_target in ((0, "top"), (18, "middle"), (35, "bottom")):
        actions.extend(
            (
                PromptAbuseAction(
                    "search_highlights",
                    value="set",
                    source_ranges=ranges,
                    active_index=active_index,
                    expected_source=source,
                    expected_cursor_position=cursor,
                    expected_anchor_position=cursor,
                ),
                _stable_action("scroll", source, cursor, value=scroll_target),
                _stable_action("request_paint", source, cursor),
                _stable_action("event_turn", source, cursor),
            )
        )
    actions.extend(
        (
            _stable_action(
                "search_highlights",
                source,
                cursor,
                value="clear",
            ),
            _stable_action("request_paint", source, cursor),
            _stable_action("event_turn", source, cursor),
        )
    )
    return PromptAbuseScenario(
        name="search-highlight-scroll-paint",
        initial_text=source,
        actions=tuple(actions),
        expected_text=source,
        cursor_position=cursor,
        viewport_size=(420, 280),
    )


def _caret_selection_paint_scenario(source: str) -> PromptAbuseScenario:
    """Paint collapsed and directional selections across decorated syntax."""

    start = source.index("detailed face", len(source) // 3)
    end = source.index("cinematic background", start) + len("cinematic background")
    actions = (
        _stable_action("request_paint", source, start),
        _stable_action("event_turn", source, start),
        PromptAbuseAction(
            "select",
            position=start,
            selection_end=end,
            expected_source=source,
            expected_cursor_position=end,
            expected_anchor_position=start,
        ),
        _stable_action(
            "request_paint",
            source,
            end,
            anchor_position=start,
        ),
        _stable_action("event_turn", source, end, anchor_position=start),
        PromptAbuseAction(
            "move_cursor",
            position=end,
            expected_source=source,
            expected_cursor_position=end,
            expected_anchor_position=end,
        ),
        _stable_action("request_paint", source, end),
        _stable_action("event_turn", source, end),
    )
    return PromptAbuseScenario(
        name="caret-selection-repaint",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=start,
        viewport_size=(420, 280),
    )


def _stable_action(
    kind: PromptAbuseActionKind,
    source: str,
    cursor_position: int,
    *,
    anchor_position: int | None = None,
    value: str = "",
) -> PromptAbuseAction:
    """Return one non-source-mutating action with exact cursor state."""

    return PromptAbuseAction(
        kind,
        value=value,
        expected_source=source,
        expected_cursor_position=cursor_position,
        expected_anchor_position=(
            cursor_position if anchor_position is None else anchor_position
        ),
    )


def _substring_indexes(source: str, needle: str) -> tuple[int, ...]:
    """Return all non-overlapping source indexes for one search term."""

    indexes: list[int] = []
    start = 0
    while True:
        index = source.find(needle, start)
        if index < 0:
            return tuple(indexes)
        indexes.append(index)
        start = index + len(needle)


__all__ = ["display_scenarios"]
