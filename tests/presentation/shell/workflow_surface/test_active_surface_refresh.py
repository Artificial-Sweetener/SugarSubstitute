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

"""Active workflow surface refresh contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtCore import QTimer

from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)


from tests.presentation.shell.workflow_surface.reconciler_support import (
    _active_surface_shell,
    _record_bool,
)


def test_active_surface_refresher_defers_override_presentation_after_editor_completion(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Active workflow refresh should rebuild override presentation after loading."""

    loaded: list[dict[str, object]] = []
    actions: list[str] = []
    scheduled: list[Callable[[], None]] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": "state-a", "CubeB": "state-b"},
        stack_order=["CubeB", "CubeA"],
    )

    def load_all_cubes(**kwargs: object) -> None:
        """Record editor projection without completing it immediately."""

        actions.append("load")
        loaded.append(kwargs)

    override_manager = SimpleNamespace(
        sync_state_from_workflow=lambda: actions.append("sync"),
        apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
            actions,
            "pre_apply",
            True,
        ),
        materialize_default_overrides=lambda: _record_bool(
            actions,
            "defaults",
            False,
        ),
        rebuild_override_menu=lambda: actions.append("rebuild"),
        rebuild_active_override_controls=lambda: actions.append("controls"),
        apply_global_overrides=lambda **kwargs: actions.append(
            f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
        ),
    )
    shell = _active_surface_shell(
        workflow_id="wf-copy",
        workflow=workflow,
        editor_panel=SimpleNamespace(load_all_cubes=load_all_cubes),
        override_manager=override_manager,
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: scheduled.append(callback)),
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.shell.workflow_surface_reconciler",
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    on_surface_complete = loaded[0].pop("on_complete")
    assert callable(on_surface_complete)
    assert loaded == [
        {
            "cube_entries": [("CubeB", "state-b"), ("CubeA", "state-a")],
            "cube_states": workflow.cubes,
            "stack_order": workflow.stack_order,
        }
    ]
    assert actions == ["sync", "pre_apply", "load"]
    assert scheduled == []

    on_surface_complete()

    assert actions == ["sync", "pre_apply", "load", "defaults", "apply:True"]
    assert len(scheduled) == 1
    assert "Started active workflow surface refresh" in caplog.text
    assert "Loading active editor cube surface" in caplog.text
    assert "Queued active editor cube surface refresh" in caplog.text
    assert "Completed active workflow surface refresh" in caplog.text
    assert "Scheduled deferred active override presentation rebuild" in caplog.text
    assert "workflow_id=wf-copy" in caplog.text
    assert "cube_section_count=2" in caplog.text
    assert "stack_order_count=2" in caplog.text

    scheduled[0]()

    assert actions == [
        "sync",
        "pre_apply",
        "load",
        "defaults",
        "apply:True",
        "rebuild",
        "controls",
    ]
    assert "Rebuilt active override presentation" in caplog.text


def test_active_surface_refresher_projects_buffers_after_pre_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restored override values should settle before editor cards are loaded."""

    loaded_sampler_values: list[object] = []
    workflow = SimpleNamespace(
        cubes={
            "CubeA": SimpleNamespace(
                buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": ""}}}}
            )
        },
        stack_order=["CubeA"],
    )

    def pre_apply() -> bool:
        """Mutate the workflow buffer the way restored overrides do."""

        workflow.cubes["CubeA"].buffer["nodes"]["ksampler"]["inputs"][
            "sampler_name"
        ] = "euler_ancestral"
        return True

    def load_all_cubes(**kwargs: object) -> None:
        """Record the sampler value observed by editor projection."""

        cube_states = cast(Mapping[str, Any], kwargs["cube_states"])
        loaded_sampler_values.append(
            cube_states["CubeA"].buffer["nodes"]["ksampler"]["inputs"]["sampler_name"]
        )

    shell = _active_surface_shell(
        workflow_id="wf-restore",
        workflow=workflow,
        editor_panel=SimpleNamespace(load_all_cubes=load_all_cubes),
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: None,
            apply_global_overrides_without_snapshot_fallback=pre_apply,
            materialize_default_overrides=lambda: False,
            apply_global_overrides=lambda **_kwargs: None,
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda *_args: None),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    assert loaded_sampler_values == ["euler_ancestral"]


def test_active_surface_refresher_skips_clean_editor_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clean workflow switches should reuse the existing editor surface."""

    actions: list[str] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": SimpleNamespace(buffer={"nodes": {}})},
        stack_order=["CubeA"],
    )
    signature = object()
    editor_panel = SimpleNamespace(
        current_projection_signature=lambda **_kwargs: signature,
        is_projection_clean=lambda value: value is signature,
        refresh_clean_projection=lambda **_kwargs: actions.append("clean_refresh"),
        load_all_cubes=lambda **_kwargs: actions.append("load"),
    )
    shell = _active_surface_shell(
        workflow_id="wf-clean",
        workflow=workflow,
        editor_panel=editor_panel,
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: actions.append("sync"),
            apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
                actions,
                "pre_apply",
                False,
            ),
            materialize_default_overrides=lambda: _record_bool(
                actions,
                "defaults",
                False,
            ),
            apply_global_overrides=lambda **kwargs: actions.append(
                f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
            ),
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda *_args: None),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    assert actions == [
        "sync",
        "pre_apply",
        "clean_refresh",
        "defaults",
        "apply:True",
    ]
    assert "load" not in actions


