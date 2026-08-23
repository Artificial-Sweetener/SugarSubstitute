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

"""Tests for process-lifetime execution runtime composition."""

from __future__ import annotations

from threading import Event, Thread

import pytest

from substitute.app.bootstrap.execution_runtime import (
    DEFAULT_EXECUTION_LANE_CONFIGS,
    LONG_LIVED_EXECUTION_REGISTRIES,
    ExecutionRuntime,
)
from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
)
from tests.support.execution import RecordingDispatcher


def test_execution_runtime_exposes_configured_lanes_and_registries() -> None:
    """Runtime should expose the planned lane and long-lived registry names."""

    runtime = ExecutionRuntime()
    try:
        expected_lane_names = tuple(
            config.name for config in DEFAULT_EXECUTION_LANE_CONFIGS
        )

        assert runtime.lane_names == expected_lane_names
        assert runtime.long_lived_registry_names == tuple(
            sorted(LONG_LIVED_EXECUTION_REGISTRIES)
        )
        assert runtime.prompt_editor is runtime.lane("prompt_editor")
        assert runtime.settings_io is runtime.lane("settings_io")
        assert runtime.onboarding_environment is runtime.lane("onboarding_environment")
        assert runtime.thumbnail_decode is runtime.lane("thumbnail_decode")
        assert runtime.shutdown_execution is runtime.lane("shutdown")
        with pytest.raises(ValueError, match="Unknown execution lane"):
            runtime.lane("missing")
    finally:
        runtime.shutdown()


def test_default_prompt_editor_lane_has_startup_burst_headroom() -> None:
    """Prompt-editor lane defaults should absorb multi-editor startup bursts."""

    prompt_config = next(
        config
        for config in DEFAULT_EXECUTION_LANE_CONFIGS
        if config.name == "prompt_editor"
    )

    assert prompt_config.max_workers == 2
    assert prompt_config.queue_capacity == 128


def test_thumbnail_decode_lane_is_isolated_and_burst_tolerant() -> None:
    """Picker thumbnails should not contend with generation image decoding."""

    thumbnail_config = next(
        config
        for config in DEFAULT_EXECUTION_LANE_CONFIGS
        if config.name == "thumbnail_decode"
    )

    assert thumbnail_config.max_workers == 4
    assert thumbnail_config.queue_capacity == 64


def test_execution_runtime_scope_routes_callbacks_by_owner_dispatcher() -> None:
    """Owner scopes should stamp context and publish through their dispatcher."""

    runtime = ExecutionRuntime()
    dispatcher = RecordingDispatcher()
    delivered: list[tuple[str, str, str]] = []
    try:
        scope = runtime.scope(
            "settings_io",
            owner_id="settings-page",
            dispatcher=dispatcher,
        )
        handle = scope.submit(
            TaskRequest(
                identity=TaskIdentity(request_id=1, domain="settings", parts=()),
                context=ExecutionContext(
                    operation="load_settings",
                    reason="test",
                    lane="placeholder",
                ),
                work=lambda _token: "loaded",
            )
        )
        handle.add_done_callback(
            lambda outcome: delivered.append(
                (
                    str(outcome.result),
                    outcome.context.lane,
                    str(outcome.context.owner_id),
                )
            ),
            reason="test_completion",
        )

        dispatcher.wait_for_callbacks(1)
        assert handle.is_finished
        assert delivered == []
        dispatcher.run_all()

        assert delivered == [("loaded", "settings_io", "settings-page")]
    finally:
        scope.close(reason="test_complete")
        runtime.shutdown()


def test_execution_runtime_scope_close_unregisters_owner_dispatcher() -> None:
    """Closing a scope should allow a later scope to reuse the owner id."""

    runtime = ExecutionRuntime()
    try:
        first_scope = runtime.scope(
            "prompt_editor",
            owner_id="editor",
            dispatcher=RecordingDispatcher(),
        )
        with pytest.raises(RuntimeError, match="already registered"):
            runtime.scope(
                "prompt_editor",
                owner_id="editor",
                dispatcher=RecordingDispatcher(),
            )

        first_scope.close(reason="editor_closed")
        second_scope = runtime.scope(
            "prompt_editor",
            owner_id="editor",
            dispatcher=RecordingDispatcher(),
        )

        assert second_scope.scope_id == "editor"
        second_scope.close(reason="editor_closed")
    finally:
        runtime.shutdown()


def test_execution_runtime_shutdown_releases_lanes_and_long_lived_handles() -> None:
    """Runtime shutdown should stop registered long-lived handles and lanes."""

    runtime = ExecutionRuntime()
    long_lived_started = Event()
    release_long_lived = Event()
    long_lived_stopped: list[str] = []
    runtime.start_long_lived(
        "process_pump",
        "comfy",
        identity=TaskIdentity(request_id=1, domain="process_pump", parts=()),
        context=ExecutionContext(
            operation="pump_process",
            reason="test",
            lane="process_pump",
        ),
        work=lambda token: _record_after_release(
            token,
            long_lived_started,
            release_long_lived,
            stopped=long_lived_stopped,
        ),
        dispatcher=RecordingDispatcher(),
        close_hook=release_long_lived.set,
        thread_name="test-process-pump-shutdown",
    )
    dispatcher = RecordingDispatcher()
    scope = runtime.scope(
        "cube_load",
        owner_id="workspace",
        dispatcher=dispatcher,
    )

    runtime.shutdown()

    assert long_lived_started.is_set()
    assert long_lived_stopped == ["runtime_shutdown"]
    with pytest.raises(RuntimeError, match="shut down"):
        scope.submit(
            TaskRequest(
                identity=TaskIdentity(request_id=1, domain="cube", parts=()),
                context=ExecutionContext(
                    operation="load_cube",
                    reason="test",
                    lane="cube_load",
                ),
                work=lambda _token: "loaded",
            )
        )


