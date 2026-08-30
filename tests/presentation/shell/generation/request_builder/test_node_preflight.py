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

"""Tests for shell generation request-building policy helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
)
from substitute.application.workflows import CubeRuntimeIssueSource
from substitute.presentation.shell.workspace_generation_request_builder import (
    preflight_live_node_definitions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_preflight_live_node_definitions_registers_cube_issue() -> None:
    """Cube-attributed live metadata failures should be registered as recoverable."""

    register_calls: list[
        tuple[LiveNodeDefinitionError, str, CubeRuntimeIssueSource]
    ] = []

    class _Panel:
        """Raise and register a cube-attributed live metadata error."""

        def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
            """Raise a cube-attributed metadata failure from generation preflight."""

            assert reason == "generation_preflight"
            raise LiveNodeDefinitionError(
                operation="hydrate generation node definitions",
                missing_definitions=(
                    MissingLiveNodeDefinition(
                        class_type="SimpleSyrup.Detailer",
                        cube_aliases=("CubeA",),
                        node_names=("detailer",),
                    ),
                ),
            )

        def register_projection_live_node_definition_error(
            self,
            error: LiveNodeDefinitionError,
            *,
            reason: str,
            source: CubeRuntimeIssueSource,
        ) -> bool:
            """Record the recoverable issue registration request."""

            register_calls.append((error, reason, source))
            return True

    preflight_live_node_definitions(
        view=SimpleNamespace(
            editor_panels={"wf-a": _Panel()},
            active_editor_panel=None,
        ),
        workflow_id="wf-a",
        preflight_error=lambda error: AssertionError(error),
    )

    assert len(register_calls) == 1
    _error, reason, source = register_calls[0]
    assert reason == "generation_preflight"
    assert source == CubeRuntimeIssueSource.PROJECTION


def test_preflight_live_node_definitions_raises_preflight_error() -> None:
    """Unowned live metadata failures should fail generation preflight."""

    class _Panel:
        """Raise an unowned live metadata error."""

        def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
            """Raise a metadata failure from generation preflight."""

            assert reason == "generation_preflight"
            raise LiveNodeDefinitionError(
                operation="hydrate generation node definitions",
                missing_definitions=(
                    MissingLiveNodeDefinition(class_type="SimpleSyrup.Detailer"),
                ),
            )

    expected_error = RuntimeError("preflight failed")

    try:
        preflight_live_node_definitions(
            view=SimpleNamespace(
                editor_panels={"wf-a": _Panel()},
                active_editor_panel=None,
            ),
            workflow_id="wf-a",
            preflight_error=lambda _error: expected_error,
        )
    except RuntimeError as error:
        assert error is expected_error
        assert isinstance(error.__cause__, LiveNodeDefinitionError)
    else:
        raise AssertionError("expected preflight error")


def test_preflight_live_node_definitions_logs_missing_panel() -> None:
    """Missing editor panels should skip preflight through the provided logger."""

    logged: list[str] = []

    preflight_live_node_definitions(
        view=SimpleNamespace(editor_panels={}, active_editor_panel=object()),
        workflow_id="wf-a",
        preflight_error=lambda error: AssertionError(error),
        missing_panel_logger=logged.append,
    )

    assert logged == ["wf-a"]
