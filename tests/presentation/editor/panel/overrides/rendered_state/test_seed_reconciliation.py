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

"""Verify cached toolbar seeds reconcile authoritative state without edits."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.presentation.widgets import SeedBox
from tests.presentation.editor.panel.overrides.rendered_state.support import (
    DeterministicSeedRandomizer,
    build_workflow,
    randomize_for_generation,
    render_harness,
)


@pytest.mark.parametrize("detached", [False, True], ids=["mounted", "remounted"])
@pytest.mark.parametrize(
    ("initial_mode", "restored_mode"),
    [
        (SeedMode.FIXED, SeedMode.RANDOM),
        (SeedMode.RANDOM, SeedMode.FIXED),
        (SeedMode.FIXED, None),
    ],
    ids=["fixed-to-random", "random-to-fixed", "fixed-to-default"],
)
def test_reused_seed_restores_external_mode_without_editing_workflow(
    qt_application_owner: QApplication,
    detached: bool,
    initial_mode: SeedMode,
    restored_mode: SeedMode | None,
) -> None:
    """Refresh a mode-only owner change on the same mounted seed widget."""

    workflow = build_workflow()
    workflow.override_control_states["seed"] = SeedControlState(initial_mode)
    harness = render_harness(qt_application_owner, workflow)
    seed = cast(SeedBox, harness.toolbar_widget("seed"))
    try:
        assert seed.mode() == initial_mode.value
        if detached:
            harness.manager.detach_override_widgets()
        if restored_mode is None:
            workflow.override_control_states.clear()
        else:
            workflow.override_control_states["seed"] = SeedControlState(restored_mode)
        expected = deepcopy(workflow)
        autosaves_before = len(harness.autosave_payloads)
        value_edits = QSignalSpy(seed.valueChanged)
        mode_edits = QSignalSpy(seed.modeChanged)

        harness.manager.sync_state_from_workflow()
        harness.manager.rebuild_active_override_controls()

        assert harness.toolbar_widget("seed") is seed
        assert seed.isVisible()
        assert seed.value() == 11
        assert seed.line_edit.text() == "11"
        assert seed.mode() == (restored_mode or SeedMode.RANDOM).value
        assert value_edits.count() == 0
        assert mode_edits.count() == 0
        assert len(harness.autosave_payloads) == autosaves_before
        assert workflow == expected
        assert not seed.signalsBlocked()
        next_mode = (
            SeedMode.FIXED if seed.mode() == SeedMode.RANDOM.value else SeedMode.RANDOM
        )
        seed.setMode(next_mode.value)
        assert mode_edits.count() == 1
        assert workflow.override_control_states["seed"].mode is next_mode
        assert len(harness.autosave_payloads) == autosaves_before + 1
    finally:
        harness.close()


@pytest.mark.parametrize("detached", [False, True], ids=["mounted", "remounted"])
@pytest.mark.parametrize("restored_mode", [SeedMode.RANDOM, SeedMode.FIXED])
def test_reused_seed_restores_creation_value_after_generation_projection(
    qt_application_owner: QApplication,
    detached: bool,
    restored_mode: SeedMode,
) -> None:
    """Reconcile a restored owner value even when it matches the cached signature."""

    harness = render_harness(qt_application_owner)
    seed = cast(SeedBox, harness.toolbar_widget("seed"))
    try:
        randomize_for_generation(harness, DeterministicSeedRandomizer([101]))
        assert seed.value() == 101
        if detached:
            harness.manager.detach_override_widgets()
        harness.workflow.global_overrides["seed"]["value"] = 11
        harness.workflow.override_control_states["seed"] = SeedControlState(
            restored_mode
        )
        expected = deepcopy(harness.workflow)
        autosaves_before = len(harness.autosave_payloads)
        value_edits = QSignalSpy(seed.valueChanged)
        mode_edits = QSignalSpy(seed.modeChanged)

        harness.manager.sync_state_from_workflow()
        harness.manager.rebuild_active_override_controls()

        assert harness.toolbar_widget("seed") is seed
        assert seed.isVisible()
        assert seed.value() == 11
        assert seed.line_edit.text() == "11"
        assert seed.mode() == restored_mode.value
        assert value_edits.count() == 0
        assert mode_edits.count() == 0
        assert len(harness.autosave_payloads) == autosaves_before
        assert harness.workflow == expected
    finally:
        harness.close()


def test_unchanged_seed_rebuild_preserves_text_selection(
    qt_application_owner: QApplication,
) -> None:
    """Leave an unchanged seed editor's selection intact during reconciliation."""

    harness = render_harness(qt_application_owner)
    seed = cast(SeedBox, harness.toolbar_widget("seed"))
    try:
        seed.line_edit.setSelection(0, 1)
        value_edits = QSignalSpy(seed.valueChanged)
        mode_edits = QSignalSpy(seed.modeChanged)
        expected = deepcopy(harness.workflow)

        harness.manager.rebuild_active_override_controls()

        assert harness.toolbar_widget("seed") is seed
        assert seed.line_edit.selectedText() == "1"
        assert seed.line_edit.selectionStart() == 0
        assert value_edits.count() == 0
        assert mode_edits.count() == 0
        assert harness.autosave_payloads == []
        assert harness.workflow == expected
    finally:
        harness.close()
