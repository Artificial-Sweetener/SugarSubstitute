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

"""Verify startup shutdown and relaunch policy."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path

from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap.startup_shutdown import (
    StartupShutdownRuntime,
    cleanup_result_allows_relaunch,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_SHUTDOWN_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shutdown.py"
)
FORBIDDEN_SHUTDOWN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_cleanup_result_allows_relaunch_after_successful_cleanup() -> None:
    """Comfy restart relaunch should be gated by a real successful cleanup result."""

    assert cleanup_result_allows_relaunch(_cleanup_result()) is True
    assert (
        cleanup_result_allows_relaunch(
            _cleanup_result(ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED)
        )
        is True
    )


def test_cleanup_result_rejects_missing_or_failed_cleanup() -> None:
    """Missing, skipped, and failed cleanup results should not relaunch."""

    assert cleanup_result_allows_relaunch(None) is False
    assert cleanup_result_allows_relaunch(_cleanup_result(cleanup_ran=False)) is False
    assert (
        cleanup_result_allows_relaunch(
            _cleanup_result(ManagedComfyCleanupOutcome.FAILURE)
        )
        is False
    )
    assert (
        cleanup_result_allows_relaunch(
            _cleanup_result(ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS)
        )
        is False
    )


def test_startup_shutdown_runtime_saves_session_and_tracks_cleanup() -> None:
    """Startup shutdown runtime should own pre-cleanup save and cleanup state."""

    events: list[str] = []
    cleanup_handler = _CleanupHandler(events)
    runtime = StartupShutdownRuntime(
        cleanup_handler=cleanup_handler,
        save_session_before_cleanup=lambda: events.append("save_session"),
    )

    runtime.save_session_before_cleanup()
    result = runtime.cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS
    assert runtime.last_cleanup_result is result
    assert runtime.cleanup_bypass == cleanup_handler.skip_future_cleanup
    assert events == ["save_session", "cleanup"]


def test_startup_shutdown_runtime_relaunches_only_after_requested_success() -> None:
    """Ready relaunch should occur only after an explicit request and safe cleanup."""

    launched_commands: list[tuple[str, ...]] = []
    runtime = StartupShutdownRuntime(cleanup_handler=_CleanupHandler([]))

    def launch(command: Sequence[str]) -> bool:
        """Record one relaunch command."""

        launched_commands.append(tuple(command))
        return True

    runtime.relaunch_after_cleanup_if_requested(
        restart_requested=True,
        restart_launch_command=("python", "main.py"),
        start_ready_app_process=launch,
    )
    assert launched_commands == []

    runtime.cleanup()
    runtime.relaunch_after_cleanup_if_requested(
        restart_requested=False,
        restart_launch_command=("python", "main.py"),
        start_ready_app_process=launch,
    )
    assert launched_commands == []

    runtime.relaunch_after_cleanup_if_requested(
        restart_requested=True,
        restart_launch_command=("python", "main.py"),
        start_ready_app_process=launch,
    )
    assert launched_commands == [("python", "main.py")]

    failed_runtime = StartupShutdownRuntime(
        cleanup_handler=_CleanupHandler(
            [],
            outcome=ManagedComfyCleanupOutcome.FAILURE,
        )
    )
    failed_runtime.cleanup()
    failed_runtime.relaunch_after_cleanup_if_requested(
        restart_requested=True,
        restart_launch_command=("python", "main.py"),
        start_ready_app_process=launch,
    )
    assert launched_commands == [("python", "main.py")]


def test_startup_shutdown_imports_no_forbidden_boundaries() -> None:
    """Shutdown relaunch policy should remain free of Qt, presentation, and subprocess."""

    imported_modules = _imported_module_names(STARTUP_SHUTDOWN_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SHUTDOWN_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_cleanup_relaunch_policy() -> None:
    """The startup facade should delegate shutdown cleanup and relaunch decisions."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "lifecycle.create_cleanup_handler" not in source
    assert "lifecycle.register_shutdown_handlers" not in source
    assert "last_cleanup_result" not in source
    assert "def _cleanup_result_allows_relaunch" not in source
    assert "cleanup_result_allows_relaunch" not in source
    assert "ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED" not in source
    assert "from substitute.infrastructure.comfy import process_manager" not in source
    assert "process_manager.kill_comfyui_state" not in source
    assert "create_startup_shell_runtime_graph(" in source
    assert "create_process_manager_startup_shutdown_runtime(" not in source
    assert '"process_manager"' not in source


class _CleanupHandler:
    """Record cleanup and force-close bypass calls for shutdown runtime tests."""

    def __init__(
        self,
        events: list[str],
        *,
        outcome: ManagedComfyCleanupOutcome = (
            ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS
        ),
    ) -> None:
        """Store mutable test events and cleanup outcome."""

        self._events = events
        self._outcome = outcome

    def __call__(self) -> ManagedComfyCleanupResult:
        """Record cleanup and return the configured result."""

        self._events.append("cleanup")
        return _cleanup_result(self._outcome)

    def skip_future_cleanup(self) -> None:
        """Record a force-close cleanup bypass request."""

        self._events.append("skip_cleanup")


def _cleanup_result(
    outcome: ManagedComfyCleanupOutcome = ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
    *,
    cleanup_ran: bool = True,
) -> ManagedComfyCleanupResult:
    """Build a managed cleanup result for relaunch policy tests."""

    return ManagedComfyCleanupResult(
        cleanup_ran=cleanup_ran,
        outcome=outcome,
        managed_resource_present=outcome
        is not ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        live_process_present=True,
        metadata_present=True,
        used_persisted_metadata=False,
        termination_attempted=outcome
        is not ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        registry_cleared=outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        pid=123,
        host="127.0.0.1",
        port=8188,
        workspace=None,
        elapsed_ms=10,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="clean",
        technical_detail="clean",
        diagnostic_detail="clean",
    )
