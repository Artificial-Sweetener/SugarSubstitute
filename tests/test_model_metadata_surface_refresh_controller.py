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

"""Verify model metadata surface refresh coordination outside MainWindow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.model_metadata import (
    ModelCatalogSnapshot,
    ModelMetadataRefreshEvent,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.presentation.shell import model_metadata_surface_refresh_controller


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)


class _FakeSnapshotRefreshCoordinator:
    """Capture LoRA snapshot refresh requests."""

    def __init__(
        self,
        *,
        model_catalog: object,
        completed: Callable[[ModelCatalogSnapshot, object | None], None],
        parent: object | None,
        submitter: object,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Store construction collaborators."""

        self.model_catalog = model_catalog
        self.completed = completed
        self.parent = parent
        self.submitter = submitter
        self.close_submitter = close_submitter
        self.requests: list[tuple[str, object | None]] = []

    def request_refresh(self, kind: str, context: object | None = None) -> None:
        """Record a requested refresh."""

        self.requests.append((kind, context))


class _Timer:
    """Capture retry timers."""

    single_shots: list[tuple[int, Callable[[], None]]] = []

    @classmethod
    def singleShot(cls, delay_ms: int, callback: Callable[[], None]) -> None:
        """Record one delayed callback."""

        cls.single_shots.append((delay_ms, callback))


