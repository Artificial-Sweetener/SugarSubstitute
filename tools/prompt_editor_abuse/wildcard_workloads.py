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

"""Define hostile wildcard TXT, CSV, zebra, and reorder workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder
from .workload_constants import KEY_SLAM


def wildcard_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return the complete hostile wildcard-editor workload matrix."""

    return (
        _wildcard_txt_typing_scenario(),
        _wildcard_scene_error_scenario(),
        _wildcard_csv_typing_scenario(),
        _wildcard_syntax_scenario(),
        _wildcard_duplicate_scope_scenario(),
        _wildcard_scene_help_scenario(),
        _wildcard_alt_zebra_scenario(),
        _wildcard_mouse_drag_scenario(),
        _wildcard_whole_line_cancel_scenario(),
        _wildcard_drag_autoscroll_scenario(),
    )


def _wildcard_txt_typing_scenario() -> PromptAbuseScenario:
    """Return long zebra-value typing abuse in the production wildcard editor."""

    value = "1girl, blonde hair, blue eyes, (portrait:1.15), {lighting/day}"
    source = "\n".join(f"{value}, variation {index}" for index in range(100))
    start = source.index("variation 50")
    builder = PromptAbuseScenarioBuilder(source, cursor_position=start)
    builder.type_text(KEY_SLAM + ", more text, ")
    return builder.build(
        "wildcard-txt-zebra-typing",
        source,
        initial_cursor_position=start,
        viewport_size=(430, 320),
        editor_kind="wildcard_txt",
    )


def _wildcard_scene_error_scenario() -> PromptAbuseScenario:
    """Return literal scene-marker error formation inside wildcard values."""

    source = "1girl, blonde hair, blue eyes\nsmile, red dress"
    builder = PromptAbuseScenarioBuilder(source, cursor_position=len(source))
    builder.key("enter")
    builder.type_text("**Unsupported Scene")
    builder.drain_events()
    return builder.build(
        "wildcard-scene-marker-error",
        source,
        initial_cursor_position=len(source),
        viewport_size=(430, 300),
        editor_kind="wildcard_txt",
    )


