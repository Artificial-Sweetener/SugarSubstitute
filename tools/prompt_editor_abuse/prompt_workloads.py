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

"""Define hostile production prompt-editor workloads."""

from __future__ import annotations

import random

from substitute.application.prompt_editor import PromptDocumentService

from .models import PromptAbuseScenario
from .reorder_workloads import prompt_reorder_scenarios
from .scenario_builder import PromptAbuseScenarioBuilder
from .workload_constants import KEY_SLAM, PUNCTUATION_SLAM


def prompt_scenarios(*, seed: int = 7) -> tuple[PromptAbuseScenario, ...]:
    """Return hostile typing, editing, lifecycle, and layout workloads."""

    decorated_unit = (
        "masterpiece, (detailed face:1.20), {lighting/day}, "
        "<lora:detail_booster:0.80>, cinematic background, "
    )
    long_prompt = decorated_unit * 90
    scene_prompt = "\n".join(
        (
            decorated_unit * 18,
            "**Portrait",
            decorated_unit * 18,
            "**Landscape",
            decorated_unit * 18,
        )
    )
    scenarios = [
        _typing_scenario("empty-key-slam", "", KEY_SLAM, 0),
        _typing_scenario("long-decorated-start", long_prompt, KEY_SLAM, 0),
        _typing_scenario(
            "long-decorated-middle",
            long_prompt,
            PUNCTUATION_SLAM,
            len(long_prompt) // 2,
            viewport_size=(420, 300),
        ),
        _typing_scenario(
            "long-decorated-end",
            long_prompt,
            KEY_SLAM,
            len(long_prompt),
        ),
        _typing_scenario(
            "scene-heavy-middle",
            scene_prompt,
            KEY_SLAM,
            scene_prompt.index("**Landscape") - 1,
            viewport_size=(430, 320),
        ),
        _typing_scenario(
            "syntax-boundary-slam",
            "alpha, (weighted segment:1.20), omega",
            PUNCTUATION_SLAM,
            len("alpha, (weighted segment"),
        ),
        _destructive_edit_scenario(long_prompt),
        _paste_undo_redo_scenario(long_prompt),
        _scene_creation_scenario(scene_prompt),
        _selection_replacement_scenario(long_prompt),
        _resize_churn_scenario(long_prompt),
        _autocomplete_churn_scenario(long_prompt),
        _lifecycle_scroll_scenario(long_prompt),
        *prompt_reorder_scenarios(),
        _seeded_mixed_scenario(decorated_unit, seed=seed),
    ]
    return tuple(scenarios)


def _lifecycle_scroll_scenario(long_prompt: str) -> PromptAbuseScenario:
    """Return scrolling, focus, workflow, canvas, and post-switch typing abuse."""

    start = len(long_prompt) // 2
    builder = PromptAbuseScenarioBuilder(long_prompt, cursor_position=start)
    builder.passive_action("scroll", value="bottom")
    builder.drain_events()
    builder.passive_action("focus_cycle")
    builder.passive_action("workflow_round_trip")
    builder.passive_action("canvas_round_trip")
    builder.resize(330, 240)
    builder.passive_action("scroll", value="middle")
    builder.drain_events()
    builder.move_cursor(start)
    builder.type_text(KEY_SLAM)
    builder.passive_action("scroll", value="top")
    builder.drain_events()
    return builder.build(
        "lifecycle-scroll-switch-churn",
        long_prompt,
        initial_cursor_position=start,
        viewport_size=(420, 300),
    )


