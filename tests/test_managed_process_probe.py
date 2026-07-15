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

"""Tests for managed Comfy listener ownership probing."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerStatus,
    is_endpoint_listening,
    is_process_running,
    probe_managed_listener,
)


def test_probe_managed_listener_treats_stale_metadata_without_process_as_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Metadata alone should not force repair when no process or listener exists."""

    metadata = ManagedProcessMetadata(
        pid=321,
        host="127.0.0.1",
        port=8188,
        workspace_path=tmp_path / "comfyui",
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.is_endpoint_listening",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.is_process_running",
        lambda *_args, **_kwargs: False,
    )

    result = probe_managed_listener(
        host="127.0.0.1",
        port=8188,
        workspace=tmp_path / "comfyui",
        metadata=metadata,
    )

    assert result.status is ManagedListenerStatus.ABSENT
    assert result.metadata == metadata


def test_probe_managed_listener_ignores_pid_reuse_for_unrelated_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reused pids should not be treated as stale owned managed Comfy processes."""

    metadata = ManagedProcessMetadata(
        pid=321,
        host="127.0.0.1",
        port=8188,
        workspace_path=tmp_path / "comfyui",
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.is_endpoint_listening",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.is_process_running",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._get_process_command_line",
        lambda *_args, **_kwargs: '"C:\\Python312\\python.exe" C:\\OtherApp\\main.py',
    )

    result = probe_managed_listener(
        host="127.0.0.1",
        port=8188,
        workspace=tmp_path / "comfyui",
        metadata=metadata,
    )

    assert result.status is ManagedListenerStatus.ABSENT
    assert result.metadata == metadata


def test_is_endpoint_listening_uses_http_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listener detection should use HTTP readiness after a TCP preflight."""

    observed: list[tuple[str, int]] = []
    preflights: list[tuple[str, int, float]] = []

    def _fake_probe_http_ready(*, host: str, port: int) -> bool:
        observed.append((host, port))
        return True

    def _fake_tcp_endpoint_accepts_connections(
        *,
        host: str,
        port: int,
        timeout: float,
    ) -> bool:
        preflights.append((host, port, timeout))
        return True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.probe_http_ready",
        _fake_probe_http_ready,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._tcp_endpoint_accepts_connections",
        _fake_tcp_endpoint_accepts_connections,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._local_port_is_available",
        lambda **_kwargs: False,
    )

    assert is_endpoint_listening("127.0.0.1", 8188) is True
    assert preflights == [("127.0.0.1", 8188, 0.005)]
    assert observed == [("127.0.0.1", 8188)]


def test_is_endpoint_listening_skips_tcp_probe_when_loopback_port_is_bindable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bindable loopback ports should avoid slow failed TCP connection probes."""

    preflights: list[tuple[str, int, float]] = []
    http_probes: list[tuple[str, int]] = []

    def _fake_tcp_endpoint_accepts_connections(
        *,
        host: str,
        port: int,
        timeout: float,
    ) -> bool:
        preflights.append((host, port, timeout))
        return True

    def _fake_probe_http_ready(*, host: str, port: int) -> bool:
        http_probes.append((host, port))
        return True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._local_port_is_available",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._tcp_endpoint_accepts_connections",
        _fake_tcp_endpoint_accepts_connections,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.probe_http_ready",
        _fake_probe_http_ready,
    )

    assert is_endpoint_listening("127.0.0.1", 8188) is False
    assert preflights == []
    assert http_probes == []


def test_is_endpoint_listening_does_not_bind_probe_named_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Named hosts should keep the TCP preflight path to avoid resolver ambiguity."""

    bind_probes: list[tuple[str, int]] = []
    preflights: list[tuple[str, int, float]] = []

    def _fake_tcp_endpoint_accepts_connections(
        *,
        host: str,
        port: int,
        timeout: float,
    ) -> bool:
        preflights.append((host, port, timeout))
        return False

    def _fake_local_port_is_available(*, host: str, port: int) -> bool:
        bind_probes.append((host, port))
        return True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._local_port_is_available",
        _fake_local_port_is_available,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._tcp_endpoint_accepts_connections",
        _fake_tcp_endpoint_accepts_connections,
    )

    assert is_endpoint_listening("localhost", 8188) is False
    assert bind_probes == []
    assert preflights == [("localhost", 8188, 0.005)]


def test_is_endpoint_listening_skips_http_probe_when_tcp_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent TCP endpoints should not pay the HTTP readiness timeout."""

    observed: list[tuple[str, int]] = []

    def _fake_probe_http_ready(*, host: str, port: int) -> bool:
        observed.append((host, port))
        return True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe.probe_http_ready",
        _fake_probe_http_ready,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._local_port_is_available",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._tcp_endpoint_accepts_connections",
        lambda **_kwargs: False,
    )

    assert is_endpoint_listening("127.0.0.1", 8188) is False
    assert observed == []


def test_is_process_running_uses_windows_handle_wait_for_live_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows liveness checks should treat wait timeout as still running."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._open_windows_process_handle",
        lambda _pid: 123,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._wait_for_windows_process_handle",
        lambda _handle: 0x00000102,
    )
    closed_handles: list[int] = []
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._close_windows_process_handle",
        lambda handle: closed_handles.append(handle),
    )

    assert is_process_running(321) is True
    assert closed_handles == [123]


def test_is_process_running_uses_windows_handle_wait_for_dead_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows liveness checks should treat a signaled process handle as exited."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._open_windows_process_handle",
        lambda _pid: 123,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._wait_for_windows_process_handle",
        lambda _handle: 0x00000000,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._close_windows_process_handle",
        lambda _handle: None,
    )

    assert is_process_running(321) is False


def test_is_process_running_treats_windows_access_denied_as_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Access-denied Windows handles should be treated as an existing process."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._open_windows_process_handle",
        lambda _pid: None,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_process_probe._get_windows_last_error",
        lambda: 5,
    )

    assert is_process_running(321) is True
