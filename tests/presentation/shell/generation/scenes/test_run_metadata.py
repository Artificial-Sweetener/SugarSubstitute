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


from substitute.application.generation import (
    GenerationJobSnapshot,
)
from substitute.presentation.shell.workspace_scene_generation_controller import (
    register_output_scene_run,
    scene_run_entries_from_snapshots,
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


def test_scene_run_entries_from_snapshots_orders_scene_metadata() -> None:
    """Scene-run entries should follow snapshot scene order with fallback ordering."""

    snapshots = (
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - later",
            sugar_script_text="# later",
            scene_key="later",
            scene_title="Later",
            scene_order=3,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - missing-order",
            sugar_script_text="# missing",
            scene_key="missing-order",
            scene_title=None,
            scene_order=None,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - first",
            sugar_script_text="# first",
            scene_key="first",
            scene_title="First",
            scene_order=0,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            sugar_script_text="# no scene",
        ),
    )

    assert scene_run_entries_from_snapshots(
        snapshots=snapshots,
        scene_count=4,
    ) == (
        ("first", "First", 0),
        ("later", "Later", 1),
        ("missing-order", "missing-order", 2),
    )


def test_register_output_scene_run_updates_scene_metadata() -> None:
    """Scene-run bookkeeping should register prepared scene navigation metadata."""

    calls: list[tuple[str, object]] = []
    snapshots = (
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - portrait",
            sugar_script_text="# portrait",
            scene_run_id="scene-run-a",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
    )

    class _SceneRunService:
        """Record scene-run navigation metadata."""

        def start_scene_run(
            self,
            *,
            scene_run_id: str,
            workflow_id: str,
            workflow_name: str,
            scenes: object,
        ) -> None:
            """Record scene-run start arguments."""

            calls.append(
                (
                    "scene_run",
                    {
                        "scene_run_id": scene_run_id,
                        "workflow_id": workflow_id,
                        "workflow_name": workflow_name,
                        "scenes": scenes,
                    },
                )
            )

    register_output_scene_run(
        output_scene_run_service=_SceneRunService(),
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        scene_run_id="scene-run-a",
        scene_count=1,
        snapshots=snapshots,
    )

    assert calls == [
        (
            "scene_run",
            {
                "scene_run_id": "scene-run-a",
                "workflow_id": "workflow-a",
                "workflow_name": "Recipe A",
                "scenes": (("portrait", "Portrait", 0),),
            },
        ),
    ]


def test_register_output_scene_run_tolerates_missing_scene_service() -> None:
    """Scene-run metadata registration should tolerate absent navigation chrome."""

    register_output_scene_run(
        output_scene_run_service=None,
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        scene_run_id="scene-run-a",
        scene_count=2,
    )