def _seeded_mixed_scenario(
    decorated_unit: str,
    *,
    seed: int,
) -> PromptAbuseScenario:
    """Return reproducible mixed abuse across content, positions, and layout state."""

    rng = random.Random(seed)
    initial_text = (decorated_unit * 24) + "\n**Seeded Scene\n" + (decorated_unit * 24)
    initial_cursor = len(initial_text) // 2
    builder = PromptAbuseScenarioBuilder(initial_text, cursor_position=initial_cursor)
    alphabet = "abcdefghijklmnopqrstuvwxyz     ,,,{}<>:;_-/\\123456789"
    for _step in range(48):
        action = rng.choice(
            (
                "type",
                "type",
                "type",
                "move",
                "backspace",
                "delete",
                "select_replace",
                "paste",
                "newline",
                "resize",
                "drain",
            )
        )
        if action == "type":
            builder.type_text(
                "".join(rng.choice(alphabet) for _index in range(rng.randint(1, 14)))
            )
        elif action == "move":
            plain_start, plain_end = rng.choice(_plain_source_ranges(builder.text))
            builder.move_cursor(rng.randrange(plain_start, plain_end + 1))
        elif action == "backspace":
            builder.move_cursor(_interior_plain_position(builder.text, rng=rng))
            builder.key("backspace")
        elif action == "delete":
            builder.move_cursor(_interior_plain_position(builder.text, rng=rng))
            builder.key("delete")
        elif action == "select_replace":
            plain_start, plain_end = rng.choice(_plain_source_ranges(builder.text))
            start = rng.randrange(plain_start, plain_end + 1)
            end = min(plain_end, start + rng.randint(0, 28))
            builder.select(start, end)
            builder.type_text(
                "".join(rng.choice(alphabet) for _index in range(rng.randint(1, 10)))
            )
        elif action == "paste":
            builder.paste(rng.choice((KEY_SLAM, "alpha, beta\ngamma", "(burst:1.25)")))
        elif action == "newline":
            builder.key("enter")
        elif action == "resize":
            builder.resize(
                rng.choice((280, 420, 760, 980)), rng.choice((220, 320, 480))
            )
        else:
            builder.drain_events()
    builder.drain_events()
    return builder.build(
        "seeded-mixed-abuse",
        initial_text,
        initial_cursor_position=initial_cursor,
        viewport_size=(420, 300),
        seed=seed,
    )


def _plain_source_ranges(source_text: str) -> tuple[tuple[int, int], ...]:
    """Return non-structural source ranges that accept exact projected carets."""

    known_plain_ranges = tuple(
        (index, index + len(needle))
        for needle in ("masterpiece", "cinematic background")
        for index in _substring_indexes(source_text, needle)
    )
    if known_plain_ranges:
        return known_plain_ranges
    syntax_ranges = sorted(
        (span.start, span.end)
        for span in PromptDocumentService()
        .build_document_view(source_text)
        .syntax_spans
        if span.end > span.start
    )
    plain_ranges: list[tuple[int, int]] = []
    cursor = 0
    for syntax_start, syntax_end in syntax_ranges:
        if syntax_start > cursor:
            plain_ranges.append((cursor, syntax_start))
        cursor = max(cursor, syntax_end)
    if cursor < len(source_text):
        plain_ranges.append((cursor, len(source_text)))
    return tuple(plain_ranges or ((0, len(source_text)),))


def _substring_indexes(source_text: str, needle: str) -> tuple[int, ...]:
    """Return every non-overlapping occurrence of one known plain-text value."""

    indexes: list[int] = []
    search_start = 0
    while True:
        index = source_text.find(needle, search_start)
        if index < 0:
            return tuple(indexes)
        indexes.append(index)
        search_start = index + len(needle)


def _interior_plain_position(source_text: str, *, rng: random.Random) -> int:
    """Return a boundary with ordinary source text on both sides."""

    ranges = tuple(
        (start, end)
        for start, end in _plain_source_ranges(source_text)
        if end - start >= 2
    )
    if not ranges:
        return min(1, len(source_text))
    start, end = rng.choice(ranges)
    return rng.randrange(start + 1, end)


def _typing_scenario(
    name: str,
    initial_text: str,
    typed_text: str,
    cursor_position: int,
    *,
    viewport_size: tuple[int, int] = (720, 240),
) -> PromptAbuseScenario:
    """Return one per-character timed typing scenario."""

    builder = PromptAbuseScenarioBuilder(initial_text, cursor_position=cursor_position)
    builder.type_text(typed_text)
    return builder.build(
        name,
        initial_text,
        initial_cursor_position=cursor_position,
        viewport_size=viewport_size,
    )


