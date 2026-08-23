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

"""Test bounded full-projection failure cleanup and recovery behavior."""

from __future__ import annotations

from __future__ import annotations
import importlib
from types import SimpleNamespace
import pytest
from tests.presentation.editor.panel.projection_support import (
    _Layout,
    _Signal,
    _Widget,
)


def test_load_all_cubes_clears_preparation_prompt_context_after_widget_failure() -> (
    None
):
    """Widget-preparation failures should clear full projection prompt context."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    cube = SimpleNamespace(buffer={"nodes": {}})

    def _raise_build_failure(_alias: str, _state: object) -> object:
        calls.append("build")
        raise RuntimeError("build failed")

    def _build_behavior_snapshot(**_kwargs: object) -> str:
        calls.append("snapshot")
        return "snapshot"

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=_raise_build_failure,
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=_build_behavior_snapshot,
        begin_behavior_refresh_transaction=lambda *, reason: calls.append(
            f"begin_transaction:{reason}"
        ),
        end_behavior_refresh_transaction=lambda *, reason: calls.append(
            f"end_transaction:{reason}"
        ),
        begin_projection_prompt_context=lambda **_kwargs: calls.append("context_begin"),
        clear_projection_prompt_context=lambda *, reason: calls.append(
            f"context_clear:{reason}"
        ),
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: None,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    with pytest.raises(RuntimeError, match="build failed"):
        coordinator.load_all_cubes(
            [("A", cube)],
            cube_states={"A": cube},
            stack_order=["A"],
        )

    assert "context_begin" in calls
    assert "context_clear:full_workflow_projection_error" in calls
    assert calls.count("end_transaction:full_workflow_projection") == 1


def test_load_all_cubes_stops_when_hydration_fails() -> None:
    """Missing live definitions should block prompt migration and projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    cube = SimpleNamespace(buffer={"nodes": {"sampler": {"class_type": "KSampler"}}})
    live_error = error_mod.LiveNodeDefinitionError(
        operation="hydrate editor projection node definitions",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(class_type="KSampler"),
        ),
    )

    def _raise_hydration_error(**_kwargs: object) -> None:
        calls.append("hydrate")
        raise live_error

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: _Widget("new"),
        hydrate_node_definitions_for_projection=_raise_hydration_error,
        _build_behavior_snapshot=lambda **_kwargs: calls.append("snapshot"),
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    with pytest.raises(error_mod.LiveNodeDefinitionError):
        mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
            [("A", cube)],
            cube_states={"A": cube},
            stack_order=["A"],
        )

    assert calls == ["hydrate"]
    assert panel._cube_states == {"A": cube}
    assert panel._stack_order == ["A"]


