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

"""Build hostile regular-prompt reorder correctness and latency workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario


def prompt_reorder_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return regular-prompt pointer reorder torture scenarios."""

    return (
        _long_decorated_pointer_reorder_scenario(),
        _long_wrapped_cross_line_pointer_reorder_scenario(),
        _max_span_pointer_reorder_preview_scenario(),
        _scene_partition_pointer_reorder_visibility_scenario(),
        _scene_marker_alt_release_retention_scenario(),
        _post_reorder_typing_visibility_scenario(),
    )


def _pointer_drag_actions(
    source: str,
    descriptor: str,
    *,
    progresses: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0),
    drain_after_release: bool = True,
) -> tuple[PromptAbuseAction, ...]:
    """Return one measured pointer drag with optional post-release draining."""

    actions = [
        PromptAbuseAction(
            "reorder_drag_press",
            value=descriptor,
            expected_source=source,
        ),
        PromptAbuseAction("reorder_drag_threshold", expected_source=source),
    ]
    for progress in progresses:
        actions.extend(
            (
                PromptAbuseAction(
                    "reorder_drag_move",
                    value=f"{progress:.6f}",
                    expected_source=source,
                ),
                PromptAbuseAction("event_turn", expected_source=source),
            )
        )
    actions.append(PromptAbuseAction("reorder_drag_release", expected_source=source))
    if drain_after_release:
        actions.append(PromptAbuseAction("drain_events", expected_source=source))
    return tuple(actions)