def _destructive_edit_scenario(long_prompt: str) -> PromptAbuseScenario:
    """Return mixed insertion, backspace, delete, and navigation abuse."""

    start = len(long_prompt) // 2
    builder = PromptAbuseScenarioBuilder(long_prompt, cursor_position=start)
    builder.type_text(KEY_SLAM)
    for _index in range(18):
        builder.key("backspace")
    builder.key("left")
    builder.key("right")
    for _index in range(8):
        builder.key("delete")
    builder.type_text(", more text, spaces   and punctuation")
    return builder.build(
        "mixed-destructive-editing",
        long_prompt,
        initial_cursor_position=start,
        viewport_size=(410, 280),
    )


def _paste_undo_redo_scenario(long_prompt: str) -> PromptAbuseScenario:
    """Return large paste plus undo/redo correctness and timing abuse."""

    start = len(long_prompt) // 3
    payload = "pasted tag, (pasted weight:1.30), {lighting/night}, " * 12
    builder = PromptAbuseScenarioBuilder(long_prompt, cursor_position=start)
    builder.paste(payload)
    pasted_text = builder.text
    builder.key("undo", expected_source=long_prompt)
    builder.key("redo", expected_source=pasted_text)
    builder.drain_events()
    return builder.build(
        "paste-undo-redo",
        long_prompt,
        initial_cursor_position=start,
        viewport_size=(430, 300),
    )


def _scene_creation_scenario(scene_prompt: str) -> PromptAbuseScenario:
    """Return immediate scene-marker and title publication abuse."""

    start = scene_prompt.index("**Landscape")
    builder = PromptAbuseScenarioBuilder(scene_prompt, cursor_position=start)
    builder.key("enter")
    builder.type_text("**Burst Scene")
    builder.key("enter")
    builder.type_text(KEY_SLAM)
    builder.drain_events()
    return builder.build(
        "scene-marker-creation",
        scene_prompt,
        initial_cursor_position=start,
        viewport_size=(430, 320),
    )


def _selection_replacement_scenario(long_prompt: str) -> PromptAbuseScenario:
    """Return cross-token selection replacement and deletion abuse."""

    start = len(long_prompt) // 2
    end = start + len("masterpiece, (detailed face:1.20)")
    builder = PromptAbuseScenarioBuilder(long_prompt, cursor_position=start)
    builder.select(start, end)
    builder.type_text("replacement, (sharp eyes:1.25)")
    replacement_end = builder.cursor_position
    builder.select(replacement_end - len("sharp eyes"), replacement_end)
    builder.key("delete")
    builder.type_text(KEY_SLAM)
    return builder.build(
        "selection-replace-delete",
        long_prompt,
        initial_cursor_position=start,
        viewport_size=(420, 290),
    )


def _resize_churn_scenario(long_prompt: str) -> PromptAbuseScenario:
    """Return edits interleaved with hostile wrapping-width changes."""

    start = len(long_prompt) // 2
    builder = PromptAbuseScenarioBuilder(long_prompt, cursor_position=start)
    builder.resize(260, 220)
    builder.type_text("narrow burst, ")
    builder.resize(980, 360)
    builder.type_text("wide burst, ")
    builder.resize(380, 260)
    builder.type_text(KEY_SLAM)
    return builder.build(
        "resize-wrap-churn",
        long_prompt,
        initial_cursor_position=start,
        viewport_size=(420, 290),
    )


def _autocomplete_churn_scenario(long_prompt: str) -> PromptAbuseScenario:
    """Return debounced autocomplete retarget and dismissal abuse."""

    start = len(long_prompt) // 2
    builder = PromptAbuseScenarioBuilder(long_prompt, cursor_position=start)
    builder.type_text("mas")
    builder.drain_events()
    builder.type_text("terpiece")
    builder.key("escape")
    builder.type_text(", {light")
    builder.drain_events()
    builder.key("escape")
    return builder.build(
        "autocomplete-race-churn",
        long_prompt,
        initial_cursor_position=start,
        viewport_size=(420, 290),
    )


__all__ = ["prompt_scenarios"]
