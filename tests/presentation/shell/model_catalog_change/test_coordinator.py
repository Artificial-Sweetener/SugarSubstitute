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

"""Tests for shell model-catalog change coordination."""

from __future__ import annotations

from typing import Any, cast

from substitute.domain.model_metadata import (
    BackendModelCatalogChangeEvent,
    parse_backend_model_catalog_change_event,
)
from substitute.presentation.shell.model_catalog_change_coordinator import (
    ModelCatalogChangeCoordinator,
)
from tests.support.execution import ImmediateTaskSubmitter, QueuedTaskSubmitter


def test_model_catalog_change_coordinator_invalidates_and_fans_out_work() -> None:
    """Invalidate caches and send each model-catalog follow-up to its owner."""

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
    event = _event()

    coordinator.handle_change(event)

    assert catalog.invalidated == ["loras"]
    assert rich_choices.invalidated == ["loras"]
    assert lora_refresh.calls == [("loras", event)]
    assert node_definitions.calls == [("LoraLoader",)]
    assert scoped_refresh.entries == event.added


def test_model_catalog_change_coordinator_cancels_pending_node_refresh_on_shutdown() -> (
    None
):
    """Cancel owner-scoped node-definition work during shutdown."""

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
    coordinator.handle_change(_event())
    assert len(submitter.handles) == 1
    assert submitter.cancellations[0].is_cancelled is False

    coordinator.shutdown()

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "model_catalog_change_shutdown"
    assert submitter.handles[0].cancel_reason == "model_catalog_change_shutdown"
    assert close_calls == ["closed"]
    assert scoped_refresh.shutdown_calls == 1


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


class _QueuedScopedRefresh:
    """Collect queued scoped metadata entries."""

    def __init__(self) -> None:
        """Initialize queued entry state."""

        self.entries: tuple[object, ...] = ()
        self.shutdown_calls = 0

    def queue_entries(self, entries: tuple[object, ...]) -> None:
        """Record queued entries."""

        self.entries = entries

    def shutdown(self) -> None:
        """Record one shutdown request."""

        self.shutdown_calls += 1


def _event() -> BackendModelCatalogChangeEvent:
    """Return a parsed supported model-catalog event."""

    event = parse_backend_model_catalog_change_event(
        {
            "schemaVersion": 1,
            "revision": "rev2",
            "previousRevision": "rev1",
            "generatedAt": "2026-05-26T12:00:01Z",
            "reason": "folder-changed",
            "kinds": ["loras"],
            "affectedNodeClasses": ["LoraLoader"],
            "added": [
                {
                    "kind": "loras",
                    "value": "style.safetensors",
                    "source": {
                        "rootId": "loras:0",
                        "relativePath": "style.safetensors",
                    },
                    "file": {"sizeBytes": 123, "modifiedAt": "2026-05-26T12:00:00Z"},
                }
            ],
            "removed": [],
            "modified": [],
        }
    )
    assert event is not None
    return event