def test_execution_runtime_shutdown_waits_for_running_short_task() -> None:
    """Shutdown should settle running work before returning to Qt teardown."""

    runtime = ExecutionRuntime()
    work_started = Event()
    release_work = Event()
    shutdown_started = Event()
    shutdown_finished = Event()
    scope = runtime.scope(
        "node_definition",
        owner_id="runtime_shutdown_wait",
        dispatcher=RecordingDispatcher(),
    )

    def shutdown_runtime() -> None:
        """Record completion only after the runtime releases its lanes."""

        shutdown_started.set()
        runtime.shutdown()
        shutdown_finished.set()

    try:
        scope.submit(
            TaskRequest(
                identity=TaskIdentity(
                    request_id=1,
                    domain="runtime_shutdown_wait",
                    parts=(),
                ),
                context=ExecutionContext(
                    operation="wait_for_runtime_shutdown",
                    reason="test",
                    lane="node_definition",
                ),
                work=lambda _token: _wait_for_release(work_started, release_work),
            )
        )
        assert work_started.wait(timeout=1.0)

        shutdown_thread = Thread(
            target=shutdown_runtime,
            name="test-runtime-shutdown",
        )
        shutdown_thread.start()
        assert shutdown_started.wait(timeout=1.0)
        assert not shutdown_finished.wait(timeout=0.05)

        release_work.set()
        shutdown_thread.join(timeout=1.0)
        assert shutdown_finished.is_set()
    finally:
        release_work.set()
        runtime.shutdown()


def test_execution_runtime_rejects_unknown_long_lived_registry_before_start() -> None:
    """Unknown long-lived registries should reject work before it starts."""

    runtime = ExecutionRuntime()
    started = Event()
    release = Event()
    try:
        with pytest.raises(ValueError, match="Unknown long-lived"):
            runtime.start_long_lived(
                "missing",
                "main",
                identity=TaskIdentity(request_id=1, domain="missing", parts=()),
                context=ExecutionContext(
                    operation="missing_registry",
                    reason="test",
                    lane="missing",
                ),
                work=lambda token: _record_after_release(
                    token,
                    started,
                    release,
                ),
                dispatcher=RecordingDispatcher(),
                thread_name="test-missing-registry",
            )
        assert not started.is_set()
    finally:
        runtime.shutdown()


def test_execution_runtime_start_long_lived_rejects_duplicate_before_start() -> None:
    """Duplicate long-lived starts should not launch rejected work."""

    runtime = ExecutionRuntime()
    first_started = Event()
    release_first = Event()
    duplicate_started = Event()
    release_duplicate = Event()
    try:
        runtime.start_long_lived(
            "generation_listener",
            "main",
            identity=TaskIdentity(request_id=1, domain="generation", parts=()),
            context=ExecutionContext(
                operation="listen_generation",
                reason="test",
                lane="generation_listener",
            ),
            work=lambda token: _record_after_release(
                token,
                first_started,
                release_first,
            ),
            dispatcher=RecordingDispatcher(),
            close_hook=release_first.set,
            thread_name="test-generation-listener",
        )
        assert first_started.wait(timeout=1.0)

        with pytest.raises(RuntimeError, match="already registered"):
            runtime.start_long_lived(
                "generation_listener",
                "main",
                identity=TaskIdentity(request_id=2, domain="generation", parts=()),
                context=ExecutionContext(
                    operation="listen_generation",
                    reason="test",
                    lane="generation_listener",
                ),
                work=lambda token: _record_after_release(
                    token,
                    duplicate_started,
                    release_duplicate,
                ),
                dispatcher=RecordingDispatcher(),
                thread_name="test-generation-listener-duplicate",
            )

        assert not duplicate_started.is_set()
    finally:
        runtime.shutdown()


def test_execution_runtime_start_long_lived_rejects_shutdown_before_start() -> None:
    """Shutdown runtime rejection should not launch long-lived work."""

    runtime = ExecutionRuntime()
    started = Event()
    release = Event()
    runtime.shutdown()

    with pytest.raises(RuntimeError, match="shut down"):
        runtime.start_long_lived(
            "process_pump",
            "main",
            identity=TaskIdentity(request_id=1, domain="process_pump", parts=()),
            context=ExecutionContext(
                operation="pump_process",
                reason="test",
                lane="process_pump",
            ),
            work=lambda token: _record_after_release(
                token,
                started,
                release,
            ),
            dispatcher=RecordingDispatcher(),
            thread_name="test-process-pump",
        )

    assert not started.is_set()


def _wait_for_release(work_started: Event, release_work: Event) -> None:
    """Block a worker until the shutdown test explicitly permits completion."""

    work_started.set()
    if not release_work.wait(timeout=1.0):
        raise TimeoutError("Test worker was not released before timeout.")


def _record_after_release(
    token: CancellationToken,
    started: Event,
    release: Event,
    *,
    stopped: list[str] | None = None,
) -> None:
    """Observe entry, close-hook release, and the runtime cancellation request."""

    started.set()
    if not release.wait(timeout=1.0):
        raise TimeoutError("Long-lived worker was not released before timeout.")
    if not token.is_cancelled:
        raise AssertionError("Long-lived worker was released before cancellation.")
    if stopped is not None:
        stopped.append(token.reason or "cancelled")