def test_active_surface_refresher_force_refresh_bypasses_clean_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forced workflow refresh should rebuild even when the editor surface is clean."""

    actions: list[str] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": SimpleNamespace(buffer={"nodes": {}})},
        stack_order=["CubeA"],
    )
    signature = object()

    def load_all_cubes(**kwargs: object) -> None:
        """Record forced load and complete the projection."""

        actions.append("load")
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    editor_panel = SimpleNamespace(
        current_projection_signature=lambda **_kwargs: signature,
        is_projection_clean=lambda value: value is signature,
        refresh_clean_projection=lambda **_kwargs: actions.append("clean_refresh"),
        load_all_cubes=load_all_cubes,
    )
    shell = _active_surface_shell(
        workflow_id="wf-clean",
        workflow=workflow,
        editor_panel=editor_panel,
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: actions.append("sync"),
            apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
                actions,
                "pre_apply",
                False,
            ),
            materialize_default_overrides=lambda: _record_bool(
                actions,
                "defaults",
                False,
            ),
            apply_global_overrides=lambda **kwargs: actions.append(
                f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
            ),
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda *_args: None),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface(
        force_refresh=True
    )

    assert actions == [
        "sync",
        "pre_apply",
        "load",
        "defaults",
        "apply:True",
    ]
    assert "clean_refresh" not in actions


def test_active_surface_refresher_disables_generation_without_cubes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active workflow refresh should disable Generate when no cubes are loaded."""

    loaded: list[dict[str, object]] = []
    actions: list[str] = []
    scheduled: list[Callable[[], None]] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    def load_all_cubes(**kwargs: object) -> None:
        """Record editor projection without completing it immediately."""

        actions.append("load")
        loaded.append(kwargs)

    shell = _active_surface_shell(
        workflow_id="wf-empty",
        workflow=workflow,
        editor_panel=SimpleNamespace(load_all_cubes=load_all_cubes),
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: actions.append("sync"),
            apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
                actions,
                "pre_apply",
                False,
            ),
            materialize_default_overrides=lambda: _record_bool(
                actions,
                "defaults",
                False,
            ),
            rebuild_override_menu=lambda: actions.append("rebuild"),
            rebuild_active_override_controls=lambda: actions.append("controls"),
            apply_global_overrides=lambda **kwargs: actions.append(
                f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
            ),
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: scheduled.append(callback)),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    on_surface_complete = loaded[0].pop("on_complete")
    assert callable(on_surface_complete)
    assert loaded == [
        {
            "cube_entries": [],
            "cube_states": workflow.cubes,
            "stack_order": workflow.stack_order,
        }
    ]
    assert actions == ["sync", "pre_apply", "load"]
    assert scheduled == []

    on_surface_complete()

    presentation = shell.generationActionCluster.presentations[-1]
    assert actions == ["sync", "pre_apply", "load", "defaults", "apply:True"]
    assert len(scheduled) == 1
    assert presentation.play_enabled is False
    assert presentation.skip_enabled is False
    assert presentation.stop_enabled is False
    assert presentation.queue_primary_enabled is False
