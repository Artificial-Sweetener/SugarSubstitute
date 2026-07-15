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

"""Tests for live model catalog change events and scoped refresh wiring."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.execution import ExecutionContext, TaskIdentity
from tests.execution_testing import (
    ImmediateTaskSubmitter,
    QueuedTaskSubmitter,
)
from substitute.application.model_metadata import (
    ModelMetadataRefreshSummary,
    ScopedMetadataRefreshService,
)
from substitute.domain.model_metadata import (
    BackendFingerprint,
    BackendLocalPreview,
    BackendModelCatalogChangedEntry,
    BackendModelCatalogChangedFile,
    BackendModelCatalogChangedSource,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    FingerprintStatus,
    parse_backend_model_catalog_change_event,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.model_catalog_event_listener import (
    ModelCatalogEventListener,
)
from substitute.presentation.shell.model_catalog_change_coordinator import (
    ModelCatalogChangeCoordinator,
)


class _Backend:
    """Return configured backend catalog entries."""

    def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
        """Store fake catalog entries."""

        self.entries = entries
        self.calls: list[tuple[str, ...]] = []

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return entries matching requested kinds."""

        _ = refresh
        self.calls.append(kinds)
        return tuple(entry for entry in self.entries if entry.kind in kinds)


class _RefreshService:
    """Collect scoped refresh requests."""

    def __init__(self) -> None:
        """Initialize empty refresh call list."""

        self.calls: list[tuple[BackendModelCatalogEntry, ...]] = []

    def refresh_entries(
        self,
        models: tuple[BackendModelCatalogEntry, ...],
        progress: object,
        *,
        cancellation_token: object | None = None,
    ) -> ModelMetadataRefreshSummary:
        """Record models selected for refresh."""

        _ = (progress, cancellation_token)
        self.calls.append(models)
        return ModelMetadataRefreshSummary(discovered=len(models), enriched=len(models))


class _UpdateSink:
    """Accept metadata updates without side effects."""

    def emit_model_updated(self, event: object) -> None:
        """Ignore one metadata update."""

        _ = event


class _Catalog:
    """Collect catalog invalidations."""

    def __init__(self) -> None:
        """Initialize invalidation list."""

        self.invalidated: list[str] = []

    def invalidate(self, kind: str | None = None) -> None:
        """Record invalidated kinds."""

        if kind is not None:
            self.invalidated.append(kind)


class _RichChoices:
    """Collect rich choice invalidations."""

    def __init__(self) -> None:
        """Initialize invalidation list."""

        self.invalidated: list[str] = []

    def invalidate(self, kind: str) -> None:
        """Record invalidated kinds."""

        self.invalidated.append(kind)


