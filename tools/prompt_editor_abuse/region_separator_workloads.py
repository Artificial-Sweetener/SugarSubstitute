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

"""Define hostile regional-separator prompt-editor workloads."""

from __future__ import annotations

import random

from .models import PromptAbuseAction, PromptAbuseActionKind, PromptAbuseScenario

_REGION_TOKEN = ("region_separator",)
_TWO_REGION_TOKENS = ("region_separator", "region_separator")


def prompt_region_separator_scenarios(
    *,
    seed: int = 7,
) -> tuple[PromptAbuseScenario, ...]:
    """Return deterministic separator editing, navigation, and paint abuse."""

    return (
        _horizontal_atomic_navigation_scenario(),
        _vertical_navigation_scenario(),
        _mouse_placement_scenario(),
        _raw_rich_boundary_scenario(),
        _topology_promotion_scenario(),
        _adjacent_authoring_scenario(),
        _adjacent_partition_population_scenario(),
        _continued_authoring_scenario(),
        _nearby_authoring_scenario(),
        _delete_join_split_scenario(),
        _paste_selection_resize_scenario(),
        _multi_separator_line_break_scenario(),
        _canvas_lifecycle_scenario(),
        _seeded_separator_churn_scenario(seed),
    )


def _horizontal_atomic_navigation_scenario() -> PromptAbuseScenario:
    """Cross each hidden marker in one horizontal key action."""

    source = "alpha\n[SEP]\nbravo\n[SEP]\ncharlie"
    alpha_end = source.index("\n")
    bravo_start = source.index("bravo")
    bravo_end = bravo_start + len("bravo")
    charlie_start = source.index("charlie")
    actions = (
        _key(source, "right", bravo_start, _TWO_REGION_TOKENS),
        _key(source, "left", alpha_end, _TWO_REGION_TOKENS),
        PromptAbuseAction(
            "move_cursor",
            position=bravo_end,
            expected_source=source,
            expected_cursor_position=bravo_end,
            expected_anchor_position=bravo_end,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _key(source, "right", charlie_start, _TWO_REGION_TOKENS),
        _key(source, "left", bravo_end, _TWO_REGION_TOKENS),
        _passive(source, "request_paint", bravo_end, _TWO_REGION_TOKENS),
    )
    return PromptAbuseScenario(
        name="region-separator-horizontal-atomic-navigation",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=alpha_end,
    )


def _raw_rich_boundary_scenario() -> PromptAbuseScenario:
    """Edit literal marker source and repeatedly cross the raw/rich boundary."""

    source = "global\n[SEP]\nregional"
    separator_start = source.index("[SEP]")
    raw_cursor = separator_start + 2
    broken_source = source[:raw_cursor] + "X" + source[raw_cursor:]
    regional_start = source.index("regional")
    actions = (
        PromptAbuseAction(
            "display_mode",
            value="raw",
            expected_source=source,
            expected_cursor_position=separator_start,
            expected_anchor_position=separator_start,
            expected_token_kinds=(),
        ),
        PromptAbuseAction(
            "move_cursor",
            position=raw_cursor,
            expected_source=source,
            expected_cursor_position=raw_cursor,
            expected_anchor_position=raw_cursor,
            expected_token_kinds=(),
        ),
        PromptAbuseAction(
            "type",
            value="X",
            expected_source=broken_source,
            expected_cursor_position=raw_cursor + 1,
            expected_anchor_position=raw_cursor + 1,
            expected_token_kinds=(),
        ),
        _key(source, "undo", raw_cursor, ()),
        PromptAbuseAction(
            "display_mode",
            value="rich",
            expected_source=source,
            expected_cursor_position=separator_start,
            expected_anchor_position=separator_start,
            expected_token_kinds=_REGION_TOKEN,
        ),
        _passive(source, "request_paint", separator_start, _REGION_TOKEN),
        PromptAbuseAction(
            "display_mode",
            value="raw",
            expected_source=source,
            expected_cursor_position=separator_start,
            expected_anchor_position=separator_start,
            expected_token_kinds=(),
        ),
        _passive(source, "request_paint", separator_start, ()),
        PromptAbuseAction(
            "display_mode",
            value="rich",
            expected_source=source,
            expected_cursor_position=separator_start,
            expected_anchor_position=separator_start,
            expected_token_kinds=_REGION_TOKEN,
        ),
        PromptAbuseAction(
            "display_mode",
            value="raw",
            expected_source=source,
            expected_cursor_position=separator_start,
            expected_anchor_position=separator_start,
            expected_token_kinds=(),
        ),
        PromptAbuseAction(
            "move_cursor",
            position=regional_start,
            expected_source=source,
            expected_cursor_position=regional_start,
            expected_anchor_position=regional_start,
            expected_token_kinds=(),
        ),
        PromptAbuseAction(
            "display_mode",
            value="rich",
            expected_source=source,
            expected_cursor_position=regional_start,
            expected_anchor_position=regional_start,
            expected_token_kinds=_REGION_TOKEN,
        ),
        PromptAbuseAction(
            "display_mode",
            value="raw",
            expected_source=source,
            expected_cursor_position=regional_start,
            expected_anchor_position=regional_start,
            expected_token_kinds=(),
        ),
        PromptAbuseAction(
            "display_mode",
            value="rich",
            expected_source=source,
            expected_cursor_position=regional_start,
            expected_anchor_position=regional_start,
            expected_token_kinds=_REGION_TOKEN,
        ),
        _passive(source, "request_paint", regional_start, _REGION_TOKEN),
    )
    return PromptAbuseScenario(
        name="region-separator-raw-rich-boundary",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=separator_start,
    )


def _adjacent_authoring_scenario() -> PromptAbuseScenario:
    """Complete a second nearby separator and retain its empty partition."""

    initial_source = "global\n[SEP]\n[SEPregional"
    completion_position = initial_source.index("regional")
    normalized_source = "global\n[SEP]\n[SEP]\nregional"
    normalized_cursor = normalized_source.index("regional")
    actions = (
        PromptAbuseAction(
            "type",
            value="]",
            expected_source=normalized_source,
            expected_cursor_position=normalized_cursor,
            expected_anchor_position=normalized_cursor,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _passive(
            normalized_source,
            "request_paint",
            normalized_cursor,
            _TWO_REGION_TOKENS,
        ),
        _key(initial_source, "undo", completion_position, _REGION_TOKEN),
        _key(
            normalized_source,
            "redo",
            normalized_cursor,
            _TWO_REGION_TOKENS,
        ),
        _passive(
            normalized_source,
            "drain_events",
            normalized_cursor,
            _TWO_REGION_TOKENS,
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-adjacent-authoring",
        initial_text=initial_source,
        actions=actions,
        expected_text=normalized_source,
        cursor_position=completion_position,
    )


def _continued_authoring_scenario() -> PromptAbuseScenario:
    """Continue typing in the empty region created by a terminal separator."""

    initial_source = "global\n[SEP]\n[SEP"
    normalized_source = "global\n[SEP]\n[SEP]\n"
    regional_source = normalized_source + "jfklasfjal"
    actions = (
        PromptAbuseAction(
            "type",
            value="]",
            expected_source=normalized_source,
            expected_cursor_position=len(normalized_source),
            expected_anchor_position=len(normalized_source),
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "type",
            value="jfklasfjal",
            expected_source=regional_source,
            expected_cursor_position=len(regional_source),
            expected_anchor_position=len(regional_source),
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _passive(
            regional_source,
            "request_paint",
            len(regional_source),
            _TWO_REGION_TOKENS,
        ),
        _passive(
            regional_source,
            "drain_events",
            len(regional_source),
            _TWO_REGION_TOKENS,
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-continued-authoring",
        initial_text=initial_source,
        actions=actions,
        expected_text=regional_source,
        cursor_position=len(initial_source),
    )


def _adjacent_partition_population_scenario() -> PromptAbuseScenario:
    """Populate the editable zero-length region between adjacent dividers."""

    source = "global\n[SEP]\n[SEP]\nregional"
    insertion_position = source.rindex("[SEP]")
    expected_source = "global\n[SEP]\nmiddle\n[SEP]\nregional"
    expected_cursor = len("global\n[SEP]\nmiddle")
    actions: list[PromptAbuseAction] = []
    current_source = source
    current_cursor = insertion_position
    for character_index, character in enumerate("middle"):
        insertion = f"{character}\n" if character_index == 0 else character
        current_source = (
            current_source[:current_cursor]
            + insertion
            + current_source[current_cursor:]
        )
        current_cursor += 1
        actions.append(
            PromptAbuseAction(
                "type",
                value=character,
                expected_source=current_source,
                expected_cursor_position=current_cursor,
                expected_anchor_position=current_cursor,
                expected_token_kinds=_TWO_REGION_TOKENS,
            )
        )
    actions.extend(
        (
            _passive(
                expected_source,
                "request_paint",
                expected_cursor,
                _TWO_REGION_TOKENS,
            ),
            _passive(
                expected_source,
                "drain_events",
                expected_cursor,
                _TWO_REGION_TOKENS,
            ),
        )
    )
    return PromptAbuseScenario(
        name="region-separator-adjacent-partition-population",
        initial_text=source,
        actions=tuple(actions),
        expected_text=expected_source,
        cursor_position=insertion_position,
    )


def _nearby_authoring_scenario() -> PromptAbuseScenario:
    """Create another section from an empty row beside an existing divider."""

    source = "global\n[SEP]\nregion\n[SEP]\n\n tail"
    insertion_position = source.rindex("[SEP]") + len("[SEP]\n")
    normalized_insert = "fasdfsa\n[SEP]"
    partial_insert = "fasdfsa[SEP"
    expected_source = (
        source[:insertion_position] + normalized_insert + source[insertion_position:]
    )
    undone_source = (
        source[:insertion_position] + partial_insert + source[insertion_position:]
    )
    normalized_cursor = insertion_position + len(normalized_insert) + 1
    undone_cursor = insertion_position + len(partial_insert)
    actions = (
        PromptAbuseAction(
            "type",
            value="fasdfsa[SEP]",
            expected_source=expected_source,
            expected_cursor_position=normalized_cursor,
            expected_anchor_position=normalized_cursor,
            expected_token_kinds=(
                "region_separator",
                "region_separator",
                "region_separator",
            ),
        ),
        _passive(
            expected_source,
            "request_paint",
            normalized_cursor,
            (
                "region_separator",
                "region_separator",
                "region_separator",
            ),
        ),
        _key(undone_source, "undo", undone_cursor, _TWO_REGION_TOKENS),
        _key(
            expected_source,
            "redo",
            normalized_cursor,
            (
                "region_separator",
                "region_separator",
                "region_separator",
            ),
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-nearby-authoring",
        initial_text=source,
        actions=actions,
        expected_text=expected_source,
        cursor_position=insertion_position,
    )


def _vertical_navigation_scenario() -> PromptAbuseScenario:
    """Cross two structural rows repeatedly while layout and paint churn."""

    source = "alpha\n[SEP]\nbravo\n[SEP]\ncharlie"
    global_position = source.index("alpha") + 3
    middle_position = source.index("bravo") + 3
    regional_position = source.index("charlie") + 3
    actions: list[PromptAbuseAction] = []
    for _cycle in range(6):
        actions.extend(
            (
                _key(source, "up", global_position, _TWO_REGION_TOKENS),
                _key(source, "down", middle_position, _TWO_REGION_TOKENS),
                _key(source, "down", regional_position, _TWO_REGION_TOKENS),
                _key(source, "up", middle_position, _TWO_REGION_TOKENS),
                _passive(
                    source,
                    "request_paint",
                    middle_position,
                    _TWO_REGION_TOKENS,
                ),
            )
        )
    actions.insert(
        10,
        PromptAbuseAction(
            "resize",
            viewport_size=(280, 220),
            expected_source=source,
            expected_cursor_position=middle_position,
            expected_anchor_position=middle_position,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
    )
    actions.append(
        _passive(
            source,
            "drain_events",
            middle_position,
            _TWO_REGION_TOKENS,
        )
    )
    return PromptAbuseScenario(
        name="region-separator-vertical-navigation",
        initial_text=source,
        actions=tuple(actions),
        expected_text=source,
        cursor_position=middle_position,
        viewport_size=(360, 240),
    )


def _topology_promotion_scenario() -> PromptAbuseScenario:
    """Promote and demote an inline marker through undoable newline edits."""

    inline_source = "global [SEP]\nregional"
    separator_start = len("global ")
    promoted_source = "global \n[SEP]\nregional"
    promoted_cursor = separator_start + 1
    actions = (
        _key(promoted_source, "enter", promoted_cursor, _REGION_TOKEN),
        _passive(
            promoted_source,
            "request_paint",
            promoted_cursor,
            _REGION_TOKEN,
        ),
        _key(inline_source, "undo", separator_start, ()),
        _key(promoted_source, "redo", promoted_cursor, _REGION_TOKEN),
        _key(inline_source, "undo", separator_start, ()),
        _key(promoted_source, "enter", promoted_cursor, _REGION_TOKEN),
        _passive(
            promoted_source,
            "drain_events",
            promoted_cursor,
            _REGION_TOKEN,
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-topology-promotion",
        initial_text=inline_source,
        actions=actions,
        expected_text=promoted_source,
        cursor_position=separator_start,
    )


def _mouse_placement_scenario() -> PromptAbuseScenario:
    """Place and drag the pointer across a separator without hidden endpoints."""

    source = "global\n[SEP]\nregional"
    token_start = source.index("[SEP]")
    token_end = token_start + len("[SEP]")
    regional_start = source.index("regional")
    actions = (
        _mouse_caret(
            source,
            token_start,
            expected_cursor_position=token_start - 1,
            token_kinds=_REGION_TOKEN,
        ),
        _mouse_caret(
            source,
            token_end,
            expected_cursor_position=regional_start,
            token_kinds=_REGION_TOKEN,
        ),
        _mouse_caret(
            source,
            regional_start,
            expected_cursor_position=regional_start,
            token_kinds=_REGION_TOKEN,
        ),
        PromptAbuseAction(
            "mouse_drag_selection",
            position=2,
            selection_end=regional_start + 3,
            expected_source=source,
            expected_cursor_position=regional_start + 3,
            expected_anchor_position=2,
            expected_token_kinds=_REGION_TOKEN,
        ),
        PromptAbuseAction(
            "move_cursor",
            position=regional_start,
            expected_source=source,
            expected_cursor_position=regional_start,
            expected_anchor_position=regional_start,
            expected_token_kinds=_REGION_TOKEN,
        ),
        _passive(source, "request_paint", regional_start, _REGION_TOKEN),
    )
    return PromptAbuseScenario(
        name="region-separator-mouse-placement",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=0,
    )


def _delete_join_split_scenario() -> PromptAbuseScenario:
    """Expose either separator edge and restore its structural source exactly."""

    initial_source = "global\n\n[SEP]\nregional"
    canonical_source = "global\n[SEP]\nregional"
    leading_partial_source = "global\nSEP]\nregional"
    cursor = len("global")
    separator_start = canonical_source.index("[SEP]")
    actions = (
        _key(canonical_source, "delete", cursor, _REGION_TOKEN),
        _key(canonical_source, "escape", cursor, _REGION_TOKEN),
        _key(leading_partial_source, "delete", separator_start, ()),
        _key(canonical_source, "undo", cursor, _REGION_TOKEN),
        _key(initial_source, "undo", cursor, _REGION_TOKEN),
        _passive(
            initial_source,
            "request_paint",
            cursor,
            _REGION_TOKEN,
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-delete-join-split",
        initial_text=initial_source,
        actions=actions,
        expected_text=initial_source,
        cursor_position=cursor,
    )


def _paste_selection_resize_scenario() -> PromptAbuseScenario:
    """Paste, undo, redo, reflow, paint, and replace one of two separators."""

    initial_source = "base"
    pasted_text = "\n[SEP]\nred\n[SEP]\nblue"
    regional_source = initial_source + pasted_text
    first_separator_start = regional_source.index("[SEP]")
    first_separator_end = first_separator_start + len("[SEP]")
    replaced_source = (
        regional_source[:first_separator_start]
        + "X"
        + regional_source[first_separator_end:]
    )
    actions = (
        PromptAbuseAction(
            "paste",
            value=pasted_text,
            expected_source=regional_source,
            expected_cursor_position=len(regional_source),
            expected_anchor_position=len(regional_source),
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _key(initial_source, "undo", len(initial_source), ()),
        _key(
            regional_source,
            "redo",
            len(regional_source),
            _TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "resize",
            viewport_size=(190, 180),
            expected_source=regional_source,
            expected_cursor_position=len(regional_source),
            expected_anchor_position=len(regional_source),
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _passive(
            regional_source,
            "request_paint",
            len(regional_source),
            _TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "select",
            position=first_separator_start,
            selection_end=first_separator_end,
            expected_source=regional_source,
            expected_cursor_position=first_separator_end,
            expected_anchor_position=first_separator_start,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "paste",
            value="X",
            expected_source=replaced_source,
            expected_cursor_position=first_separator_start + 1,
            expected_anchor_position=first_separator_start + 1,
            expected_token_kinds=_REGION_TOKEN,
        ),
        _passive(
            replaced_source,
            "drain_events",
            first_separator_start + 1,
            _REGION_TOKEN,
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-paste-selection-resize",
        initial_text=initial_source,
        actions=actions,
        expected_text=replaced_source,
        cursor_position=len(initial_source),
        viewport_size=(320, 220),
    )


def _multi_separator_line_break_scenario() -> PromptAbuseScenario:
    """Preserve both separators while adding blank lines around exact user input."""

    source = (
        "testbest quality, score_7, masterpiece, very aesthetic\n\n"
        "2girls, standing, full body, looking at viewer, outdoors, cherry blossoms, "
        "school uniform \n"
        "[SEP]\n"
        "1girl, red hair, long hair, green eyes, smile, blazer, pleated skirt, "
        "black thighhighs \n\n\n"
        "[SEP]\n"
        "1girl, blue hair, short hair, blue eyes, serious, cardigan, pleated skirt, "
        "kneehighs\n"
    )
    first_separator = source.index("[SEP]")
    after_first_separator = first_separator + len("[SEP]\n")
    first_edit = source[:after_first_separator] + "\n" + source[after_first_separator:]
    second_separator = first_edit.rindex("[SEP]")
    second_edit = first_edit[:second_separator] + "\n" + first_edit[second_separator:]
    actions = (
        _key(
            first_edit,
            "enter",
            after_first_separator + 1,
            _TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "resize",
            viewport_size=(250, 210),
            expected_source=first_edit,
            expected_cursor_position=after_first_separator + 1,
            expected_anchor_position=after_first_separator + 1,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _passive(
            first_edit,
            "request_paint",
            after_first_separator + 1,
            _TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "move_cursor",
            position=second_separator,
            expected_source=first_edit,
            expected_cursor_position=second_separator,
            expected_anchor_position=second_separator,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _key(
            second_edit,
            "enter",
            second_separator + 1,
            _TWO_REGION_TOKENS,
        ),
        _passive(
            second_edit,
            "drain_events",
            second_separator + 1,
            _TWO_REGION_TOKENS,
        ),
    )
    return PromptAbuseScenario(
        name="region-separator-multi-line-break",
        initial_text=source,
        actions=actions,
        expected_text=second_edit,
        cursor_position=after_first_separator,
        viewport_size=(420, 260),
    )


def _seeded_separator_churn_scenario(seed: int) -> PromptAbuseScenario:
    """Mix every source-neutral separator interaction reproducibly."""

    rng = random.Random(seed)
    source = "alpha\n[SEP]\nbravo\n[SEP]\ncharlie"
    global_position = source.index("alpha") + 3
    middle_position = source.index("bravo") + 3
    regional_position = source.index("charlie") + 3
    first_separator_start = source.index("[SEP]")
    alpha_end = source.index("\n")
    bravo_start = source.index("bravo")
    actions: list[PromptAbuseAction] = [
        PromptAbuseAction(
            "move_cursor",
            position=alpha_end,
            expected_source=source,
            expected_cursor_position=alpha_end,
            expected_anchor_position=alpha_end,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _key(source, "right", bravo_start, _TWO_REGION_TOKENS),
        _key(source, "left", alpha_end, _TWO_REGION_TOKENS),
        PromptAbuseAction(
            "mouse_drag_selection",
            position=global_position,
            selection_end=regional_position,
            expected_source=source,
            expected_cursor_position=regional_position,
            expected_anchor_position=global_position,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "move_cursor",
            position=middle_position,
            expected_source=source,
            expected_cursor_position=middle_position,
            expected_anchor_position=middle_position,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "display_mode",
            value="raw",
            expected_source=source,
            expected_cursor_position=middle_position,
            expected_anchor_position=middle_position,
            expected_token_kinds=(),
        ),
        _passive(source, "request_paint", middle_position, ()),
        PromptAbuseAction(
            "display_mode",
            value="rich",
            expected_source=source,
            expected_cursor_position=middle_position,
            expected_anchor_position=middle_position,
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        PromptAbuseAction(
            "paste",
            value="[SE",
            expected_source=(
                source[:middle_position] + "[SE" + source[middle_position:]
            ),
            expected_cursor_position=middle_position + len("[SE"),
            expected_anchor_position=middle_position + len("[SE"),
            expected_token_kinds=_TWO_REGION_TOKENS,
        ),
        _key(source, "undo", middle_position, _TWO_REGION_TOKENS),
        PromptAbuseAction(
            "paste",
            value="[SEP]",
            expected_source=(
                source[:middle_position] + "\n[SEP]\n" + source[middle_position:]
            ),
            expected_cursor_position=middle_position + len("\n[SEP]\n"),
            expected_anchor_position=middle_position + len("\n[SEP]\n"),
            expected_token_kinds=(
                "region_separator",
                "region_separator",
                "region_separator",
            ),
        ),
        _key(source, "undo", middle_position, _TWO_REGION_TOKENS),
        PromptAbuseAction(
            "paste",
            value="\n[SEP]\nnoise",
            expected_source=(
                source[:middle_position] + "\n[SEP]\nnoise" + source[middle_position:]
            ),
            expected_cursor_position=middle_position + len("\n[SEP]\nnoise"),
            expected_anchor_position=middle_position + len("\n[SEP]\nnoise"),
            expected_token_kinds=(
                "region_separator",
                "region_separator",
                "region_separator",
            ),
        ),
        _key(source, "undo", middle_position, _TWO_REGION_TOKENS),
    ]
    for _step in range(32):
        operation = rng.choice(
            (
                "vertical",
                "horizontal",
                "mouse",
                "drag",
                "mode",
                "resize",
                "paint",
                "drain",
            )
        )
        if operation == "vertical":
            direction = rng.choice(("up", "down"))
            target = global_position if direction == "up" else regional_position
            actions.append(_key(source, direction, target, _TWO_REGION_TOKENS))
            actions.append(
                _key(
                    source,
                    "down" if direction == "up" else "up",
                    middle_position,
                    _TWO_REGION_TOKENS,
                )
            )
        elif operation == "horizontal":
            actions.extend(
                (
                    PromptAbuseAction(
                        "move_cursor",
                        position=alpha_end,
                        expected_source=source,
                        expected_cursor_position=alpha_end,
                        expected_anchor_position=alpha_end,
                        expected_token_kinds=_TWO_REGION_TOKENS,
                    ),
                    _key(source, "right", bravo_start, _TWO_REGION_TOKENS),
                    _key(source, "left", alpha_end, _TWO_REGION_TOKENS),
                    PromptAbuseAction(
                        "move_cursor",
                        position=middle_position,
                        expected_source=source,
                        expected_cursor_position=middle_position,
                        expected_anchor_position=middle_position,
                        expected_token_kinds=_TWO_REGION_TOKENS,
                    ),
                )
            )
        elif operation == "mouse":
            actions.append(
                _mouse_caret(
                    source,
                    first_separator_start,
                    expected_cursor_position=first_separator_start - 1,
                    token_kinds=_TWO_REGION_TOKENS,
                )
            )
            actions.append(
                PromptAbuseAction(
                    "move_cursor",
                    position=middle_position,
                    expected_source=source,
                    expected_cursor_position=middle_position,
                    expected_anchor_position=middle_position,
                    expected_token_kinds=_TWO_REGION_TOKENS,
                )
            )
        elif operation == "drag":
            actions.extend(
                (
                    PromptAbuseAction(
                        "mouse_drag_selection",
                        position=global_position,
                        selection_end=regional_position,
                        expected_source=source,
                        expected_cursor_position=regional_position,
                        expected_anchor_position=global_position,
                        expected_token_kinds=_TWO_REGION_TOKENS,
                    ),
                    PromptAbuseAction(
                        "move_cursor",
                        position=middle_position,
                        expected_source=source,
                        expected_cursor_position=middle_position,
                        expected_anchor_position=middle_position,
                        expected_token_kinds=_TWO_REGION_TOKENS,
                    ),
                )
            )
        elif operation == "mode":
            actions.extend(
                (
                    PromptAbuseAction(
                        "display_mode",
                        value="raw",
                        expected_source=source,
                        expected_cursor_position=middle_position,
                        expected_anchor_position=middle_position,
                        expected_token_kinds=(),
                    ),
                    _passive(source, "request_paint", middle_position, ()),
                    PromptAbuseAction(
                        "display_mode",
                        value="rich",
                        expected_source=source,
                        expected_cursor_position=middle_position,
                        expected_anchor_position=middle_position,
                        expected_token_kinds=_TWO_REGION_TOKENS,
                    ),
                )
            )
        elif operation == "resize":
            actions.append(
                PromptAbuseAction(
                    "resize",
                    viewport_size=(
                        rng.choice((180, 280, 420, 760)),
                        rng.choice((160, 240, 360)),
                    ),
                    expected_source=source,
                    expected_cursor_position=middle_position,
                    expected_anchor_position=middle_position,
                    expected_token_kinds=_TWO_REGION_TOKENS,
                )
            )
        else:
            actions.append(
                _passive(
                    source,
                    "request_paint" if operation == "paint" else "drain_events",
                    middle_position,
                    _TWO_REGION_TOKENS,
                )
            )
    return PromptAbuseScenario(
        name="region-separator-seeded-churn",
        initial_text=source,
        actions=tuple(actions),
        expected_text=source,
        cursor_position=middle_position,
        viewport_size=(360, 240),
        seed=seed,
    )


def _canvas_lifecycle_scenario() -> PromptAbuseScenario:
    """Exercise canvas and workflow switches with prepared regional chrome."""

    regional_line = (
        "regional prompt content, detailed lighting, layered background, "
        "character pose, "
    )
    source = "global prompt\n[SEP]\n" + regional_line * 24
    cursor = source.index("regional") + 4
    actions = (
        PromptAbuseAction(
            "resize",
            viewport_size=(300, 220),
            expected_source=source,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
            expected_token_kinds=_REGION_TOKEN,
        ),
        PromptAbuseAction(
            "scroll",
            value="bottom",
            expected_source=source,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
            expected_token_kinds=_REGION_TOKEN,
        ),
        _passive(source, "canvas_round_trip", cursor, _REGION_TOKEN),
        _passive(source, "workflow_round_trip", cursor, _REGION_TOKEN),
        _passive(source, "focus_cycle", cursor, _REGION_TOKEN),
        _passive(source, "request_paint", cursor, _REGION_TOKEN),
        _passive(source, "drain_events", cursor, _REGION_TOKEN),
    )
    return PromptAbuseScenario(
        name="region-separator-canvas-lifecycle",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=cursor,
        viewport_size=(420, 260),
    )


def _key(
    source: str,
    key: str,
    cursor_position: int,
    token_kinds: tuple[str, ...],
) -> PromptAbuseAction:
    """Return one exact key checkpoint for regional-separator abuse."""

    return PromptAbuseAction(
        "key",
        value=key,
        expected_source=source,
        expected_cursor_position=cursor_position,
        expected_anchor_position=cursor_position,
        expected_token_kinds=token_kinds,
    )


def _passive(
    source: str,
    kind: PromptAbuseActionKind,
    cursor_position: int,
    token_kinds: tuple[str, ...],
) -> PromptAbuseAction:
    """Return one source-neutral regional-separator checkpoint."""

    return PromptAbuseAction(
        kind,
        expected_source=source,
        expected_cursor_position=cursor_position,
        expected_anchor_position=cursor_position,
        expected_token_kinds=token_kinds,
    )


def _mouse_caret(
    source: str,
    position: int,
    *,
    expected_cursor_position: int,
    token_kinds: tuple[str, ...],
) -> PromptAbuseAction:
    """Return one exact pointer-placement checkpoint."""

    return PromptAbuseAction(
        "mouse_caret",
        position=position,
        expected_source=source,
        expected_cursor_position=expected_cursor_position,
        expected_anchor_position=expected_cursor_position,
        expected_token_kinds=token_kinds,
    )


__all__ = ["prompt_region_separator_scenarios"]