@pytest.fixture(autouse=True)
def controller_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace coordinator and timer dependencies with deterministic fakes."""

    _Timer.single_shots = []
    monkeypatch.setattr(
        model_metadata_surface_refresh_controller,
        "ModelCatalogSnapshotRefreshCoordinator",
        _FakeSnapshotRefreshCoordinator,
    )
    monkeypatch.setattr(model_metadata_surface_refresh_controller, "QTimer", _Timer)


def _event(
    kind: str = "loras",
    *,
    thumbnail_updated: bool = True,
) -> ModelMetadataRefreshEvent:
    """Create one metadata refresh event."""

    return ModelMetadataRefreshEvent(
        kind=kind,
        value="models/base.safetensors",
        relative_path="models/base.safetensors",
        sha256="ABC123",
        provider_status="found",
        thumbnail_updated=thumbnail_updated,
    )


def _shell(*, can_report_lora_absence: bool = True) -> SimpleNamespace:
    """Create a shell test double for metadata refreshes."""

    return SimpleNamespace(
        model_catalog_service=SimpleNamespace(invalidations=[]),
        model_choice_resolver=SimpleNamespace(invalidations=[]),
        prompt_lora_catalog_service=SimpleNamespace(
            can_report_lora_absence=lambda: can_report_lora_absence,
        ),
        _lora_metadata_refresh_coordinator=SimpleNamespace(adaptations=[]),
        editor_panels={},
    )


def _controller(
    shell: SimpleNamespace | None = None,
    *,
    retry_delays_ms: tuple[int, ...] = (2_000, 7_000),
) -> model_metadata_surface_refresh_controller.ModelMetadataSurfaceRefreshController:
    """Create a controller with list-recording shell collaborators."""

    chosen_shell = shell or _shell()
    chosen_shell.model_catalog_service.invalidate = (
        chosen_shell.model_catalog_service.invalidations.append
    )
    chosen_shell.model_choice_resolver.invalidate = (
        chosen_shell.model_choice_resolver.invalidations.append
    )
    chosen_shell._lora_metadata_refresh_coordinator.request_lora_snapshot_adaptation = (
        chosen_shell._lora_metadata_refresh_coordinator.adaptations.append
    )
    return (
        model_metadata_surface_refresh_controller.ModelMetadataSurfaceRefreshController(
            chosen_shell,
            parent=None,
            retry_delays_ms=retry_delays_ms,
            snapshot_refresh_submitter=ImmediateTaskSubmitter(),
        )
    )


def test_invalid_metadata_events_are_ignored() -> None:
    """Invalid metadata events should not touch catalog or editor state."""

    shell = _shell()
    controller = _controller(shell)

    controller.handle_model_metadata_updated(object())

    assert shell.model_catalog_service.invalidations == []
    assert shell._lora_metadata_refresh_coordinator.adaptations == []


def test_non_lora_metadata_invalidates_and_targets_model_surfaces() -> None:
    """Non-LoRA metadata events should invalidate and use targeted picker refresh."""

    panel_calls: list[tuple[str, str]] = []

    class _Panel:
        def refresh_model_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            panel_calls.append(("targeted", event.value))
            return 2

    shell = _shell()
    shell.editor_panels = {"workflow-1": _Panel()}
    controller = _controller(shell)
    event = _event("checkpoints")

    controller.handle_model_metadata_updated(event)

    assert shell.model_catalog_service.invalidations == ["checkpoints"]
    assert shell.model_choice_resolver.invalidations == ["checkpoints"]
    assert panel_calls == [("targeted", "models/base.safetensors")]


def test_non_lora_thumbnail_update_clears_model_thumbnail_cache_before_refresh() -> (
    None
):
    """Thumbnail update events should clear picker pixmaps before targeted refresh."""

    panel_calls: list[tuple[str, str]] = []

    class _Panel:
        def clear_model_thumbnail_caches_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            panel_calls.append(("clear", event.value))
            return 1

        def refresh_model_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            panel_calls.append(("refresh", event.value))
            return 1

    shell = _shell()
    shell.editor_panels = {"workflow-1": _Panel()}
    controller = _controller(shell)
    event = _event("checkpoints")

    controller.handle_model_metadata_updated(event)

    assert panel_calls == [
        ("clear", "models/base.safetensors"),
        ("refresh", "models/base.safetensors"),
    ]


def test_non_lora_metadata_update_preserves_model_thumbnail_cache() -> None:
    """Non-thumbnail metadata events should refresh state without clearing pixmaps."""

    panel_calls: list[tuple[str, str]] = []

    class _Panel:
        def clear_model_thumbnail_caches_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            panel_calls.append(("clear", event.value))
            return 1

        def refresh_model_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            panel_calls.append(("refresh", event.value))
            return 1

    shell = _shell()
    shell.editor_panels = {"workflow-1": _Panel()}
    controller = _controller(shell)
    event = _event("checkpoints", thumbnail_updated=False)

    controller.handle_model_metadata_updated(event)

    assert panel_calls == [("refresh", "models/base.safetensors")]


def test_lora_metadata_requests_canonical_snapshot_refresh() -> None:
    """LoRA metadata events should request async canonical LoRA snapshot refresh."""

    shell = _shell()
    controller = _controller(shell)
    event = _event("loras")

    controller.handle_model_metadata_updated(event)

    assert shell.model_catalog_service.invalidations == []
    lora_refresh_coordinator = cast(
        _FakeSnapshotRefreshCoordinator,
        controller.lora_refresh_coordinator,
    )
    assert lora_refresh_coordinator.requests == [("loras", event)]


def test_lora_snapshot_callback_fans_out_shared_generation() -> None:
    """Canonical LoRA snapshots should feed rich choices and prompt LoRA adaptation."""

    panel_calls: list[str] = []

    class _Panel:
        def refresh_model_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            panel_calls.append(event.value)
            return 1

    shell = _shell()
    shell.editor_panels = {"workflow-1": _Panel()}
    controller = _controller(shell)
    event = _event("loras")
    snapshot = ModelCatalogSnapshot(kind="loras", items=(), generation=7)

    controller.handle_lora_model_catalog_snapshot_refreshed(snapshot, event)

    assert shell.model_choice_resolver.invalidations == ["loras"]
    assert shell._lora_metadata_refresh_coordinator.adaptations == [snapshot]
    assert panel_calls == ["models/base.safetensors"]


def test_lora_thumbnail_update_clears_prompt_cache_before_snapshot_adaptation() -> None:
    """LoRA thumbnail events should clear prompt pixmaps before LoRA surface fanout."""

    calls: list[str] = []

    class _Panel:
        def clear_model_thumbnail_caches_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            calls.append(f"clear-model:{event.value}")
            return 1

        def clear_lora_thumbnail_caches(self) -> int:
            calls.append("clear-lora")
            return 2

        def refresh_model_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            calls.append(f"refresh:{event.value}")
            return 1

    shell = _shell()
    shell.editor_panels = {"workflow-1": _Panel()}
    controller = _controller(shell)
    snapshot = ModelCatalogSnapshot(kind="loras", items=(), generation=7)

    def adapt(snapshot: ModelCatalogSnapshot) -> None:
        calls.append(f"adapt:{snapshot.generation}")
        shell._lora_metadata_refresh_coordinator.adaptations.append(snapshot)

    shell._lora_metadata_refresh_coordinator.request_lora_snapshot_adaptation = adapt

    controller.handle_lora_model_catalog_snapshot_refreshed(snapshot, _event("loras"))

    assert calls == [
        "clear-model:models/base.safetensors",
        "clear-lora",
        "adapt:7",
        "refresh:models/base.safetensors",
    ]


def test_lora_metadata_update_preserves_prompt_thumbnail_cache() -> None:
    """LoRA metadata events without thumbnail changes should not clear prompt pixmaps."""

    calls: list[str] = []

    class _Panel:
        def clear_lora_thumbnail_caches(self) -> int:
            calls.append("clear-lora")
            return 1

        def refresh_model_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> int:
            calls.append(f"refresh:{event.value}")
            return 1

    shell = _shell()
    shell.editor_panels = {"workflow-1": _Panel()}
    controller = _controller(shell)
    snapshot = ModelCatalogSnapshot(kind="loras", items=(), generation=7)

    controller.handle_lora_model_catalog_snapshot_refreshed(
        snapshot,
        _event("loras", thumbnail_updated=False),
    )

    assert calls == ["refresh:models/base.safetensors"]


def test_initial_lora_model_catalog_refresh_is_requested_once() -> None:
    """Restored prompt editors should get one async LoRA metadata pass."""

    controller = _controller(_shell(can_report_lora_absence=True))

    controller.request_initial_lora_model_catalog_refresh("active_surface_complete")
    controller.request_initial_lora_model_catalog_refresh("initial_editor_cubes")

    lora_refresh_coordinator = cast(
        _FakeSnapshotRefreshCoordinator,
        controller.lora_refresh_coordinator,
    )
    assert lora_refresh_coordinator.requests == [("loras", "active_surface_complete")]


def test_initial_lora_model_catalog_refresh_retries_until_authoritative() -> None:
    """Startup LoRA refresh should retry while cache is bootstrap-only."""

    controller = _controller(_shell(can_report_lora_absence=False))

    controller.request_initial_lora_model_catalog_refresh("active_surface_complete")

    lora_refresh_coordinator = cast(
        _FakeSnapshotRefreshCoordinator,
        controller.lora_refresh_coordinator,
    )
    assert lora_refresh_coordinator.requests == [("loras", "active_surface_complete")]
    assert _Timer.single_shots[0][0] == 2_000
    assert controller._initial_lora_refresh_retry_attempt == 1


def test_lora_metadata_before_editor_hydration_is_safe() -> None:
    """Metadata events should be safe before deferred editor panels exist."""

    shell = _shell()
    shell.editor_panels = {}
    controller = _controller(shell)

    controller.handle_model_metadata_updated(_event("loras"))

    assert shell.model_catalog_service.invalidations == []
    lora_refresh_coordinator = cast(
        _FakeSnapshotRefreshCoordinator,
        controller.lora_refresh_coordinator,
    )
    assert lora_refresh_coordinator.requests == [("loras", _event("loras"))]


def test_main_window_delegates_model_metadata_surface_refresh() -> None:
    """Verify MainWindow no longer owns model metadata surface refresh internals."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")
    composition_source = (
        MAIN_WINDOW_SOURCE.parent / "main_window_composition.py"
    ).read_text(encoding="utf-8")

    assert "ModelMetadataSurfaceRefreshController(" in composition_source
    assert "def handle_model_metadata_updated" not in source
    assert "def _handle_lora_model_catalog_snapshot_refreshed" not in source
    assert "def _request_initial_lora_model_catalog_refresh" not in source
    assert "def _lora_catalog_needs_authoritative_startup_refresh" not in source
