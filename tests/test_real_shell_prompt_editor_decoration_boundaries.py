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

"""Verify text insertion at every projected prompt-decoration boundary."""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
from typing import Literal, Protocol, cast

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.real_shell_prompt_editor_harness import (
    PromptFieldHandle,
    RealShellPromptEditorHarness,
)
from tests.support.prompt_editor.decoration_boundary_probe import (
    DECORATION_BOUNDARY_CASES,
    PromptDecorationBoundary,
    RealShellPromptDecorationBoundaryProbe,
    decoration_boundary_placement,
    decoration_boundary_position,
)
from tools.prompt_editor_abuse.decoration_boundary_workloads import (
    prompt_decoration_boundary_scenarios,
)
from tools.prompt_editor_abuse.real_shell_driver import run_real_shell_scenario

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real prompt editor shell harness requires non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture
def harness() -> Iterator[RealShellPromptEditorHarness]:
    """Create and close the real-shell harness for each boundary scenario."""

    shell_harness = RealShellPromptEditorHarness()
    try:
        yield shell_harness
    finally:
        shell_harness.close()


_BOUNDARY_PARAMETERS = tuple(
    pytest.param(
        case.token_kind,
        case.source_text,
        boundary,
        id=f"{case.token_kind.value}-{boundary.replace('_', '-')}",
    )
    for case in DECORATION_BOUNDARY_CASES
    for boundary in case.boundaries
)

type PromptTextInsertionPath = Literal[
    "typing",
    "clipboard",
    "mime",
    "cursor",
    "ime",
]


class _PromptMimeInsertionHost(Protocol):
    """Expose the Qt-compatible MIME insertion boundary used by the probe."""

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """Insert one plain-text MIME payload through the editor host."""


def test_boundary_matrix_covers_every_projection_token_kind() -> None:
    """Require explicit boundary fixtures whenever a decoration kind is added."""

    assert {case.token_kind for case in DECORATION_BOUNDARY_CASES} == set(
        PromptProjectionTokenKind
    )


@pytest.mark.parametrize(
    ("token_kind", "source_text", "boundary"),
    _BOUNDARY_PARAMETERS,
)
def test_space_insertion_stays_at_each_decoration_boundary(
    harness: RealShellPromptEditorHarness,
    token_kind: PromptProjectionTokenKind,
    source_text: str,
    boundary: PromptDecorationBoundary,
) -> None:
    """Insert Space at the source boundary represented by the visible caret."""

    field = harness.add_prompt_workflow(initial_text=source_text)
    probe = RealShellPromptDecorationBoundaryProbe(harness)
    token = probe.token_for_kind(field, token_kind)
    insertion_position = decoration_boundary_position(token, boundary)
    before = probe.place_caret(field, token, boundary)

    assert before.cursor_position == insertion_position
    assert before.caret_state_source_position == insertion_position
    assert before.caret_state_placement == decoration_boundary_placement(boundary)

    route = harness.press_key(field, Qt.Key.Key_Space, text=" ")
    after = harness.capture_state_snapshot(
        field,
        label=f"{token_kind.value}-{boundary}-after-space",
    )

    assert route.source_before == source_text
    assert route.cursor_before == insertion_position
    assert after.source_text == (
        source_text[:insertion_position] + " " + source_text[insertion_position:]
    )
    assert after.cursor_position == insertion_position + 1
    assert after.caret_state_source_position == insertion_position + 1
    assert not harness.invariant_violations(after)


