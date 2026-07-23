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

"""Validate transient wildcard visuals outside primary timing sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication

from tests.real_shell_prompt_editor_harness import RealShellPromptEditorHarness

from .action_driver import dispatch_action
from .models import PromptAbuseAction, PromptAbuseScenario
from .reorder_action_host import PromptReorderAbuseActionHost
from .wildcard_mount import mount_wildcard_editor


def capture_wildcard_visual_violations(
    scenario: PromptAbuseScenario,
    *,
    artifact_root: Path,
) -> tuple[str, ...]:
    """Replay selected visuals and return stable zebra/preview violations."""

    if scenario.name not in {
        "wildcard-alt-zebra-reorder",
        "wildcard-mouse-drag-zebra",
    }:
        return ()
    violations: list[str] = []
    with mount_wildcard_editor(scenario, artifact_root=artifact_root) as mounted:
        host = PromptReorderAbuseActionHost()
        for action_index, action in enumerate(scenario.actions):
            dispatch_action(
                host,
                mounted.editor,
                mounted.editor,
                action,
                action_index=action_index,
            )
            if _is_visual_checkpoint(scenario, action_index, action):
                _capture_visual_checkpoint(
                    mounted.editor,
                    scenario=scenario,
                    action_index=action_index,
                    action=action,
                    violations=violations,
                )
    return tuple(dict.fromkeys(violations))


def _is_visual_checkpoint(
    scenario: PromptAbuseScenario,
    action_index: int,
    action: PromptAbuseAction,
) -> bool:
    """Return whether one unmeasured replay action needs rendered evidence."""

    if scenario.name == "wildcard-alt-zebra-reorder":
        return action_index in {1, 6}
    return bool(
        action_index == 1
        or action.kind
        in {"reorder_drag_press", "reorder_drag_threshold", "reorder_drag_release"}
        or (
            action.kind == "reorder_drag_move"
            and action.value in {"0.500000", "1.000000"}
        )
    )


def _capture_visual_checkpoint(
    editor: object,
    *,
    scenario: PromptAbuseScenario,
    action_index: int,
    action: PromptAbuseAction,
    violations: list[str],
) -> None:
    """Assert zebra chrome and preview state from a rendered owner snapshot."""

    preview_expected = _preview_expected(scenario, action_index, action)
    if preview_expected:
        _wait_for_preview(editor)
    probe = RealShellPromptEditorHarness.capture_source_line_chrome_render_probe(
        cast(Any, editor),
        label=f"{scenario.name}-action-{action_index}",
    )
    colors = dict(probe.line_colors)
    if not probe.reorder_overlay_active:
        violations.append(f"wildcard_alt_overlay_inactive_at_action_{action_index}")
    if colors.get(1) == colors.get(2):
        violations.append(f"wildcard_zebra_missing_at_action_{action_index}")
    if preview_expected and not probe.projection_preview_active:
        violations.append(f"wildcard_reorder_preview_inactive_at_action_{action_index}")


def _preview_expected(
    scenario: PromptAbuseScenario,
    action_index: int,
    action: PromptAbuseAction,
) -> bool:
    """Return whether the checkpoint must expose a reorder preview."""

    return bool(
        (scenario.name == "wildcard-alt-zebra-reorder" and action_index == 6)
        or (
            scenario.name == "wildcard-mouse-drag-zebra"
            and (
                action.kind == "reorder_drag_release"
                or (
                    action.kind == "reorder_drag_move"
                    and action.value in {"0.500000", "1.000000"}
                )
            )
        )
    )


def _wait_for_preview(editor: object, *, timeout_ms: int = 250) -> None:
    """Drain queued preview work until the production projection becomes current."""

    prompt_editor = cast(Any, editor)
    remaining_ms = timeout_ms
    while (
        prompt_editor._surface._reorder_preview_projection.preview_layout is None
        and remaining_ms > 0
    ):
        loop = QEventLoop()
        interval_ms = min(5, remaining_ms)
        QTimer.singleShot(interval_ms, loop.quit)
        loop.exec()
        remaining_ms -= interval_ms
    QGuiApplication.processEvents()


__all__ = ["capture_wildcard_visual_violations"]
