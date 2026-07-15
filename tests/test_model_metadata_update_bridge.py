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

"""Tests for GUI-thread model metadata update bridging."""

from __future__ import annotations

from pathlib import Path
from threading import Thread, get_ident
from typing import cast

from PySide6.QtWidgets import QApplication

from substitute.application.model_metadata import ModelMetadataRefreshEvent
from substitute.presentation.shell.model_metadata_update_bridge import (
    ModelMetadataUpdateBridge,
)


def test_bridge_emits_immediately_when_not_coalescing() -> None:
    """Normal bridge behavior should emit each update immediately."""

    bridge = ModelMetadataUpdateBridge()
    received: list[ModelMetadataRefreshEvent] = []
    bridge.model_updated.connect(received.append)
    event = _event("checkpoint", "a")

    bridge.emit_model_updated(event)

    assert received == [event]


def test_bridge_coalesces_until_flush() -> None:
    """Startup coalescing should retain only the latest event per key."""

    bridge = ModelMetadataUpdateBridge()
    received: list[ModelMetadataRefreshEvent] = []
    bridge.model_updated.connect(received.append)
    first = _event("checkpoint", "a")
    latest = _event("checkpoint", "b")
    other = _event("vae", "c")

    bridge.begin_startup_coalescing()
    bridge.emit_model_updated(first)
    bridge.emit_model_updated(latest)
    bridge.emit_model_updated(other)

    assert received == []

    bridge.flush_startup_coalescing()

    assert received == [latest, other]


def test_bridge_coalesces_worker_thread_updates_on_owner_thread() -> None:
    """Worker-originated metadata updates should publish on the Qt owner thread."""

    app = _app()
    bridge = ModelMetadataUpdateBridge()
    received: list[ModelMetadataRefreshEvent] = []
    delivery_thread_ids: list[int] = []

    def record(event: object) -> None:
        """Record one delivered event and the thread that handled it."""

        assert isinstance(event, ModelMetadataRefreshEvent)
        received.append(event)
        delivery_thread_ids.append(get_ident())

    bridge.model_updated.connect(record)
    first = _event("checkpoint", "a")
    latest = _event("checkpoint", "b", thumbnail_updated=True)
    main_thread_id = get_ident()

    bridge.begin_startup_coalescing()

    def emit_from_worker() -> None:
        """Emit stale then current events from a background thread."""

        bridge.emit_model_updated(first)
        bridge.emit_model_updated(latest)

    worker = Thread(target=emit_from_worker, name="metadata-bridge-test")
    worker.start()
    worker.join(timeout=2.0)
    assert not worker.is_alive()

    app.processEvents()
    assert received == []

    bridge.end_startup_coalescing()
    app.processEvents()

    assert received == [latest]
    assert delivery_thread_ids == [main_thread_id]


def test_bridge_coalesces_by_kind_and_preserves_thumbnail_updates() -> None:
    """Startup coalescing should not lose thumbnail refresh information."""

    bridge = ModelMetadataUpdateBridge()
    received: list[ModelMetadataRefreshEvent] = []
    bridge.model_updated.connect(received.append)
    thumbnail = _event("vae", "thumbnail", thumbnail_updated=True)
    later_metadata = _event("vae", "metadata", thumbnail_updated=False)

    bridge.begin_startup_coalescing()
    bridge.emit_model_updated(thumbnail)
    bridge.emit_model_updated(later_metadata)
    bridge.end_startup_coalescing()

    assert received == [thumbnail]


def test_bridge_end_coalescing_flushes_and_resumes_immediate_emits() -> None:
    """Ending coalescing should flush pending events and resume normal dispatch."""

    bridge = ModelMetadataUpdateBridge()
    received: list[ModelMetadataRefreshEvent] = []
    bridge.model_updated.connect(received.append)
    pending = _event("checkpoint", "a")
    immediate = _event("checkpoint", "b")

    bridge.begin_startup_coalescing()
    bridge.emit_model_updated(pending)
    bridge.end_startup_coalescing()
    bridge.emit_model_updated(immediate)

    assert received == [pending, immediate]


def test_bridge_timeout_flushes_startup_coalescing() -> None:
    """Safety timeout should flush pending startup metadata updates."""

    bridge = ModelMetadataUpdateBridge()
    received: list[ModelMetadataRefreshEvent] = []
    bridge.model_updated.connect(received.append)
    pending = _event("checkpoint", "a")

    bridge.begin_startup_coalescing()
    bridge.emit_model_updated(pending)
    bridge.timeout_startup_coalescing()

    assert received == [pending]


def test_main_window_uses_shared_model_metadata_update_bridge() -> None:
    """Keep MainWindow wired to the shared metadata update bridge."""

    main_window_source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "presentation"
        / "shell"
        / "main_window.py"
    )
    catalog_controller_source_path = (
        main_window_source_path.parent / "model_catalog_update_controller.py"
    )
    source_text = main_window_source_path.read_text(encoding="utf-8")
    catalog_controller_source = catalog_controller_source_path.read_text(
        encoding="utf-8"
    )

    assert "class _MainWindowMetadataUpdateSink" not in source_text
    assert "ModelMetadataUpdateBridge(shell)" in catalog_controller_source
    assert "metadata_update_bridge.model_updated.connect" in catalog_controller_source


def _event(
    kind: str,
    value: str,
    *,
    thumbnail_updated: bool = False,
) -> ModelMetadataRefreshEvent:
    """Build one metadata refresh event."""

    return ModelMetadataRefreshEvent(
        kind=kind,
        value=value,
        relative_path=f"{value}.safetensors",
        sha256=value,
        provider_status="ok",
        thumbnail_updated=thumbnail_updated,
    )


def _app() -> QApplication:
    """Return a QApplication for queued signal delivery tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
