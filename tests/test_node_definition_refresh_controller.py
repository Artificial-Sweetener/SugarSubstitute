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

"""Verify live node-definition refresh coordination outside MainWindow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.application.ports import NodeDefinitionRefreshEvent
from substitute.presentation.shell import node_definition_refresh_controller


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)


class _Signal:
    """Provide a small Qt-like signal test double."""

    def __init__(self) -> None:
        """Create disconnected signal state."""

        self.callbacks: list[Callable[[object], None]] = []
        self.emitted: list[object] = []

    def connect(self, callback: Callable[[object], None]) -> None:
        """Record a connected callback."""

        self.callbacks.append(callback)

    def emit(self, event: object) -> None:
        """Record an emitted event and invoke connected callbacks."""

        self.emitted.append(event)
        for callback in self.callbacks:
            callback(event)


class _ObservableGateway:
    """Provide observable node-definition gateway behavior."""

    def __init__(self) -> None:
        """Create observer state."""

        self.observers: list[Callable[[NodeDefinitionRefreshEvent], None]] = []
        self.unsubscribe_count = 0

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no definitions for this subscription-only double."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no required definitions for this subscription-only double."""

        _ = node_class
        return {}

    def add_refresh_observer(
        self,
        observer: Callable[[NodeDefinitionRefreshEvent], None],
    ) -> Callable[[], None]:
        """Record observer registration and return an unsubscribe callback."""

        self.observers.append(observer)

        def unsubscribe() -> None:
            """Remove the observer once."""

            self.unsubscribe_count += 1
            self.observers.remove(observer)

        return unsubscribe


class _Timer:
    """Capture scheduled callbacks."""

    scheduled_callbacks: list[Callable[[], None]] = []

    @classmethod
    def singleShot(cls, _delay_ms: int, callback: Callable[[], None]) -> None:
        """Record a delayed callback."""

        cls.scheduled_callbacks.append(callback)


@pytest.fixture(autouse=True)
def timer_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace QTimer with a deterministic scheduler."""

    _Timer.scheduled_callbacks = []
    monkeypatch.setattr(node_definition_refresh_controller, "QTimer", _Timer)


def test_controller_bridges_observable_gateway_events_to_shell_signal() -> None:
    """Observable gateway refreshes should arrive through the shell signal."""

    gateway = _ObservableGateway()
    shell = SimpleNamespace(
        node_definition_gateway=gateway,
        node_definition_refreshed=_Signal(),
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-1"),
        active_editor_panel=None,
        active_override_manager=None,
    )

    controller = node_definition_refresh_controller.NodeDefinitionRefreshController(
        shell
    )
    event = NodeDefinitionRefreshEvent("KSampler", available=True)
    gateway.observers[0](event)

    assert shell.node_definition_refreshed.emitted == [event]
    controller.dispose()
    assert gateway.unsubscribe_count == 1
    assert gateway.observers == []


def test_queue_refresh_coalesces_available_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Available node-definition refreshes should drain in one UI callback."""

    drained: list[tuple[str, ...]] = []
    shell = SimpleNamespace(
        node_definition_gateway=object(),
        node_definition_refreshed=_Signal(),
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-1"),
        active_editor_panel=None,
        active_override_manager=None,
    )
    controller = node_definition_refresh_controller.NodeDefinitionRefreshController(
        shell
    )
    monkeypatch.setattr(
        controller,
        "refresh_surfaces",
        lambda *, refreshed_node_classes: drained.append(refreshed_node_classes),
    )

    controller.queue_refresh(NodeDefinitionRefreshEvent("KSampler", available=True))
    controller.queue_refresh(NodeDefinitionRefreshEvent("VAELoader", available=True))
    controller.queue_refresh(NodeDefinitionRefreshEvent("OfflineNode", available=False))

    assert len(_Timer.scheduled_callbacks) == 1

    _Timer.scheduled_callbacks[0]()

    assert drained == [("KSampler", "VAELoader")]
    assert controller._rebuild_scheduled is False
    assert controller._pending_node_classes == set()


def test_refresh_surfaces_reconciles_every_loaded_panel_before_toolbar() -> None:
    """Drained refreshes should update loaded panels without active-only ownership."""

    calls: list[tuple[str, object]] = []

    class _Panel:
        def refresh_node_behavior_state(self, **kwargs: object) -> None:
            calls.append(("refresh_node_behavior_state", kwargs))

        def reconcile_choice_fields_after_node_definition_update(
            self,
            **kwargs: object,
        ) -> object:
            calls.append(("reconcile_choice_fields", kwargs))
            return SimpleNamespace(fallback_node_classes=())

    class _Manager:
        def rebuild_override_menu(self) -> None:
            calls.append(("rebuild_override_menu", None))

        def rebuild_active_override_controls(self) -> None:
            calls.append(("rebuild_active_override_controls", None))

    class _CanvasRouteController:
        def refresh_input_canvas_availability(self) -> None:
            """Record semantic Input capability refresh after metadata arrives."""

            calls.append(("refresh_input_canvas_availability", None))

    shell = SimpleNamespace(
        node_definition_gateway=object(),
        node_definition_refreshed=_Signal(),
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-1"),
        editor_panels={"workflow-1": _Panel(), "workflow-2": _Panel()},
        active_editor_panel=None,
        active_override_manager=_Manager(),
        canvas_route_controller=_CanvasRouteController(),
    )
    controller = node_definition_refresh_controller.NodeDefinitionRefreshController(
        shell
    )

    controller.refresh_surfaces(refreshed_node_classes=("KSampler",))

    assert calls == [
        (
            "refresh_node_behavior_state",
            {
                "reason": "model_options_changed",
                "use_cached_snapshot": False,
            },
        ),
        ("reconcile_choice_fields", {"refreshed_node_classes": ("KSampler",)}),
        (
            "refresh_node_behavior_state",
            {
                "reason": "model_options_changed",
                "use_cached_snapshot": False,
            },
        ),
        ("reconcile_choice_fields", {"refreshed_node_classes": ("KSampler",)}),
        ("refresh_input_canvas_availability", None),
        ("rebuild_override_menu", None),
        ("rebuild_active_override_controls", None),
    ]


