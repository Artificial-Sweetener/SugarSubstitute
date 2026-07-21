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

"""Prove prompt text remains present in actual backing-store frames."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from .action_driver import dispatch_action
from .backing_store_capture import capture_editor_backing_store
from .models import PromptAbuseAction, PromptAbuseScenario
from .owner_state import capture_prompt_editor_owner_state
from .projection_frame_diff import missing_projection_text_tiles
from .real_shell_mount import (
    create_prompt_abuse_real_shell_harness,
    prepare_prompt_abuse_real_shell_mount,
)


def capture_prompt_text_visual_violations(
    scenario: PromptAbuseScenario,
    *,
    repetition: int,
    artifact_root: Path,
) -> tuple[str, ...]:
    """Replay one prompt persistently and reject any missing visible text chunk."""

    if scenario.editor_kind != "prompt":
        return ()
    harness = create_prompt_abuse_real_shell_harness(
        scenario,
        artifact_root=artifact_root,
    )
    violations: list[str] = []
    try:
        mounted = prepare_prompt_abuse_real_shell_mount(
            harness,
            scenario,
            alias=f"text-visual-{scenario.name}-{repetition}",
        )
        editor = mounted.field.editor
        violations.extend(
            _capture_checkpoint_violations(
                editor,
                scenario=scenario,
                checkpoint="baseline",
                artifact_root=artifact_root,
            )
        )
        for action_index, action in enumerate(scenario.actions):
            units = _visual_dispatch_units(action)
            for visual_unit_index, unit in enumerate(units):
                dispatch_action(
                    mounted.action_host,
                    editor,
                    mounted.target,
                    unit,
                    action_index=action_index,
                )
                checkpoint = f"a{action_index}-u{visual_unit_index}-{action.kind}"
                violations.extend(
                    _capture_checkpoint_violations(
                        editor,
                        scenario=scenario,
                        checkpoint=checkpoint,
                        artifact_root=artifact_root,
                    )
                )
    finally:
        harness.close()
    return tuple(dict.fromkeys(violations))


def _visual_dispatch_units(action: PromptAbuseAction) -> tuple[PromptAbuseAction, ...]:
    """Split typing into independently painted characters; retain other actions."""

    if action.kind != "type" or len(action.value) <= 1:
        return (action,)
    return tuple(
        replace(
            action,
            value=character,
            expected_source=None,
            expected_cursor_position=None,
            expected_anchor_position=None,
        )
        for character in action.value
    )


def _capture_checkpoint_violations(
    editor: object,
    *,
    scenario: PromptAbuseScenario,
    checkpoint: str,
    artifact_root: Path,
) -> tuple[str, ...]:
    """Capture one user-visible frame and return exact missing-text evidence."""

    prompt_editor = cast(Any, editor)
    owner_state = capture_prompt_editor_owner_state(prompt_editor)
    violations: list[str] = []
    if owner_state.layout_fragment_ownership_valid is False:
        violations.append(
            f"layout_fragment_owner_invalid:{checkpoint}:"
            f"{owner_state.layout_fragment_ownership_mismatch}"
        )
    for phase, event_cycles in (("immediate", 0), ("settled-turn", 1)):
        image = capture_editor_backing_store(
            prompt_editor,
            event_cycles=event_cycles,
        )
        if image is None:
            violations.append(f"backing_store_capture_unavailable:{checkpoint}:{phase}")
            continue
        if prompt_editor._segment_overlay is not None:
            continue
        missing_tiles = missing_projection_text_tiles(prompt_editor, image)
        if not missing_tiles:
            continue
        violations.append(
            f"backing_store_text_missing:{checkpoint}:{phase}:"
            f"tiles={missing_tiles[:12]!r}"
        )
        failure_path = artifact_root / (
            f"{scenario.name}-repetition-{checkpoint}-{phase}-text-missing.png"
        )
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(failure_path))
    return tuple(violations)


__all__ = ["capture_prompt_text_visual_violations"]
