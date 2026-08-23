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

"""Tests for Comfy model-catalog listener event handling and lifecycle."""

from __future__ import annotations

import json
from typing import cast

from substitute.application.execution import ExecutionContext, TaskIdentity
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.model_catalog_event_listener import (
    ModelCatalogEventListener,
)


def test_model_catalog_event_listener_dispatches_valid_events_once() -> None:
    """Ignore unrelated and duplicate websocket events."""

    updates: list[str] = []
    listener = ModelCatalogEventListener(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        on_update=lambda event: updates.append(event.revision),
    )

    listener._handle_text_message('{"type": "unrelated", "data": {}}')  # noqa: SLF001
    listener._handle_text_message(  # noqa: SLF001
        '{"type": "substitute_model_catalog_changed", "data": '
        + json.dumps(_event_payload())
        + "}"
    )
    listener._handle_text_message(  # noqa: SLF001
        '{"type": "substitute_model_catalog_changed", "data": '
        + json.dumps(_event_payload())
        + "}"
    )

    assert updates == ["rev2"]


def test_model_catalog_event_listener_start_stop_uses_task_factory() -> None:
    """Delegate listener lifecycle to the injected long-lived task factory."""

    handle = _ListenerTaskHandle()
    task_calls: list[dict[str, object]] = []

    def task_factory(
        identity: TaskIdentity,
        context: ExecutionContext,
        work: object,
        thread_name: str,
    ) -> _ListenerTaskHandle:
        """Record one model-catalog listener task request."""

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


def _event_payload() -> dict[str, object]:
    """Build one supported backend model-catalog event payload."""

    return {
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
                "source": {"rootId": "loras:0", "relativePath": "style.safetensors"},
                "file": {"sizeBytes": 123, "modifiedAt": "2026-05-26T12:00:00Z"},
            }
        ],
        "removed": [],
        "modified": [],
    }