def _long_decorated_pointer_reorder_scenario() -> PromptAbuseScenario:
    """Reorder a visible tag while a large decorated suffix remains paintable."""

    first_line = (
        "best quality, score_7, masterpiece, very aesthetic, full body, "
        "dramatic angle, dusk"
    )
    suffix = ",\n\n".join(
        (
            "1girl, (wind:2.00), petite, looking away, facing away, mature female, "
            "(leaning on weapon:2.00), (holding staff:1.60), large wooden staff",
            "(wind lift, floating hair, hat lift, skirt lift:3.00), purple petals, "
            "(hand on own hat, ribbon lift:3.00), fighting stance, holding down headwear",
            "pink witch hat, slim, pigeon-toed, falling petals",
            "determined, narrowed eyes, threat, fang, shaded face, white frilled wrist cuffs",
            "(pink and blue:1.05) witch outfit, bare arms, magical girl, blue ribbon trim, "
            "(blue accents:1.10), pink corset, off shoulder, butterfly shaped bows",
            "(blue laces:1.50), blue ribbon, pink short skirt, pink petticoat, pink frills, "
            "blue frills, blue butterfly ornaments, (red:1.10) heart jewel ornaments",
            "pink hair, long hair, twintails, (hair between eyes:1.20)",
            "ribbon-trimmed vertical-striped pink thighhighs, swept bangs, hair ribbon, "
            "pink eyes, (blue:1.35) ribbon, (skin dentation:1.40), (blue:1.15) bow",
            "calf bone, pink nails, cinematic background, dramatic rim light",
            "ornate staff head, sparkling particles, detailed fabric, high contrast",
        )
    )
    source = f"{first_line},\n\n{suffix},"
    reordered_first_line = (
        "score_7, best quality, masterpiece, very aesthetic, full body, "
        "dramatic angle, dusk"
    )
    reordered = f"{reordered_first_line},\n\n{suffix},"
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        *_pointer_drag_actions(source, "1:0", progresses=(0.5, 1.0)),
        PromptAbuseAction("key_release", value="alt", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
        PromptAbuseAction("request_paint", expected_source=reordered),
        PromptAbuseAction("event_turn", expected_source=reordered),
        PromptAbuseAction("scroll", value="bottom", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
        PromptAbuseAction("scroll", value="top", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
    )
    return PromptAbuseScenario(
        name="long-decorated-pointer-reorder-visibility",
        initial_text=source,
        actions=actions,
        expected_text=reordered,
        viewport_size=(960, 780),
    )


def _long_wrapped_cross_line_pointer_reorder_scenario() -> PromptAbuseScenario:
    """Drag one tag across many wrapped rows without losing overlay text."""

    tags = tuple(
        (
            f"(weighted tag {index}:1.{index % 10}0)"
            if index % 6 == 0
            else f"descriptive prompt tag {index}"
        )
        for index in range(120)
    )
    dragged_index = 12
    source = ", ".join(tags)
    reordered_tags = (
        (tags[dragged_index],) + tags[:dragged_index] + tags[dragged_index + 1 :]
    )
    reordered = ", ".join(reordered_tags)
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        *_pointer_drag_actions(source, f"{dragged_index}:0"),
        PromptAbuseAction("key_release", value="alt", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
        PromptAbuseAction("request_paint", expected_source=reordered),
        PromptAbuseAction("event_turn", expected_source=reordered),
        PromptAbuseAction("scroll", value="bottom", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
        PromptAbuseAction("scroll", value="top", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
    )
    return PromptAbuseScenario(
        name="long-wrapped-cross-line-pointer-reorder-visibility",
        initial_text=source,
        actions=actions,
        expected_text=reordered,
        viewport_size=(960, 780),
    )


def _max_span_pointer_reorder_preview_scenario() -> PromptAbuseScenario:
    """Drag the last visible tag to the first row and retain all preview text."""

    paragraph = (
        "best quality, score_7, masterpiece, very aesthetic, full body, dramatic angle, "
        "1girl, (wind:2.00), petite, looking away, facing away, mature female, "
        "(leaning on weapon:2.00), (holding staff:1.60), large wooden staff, "
        "crook mage staff, large crook, (flat chest:2.00), small breasts"
    )
    source = ",\n\n".join(
        f"{paragraph}, paragraph marker {index}, (weighted detail {index}:1.20)"
        for index in range(16)
    )
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        *_pointer_drag_actions(source, "last-visible:0"),
        PromptAbuseAction("key", value="escape", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
    )
    return PromptAbuseScenario(
        name="max-span-pointer-reorder-preview-visibility",
        initial_text=source,
        actions=actions,
        expected_text=source,
        viewport_size=(1120, 860),
    )


def _scene_partition_pointer_reorder_visibility_scenario() -> PromptAbuseScenario:
    """Repeat cross-row drops while ordinary and decorated chip text stays visible."""

    prompt_lines = (
        "best quality, score_7, masterpiece, very aesthetic, full body, dramatic angle, dusk",
        "1girl, (wind:2.00), petite, looking away, facing away, mature female, "
        "(leaning on weapon:2.00), (holding staff:1.60), large wooden staff, "
        "crook mage staff, large crook, (flat chest:2.00), small breasts",
        "(wind lift, floating hair, hat lift, skirt lift:3.00), purple petals, "
        "(hand on own hat, ribbon lift:3.00), fighting stance, holding down headwear",
        "pink witch hat, slim, pigeon-toed, falling petals",
        "determined, narrowed eyes, threat, fang, shaded face, white frilled wrist cuffs",
        "(pink and blue:1.05) witch outfit, bare arms, magical girl, blue ribbon trim, "
        "(blue accents:1.10), zettai ryouiki, pink corset, off shoulder, "
        "butterfly shaped bows, pink boots",
        "(blue laces:1.50), blue ribbon, pink short skirt, pink petticoat, pink frills, "
        "blue frills, blue butterfly ornaments, (red:1.10) heart jewel ornaments, "
        "heart-shaped gem, heart jeweled collar, beautiful orange and purple sunset sky",
        "pink hair, long hair, twintails, (hair between eyes:1.20)",
        "ribbon-trimmed vertical-striped pink thighhighs, swept bangs, hair ribbon, "
        "pink eyes, (blue:1.35) ribbon, (skin dentation:1.40), (blue:1.10) bow, "
        "collarbone, pink nails",
        "blue decorative staff bow ribbon, floating red staff orb",
        "grass, flower field, mountainous horizon, cloudy sky, pink petals, red petals, "
        "blue petals",
    )
    source = ",\n\n".join(prompt_lines) + (
        ",\n\n**scene fikalsfjalk fasjkl fasjfkla\ntest, test test, 1girl, fiksla"
    )
    reordered = (
        source.replace(
            "pink witch hat, slim, pigeon-toed, falling petals",
            "hair ribbon, swept bangs, pink witch hat, slim, pigeon-toed, falling petals",
        )
        .replace("determined, narrowed eyes, threat", "determined, threat")
        .replace(
            "heart-shaped gem, heart jeweled collar, beautiful",
            "heart-shaped gem, heart jeweled collar, narrowed eyes, beautiful",
        )
        .replace(
            "ribbon-trimmed vertical-striped pink thighhighs, swept bangs, hair ribbon, pink eyes",
            "ribbon-trimmed vertical-striped pink thighhighs, pink eyes",
        )
        .replace(
            "test, test test, 1girl, fiksla",
            "test, 1girl, fiksla, test test",
        )
    )
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        *_pointer_drag_actions(source, "66:29", drain_after_release=False),
        *_pointer_drag_actions(source, "65:29", drain_after_release=False),
        *_pointer_drag_actions(source, "34:59", drain_after_release=False),
        *_pointer_drag_actions(source, "85:84", drain_after_release=False),
        *_pointer_drag_actions(source, "86:84", drain_after_release=False),
        PromptAbuseAction("key_release", value="alt", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
        PromptAbuseAction("request_paint", expected_source=reordered),
        PromptAbuseAction("event_turn", expected_source=reordered),
    )
    return PromptAbuseScenario(
        name="scene-partition-pointer-reorder-visibility",
        initial_text=source,
        actions=actions,
        expected_text=reordered,
        viewport_size=(1120, 1050),
    )


def _scene_marker_alt_release_retention_scenario() -> PromptAbuseScenario:
    """Commit repeated pre-scene drags without losing the scene-title projection."""

    source = "alpha, beta, gamma, delta,\n\n**scene marker\nbody, tag"
    reordered = "delta, beta, gamma, alpha, \n\n**scene marker\nbody, tag"
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        *_pointer_drag_actions(
            source, "1:0", progresses=(0.5, 1.0), drain_after_release=False
        ),
        *_pointer_drag_actions(
            source, "2:0", progresses=(0.5, 1.0), drain_after_release=False
        ),
        *_pointer_drag_actions(
            source, "3:1", progresses=(0.5, 1.0), drain_after_release=False
        ),
        PromptAbuseAction("key_release", value="alt", expected_source=reordered),
        PromptAbuseAction("drain_events", expected_source=reordered),
        PromptAbuseAction("request_paint", expected_source=reordered),
        PromptAbuseAction("event_turn", expected_source=reordered),
    )
    return PromptAbuseScenario(
        name="scene-marker-alt-release-retention",
        initial_text=source,
        actions=actions,
        expected_text=reordered,
        viewport_size=(520, 260),
    )


def _post_reorder_typing_visibility_scenario() -> PromptAbuseScenario:
    """Type at distant positions after repeated drags without losing old glyphs."""

    base = _scene_partition_pointer_reorder_visibility_scenario()
    after_reorder = base.expected_text
    suffix = "more text, even more text, (fast:1.20), <lora:detail:0.8>, "
    after_newline = after_reorder + "\n"
    after_suffix = after_newline + suffix
    middle_position = after_suffix.index("1girl") + len("1girl")
    middle_burst = " sfhjaklfhj jasfklaj flaosjufioewjflafiws"
    final_text = (
        after_suffix[:middle_position] + middle_burst + after_suffix[middle_position:]
    )
    actions = base.actions + (
        PromptAbuseAction(
            "move_cursor",
            position=len(after_reorder),
            expected_source=after_reorder,
            expected_cursor_position=len(after_reorder),
        ),
        PromptAbuseAction(
            "key",
            value="enter",
            expected_source=after_newline,
            expected_cursor_position=len(after_newline),
        ),
        PromptAbuseAction(
            "type",
            value=suffix,
            expected_source=after_suffix,
            expected_cursor_position=len(after_suffix),
        ),
        PromptAbuseAction("drain_events", expected_source=after_suffix),
        PromptAbuseAction(
            "move_cursor",
            position=middle_position,
            expected_source=after_suffix,
            expected_cursor_position=middle_position,
        ),
        PromptAbuseAction(
            "type",
            value=middle_burst,
            expected_source=final_text,
            expected_cursor_position=middle_position + len(middle_burst),
        ),
        PromptAbuseAction("drain_events", expected_source=final_text),
        PromptAbuseAction("key_press", value="alt", expected_source=final_text),
        PromptAbuseAction("drain_events", expected_source=final_text),
        PromptAbuseAction("key_release", value="alt", expected_source=final_text),
        PromptAbuseAction("drain_events", expected_source=final_text),
        PromptAbuseAction("request_paint", expected_source=final_text),
        PromptAbuseAction("event_turn", expected_source=final_text),
    )
    return PromptAbuseScenario(
        name="post-reorder-typing-visibility",
        initial_text=base.initial_text,
        actions=actions,
        expected_text=final_text,
        viewport_size=base.viewport_size,
    )


__all__ = ["prompt_reorder_scenarios"]
