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

"""Verify recipe surfaces publish only after canonical graph installation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.shell.cube_loader import (
    CubeLoadPresentationIntent,
    CubeLoadUiCallbacks,
)
from substitute.presentation.shell.workflow_snapshot_materialization import (
    WorkflowSnapshotMaterializer,
)
from substitute.presentation.shell.workflow_surface_commit import (
    DeferredWorkflowSurfaceCommit,
)
from tests.presentation.shell.file_actions.support import (
    _CubeStack,
    _EditorBusyRecorder,
    _EditorPanel,
)
from tests.support.canonical_cube_graph import graph_backed_cube_workflow


def test_canonical_graph_precedes_editor_and_mask_projection() -> None:
    """Recipe loading must never expose a provisional noncanonical surface."""

    events: list[tuple[str, str]] = []
    canonical_installed = False

    def refresh_async(
        _workflow_id: str,
        alias: str,
        on_complete: Any,
        **_kwargs: object,
    ) -> None:
        """Record one real editor refresh and complete it deterministically."""

        assert canonical_installed
        events.append(("refresh", alias))
        on_complete(True)

    def materialize(_workflow_id: str, alias: str) -> None:
        """Record canonical Input mask materialization."""

        assert canonical_installed
        events.append(("materialize", alias))

    callbacks = CubeLoadUiCallbacks(
        workflow_session_service=cast(Any, SimpleNamespace()),
        cube_stacks={},
        editor_panels={},
        cube_load_service=cast(Any, SimpleNamespace()),
        cube_stack_service=cast(Any, SimpleNamespace()),
        materialize_loaded_cube_input_canvas=materialize,
        refresh_workflow_after_cube_load=lambda *_args: None,
        prepare_node_behavior_runtime=lambda *_args: cast(Any, None),
        cube_icon_factory=cast(Any, SimpleNamespace()),
        cube_load_execution_route_factory=cast(Any, SimpleNamespace()),
        refresh_loaded_cube_surface_async=refresh_async,
        schedule_next_gui_turn=lambda callback: callback(),
    )

    def install_canonical_graph() -> None:
        """Publish canonical graph authority for the projection assertions."""

        nonlocal canonical_installed
        canonical_installed = True
        events.append(("install", "graph"))

    commit = DeferredWorkflowSurfaceCommit(
        callbacks=callbacks,
        workflow_id="workflow",
        source_aliases=("Region", "Upscale"),
        install_authority=install_canonical_graph,
        on_complete=lambda aliases: events.append(("complete", ",".join(aliases))),
    )
    loading = commit.loading_callbacks

    suppressed_refresh = loading.refresh_loaded_cube_surface_async
    assert suppressed_refresh is not None
    suppressed_refresh(
        "workflow",
        "Region",
        lambda refreshed: events.append(("provisional", str(refreshed))),
        wait_for_complete=True,
    )
    loading.materialize_loaded_cube_input_canvas("workflow", "Region")
    assert events == [("provisional", "True")]

    commit.record_loaded("Region", "Region")
    assert events == [("provisional", "True")]
    commit.record_loaded("Upscale", "Upscale")

    assert events == [
        ("provisional", "True"),
        ("install", "graph"),
        ("refresh", "Region"),
        ("materialize", "Region"),
        ("refresh", "Upscale"),
        ("materialize", "Upscale"),
        ("complete", "Region,Upscale"),
    ]


def test_recipe_materializer_projects_masks_from_installed_graph(
    tmp_path: Path,
) -> None:
    """Out-of-order cube completion must still publish one canonical surface."""

    canonical = graph_backed_cube_workflow("Region", "Upscale")
    assert canonical.direct_workflow is not None
    analysis = canonical.direct_workflow.cube_analysis
    assert analysis is not None
    target = type(canonical)()
    events: list[tuple[str, str]] = []
    queued: list[tuple[CubeLoadUiCallbacks, dict[str, object]]] = []

    def refresh_async(
        _workflow_id: str,
        alias: str,
        on_complete: Any,
        **_kwargs: object,
    ) -> None:
        """Prove every real editor refresh observes graph authority."""

        assert target.direct_workflow is not None
        events.append(("refresh", alias))
        on_complete(True)

    def materialize(_workflow_id: str, alias: str) -> None:
        """Prove every Input canvas projection observes graph authority."""

        assert target.direct_workflow is not None
        events.append(("materialize", alias))

    callbacks = CubeLoadUiCallbacks(
        workflow_session_service=cast(
            Any,
            SimpleNamespace(active_workflow_id="workflow"),
        ),
        cube_stacks={},
        editor_panels={},
        cube_load_service=cast(Any, SimpleNamespace()),
        cube_stack_service=cast(Any, SimpleNamespace()),
        materialize_loaded_cube_input_canvas=materialize,
        refresh_workflow_after_cube_load=lambda *_args: None,
        prepare_node_behavior_runtime=lambda *_args: cast(Any, None),
        cube_icon_factory=cast(Any, SimpleNamespace()),
        cube_load_execution_route_factory=cast(Any, SimpleNamespace()),
        refresh_loaded_cube_surface_async=refresh_async,
        schedule_next_gui_turn=lambda callback: callback(),
    )
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(itemMap={}),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="workflow",
            workflows={"workflow": target},
        ),
        cube_stacks={"workflow": _CubeStack()},
        editor_panels={"workflow": _EditorPanel()},
        active_override_manager=None,
        editor_busy=_EditorBusyRecorder(),
        _pending_cubes={},
    )

    class _IconProvider:
        """Provide the one placeholder icon requested by materialization."""

        class CLOSE:
            """Provide a deterministic placeholder token."""

            @staticmethod
            def icon() -> str:
                """Return a stable fake icon."""

                return "close"

    def queue_cube(
        callbacks: CubeLoadUiCallbacks,
        *,
        cube_id: str,
        alias_name: str,
        placeholder_index: int,
        buffer_patch: dict[str, object] | None = None,
        reveal_after_load: bool = True,
        presentation_intent: CubeLoadPresentationIntent | None = None,
        on_load_finished: Callable[[str | None], None] | None = None,
    ) -> None:
        """Capture cube completions without performing external loading."""

        queued.append(
            (
                callbacks,
                {
                    "cube_id": cube_id,
                    "alias_name": alias_name,
                    "placeholder_index": placeholder_index,
                    "buffer_patch": buffer_patch,
                    "reveal_after_load": reveal_after_load,
                    "presentation_intent": presentation_intent,
                    "on_load_finished": on_load_finished,
                },
            )
        )

    WorkflowSnapshotMaterializer(
        view,
        build_cube_load_ui_callbacks=lambda **_kwargs: callbacks,
    ).materialize(
        workflow_id="workflow",
        workflow_name="Loaded",
        loaded_buffers={
            "Region": {"cube_id": "test/Region.cube"},
            "Upscale": {"cube_id": "test/Upscale.cube"},
        },
        global_overrides={},
        projects_dir=tmp_path,
        cube_loader=queue_cube,
        icon_provider=cast(Any, _IconProvider),
        cube_graph_analysis=analysis,
    )

    assert target.direct_workflow is None
    for loading_callbacks, _kwargs in queued:
        loading_callbacks.materialize_loaded_cube_input_canvas(
            "workflow",
            "provisional",
        )
    assert events == []

    second_finished = cast(Any, queued[1][1]["on_load_finished"])
    first_finished = cast(Any, queued[0][1]["on_load_finished"])
    second_finished("Upscale")
    assert events == []
    first_finished("Region")

    assert target.direct_workflow is not None
    assert target.stack_order == ["Region", "Upscale"]
    assert events == [
        ("refresh", "Region"),
        ("materialize", "Region"),
        ("refresh", "Upscale"),
        ("materialize", "Upscale"),
    ]


def test_failed_cube_never_installs_incomplete_graph_authority() -> None:
    """A partial load may publish its survivor but must not claim full authority."""

    events: list[tuple[str, str]] = []
    callbacks = CubeLoadUiCallbacks(
        workflow_session_service=cast(Any, SimpleNamespace()),
        cube_stacks={},
        editor_panels={},
        cube_load_service=cast(Any, SimpleNamespace()),
        cube_stack_service=cast(Any, SimpleNamespace()),
        materialize_loaded_cube_input_canvas=lambda _workflow_id, alias: events.append(
            ("materialize", alias)
        ),
        refresh_workflow_after_cube_load=lambda _workflow_id, alias: events.append(
            ("refresh", alias)
        ),
        prepare_node_behavior_runtime=lambda *_args: cast(Any, None),
        cube_icon_factory=cast(Any, SimpleNamespace()),
        cube_load_execution_route_factory=cast(Any, SimpleNamespace()),
        schedule_next_gui_turn=lambda callback: callback(),
    )
    commit = DeferredWorkflowSurfaceCommit(
        callbacks=callbacks,
        workflow_id="workflow",
        source_aliases=("Missing", "Survivor"),
        install_authority=lambda: events.append(("install", "graph")),
        on_complete=lambda aliases: events.append(("complete", ",".join(aliases))),
    )

    commit.record_loaded("Survivor", "Survivor")
    commit.record_loaded("Missing", None)
    commit.record_loaded("Missing", None)

    assert events == [
        ("refresh", "Survivor"),
        ("materialize", "Survivor"),
        ("complete", "Survivor"),
    ]
