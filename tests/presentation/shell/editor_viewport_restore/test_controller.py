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

"""Cover restored editor viewport behavior outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    WorkflowSnapshot,
)
from substitute.presentation.shell.editor_viewport_restore import (
    EditorViewportRestoreController,
)


class _ViewportScrollBar:
    """Record editor scrollbar state for viewport restore tests."""

    def __init__(self, *, value: int, maximum: int) -> None:
        """Store initial scrollbar values."""

        self._value = value
        self._maximum = maximum

    def value(self) -> int:
        """Return the current scrollbar value."""

        return self._value

    def maximum(self) -> int:
        """Return the current scrollbar maximum."""

        return self._maximum

    def setValue(self, value: int) -> None:
        """Record the restored scrollbar value."""

        self._value = value


class _ViewportScroll:
    """Expose the vertical scrollbar expected by editor panels."""

    def __init__(self, scrollbar: _ViewportScrollBar) -> None:
        """Store the scrollbar."""

        self._scrollbar = scrollbar

    def verticalScrollBar(self) -> _ViewportScrollBar:
        """Return the vertical scrollbar."""

        return self._scrollbar


class _ViewportEditorPanel:
    """Record exact and fallback viewport restore operations."""

    def __init__(self, scrollbar: _ViewportScrollBar) -> None:
        """Initialize scroll state and fallback call records."""

        self.scroll = _ViewportScroll(scrollbar)
        self.scroll_to_cube_calls: list[tuple[str, bool, bool]] = []

    def scroll_to_cube(
        self,
        alias: str,
        *,
        animated: bool,
        only_if_needed: bool,
    ) -> None:
        """Record cube-scroll fallback requests."""

        self.scroll_to_cube_calls.append((alias, animated, only_if_needed))


def _snapshot(
    *,
    active_cube_alias: str | None = "CubeB",
    viewport: EditorViewportSnapshot | None = None,
    stack_order: list[str] | None = None,
) -> WorkflowSnapshot:
    """Build a restored workflow snapshot for viewport tests."""

    aliases = stack_order or ["CubeA", "CubeB"]
    return WorkflowSnapshot(
        workflow_id="wf-a",
        tab_label="Restored",
        workflow=WorkflowState(
            cubes={
                alias: CubeState(
                    cube_id=f"cube.{alias}",
                    version="1",
                    alias=alias,
                    original_cube={},
                    buffer={},
                )
                for alias in aliases
            },
            stack_order=aliases,
        ),
        active_cube_alias=active_cube_alias,
        editor_viewport=viewport,
    )


def test_restore_editor_viewport_applies_exact_saved_scroll() -> None:
    """Compatible scroll ranges should restore the exact saved value."""

    scrollbar = _ViewportScrollBar(value=0, maximum=130)
    panel = _ViewportEditorPanel(scrollbar)
    shell = SimpleNamespace(
        _shell_restore_lifecycle="running",
        editor_panels={"wf-a": panel},
    )
    snapshot = _snapshot(
        viewport=EditorViewportSnapshot(
            scroll_value=120,
            scroll_maximum=128,
            anchor_cube_alias="CubeA",
        )
    )

    EditorViewportRestoreController(shell).restore_editor_viewport_for_workflow(
        snapshot
    )

    assert scrollbar.value() == 120
    assert panel.scroll_to_cube_calls == []
    assert shell._shell_restore_lifecycle == "running"


def test_restore_editor_viewport_falls_back_to_active_cube_on_range_drift() -> None:
    """Range drift should scroll to the restored active cube."""

    scrollbar = _ViewportScrollBar(value=0, maximum=500)
    panel = _ViewportEditorPanel(scrollbar)
    shell = SimpleNamespace(
        _shell_restore_lifecycle="running",
        editor_panels={"wf-a": panel},
    )
    snapshot = _snapshot(
        active_cube_alias="CubeB",
        viewport=EditorViewportSnapshot(
            scroll_value=90,
            scroll_maximum=100,
            anchor_cube_alias="CubeA",
        ),
    )

    EditorViewportRestoreController(shell).restore_editor_viewport_for_workflow(
        snapshot
    )

    assert scrollbar.value() == 0
    assert panel.scroll_to_cube_calls == [("CubeB", False, False)]
    assert shell._shell_restore_lifecycle == "running"


def test_restore_viewport_target_alias_prefers_anchor_when_active_missing() -> None:
    """Fallback targeting should use the saved anchor when active alias is unavailable."""

    snapshot = _snapshot(
        active_cube_alias="Missing",
        viewport=EditorViewportSnapshot(
            scroll_value=10,
            scroll_maximum=100,
            anchor_cube_alias="CubeA",
        ),
    )

    target = EditorViewportRestoreController.restore_viewport_target_alias(snapshot)

    assert target == "CubeA"


def test_restore_viewport_target_alias_uses_first_stack_alias_without_saved_target() -> (
    None
):
    """Fallback targeting should use the first stack alias when no saved target exists."""

    snapshot = _snapshot(
        active_cube_alias="Missing",
        viewport=EditorViewportSnapshot(
            scroll_value=10,
            scroll_maximum=100,
            anchor_cube_alias="AlsoMissing",
        ),
    )

    target = EditorViewportRestoreController.restore_viewport_target_alias(snapshot)

    assert target == "CubeA"


def test_restore_editor_viewport_skips_when_editor_panel_missing() -> None:
    """Missing restored editor panels should leave lifecycle state unchanged."""

    shell = SimpleNamespace(
        _shell_restore_lifecycle="running",
        editor_panels={},
    )

    EditorViewportRestoreController(shell).restore_editor_viewport_for_workflow(
        _snapshot()
    )

    assert shell._shell_restore_lifecycle == "running"


def test_exact_viewport_rejects_empty_or_drifted_scroll_ranges() -> None:
    """Exact restore should reject empty ranges and large range drift."""

    empty_panel = _ViewportEditorPanel(_ViewportScrollBar(value=0, maximum=0))
    drifted_panel = _ViewportEditorPanel(_ViewportScrollBar(value=0, maximum=500))
    viewport = EditorViewportSnapshot(
        scroll_value=90,
        scroll_maximum=100,
        anchor_cube_alias="CubeA",
    )

    assert (
        EditorViewportRestoreController.apply_exact_editor_viewport(
            empty_panel,
            viewport,
            workflow_id="wf-a",
            target_alias="CubeA",
        )
        is False
    )
    assert (
        EditorViewportRestoreController.apply_exact_editor_viewport(
            drifted_panel,
            viewport,
            workflow_id="wf-a",
            target_alias="CubeA",
        )
        is False
    )
