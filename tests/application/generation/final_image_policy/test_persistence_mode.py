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

"""Verify final-image persistence topology and explicit mute policy."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path


from substitute.application.generation import (
    OutputPersistenceMode,
    OutputPreferenceService,
)
from substitute.infrastructure.persistence.file_output_preference_repository import (
    FileOutputPreferenceRepository,
)


def test_final_only_policy_uses_active_topology_and_explicit_mute_wins(
    tmp_path: Path,
) -> None:
    """Final means the last active cube, while an explicit final mute saves nothing."""

    repository = FileOutputPreferenceRepository(tmp_path / "settings")
    service = OutputPreferenceService(repository, default_output_root=tmp_path)
    service.save_preferences(
        replace(
            service.load_preferences(),
            persistence_mode=OutputPersistenceMode.FINAL_CUBE,
        )
    )

    plan = service.create_save_plan(
        workflow_name="Workflow",
        output_run_number=1,
        job_started_at=datetime(2026, 7, 18),
        active_cube_aliases=("First", "Bypassed", "Final"),
        muted_cube_aliases=frozenset({"Bypassed"}),
    )

    assert plan.persists_cube("First") is False
    assert plan.persists_cube("Bypassed") is False
    assert plan.persists_cube("Final") is True

    muted_final_plan = service.create_save_plan(
        workflow_name="Workflow",
        output_run_number=1,
        job_started_at=datetime(2026, 7, 18),
        active_cube_aliases=("First", "Final"),
        muted_cube_aliases=frozenset({"Final"}),
    )

    assert muted_final_plan.persists_cube("First") is False
    assert muted_final_plan.persists_cube("Final") is False
