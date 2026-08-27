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

"""Verify incremental prompt projection paths through the real shell."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
import pytest

from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
)
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


@pytest.mark.parametrize(
    ("label", "initial_text", "cursor_position"),
    (
        ("before-scene", "quality\n**Portrait\nstudio", 0),
        ("scene-title-end", "**Portrait\nstudio", len("**Portrait")),
        ("scene-title-next-word", "**Portrait\nstudio", len("**Portrait")),
        (
            "before-later-scene",
            "**Portrait\nstudio\n**Landscape\nfield",
            len("**Portrait\nstudio"),
        ),
        (
            "long-prompt-before-scene",
            f"{'quality, ' * 400}\n**Portrait\nstudio",
            0,
        ),
    ),
    ids=(
        "before-scene",
        "scene-title-end",
        "scene-title-next-word",
        "before-later-scene",
        "long-prompt-before-scene",
    ),
)
def test_real_shell_routine_typing_around_scenes_never_rebuilds_projection(
    real_shell_scenario: PromptEditorRealShellScenario,
    label: str,
    initial_text: str,
    cursor_position: int,
) -> None:
    """Existing scene geometry should remap locally for ordinary source edits."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        alias=f"scene-path-{label}",
        initial_text=initial_text,
    )
    real_shell_scenario.input.set_source_cursor_position(field, cursor_position)

    typed_text = " abc" if label == "scene-title-next-word" else "abc"
    probe = real_shell_scenario.projection_probes.typed_paths(field, typed_text)

    assert probe.canonical_rebuild_count == 0, (
        label,
        probe.apply_paths,
        probe.incremental_rejection_reasons,
        probe.layout_rejection_reasons,
    )
    assert "full_rebuild" not in probe.apply_paths, (label, probe)
    assert probe.source_text == (
        initial_text[:cursor_position] + typed_text + initial_text[cursor_position:]
    )
    if label == "long-prompt-before-scene":
        assert probe.elapsed_ms < 750.0


def test_real_shell_routine_regional_typing_stays_incremental_and_bounded(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Ordinary regional text edits must avoid topology rebuilds and line scans."""

    regional_lines = "\n".join(
        f"regional line {index}, detailed background and lighting"
        for index in range(400)
    )
    initial_text = f"global\n[SEP]\n{regional_lines}"
    cursor_position = initial_text.index("regional line 200") + len("regional line 200")
    field = real_shell_scenario.workflows.add_prompt_workflow(
        alias="regional-incremental-path",
        initial_text=initial_text,
    )
    real_shell_scenario.input.set_source_cursor_position(field, cursor_position)
    before = real_shell_scenario.snapshots.capture(
        field, label="regional-typing-before"
    )

    probe = real_shell_scenario.projection_probes.typed_paths(field, "abc")
    after = real_shell_scenario.snapshots.capture(field, label="regional-typing-after")

    assert probe.canonical_rebuild_count == 0, (
        probe.apply_paths,
        probe.incremental_rejection_reasons,
        probe.layout_rejection_reasons,
    )
    assert "full_rebuild" not in probe.apply_paths
    assert after.layout_line_count > 400
    assert after.region_chrome_visited_line_count < 48
    assert after.region_chrome_visited_line_count * 10 < after.layout_line_count
    assert (
        after.region_chrome_prepare_count - before.region_chrome_prepare_count
        <= len(probe.typed_text)
    )
    assert not snapshot_invariant_violations(after)


def test_real_shell_ordinary_typing_never_prepares_region_chrome(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep separator geometry entirely absent from ordinary typing."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        alias="ordinary-region-chrome-path",
        initial_text="ordinary prompt\nwith several lines",
    )
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(
        field, label="ordinary-typing-before"
    )

    probe = real_shell_scenario.projection_probes.typed_paths(field, "abc")
    after = real_shell_scenario.snapshots.capture(field, label="ordinary-typing-after")

    assert probe.canonical_rebuild_count == 0
    assert before.region_chrome_prepare_count == 0
    assert after.region_chrome_prepare_count == 0
    assert after.region_chrome_visited_line_count == 0
    assert not snapshot_invariant_violations(after)


def test_real_shell_scene_marker_formation_rebuilds_and_projects_immediately(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """A genuine scene-topology transition should take the canonical path."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")

    probe = real_shell_scenario.projection_probes.typed_paths(field, "**S")

    assert probe.canonical_rebuild_count >= 1
    assert "full_rebuild" in probe.apply_paths
    assert probe.scene_titles == ("S",)
    assert probe.projection_text == "S"


