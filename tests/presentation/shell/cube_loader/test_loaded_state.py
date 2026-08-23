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

"""Test cube-loader loaded-state transaction contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from .execution_support import _QueuedSubmitter, _with_submitter
from .support import (
    _FailingCubeIconFactory,
    _FakeQTimer,
    _FakeTabItem,
    _build_loader_state,
    _import_cube_loader_module,
    _stub_cube_service,
)


def test_load_cube_async_applies_fallback_icon_when_resolution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loaded cube placeholder promotion should never finish without an icon."""

    from substitute.presentation.resources.app_icon import AppIcon

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()
    state.cube_icon_factory = _FailingCubeIconFactory()

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {}})),
            submitter,
        ),
        cube_id="Org/Base-Cubes/Base.cube",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    submitter.run_next()
    submitter.run_next()
    _FakeQTimer.run_all()

    assert state.cube_stacks["wfA"].tab_icon_calls == [(0, AppIcon.CUBE_20_FILLED)]
    assert state.cube_icon_factory.calls == [
        ("Org/Base-Cubes/Base.cube", "Org/Base-Cubes/Base.cube Display", None)
    ]
    assert state.cube_stacks["wfA"].tabItem(0).routeKey() == "Alias1"
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_applies_loaded_cube_metadata_tooltip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async loaded cube tabs should receive the formatted metadata tooltip."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service(
        graph={"nodes": {"n1": {}}},
        ui_payload={
            "canonical_cube": {
                "cube_id": "ArtificialSweetener/Base-Cubes/Upscale.cube",
                "version": "2.0.0",
                "description": "Upscales images with detail-preserving defaults.",
                "metadata": {
                    "default_alias": "Diffusion Upscale",
                    "supported_models": ["SDXL 1.0", "SD 1.5"],
                    "tags": ["upscale", "detailer"],
                },
                "implementation": {"nodes": {"Secret": {}}},
            },
            "source": {"repo_ref": "ArtificialSweetener/Base-Cubes"},
        },
    )

    module.load_cube_async(
        build_callbacks(service),
        cube_id="ArtificialSweetener/Base-Cubes/Upscale.cube",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    tooltip = state.cube_stacks["wfA"].tab_presentation_calls[0][3]
    assert "<b>Diffusion Upscale</b>, v2.0.0" in tooltip
    assert "Base-Cubes by ArtificialSweetener" in tooltip
    assert "<b>Supported models:</b> SDXL 1.0, SD 1.5" in tooltip
    assert "<b>Description:</b> Upscales images" in tooltip
    assert "<b>Tags:</b> upscale, detailer" in tooltip
    assert "Secret" not in tooltip
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_applies_buffer_patch_before_persisting_cube_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Buffer patch merge should run and affect persisted cube buffer."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    cube_def = {"nodes": {"Node1": {"class_type": "KSampler"}}}

    merge_calls: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []

    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service(graph=cube_def)

    def _merge_service(
        *,
        cube_buffer: dict[str, Any],
        buffer_patch: dict[str, Any],
        cube_definition: dict[str, Any],
    ) -> None:
        merge_calls.append((cube_buffer, buffer_patch, cube_definition))
        cube_buffer["patched"] = True

    service.merge_cube_buffer_patch = _merge_service
    patch = {"nodes": {"Node1": {"inputs": {"seed": 7}}}}
    module.load_cube_async(
        build_callbacks(service),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=patch,
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    cube_state = workflow.cubes["Alias1"]
    assert merge_calls and merge_calls[0][1] == patch
    assert merge_calls[0][2] is cube_def
    assert cube_state.buffer["patched"] is True
    assert cube_state.display_name == "Base Display"
    assert state.cube_stack_service.added
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1")]
    assert state.cube_stacks["wfA"].tab_presentation_calls == [
        (
            0,
            "Alias1",
            "v1.0.0",
            '<div style="max-width: 420px; width: 420px; white-space: normal; '
            'word-wrap: break-word; overflow-wrap: anywhere;">'
            "<b>Base Display</b>, v1.0.0</div>",
        )
    ]
    assert state.cube_stacks["wfA"].tab_icon_calls == [(0, "resolved-icon-token")]
    assert state.cube_stacks["wfA"].tabItem(0).routeKey() == "Alias1"
    assert workflow.stack_order == ["Alias1"]
    assert refresh == [("wfA", "Alias1")]
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_uses_version_loader_for_pinned_recipe_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pinned recipe buffers should load the requested cube version."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service()
    version_load_calls: list[tuple[str, str]] = []
    original_version_loader = service.load_cube_definition_version

    def _load_version(cube_id: str, version: str) -> object:
        version_load_calls.append((cube_id, version))
        return original_version_loader(cube_id, version)

    service.load_cube_definition_version = _load_version

    module.load_cube_async(
        build_callbacks(service),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch={
            "cube_id": "Base",
            "version": "1.2.3",
            "update_policy": "pinned",
        },
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    cube_state = workflow.cubes["Alias1"]
    assert version_load_calls == [("Base", "1.2.3")]
    assert cube_state.version == "1.2.3"
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_preserves_existing_cube_when_second_alias_is_suffixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async completion should keep both cube entries when alias resolution already suffixed the second load."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Shared 2"
    )
    existing_cube_state = SimpleNamespace(alias="Shared")
    workflow = state.workflow_session_service.workflows["wfA"]
    workflow.cubes["Shared"] = existing_cube_state
    workflow.stack_order = ["Shared"]

    existing_tab = _FakeTabItem("Shared")
    placeholder_tab = state.cube_stacks["wfA"].items[0]
    state.cube_stacks["wfA"].items = [existing_tab, placeholder_tab]
    state.cube_stacks["wfA"].itemMap = {
        "Shared": existing_tab,
        "loading:Shared 2": placeholder_tab,
    }

    module.load_cube_async(
        build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}})),
        cube_id="cube_b",
        alias_name="Shared 2",
        placeholder_index=1,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    assert set(workflow.cubes) == {"Shared", "Shared 2"}
    assert workflow.stack_order == ["Shared", "Shared 2"]
    assert state.cube_stacks["wfA"].tab_text_calls == [(1, "Shared 2")]
    assert state.cube_stacks["wfA"].tab_presentation_calls == [
        (
            1,
            "Shared 2",
            "v1.0.0",
            '<div style="max-width: 420px; width: 420px; white-space: normal; '
            'word-wrap: break-word; overflow-wrap: anywhere;">'
            "<b>cube_b Display</b>, v1.0.0</div>",
        )
    ]
    assert state.cube_stacks["wfA"].tabItem(1).routeKey() == "Shared 2"
    assert materialized == [("wfA", "Shared 2")]


def test_load_cube_async_excludes_loading_placeholders_from_workflow_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow stack order sync should ignore staged placeholders not loaded yet."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    stack = state.cube_stacks["wfA"]
    stack.items.append(_FakeTabItem("loading:Alias2"))
    stack.items.append(_FakeTabItem("Already Loaded"))
    stack.itemMap["loading:Alias2"] = stack.items[1]
    stack.itemMap["Already Loaded"] = stack.items[2]
    workflow = state.workflow_session_service.workflows["wfA"]
    workflow.cubes["Already Loaded"] = object()
    workflow.stack_order.append("Already Loaded")
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    finished_aliases: list[str | None] = []

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        reveal_after_load=False,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_all()

    assert workflow.stack_order == ["Alias1", "Already Loaded"]
    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]
