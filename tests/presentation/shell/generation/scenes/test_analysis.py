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

"""Tests for shell prompt-scene generation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.presentation.shell.workspace_scene_generation_controller import (
    scene_for_key,
    scene_generation_context,
)


from tests.presentation.shell.generation.scenes.support import (
    _ScenePreflightError,
    _preflight_error,
    _workflow,
    _behavior_snapshot,
    _request,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_scene_generation_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def test_scene_generation_context_analyzes_runnable_scenes() -> None:
    """Scene context construction should analyze prompt scene authority."""

    context = scene_generation_context(
        request=_request(
            _workflow("quality\n\n**portrait\nstudio portrait\n\n**cafe\nat cafe")
        ),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )

    assert context.request.workflow_id == "workflow-a"
    assert context.behavior_snapshot is not None
    assert [
        (scene.key, scene.title, scene.order) for scene in context.scene_analysis.scenes
    ] == [
        ("portrait", "portrait", 0),
        ("cafe", "cafe", 1),
    ]


def test_scene_generation_context_requires_behavior_snapshot() -> None:
    """Scene generation should fail without prompt endpoint metadata."""

    with pytest.raises(_ScenePreflightError) as raised:
        scene_generation_context(
            request=_request(_workflow("**portrait\nstudio portrait")),
            behavior_snapshot=None,
            preflight_error=_preflight_error,
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Scene generation requires an active workflow prompt index."
    )


def test_scene_generation_context_requires_scene_markers() -> None:
    """Scene generation should fail when no runnable authority scenes exist."""

    with pytest.raises(_ScenePreflightError) as raised:
        scene_generation_context(
            request=_request(_workflow("quality portrait")),
            behavior_snapshot=_behavior_snapshot(),
            preflight_error=_preflight_error,
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Scene generation requires at least one **scene marker in the "
        "first positive prompt."
    )


def test_scene_for_key_returns_matching_scene() -> None:
    """Scene lookup should return a runnable scene by key."""

    context = scene_generation_context(
        request=_request(_workflow("**portrait\nstudio\n\n**cafe\ncoffee")),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )

    scene = scene_for_key(
        scene_analysis=context.scene_analysis,
        scene_key="cafe",
        workflow_id="workflow-a",
        preflight_error=_preflight_error,
    )

    assert scene.key == "cafe"
    assert scene.order == 1


def test_scene_for_key_reports_unknown_scene() -> None:
    """Scene lookup should fail through the injected preflight error factory."""

    context = scene_generation_context(
        request=_request(_workflow("**portrait\nstudio")),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )

    with pytest.raises(_ScenePreflightError) as raised:
        scene_for_key(
            scene_analysis=context.scene_analysis,
            scene_key="missing",
            workflow_id="workflow-a",
            preflight_error=_preflight_error,
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Generate scene could not find runnable scene: missing"
    )