def test_additional_tag_remains_inside_weighted_emphasis(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep a newly typed tag before the emphasis weight and closing delimiter."""

    source_text = "(1girl, blue hair:1.2)"
    field = harness.add_prompt_workflow(initial_text=source_text)
    probe = RealShellPromptDecorationBoundaryProbe(harness)
    token = probe.token_for_kind(field, PromptProjectionTokenKind.EMPHASIS)
    probe.place_caret(field, token, "content_end")

    harness.press_key(field, Qt.Key.Key_Comma, text=",")
    settled_after_comma = harness.capture_state_snapshot(
        field,
        label="emphasis-after-comma",
    )
    harness.press_key(field, Qt.Key.Key_Space, text=" ")
    harness.type_text(field, "red eyes")
    completed = harness.capture_state_snapshot(
        field,
        label="emphasis-additional-tag-completed",
    )

    assert settled_after_comma.caret_state_placement == "token_content"
    assert completed.source_text == "(1girl, blue hair, red eyes:1.2)"
    assert completed.cursor_position == len("(1girl, blue hair, red eyes")
    assert completed.caret_state_placement == "token_content"
    assert not harness.invariant_violations(completed)


def test_rapid_additional_tag_uses_live_caret_ahead_of_stale_projection(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep uninterrupted typing ordered while projection metadata catches up."""

    source_text = "(1girl, blue hair:1.2)"
    field = harness.add_prompt_workflow(initial_text=source_text)
    probe = RealShellPromptDecorationBoundaryProbe(harness)
    token = probe.token_for_kind(field, PromptProjectionTokenKind.EMPHASIS)
    probe.place_caret(field, token, "content_end")

    harness.type_text(field, ", red eyes")
    completed = harness.capture_state_snapshot(
        field,
        label="emphasis-rapid-additional-tag-completed",
    )

    assert completed.source_text == "(1girl, blue hair, red eyes:1.2)"
    assert completed.cursor_position == len("(1girl, blue hair, red eyes")
    assert not harness.invariant_violations(completed)


@pytest.mark.parametrize(
    "insertion_path",
    ("typing", "clipboard", "mime", "cursor", "ime"),
)
def test_every_direct_text_path_keeps_emphasis_content_end(
    harness: RealShellPromptEditorHarness,
    insertion_path: PromptTextInsertionPath,
) -> None:
    """Keep equivalent direct-input adapters on the same content boundary."""

    source_text = "before (alpha:1.2) after"
    field = harness.add_prompt_workflow(initial_text=source_text)
    probe = RealShellPromptDecorationBoundaryProbe(harness)
    token = probe.token_for_kind(field, PromptProjectionTokenKind.EMPHASIS)
    insertion_position = decoration_boundary_position(token, "content_end")
    probe.place_caret(field, token, "content_end")

    _insert_space_through_path(harness, field, insertion_path)
    after = harness.capture_state_snapshot(
        field,
        label=f"emphasis-content-end-{insertion_path}",
    )

    assert after.source_text == (
        source_text[:insertion_position] + " " + source_text[insertion_position:]
    )
    assert after.cursor_position == insertion_position + 1
    assert after.caret_state_source_position == insertion_position + 1
    assert not harness.invariant_violations(after)


def _insert_space_through_path(
    harness: RealShellPromptEditorHarness,
    field: PromptFieldHandle,
    insertion_path: PromptTextInsertionPath,
) -> None:
    """Insert one space through the requested production input adapter."""

    if insertion_path == "typing":
        harness.press_key(field, Qt.Key.Key_Space, text=" ")
        return
    if insertion_path == "clipboard":
        harness.paste_text(field, " ")
        return
    if insertion_path == "mime":
        mime_data = QMimeData()
        mime_data.setText(" ")
        cast(_PromptMimeInsertionHost, field.editor).insertFromMimeData(mime_data)
        harness.process_events(cycles=8)
        return
    if insertion_path == "cursor":
        field.editor.textCursor().insertText(" ")
        harness.process_events(cycles=8)
        return
    target = harness.focus_editor(field)
    commit = QInputMethodEvent()
    commit.setCommitString(" ")
    QApplication.sendEvent(target, commit)
    harness.process_events(cycles=8)


def test_abuse_workload_checks_each_settled_boundary_edit(
    tmp_path: Path,
) -> None:
    """Keep the reproduced failure class in exact per-character abuse checkpoints."""

    scenario = prompt_decoration_boundary_scenarios()[0]
    result = run_real_shell_scenario(
        scenario,
        repetition=0,
        artifact_root=tmp_path,
    )

    assert scenario.expected_text == "(1girl, blue hair, red eyes:1.2)"
    assert result.correct
    assert all(sample.source_exact for sample in result.dispatch_samples)
    assert all(sample.caret_exact for sample in result.dispatch_samples)