def test_real_shell_scene_typing_coalesces_against_live_previous_source(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Deferred scene-document typing must not compare against stale projection text."""

    initial_text = "quality\n**Portrait\nstudio"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial_text)
    surface = cast(Any, field.editor)._surface
    delay_projection_update_scheduler(surface)
    real_shell_scenario.input.set_source_cursor_position(field, 0)

    probe = real_shell_scenario.projection_probes.typed_paths(field, "abc")

    assert probe.canonical_rebuild_count == 0
    assert "full_rebuild" not in probe.apply_paths
    assert probe.source_text == f"abc{initial_text}"
    assert surface.projection_document().source_text == f"abc{initial_text}"


def test_real_shell_scene_deletion_uses_local_path_until_topology_changes(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Scene text deletion should stay local except when it removes the marker."""

    title_field = real_shell_scenario.workflows.add_prompt_workflow(
        alias="scene-title-delete",
        initial_text="**Scene\nbody",
    )
    real_shell_scenario.input.set_source_cursor_position(title_field, len("**Scene"))

    title_probe = real_shell_scenario.projection_probes.key_path(
        title_field,
        key=Qt.Key.Key_Backspace,
        label="backspace",
    )

    assert title_probe.canonical_rebuild_count == 0
    assert title_probe.scene_titles == ("Scen",)
    assert "full_rebuild" not in title_probe.apply_paths

    topology_field = real_shell_scenario.workflows.add_prompt_workflow(
        alias="scene-topology-delete",
        initial_text="**S\nbody",
    )
    real_shell_scenario.input.set_source_cursor_position(topology_field, len("**S"))

    topology_probe = real_shell_scenario.projection_probes.key_path(
        topology_field,
        key=Qt.Key.Key_Backspace,
        label="backspace",
    )

    assert topology_probe.canonical_rebuild_count >= 1
    assert "full_rebuild" in topology_probe.apply_paths
    assert topology_probe.scene_titles == ()
    assert topology_probe.projection_text == "**\nbody"


def test_real_shell_decorated_middle_paste_uses_bounded_canonical_reflow(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """A syntax-bearing paste should rebuild semantics without relaying all layout."""

    initial_text = "alpha, (beta:1.20), gamma, delta"
    pasted_text = "pasted, (weighted:1.30), <lora:model:0.80>, "
    cursor_position = initial_text.index("gamma")
    field = real_shell_scenario.workflows.add_prompt_workflow(
        alias="decorated-middle-paste",
        initial_text=initial_text,
    )
    real_shell_scenario.input.set_source_cursor_position(field, cursor_position)

    probe = real_shell_scenario.projection_probes.paste_paths(field, pasted_text)

    expected_text = (
        initial_text[:cursor_position] + pasted_text + initial_text[cursor_position:]
    )
    assert probe.source_text == expected_text
    assert probe.canonical_rebuild_count == 0
    assert probe.apply_paths == ("reflow",)
    assert probe.projection_text

    undo_probe = real_shell_scenario.projection_probes.undo_paths(field)

    assert undo_probe.source_text == initial_text
    assert undo_probe.canonical_rebuild_count == 0
    assert undo_probe.apply_paths == ("checkpoint_restore",)

    redo_probe = real_shell_scenario.projection_probes.redo_paths(field)

    assert redo_probe.source_text == expected_text
    assert redo_probe.canonical_rebuild_count == 0
    assert redo_probe.apply_paths == ("checkpoint_restore",)