def test_projection_metadata_retry_stops_when_issue_aliases_do_not_change() -> None:
    """Recoverable metadata retries should stop when no new bad cube is isolated."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    live_error = error_mod.LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Bad",),
                node_names=("resize_by_factor",),
            ),
        ),
    )

    def _register_projection_error(
        _error: object,
        *,
        reason: str,
        source: object,
    ) -> bool:
        """Record recoverable registration without changing errored aliases."""

        _ = reason, source
        calls.append("register")
        return True

    def _present_recoverable_error(
        _error: object,
        *,
        reason: str,
    ) -> None:
        """Record recoverable report presentation."""

        _ = reason
        calls.append("present")

    panel = SimpleNamespace(
        _cube_states={"Bad": object()},
        _stack_order=["Bad"],
        register_projection_live_node_definition_error=_register_projection_error,
        present_recoverable_live_node_definition_error=_present_recoverable_error,
        cube_runtime_error_aliases=lambda: (),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    def _raise_metadata_error(_aliases: frozenset[str]) -> None:
        calls.append("metadata")
        raise live_error

    with pytest.raises(error_mod.LiveNodeDefinitionError):
        coordinator._composition.runtime_issues.run_projection_metadata_step(
            workflow_id="workflow-a",
            reason="behavior_snapshot",
            action=_raise_metadata_error,
        )

    assert calls == ["metadata", "register", "present"]


def test_load_all_cubes_recovers_when_prompt_reconciliation_finds_bad_cube() -> None:
    """Cube-attributed prompt-link metadata failures should render error sections."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    good_cube = SimpleNamespace(buffer={"nodes": {"good": {"class_type": "Good"}}})
    bad_cube = SimpleNamespace(buffer={"nodes": {"bad": {"class_type": "Bad"}}})
    good_widget = _Widget("good")
    bad_widget = _Widget("bad-error")
    live_error = error_mod.LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Bad",),
                node_names=("resize_by_factor",),
            ),
        ),
    )
    errored_aliases: set[str] = set()

    def _reconcile(**kwargs: object) -> None:
        current_stack = kwargs.get("stack_order")
        current_aliases = (
            tuple(current_stack) if isinstance(current_stack, list) else ()
        )
        calls.append(f"reconcile:{current_aliases}")
        if "Bad" in current_aliases:
            raise live_error

    def _register(
        _error: object,
        *,
        reason: str,
        source: object,
    ) -> bool:
        calls.append(f"register:{reason}:{source}")
        errored_aliases.add("Bad")
        return True

    def _present_recoverable(
        error: object,
        *,
        reason: str,
    ) -> None:
        calls.append(f"present:{reason}:{error is live_error}")

    def _build_behavior_snapshot(**_kwargs: object) -> str:
        calls.append("snapshot")
        assert panel._stack_order == ["Good"]
        return "snapshot"

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        mainwindow=SimpleNamespace(workflow_session_service=SimpleNamespace()),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=_reconcile,
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda alias, _state: (
            good_widget if alias == "Good" else None
        ),
        _build_error_cube_widget=lambda alias, _state: (
            bad_widget if alias == "Bad" else None
        ),
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        register_projection_live_node_definition_error=_register,
        present_recoverable_live_node_definition_error=_present_recoverable,
        cube_runtime_error_aliases=lambda: tuple(sorted(errored_aliases)),
        begin_live_node_definition_report_projection=lambda: calls.append(
            "begin_reports"
        ),
        clear_projection_runtime_issues=lambda: calls.append("clear_issues"),
        _build_behavior_snapshot=_build_behavior_snapshot,
        _on_scroll_updated=lambda _value: calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("Good", good_cube), ("Bad", bad_cube)],
        cube_states={"Good": good_cube, "Bad": bad_cube},
        stack_order=["Good", "Bad"],
    )

    assert "register:prompt_link_reconciliation:projection" in calls
    assert calls.count("present:prompt_link_reconciliation:True") == 1
    assert calls.index("begin_reports") < calls.index(
        "present:prompt_link_reconciliation:True"
    )
    assert "reconcile:('Good',)" in calls
    assert panel.cube_widgets == {"Good": good_widget, "Bad": bad_widget}
    assert panel.cube_sections == {"Good": good_widget, "Bad": bad_widget}


def test_load_all_cubes_recovers_when_behavior_snapshot_finds_bad_cube() -> None:
    """Cube-attributed behavior snapshot failures should retry without bad cubes."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    good_cube = SimpleNamespace(buffer={"nodes": {"good": {"class_type": "Good"}}})
    bad_cube = SimpleNamespace(buffer={"nodes": {"bad": {"class_type": "Bad"}}})
    good_widget = _Widget("good")
    bad_widget = _Widget("bad-error")
    live_error = error_mod.LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Bad",),
                node_names=("resize_by_factor",),
            ),
        ),
    )
    errored_aliases: set[str] = set()

    def _register(
        _error: object,
        *,
        reason: str,
        source: object,
    ) -> bool:
        calls.append(f"register:{reason}:{source}")
        errored_aliases.add("Bad")
        return True

    def _present_recoverable(
        error: object,
        *,
        reason: str,
    ) -> None:
        calls.append(f"present:{reason}:{error is live_error}")

    def _build_behavior_snapshot(**_kwargs: object) -> str:
        current_stack = tuple(panel._stack_order or ())
        calls.append(f"snapshot:{current_stack}")
        if "Bad" in current_stack:
            raise live_error
        return "snapshot"

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        mainwindow=SimpleNamespace(workflow_session_service=SimpleNamespace()),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda alias, _state: (
            good_widget if alias == "Good" else None
        ),
        _build_error_cube_widget=lambda alias, _state: (
            bad_widget if alias == "Bad" else None
        ),
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        register_projection_live_node_definition_error=_register,
        present_recoverable_live_node_definition_error=_present_recoverable,
        cube_runtime_error_aliases=lambda: tuple(sorted(errored_aliases)),
        clear_projection_runtime_issues=lambda: calls.append("clear_issues"),
        _build_behavior_snapshot=_build_behavior_snapshot,
        _on_scroll_updated=lambda _value: calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("Good", good_cube), ("Bad", bad_cube)],
        cube_states={"Good": good_cube, "Bad": bad_cube},
        stack_order=["Good", "Bad"],
    )

    assert "register:behavior_snapshot:projection" in calls
    assert calls.count("present:behavior_snapshot:True") == 1
    assert "snapshot:('Good', 'Bad')" in calls
    assert "snapshot:('Good',)" in calls
    assert panel._stack_order == ["Good", "Bad"]
    assert panel.cube_widgets == {"Good": good_widget, "Bad": bad_widget}