def _wildcard_csv_typing_scenario() -> PromptAbuseScenario:
    """Return quoted CSV value editing with prompt syntax and punctuation."""

    rows = [
        '"1girl, blonde hair, (blue eyes:1.20), {lighting/day}"' for _index in range(80)
    ]
    source = "value\n" + "\n".join(rows)
    start = source.index("blue eyes", len(source) // 2)
    builder = PromptAbuseScenarioBuilder(source, cursor_position=start)
    builder.type_text(KEY_SLAM + ", csv punctuation")
    builder.drain_events()
    return builder.build(
        "wildcard-csv-quoted-typing",
        source,
        initial_cursor_position=start,
        viewport_size=(440, 320),
        editor_kind="wildcard_csv",
    )


def _wildcard_syntax_scenario() -> PromptAbuseScenario:
    """Render ordinary prompt syntax inside independent wildcard candidates."""

    source = "(portrait:1.20), {animal}\n<lora:model:1.00>, {animal}"
    actions = (
        PromptAbuseAction(
            "request_paint",
            expected_source=source,
            expected_cursor_position=len(source),
            expected_anchor_position=len(source),
            expected_token_kinds=("emphasis", "wildcard", "lora", "wildcard"),
        ),
        PromptAbuseAction(
            "event_turn",
            expected_source=source,
            expected_cursor_position=len(source),
            expected_anchor_position=len(source),
            expected_token_kinds=("emphasis", "wildcard", "lora", "wildcard"),
        ),
    )
    return PromptAbuseScenario(
        name="wildcard-prompt-syntax",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=len(source),
        viewport_size=(430, 260),
        editor_kind="wildcard_txt",
    )


def _wildcard_duplicate_scope_scenario() -> PromptAbuseScenario:
    """Report duplicates only inside the same complete wildcard candidate."""

    source = "red hair, blue eyes\nred hair, green eyes\nred hair, red hair"
    duplicate_start = source.rindex("red hair")
    expected_diagnostics = (
        ("duplicate_segment", duplicate_start, duplicate_start + len("red hair")),
    )
    actions = (
        PromptAbuseAction(
            "refresh_diagnostics",
            expected_source=source,
            expected_diagnostics=expected_diagnostics,
        ),
        PromptAbuseAction(
            "request_paint",
            expected_source=source,
            expected_diagnostics=expected_diagnostics,
        ),
        PromptAbuseAction(
            "event_turn",
            expected_source=source,
            expected_diagnostics=expected_diagnostics,
        ),
    )
    return PromptAbuseScenario(
        name="wildcard-duplicate-candidate-scope",
        initial_text=source,
        actions=actions,
        expected_text=source,
        viewport_size=(430, 260),
        editor_kind="wildcard_txt",
    )


def _wildcard_scene_help_scenario() -> PromptAbuseScenario:
    """Right-click an unsupported marker and capture its concise explanation."""

    source = "**Scene\nnormal candidate"
    diagnostics = (("unsupported_scene_marker", 0, 2),)
    actions = (
        PromptAbuseAction(
            "refresh_diagnostics",
            expected_source=source,
            expected_diagnostics=diagnostics,
        ),
        PromptAbuseAction(
            "context_menu",
            position=0,
            expected_source=source,
            expected_diagnostics=diagnostics,
            expected_context_labels=("Scenes aren’t supported in wildcard values.",),
        ),
        PromptAbuseAction("event_turn", expected_source=source),
    )
    return PromptAbuseScenario(
        name="wildcard-scene-context-help",
        initial_text=source,
        actions=actions,
        expected_text=source,
        viewport_size=(430, 240),
        editor_kind="wildcard_txt",
    )


def _wildcard_alt_zebra_scenario() -> PromptAbuseScenario:
    """Return Alt preview, zebra rendering, and cross-value reorder abuse."""

    source = "1girl, blonde hair, blue eyes\nsmile, red dress\nhat, outdoors"
    reordered = "1girl, blonde hair\nblue eyes, smile, red dress\nhat, outdoors"
    blue_eyes_cursor = source.index("blue eyes") + 2
    actions = (
        PromptAbuseAction(
            "key_press",
            value="alt",
            expected_source=source,
        ),
        PromptAbuseAction("drain_events", expected_source=source),
        PromptAbuseAction(
            "key_release",
            value="alt",
            expected_source=source,
        ),
        PromptAbuseAction(
            "move_cursor",
            position=blue_eyes_cursor,
            expected_source=source,
            expected_cursor_position=blue_eyes_cursor,
        ),
        PromptAbuseAction(
            "key_press",
            value="alt",
            expected_source=source,
        ),
        PromptAbuseAction(
            "key_chord",
            value="alt+right",
            expected_source=source,
        ),
        PromptAbuseAction("drain_events", expected_source=source),
        PromptAbuseAction(
            "key_release",
            value="alt",
            expected_source=reordered,
        ),
        PromptAbuseAction("drain_events", expected_source=reordered),
    )
    return PromptAbuseScenario(
        name="wildcard-alt-zebra-reorder",
        initial_text=source,
        actions=actions,
        expected_text=reordered,
        cursor_position=0,
        viewport_size=(440, 320),
        editor_kind="wildcard_txt",
    )


def _wildcard_mouse_drag_scenario() -> PromptAbuseScenario:
    """Return sustained production mouse-drag abuse with zebra checkpoints."""

    source = "1girl, blonde hair, blue eyes\nsmile, red dress\nhat, outdoors"
    reordered = "blonde hair, 1girl, blue eyes\nsmile, red dress\nhat, outdoors"
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        PromptAbuseAction("reorder_drag_press", value="1:0", expected_source=source),
        PromptAbuseAction("reorder_drag_threshold", expected_source=source),
        *tuple(
            action
            for step in range(1, 25)
            for action in (
                PromptAbuseAction(
                    "reorder_drag_move",
                    value=f"{step / 24:.6f}",
                    expected_source=source,
                ),
                PromptAbuseAction("event_turn", expected_source=source),
            )
        ),
        PromptAbuseAction("reorder_drag_release", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        PromptAbuseAction(
            "key_release",
            value="alt",
            expected_source=reordered,
        ),
        PromptAbuseAction("drain_events", expected_source=reordered),
    )
    return PromptAbuseScenario(
        name="wildcard-mouse-drag-zebra",
        initial_text=source,
        actions=actions,
        expected_text=reordered,
        cursor_position=0,
        viewport_size=(440, 320),
        editor_kind="wildcard_txt",
    )


def _wildcard_whole_line_cancel_scenario() -> PromptAbuseScenario:
    """Start and cancel a pointer drag on one complete wildcard line."""

    source = "alpha, beta\ncomplete wildcard candidate\ngamma, delta"
    chip_texts = (
        "alpha,",
        "beta,",
        "complete wildcard candidate,",
        "gamma,",
        "delta",
    )
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction(
            "drain_events",
            expected_source=source,
            expected_reorder_chip_texts=chip_texts,
        ),
        PromptAbuseAction(
            "reorder_drag_press",
            value="2:3",
            expected_source=source,
            expected_reorder_chip_texts=chip_texts,
        ),
        PromptAbuseAction(
            "reorder_drag_threshold",
            expected_source=source,
            expected_reorder_chip_texts=chip_texts,
        ),
        PromptAbuseAction("reorder_drag_cancel", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
    )
    return PromptAbuseScenario(
        name="wildcard-whole-line-pointer-cancel",
        initial_text=source,
        actions=actions,
        expected_text=source,
        viewport_size=(430, 260),
        editor_kind="wildcard_txt",
    )


def _wildcard_drag_autoscroll_scenario() -> PromptAbuseScenario:
    """Drive an active wildcard drag into a scroll edge and then cancel it."""

    source = "\n".join(
        f"candidate {index} alpha, candidate {index} beta" for index in range(100)
    )
    actions = (
        PromptAbuseAction("key_press", value="alt", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
        PromptAbuseAction("reorder_drag_press", value="0:4", expected_source=source),
        PromptAbuseAction("reorder_drag_threshold", expected_source=source),
        PromptAbuseAction("reorder_drag_autoscroll", expected_source=source),
        PromptAbuseAction("reorder_drag_cancel", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
    )
    return PromptAbuseScenario(
        name="wildcard-pointer-drag-autoscroll",
        initial_text=source,
        actions=actions,
        expected_text=source,
        viewport_size=(300, 150),
        editor_kind="wildcard_txt",
    )


__all__ = ["wildcard_scenarios"]
