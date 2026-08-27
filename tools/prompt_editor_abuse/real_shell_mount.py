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

"""Build identical production real-shell mounts for every abuse replay mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QWidget

from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from tests.support.prompt_editor.real_shell.models import PromptFieldHandle
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)

from .fixture_bundle import build_fixture_bundle
from .fixture_preparation import prepare_prompt_abuse_fixture_state
from .models import PromptAbuseScenario
from .restored_mounts import (
    mount_cached_workspace_prompt,
    mount_image_sugar_script_prompt,
)
from .shell_action_host import RealShellPromptAbuseActionHost


@dataclass(frozen=True, slots=True)
class PromptAbuseRealShellMount:
    """Carry one prepared production field and its concrete action route."""

    field: PromptFieldHandle
    target: QWidget
    action_host: RealShellPromptAbuseActionHost


def create_prompt_abuse_real_shell_harness(
    scenario: PromptAbuseScenario,
    *,
    artifact_root: Path,
) -> PromptEditorRealShellScenario:
    """Create the production shell with the scenario's exact fixture bundle."""

    fixtures = build_fixture_bundle(scenario)
    return PromptEditorRealShellScenario(
        artifact_root=artifact_root,
        observe_owner_calls=False,
        prompt_wildcard_catalog_gateway=fixtures.wildcard_catalog_gateway,
        prompt_lora_catalog_service=fixtures.lora_catalog_service,
        prompt_spellcheck_service=fixtures.spellcheck_service,
        danbooru_url_import_service=fixtures.danbooru_import_service,
        danbooru_wiki_service=fixtures.danbooru_wiki_service,
        prompt_feature_profile=fixtures.feature_profile,
        wheel_adjustment_mode=(
            PromptWheelAdjustmentMode.FOCUS_REQUIRED
            if scenario.wheel_mode == "focus_required"
            else PromptWheelAdjustmentMode.HOVER_DWELL
        ),
    )


def prepare_prompt_abuse_real_shell_mount(
    harness: PromptEditorRealShellScenario,
    scenario: PromptAbuseScenario,
    *,
    alias: str,
) -> PromptAbuseRealShellMount:
    """Mount and prepare one field before measured or instrumented actions."""

    requested_width, requested_height = scenario.viewport_size
    harness.shell.resize(
        max(1040, requested_width * 2 + 100),
        max(760, requested_height + 240),
    )
    harness.wait_for_queued_delivery()
    field = _mount_prompt_field(harness, scenario, alias=alias)
    _apply_requested_editor_panel_width(harness, requested_width=requested_width)
    field.editor.setManualScrollHeight(requested_height)
    harness.wait_for_queued_delivery()
    harness.input.set_source_cursor_position(field, scenario.cursor_position)
    target = harness.input.focus_editor(field)
    prepare_prompt_abuse_fixture_state(harness, field, scenario)
    action_host = RealShellPromptAbuseActionHost(harness, field)
    action_host.prepare_scenario(scenario)
    return PromptAbuseRealShellMount(
        field=field,
        target=target,
        action_host=action_host,
    )


def _mount_prompt_field(
    harness: PromptEditorRealShellScenario,
    scenario: PromptAbuseScenario,
    *,
    alias: str,
) -> PromptFieldHandle:
    """Mount the prompt field through the scenario's requested lifecycle owner."""

    if scenario.mount_source in {"workspace_cache", "workspace_cache_0_19_2"}:
        return mount_cached_workspace_prompt(harness, scenario, alias=alias)
    if scenario.mount_source == "image_sugar_script":
        return mount_image_sugar_script_prompt(harness, scenario, alias=alias)
    return harness.workflows.add_prompt_workflow(
        alias=alias,
        initial_text=scenario.initial_text,
    )


def _apply_requested_editor_panel_width(
    harness: PromptEditorRealShellScenario,
    *,
    requested_width: int,
) -> None:
    """Give the production editor panel enough splitter space for the workload."""

    splitter = harness.shell.splitter
    sizes = list(splitter.sizes())
    details_index = splitter.indexOf(harness.shell.editor_output_container)
    canvas_index = splitter.indexOf(harness.shell.canvas_host_container)
    if details_index < 0 or canvas_index < 0:
        return
    fixed_total = sum(
        size
        for index, size in enumerate(sizes)
        if index not in {details_index, canvas_index}
    )
    transferable_total = max(0, sum(sizes) - fixed_total)
    details_width = min(
        max(1, requested_width + 300),
        max(1, transferable_total - 100),
    )
    sizes[details_index] = details_width
    sizes[canvas_index] = max(100, transferable_total - details_width)
    splitter.setSizes(sizes)


__all__ = [
    "PromptAbuseRealShellMount",
    "create_prompt_abuse_real_shell_harness",
    "prepare_prompt_abuse_real_shell_mount",
]