class _NodeDefinitions:
    """Collect targeted node-definition refreshes."""

    def __init__(self) -> None:
        """Initialize refresh call list."""

        self.calls: list[tuple[str, ...]] = []

    def refresh_node_definitions(
        self, node_classes: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Record requested node classes."""

        self.calls.append(node_classes)
        return node_classes


class _LoraRefresh:
    """Collect LoRA catalog refresh requests."""

    def __init__(self) -> None:
        """Initialize refresh call list."""

        self.calls: list[tuple[str, object | None]] = []

    def request_refresh(self, kind: str, context: object | None = None) -> None:
        """Record requested refreshes."""

        self.calls.append((kind, context))


def test_parse_backend_model_catalog_change_event_accepts_valid_payload() -> None:
    """App-side parser should accept the backend model catalog event contract."""

    event = parse_backend_model_catalog_change_event(_event_payload())

    assert event is not None
    assert event.revision == "rev2"
    assert event.kinds == ("loras",)
    assert event.affected_node_classes == ("LoraLoader",)
    assert event.added[0].source.relative_path == "style.safetensors"
    assert event.enrichable_entries == event.added


def test_parse_backend_model_catalog_change_event_rejects_bad_schema() -> None:
    """Malformed schema versions are ignored instead of partially parsed."""

    payload = _event_payload()
    payload["schemaVersion"] = 2

    assert parse_backend_model_catalog_change_event(payload) is None


def test_model_catalog_event_listener_dispatches_valid_events_once() -> None:
    """Listener dispatch should ignore unrelated and duplicate websocket events."""

    updates: list[str] = []
    listener = ModelCatalogEventListener(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        on_update=lambda event: updates.append(event.revision),
    )

    listener._handle_text_message('{"type": "unrelated", "data": {}}')  # noqa: SLF001
    listener._handle_text_message(  # noqa: SLF001
        '{"type": "substitute_model_catalog_changed", "data": '
        + _json_payload_text()
        + "}"
    )
    listener._handle_text_message(  # noqa: SLF001
        '{"type": "substitute_model_catalog_changed", "data": '
        + _json_payload_text()
        + "}"
    )

    assert updates == ["rev2"]


def test_model_catalog_event_listener_start_stop_uses_task_factory() -> None:
    """Listener lifecycle should be delegated to the injected long-lived task factory."""

    handle = _ListenerTaskHandle()
    task_calls: list[dict[str, object]] = []

    def task_factory(
        identity: TaskIdentity,
        context: ExecutionContext,
        work: object,
        thread_name: str,
    ) -> _ListenerTaskHandle:
        """Record one model catalog listener task request."""

        task_calls.append(
            {
                "identity": identity,
                "context": context,
                "work": work,
                "thread_name": thread_name,
            }
        )
        return handle

    listener = ModelCatalogEventListener(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        on_update=lambda _event: None,
        task_factory=task_factory,
    )

    listener.start()
    listener.start()

    assert listener.is_running is True
    assert len(task_calls) == 1
    assert task_calls[0]["thread_name"] == "substitute-model-catalog-event-listener"
    identity = cast(TaskIdentity, task_calls[0]["identity"])
    context = cast(ExecutionContext, task_calls[0]["context"])
    assert identity.domain == "model_catalog_event_listener"
    assert context.lane == "backend_event_listener"

    listener.stop()

    assert handle.stop_reasons == ["model_catalog_event_listener_stop"]
    assert listener.is_running is False


def test_scoped_metadata_refresh_deduplicates_and_matches_backend_entries() -> None:
    """Scoped refresh should enrich current backend entries once per changed file."""

    backend_entry = _backend_entry("style.safetensors")
    backend = _Backend((backend_entry,))
    refresh_service = _RefreshService()
    service = ScopedMetadataRefreshService(
        backend=cast(Any, backend),
        refresh_service=cast(Any, refresh_service),
        update_sink=cast(Any, _UpdateSink()),
        submitter=ImmediateTaskSubmitter(),
        batch_size=4,
    )
    changed = _changed_entry("style.safetensors")

    service.queue_entries((changed, changed))

    assert backend.calls == [("loras",)]
    assert refresh_service.calls == [(backend_entry,)]


def test_model_catalog_change_coordinator_invalidates_and_fans_out_work() -> None:
    """Coordinator should invalidate caches, refresh nodes, and queue enrichment."""

    catalog = _Catalog()
    rich_choices = _RichChoices()
    node_definitions = _NodeDefinitions()
    lora_refresh = _LoraRefresh()
    scoped_refresh = cast(Any, _QueuedScopedRefresh())
    coordinator = ModelCatalogChangeCoordinator(
        model_catalog_service=cast(Any, catalog),
        model_choice_resolver=cast(Any, rich_choices),
        node_definition_gateway=node_definitions,
        lora_refresh_coordinator=lora_refresh,
        scoped_metadata_refresh_service=scoped_refresh,
        submitter=ImmediateTaskSubmitter(),
    )
    event = parse_backend_model_catalog_change_event(_event_payload())
    assert event is not None

    coordinator.handle_change(event)

    assert catalog.invalidated == ["loras"]
    assert rich_choices.invalidated == ["loras"]
    assert lora_refresh.calls == [("loras", event)]
    assert node_definitions.calls == [("LoraLoader",)]
    assert scoped_refresh.entries == event.added


def test_model_catalog_change_coordinator_cancels_pending_node_refresh_on_shutdown() -> (
    None
):
    """Coordinator shutdown should cancel owner-scoped node-definition work."""

    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    scoped_refresh = cast(Any, _QueuedScopedRefresh())
    coordinator = ModelCatalogChangeCoordinator(
        model_catalog_service=cast(Any, _Catalog()),
        model_choice_resolver=cast(Any, _RichChoices()),
        node_definition_gateway=_NodeDefinitions(),
        lora_refresh_coordinator=_LoraRefresh(),
        scoped_metadata_refresh_service=scoped_refresh,
        submitter=submitter,
        close_submitter=lambda: close_calls.append("closed"),
    )
    event = parse_backend_model_catalog_change_event(_event_payload())
    assert event is not None

    coordinator.handle_change(event)
    assert len(submitter.handles) == 1
    assert submitter.cancellations[0].is_cancelled is False

    coordinator.shutdown()

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "model_catalog_change_shutdown"
    assert submitter.handles[0].cancel_reason == "model_catalog_change_shutdown"
    assert close_calls == ["closed"]
    assert scoped_refresh.shutdown_calls == 1


class _QueuedScopedRefresh:
    """Collect queued scoped metadata entries."""

    def __init__(self) -> None:
        """Initialize queued entries."""

        self.entries: tuple[BackendModelCatalogChangedEntry, ...] = ()
        self.shutdown_calls = 0

    def queue_entries(
        self,
        entries: tuple[BackendModelCatalogChangedEntry, ...],
    ) -> None:
        """Record queued entries."""

        self.entries = entries

    def shutdown(self) -> None:
        """Ignore shutdown in tests."""

        self.shutdown_calls += 1


class _ListenerTaskHandle:
    """Record long-lived listener stop requests."""

    def __init__(self) -> None:
        """Initialize an active fake listener task handle."""

        self.stop_reasons: list[str] = []
        self._is_finished = False

    @property
    def is_finished(self) -> bool:
        """Return whether this fake handle has stopped."""

        return self._is_finished

    def stop(self, *, reason: str) -> None:
        """Record one stop request and mark the handle finished."""

        self.stop_reasons.append(reason)
        self._is_finished = True


def _changed_entry(value: str) -> BackendModelCatalogChangedEntry:
    """Build one changed-entry DTO."""

    return BackendModelCatalogChangedEntry(
        kind="loras",
        value=value,
        source=BackendModelCatalogChangedSource(
            root_id="loras:0",
            relative_path=value,
        ),
        file=BackendModelCatalogChangedFile(
            size_bytes=123,
            modified_at="2026-05-26T12:00:00Z",
        ),
    )


def _backend_entry(value: str) -> BackendModelCatalogEntry:
    """Build one backend catalog entry for scoped refresh tests."""

    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target:loras:{value}",
        kind="loras",
        value=value,
        display_name="style",
        source=BackendModelSource(root_id="loras:0", relative_path=value),
        file=BackendModelFile(
            extension=".safetensors",
            size_bytes=123,
            modified_at="2026-05-26T12:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.MISSING,
            sha256=None,
            source=None,
            computed_at=None,
            error=None,
        ),
        sidecar=BackendSidecar(
            found=False,
            model_id=None,
            model_version_id=None,
            sha256=None,
            activation_text=None,
            description=None,
            base_model=None,
            modified_at=None,
        ),
        local_preview=BackendLocalPreview(
            available=False,
            preview_id=None,
            url=None,
            source=None,
            modified_at=None,
            width=None,
            height=None,
        ),
    )


def _event_payload() -> dict[str, object]:
    """Build one backend model catalog event payload."""

    return {
        "schemaVersion": 1,
        "revision": "rev2",
        "previousRevision": "rev1",
        "generatedAt": "2026-05-26T12:00:01Z",
        "reason": "folder-changed",
        "kinds": ["loras"],
        "affectedNodeClasses": ["LoraLoader"],
        "added": [_entry_payload("style.safetensors")],
        "removed": [],
        "modified": [],
    }


def _entry_payload(value: str) -> dict[str, object]:
    """Build one changed-entry payload."""

    return {
        "kind": "loras",
        "value": value,
        "source": {"rootId": "loras:0", "relativePath": value},
        "file": {
            "sizeBytes": 123,
            "modifiedAt": "2026-05-26T12:00:00Z",
        },
    }


def _json_payload_text() -> str:
    """Return event payload JSON without importing a test-only fixture library."""

    import json

    return json.dumps(_event_payload())
