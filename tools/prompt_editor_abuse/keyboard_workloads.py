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

"""Define hostile clipboard, navigation, selection, and history workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario


def keyboard_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact keyboard editing and long-history scenarios."""

    return (_clipboard_navigation_scenario(), _long_history_scenario())


def _clipboard_navigation_scenario() -> PromptAbuseScenario:
    """Exercise exact line navigation, Shift selection, copy, and cut."""

    source = "alpha beta\ngamma delta\nomega"
    actions = (
        _key("home", source, cursor=0, anchor=0),
        _key("end", source, cursor=28, anchor=28),
        _move_cursor(source, position=16),
        _key("up", source, cursor=5, anchor=5),
        _key("down", source, cursor=16, anchor=16),
        _move_cursor(source, position=11),
        _key("shift_end", source, cursor=28, anchor=11),
        _key("copy", source, cursor=28, anchor=11),
        _key("cut", "alpha beta\n", cursor=11, anchor=11),
        _key("select_all", "alpha beta\n", cursor=11, anchor=0),
        _key("copy", "alpha beta\n", cursor=11, anchor=0),
    )
    return PromptAbuseScenario(
        name="clipboard-navigation-selection",
        initial_text=source,
        actions=actions,
        expected_text="alpha beta\n",
        cursor_position=16,
        viewport_size=(360, 180),
    )


def _long_history_scenario() -> PromptAbuseScenario:
    """Exercise sustained independent paste history followed by undo and redo."""

    actions: list[PromptAbuseAction] = []
    states = [""]
    for index in range(32):
        next_text = states[-1] + f"tag{index}, "
        states.append(next_text)
        actions.append(
            PromptAbuseAction(
                "paste",
                value=f"tag{index}, ",
                expected_source=next_text,
                expected_cursor_position=len(next_text),
                expected_anchor_position=len(next_text),
            )
        )
    for previous_text in reversed(states[:-1]):
        actions.append(
            PromptAbuseAction(
                "key",
                value="undo",
                expected_source=previous_text,
            )
        )
    for next_text in states[1:]:
        actions.append(
            PromptAbuseAction(
                "key",
                value="redo",
                expected_source=next_text,
            )
        )
    actions.append(PromptAbuseAction("drain_events", expected_source=states[-1]))
    return PromptAbuseScenario(
        name="long-undo-redo-history",
        initial_text="",
        actions=tuple(actions),
        expected_text=states[-1],
    )


def _key(
    value: str,
    source: str,
    *,
    cursor: int,
    anchor: int,
) -> PromptAbuseAction:
    """Return one exact keyboard action checkpoint."""

    return PromptAbuseAction(
        "key",
        value=value,
        expected_source=source,
        expected_cursor_position=cursor,
        expected_anchor_position=anchor,
    )


def _move_cursor(source: str, *, position: int) -> PromptAbuseAction:
    """Return one exact source-cursor reset between navigation probes."""

    return PromptAbuseAction(
        "move_cursor",
        position=position,
        expected_source=source,
        expected_cursor_position=position,
        expected_anchor_position=position,
    )


__all__ = ["keyboard_scenarios"]