def test_refresh_surfaces_uses_projection_only_for_reported_structural_fallback() -> (
    None
):
    """Only classes rejected by in-place reconciliation should rebuild projection."""

    calls: list[tuple[str, object]] = []

    class _Panel:
        def refresh_projection_after_node_definition_update(
            self,
            **kwargs: object,
        ) -> bool:
            calls.append(("refresh_projection_after_node_definition_update", kwargs))
            return True

        def refresh_node_behavior_state(self, **kwargs: object) -> None:
            calls.append(("refresh_node_behavior_state", kwargs))

        def reconcile_choice_fields_after_node_definition_update(
            self,
            **kwargs: object,
        ) -> object:
            calls.append(("reconcile_choice_fields", kwargs))
            return SimpleNamespace(
                fallback_node_classes=("SimpleSyrup.ResizeImageToTarget",)
            )

    class _Manager:
        def rebuild_override_menu(self) -> None:
            calls.append(("rebuild_override_menu", None))

        def rebuild_active_override_controls(self) -> None:
            calls.append(("rebuild_active_override_controls", None))

    shell = SimpleNamespace(
        node_definition_gateway=object(),
        node_definition_refreshed=_Signal(),
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-1"),
        editor_panels={"workflow-1": _Panel()},
        active_editor_panel=None,
        active_override_manager=_Manager(),
    )
    controller = node_definition_refresh_controller.NodeDefinitionRefreshController(
        shell
    )

    controller.refresh_surfaces(
        refreshed_node_classes=("SimpleSyrup.ResizeImageToTarget",)
    )

    assert calls == [
        (
            "refresh_node_behavior_state",
            {
                "reason": "model_options_changed",
                "use_cached_snapshot": False,
            },
        ),
        (
            "reconcile_choice_fields",
            {"refreshed_node_classes": ("SimpleSyrup.ResizeImageToTarget",)},
        ),
        (
            "refresh_projection_after_node_definition_update",
            {"refreshed_node_classes": ("SimpleSyrup.ResizeImageToTarget",)},
        ),
        ("rebuild_override_menu", None),
        ("rebuild_active_override_controls", None),
    ]


def test_refresh_surfaces_falls_back_when_panel_has_no_reconciler() -> None:
    """Legacy or non-model panels should retain structural refresh safety."""

    calls: list[tuple[str, object]] = []

    class _Panel:
        def refresh_projection_after_node_definition_update(
            self,
            **kwargs: object,
        ) -> bool:
            calls.append(("refresh_projection_after_node_definition_update", kwargs))
            return False

        def refresh_node_behavior_state(self, **kwargs: object) -> None:
            calls.append(("refresh_node_behavior_state", kwargs))

    class _Manager:
        def rebuild_override_menu(self) -> None:
            calls.append(("rebuild_override_menu", None))

        def rebuild_active_override_controls(self) -> None:
            calls.append(("rebuild_active_override_controls", None))

    shell = SimpleNamespace(
        node_definition_gateway=object(),
        node_definition_refreshed=_Signal(),
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-1"),
        editor_panels={"workflow-1": _Panel()},
        active_editor_panel=None,
        active_override_manager=_Manager(),
    )
    controller = node_definition_refresh_controller.NodeDefinitionRefreshController(
        shell
    )

    controller.refresh_surfaces(refreshed_node_classes=("UnrelatedNode",))

    assert calls == [
        (
            "refresh_node_behavior_state",
            {
                "reason": "model_options_changed",
                "use_cached_snapshot": False,
            },
        ),
        (
            "refresh_projection_after_node_definition_update",
            {"refreshed_node_classes": ("UnrelatedNode",)},
        ),
        ("rebuild_override_menu", None),
        ("rebuild_active_override_controls", None),
    ]


def test_main_window_delegates_node_definition_refresh_lifecycle() -> None:
    """Verify MainWindow no longer owns node-definition refresh internals."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")
    composition_source = (
        MAIN_WINDOW_SOURCE.parent / "main_window_composition.py"
    ).read_text(encoding="utf-8")
    reload_lifecycle_source = (
        MAIN_WINDOW_SOURCE.parent / "shell_reload_lifecycle_controller.py"
    ).read_text(encoding="utf-8")

    assert "NodeDefinitionRefreshController(" in composition_source
    assert "def _subscribe_node_definition_refreshes" not in source
    assert "def _queue_node_definition_refresh" not in source
    assert "def _drain_node_definition_refresh_events" not in source
    assert "def _refresh_active_overrides_after_node_definition_update" not in source
    assert "node_definition_refresh_controller.dispose()" in reload_lifecycle_source
