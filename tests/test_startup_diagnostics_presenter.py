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

"""Tests for startup diagnostics titlebar presentation adapters."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TypeVar

import pytest

from substitute.app.bootstrap import startup_diagnostics_presenter
from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
)
from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskRequest,
)
from tests.execution_testing import ManualTaskHandle
from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

TResult = TypeVar("TResult")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRESENTER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_diagnostics_presenter.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_PRESENTER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.comfy_manager_extension_metadata",
    "subprocess",
)


def test_apply_startup_diagnostics_titlebar_state_filters_ignored_incidents() -> None:
    """Recoverable startup diagnostics should be prepared before shell handoff."""

    incident = _incident("warning-a")
    ignored_incident = _incident("existing")
    states: list[object] = []

    startup_diagnostics_presenter.apply_startup_diagnostics_titlebar_state(
        main_window=_main_window(states),
        incidents=(incident, ignored_incident),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(ignored=frozenset({"existing"})),
    )

    assert len(states) == 1
    state = states[0]
    assert isinstance(state, StartupDiagnosticsTitlebarState)
    assert state.incidents == (incident,)
    assert state.ignored_count == 1
    assert state.transcript == ("WARNING: optional package missing",)


def test_apply_startup_diagnostics_titlebar_state_clears_all_ignored() -> None:
    """Ignored recoverable startup incidents should clear shell diagnostics."""

    states: list[object | None] = []

    startup_diagnostics_presenter.apply_startup_diagnostics_titlebar_state(
        main_window=_main_window(states),
        incidents=(_incident("warning-a"),),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(ignored=frozenset({"warning-a"})),
    )

    assert states == [None]


def test_prepare_startup_diagnostics_titlebar_state_enriches_metadata() -> None:
    """Metadata providers should enrich incidents before shell handoff."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        severity=ComfyStartupIncidentSeverity.ERROR,
        title="Extension failed to load",
        message="SyntaxError: broken",
        source="BrokenExtension",
        fingerprint="broken-extension",
    )

    state = startup_diagnostics_presenter.prepare_startup_diagnostics_titlebar_state_for_shell(
        incidents=(incident,),
        transcript=("SyntaxError: broken",),
        ignore_repository=_Repository(),
        metadata_providers=(_Provider(),),
    )

    assert state is not None
    enriched = state.incidents[0]
    assert enriched.values["extension_version"] == "abc123"
    assert (
        enriched.values["repository_url"]
        == "https://github.com/example/BrokenExtension"
    )
    assert (
        enriched.values["issues_url"]
        == "https://github.com/example/BrokenExtension/issues"
    )


def test_prepare_startup_diagnostics_titlebar_state_survives_provider_failure() -> None:
    """Metadata failures should not suppress recoverable diagnostics."""

    incident = _incident("warning-a")

    state = startup_diagnostics_presenter.prepare_startup_diagnostics_titlebar_state_for_shell(
        incidents=(incident,),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
        metadata_providers=(_FailingProvider(),),
    )

    assert state is not None
    assert state.incidents == (incident,)


def test_apply_prepared_startup_diagnostics_titlebar_state_ignores_missing_shell() -> (
    None
):
    """Missing shell integration should be a no-op."""

    startup_diagnostics_presenter.apply_prepared_startup_diagnostics_titlebar_state(
        main_window=object(),
        state=None,
    )


def test_start_startup_diagnostics_preparation_skips_without_incidents() -> None:
    """Async diagnostics preparation should not submit work without incidents."""

    signal = _PreparedSignal()
    submitter = _ImmediateSubmitter()

    started = startup_diagnostics_presenter.start_startup_diagnostics_preparation(
        main_window=_main_window([]),
        incidents=(),
        transcript=(),
        ignore_repository=_Repository(),
        metadata_providers=(),
        prepared_signal=signal,
        submitter=submitter,
        startup_cancelled=lambda: False,
        shell_frame_available=lambda: True,
    )

    assert started is False
    assert signal.connected_callbacks == []
    assert submitter.submitted == 0


def test_request_startup_diagnostics_titlebar_preparation_registers_resources() -> None:
    """Diagnostics request orchestration should own resource registration order."""

    states: list[object | None] = []
    bridge = _PreparedBridge()
    submitter = _ImmediateSubmitter()
    registered: list[str] = []

    started = (
        startup_diagnostics_presenter.request_startup_diagnostics_titlebar_preparation(
            main_window=_main_window(states),
            incidents=(_incident("warning-a"),),
            transcript=("WARNING: optional package missing",),
            ignore_repository=_Repository(),
            metadata_providers=(),
            bridge_factory=lambda: bridge,
            register_bridge=lambda _bridge: registered.append("bridge"),
            submitter_factory=lambda: submitter,
            register_submitter=lambda received: registered.append(
                "submitter" if received is submitter else "wrong_submitter"
            ),
            startup_cancelled=lambda: False,
            shell_frame_available=lambda: True,
        )
    )

    assert started is True
    assert registered == ["bridge", "submitter"]
    assert bridge.signal.emitted_count == 1
    assert submitter.submitted == 1
    assert len(states) == 1
    assert isinstance(states[0], StartupDiagnosticsTitlebarState)


def test_request_startup_diagnostics_titlebar_preparation_keeps_resource_lifetime_without_incidents() -> (
    None
):
    """No-incident diagnostics requests should still register owned resources."""

    bridge = _PreparedBridge()
    submitter = _ImmediateSubmitter()
    registered: list[str] = []

    started = (
        startup_diagnostics_presenter.request_startup_diagnostics_titlebar_preparation(
            main_window=_main_window([]),
            incidents=(),
            transcript=(),
            ignore_repository=_Repository(),
            metadata_providers=(),
            bridge_factory=lambda: bridge,
            register_bridge=lambda _bridge: registered.append("bridge"),
            submitter_factory=lambda: submitter,
            register_submitter=lambda _submitter: registered.append("submitter"),
            startup_cancelled=lambda: False,
            shell_frame_available=lambda: True,
        )
    )

    assert started is False
    assert registered == ["bridge", "submitter"]
    assert bridge.signal.connected_callbacks == []
    assert submitter.submitted == 0


def test_start_startup_diagnostics_preparation_prepares_and_applies_state() -> None:
    """Async diagnostics preparation should publish state through the bridge."""

    states: list[object | None] = []
    signal = _PreparedSignal()

    started = startup_diagnostics_presenter.start_startup_diagnostics_preparation(
        main_window=_main_window(states),
        incidents=(_incident("warning-a"),),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
        metadata_providers=(),
        prepared_signal=signal,
        submitter=_ImmediateSubmitter(),
        startup_cancelled=lambda: False,
        shell_frame_available=lambda: True,
    )

    assert started is True
    assert len(states) == 1
    assert isinstance(states[0], StartupDiagnosticsTitlebarState)
    assert signal.emitted_count == 1


def test_start_startup_diagnostics_preparation_publishes_none_after_task_error() -> (
    None
):
    """Async diagnostics task failures should clear titlebar diagnostics."""

    states: list[object | None] = []

    startup_diagnostics_presenter.start_startup_diagnostics_preparation(
        main_window=_main_window(states),
        incidents=(_incident("warning-a"),),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
        metadata_providers=(),
        prepared_signal=_PreparedSignal(),
        submitter=_FailingSubmitter(),
        startup_cancelled=lambda: False,
        shell_frame_available=lambda: True,
    )

    assert states == [None]


def test_start_startup_diagnostics_preparation_skips_apply_after_cancel() -> None:
    """Prepared diagnostics should not apply after startup cancellation."""

    states: list[object | None] = []

    startup_diagnostics_presenter.start_startup_diagnostics_preparation(
        main_window=_main_window(states),
        incidents=(_incident("warning-a"),),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
        metadata_providers=(),
        prepared_signal=_PreparedSignal(),
        submitter=_ImmediateSubmitter(),
        startup_cancelled=lambda: True,
        shell_frame_available=lambda: True,
    )

    assert states == []


def test_startup_extension_metadata_providers_includes_local_git_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Local custom-node metadata should be available when the directory exists."""

    (tmp_path / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
    from substitute.infrastructure.comfy import manager_runtime_probe

    monkeypatch.setattr(
        manager_runtime_probe,
        "detect_workspace_manager_runtime",
        lambda workspace, **_kwargs: ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=tmp_path / "python",
        ),
    )

    providers = startup_diagnostics_presenter.startup_extension_metadata_providers(
        _context(tmp_path)
    )

    provider_types = {type(provider).__name__ for provider in providers}
    assert "ComfyManagerExtensionMetadataProvider" in provider_types
    assert "LocalCustomNodeGitMetadataProvider" in provider_types


def test_remote_startup_metadata_does_not_probe_unrelated_local_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Remote Manager route discovery should use its live HTTP server."""

    from substitute.infrastructure.comfy import manager_runtime_probe

    monkeypatch.setattr(
        manager_runtime_probe,
        "detect_workspace_manager_runtime",
        lambda *_args, **_kwargs: pytest.fail("unexpected local Manager probe"),
    )
    context = _context(tmp_path)
    context = InstallationContext(
        installation=context.installation,
        runtime=context.runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.REMOTE,
            endpoint=ComfyEndpoint(host="remote-box", port=8188),
            workspace_path=None,
            install_owned=False,
            launch_owned=False,
        ),
    )

    providers = startup_diagnostics_presenter.startup_extension_metadata_providers(
        context
    )

    assert [type(provider).__name__ for provider in providers] == [
        "ComfyManagerExtensionMetadataProvider"
    ]


def test_startup_diagnostics_presenter_imports_no_forbidden_boundaries() -> None:
    """Diagnostics presentation preparation should stay free of Qt and widgets."""

    imported_modules = _top_level_imported_module_names(PRESENTER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_PRESENTER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_diagnostics_titlebar_helpers() -> None:
    """Startup should delegate direct diagnostics titlebar helpers."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "def _apply_startup_diagnostics_titlebar_state" not in source
    assert "def _prepare_startup_diagnostics_titlebar_state" not in source
    assert "def _apply_prepared_startup_diagnostics_titlebar_state" not in source
    assert "def _startup_extension_metadata_providers" not in source
    assert "def start_startup_diagnostics_preparation" not in source
    assert "prepare_startup_diagnostics_titlebar_state(" not in source
    assert "apply_prepared_startup_diagnostics_titlebar_state(" not in source
    assert "prepare_startup_diagnostics_titlebar_state_for_shell(" not in source
    assert "startup_diagnostics_bridge =" not in source
    assert "startup_diagnostics_executor =" not in source
    assert "request_startup_diagnostics_titlebar_preparation(" not in source
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter" not in source
    )
    assert "create_ready_shell_startup_diagnostics_update_adapter(" not in source
    assert "ReadyShellStartupDiagnosticsUpdateAdapter(" not in source
    assert "request_ready_shell_startup_diagnostics_update(" not in source
    assert "startup_extension_metadata_providers(" not in source


def _incident(fingerprint: str) -> ComfyStartupIncident:
    """Return one recoverable startup warning incident."""

    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.STARTUP_WARNING,
        severity=ComfyStartupIncidentSeverity.WARNING,
        title="ComfyUI reported a startup warning",
        message="WARNING: optional package missing",
        fingerprint=fingerprint,
    )


def _main_window(states: list[object | None]) -> object:
    """Return a shell double that records startup diagnostics state."""

    return SimpleNamespace(
        shell_frame_integration_controller=SimpleNamespace(
            set_startup_diagnostics_state=states.append
        )
    )


def _context(tmp_path: Path) -> InstallationContext:
    """Build one managed-local installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=True,
        ),
    )


def _top_level_imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported at module load time by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _Repository:
    """Return configured ignored startup diagnostic fingerprints."""

    def __init__(self, *, ignored: frozenset[str] = frozenset()) -> None:
        self._ignored = ignored

    def load_ignored_fingerprints(self) -> frozenset[str]:
        """Return ignored fingerprints."""

        return self._ignored

    def save_ignored_fingerprints(self, fingerprints: frozenset[str]) -> None:
        """Fail if the presenter tries to persist ignores."""

        pytest.fail(f"unexpected ignore persistence: {fingerprints}")


class _Provider:
    """Return matching extension metadata."""

    def installed_extensions(self) -> dict[str, ComfyExtensionMetadata]:
        """Return matching extension metadata."""

        return {
            "brokenextension": ComfyExtensionMetadata(
                key="brokenextension",
                version="abc123",
                repository_url="https://github.com/example/BrokenExtension",
                issues_url="https://github.com/example/BrokenExtension/issues",
                source="manager_installed_aux_id",
            )
        }


class _FailingProvider:
    """Raise during extension metadata lookup."""

    def installed_extensions(self) -> dict[str, ComfyExtensionMetadata]:
        """Raise one metadata lookup error."""

        raise RuntimeError("metadata unavailable")


class _PreparedSignal:
    """Synchronous prepared-state signal test double."""

    def __init__(self) -> None:
        """Create empty signal records."""

        self.connected_callbacks: list[Callable[[object], None]] = []
        self.emitted_count = 0

    def connect(self, callback: Callable[[object], None]) -> object:
        """Record one connected callback."""

        self.connected_callbacks.append(callback)
        return callback

    def emit(self, state: object) -> None:
        """Synchronously invoke connected callbacks."""

        self.emitted_count += 1
        for callback in self.connected_callbacks:
            callback(state)


class _PreparedBridge:
    """Expose a prepared diagnostics signal for request orchestration tests."""

    def __init__(self) -> None:
        """Create an empty prepared signal."""

        self.signal = _PreparedSignal()
        self.prepared: startup_diagnostics_presenter.PreparedDiagnosticsSignalProtocol = self.signal


class _ImmediateSubmitter:
    """Run submitted diagnostics preparation immediately."""

    def __init__(self) -> None:
        """Create submitter records."""

        self.submitted = 0

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Execute one task immediately and return its completed handle."""

        self.submitted += 1
        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        if cancellation.is_cancelled:
            handle.complete_cancelled(reason=cancellation.reason or "cancelled")
        else:
            handle.complete_success(request.work(cancellation))
        return handle


class _FailingSubmitter:
    """Return a diagnostics preparation failure handle."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Return one failed handle without running the callable."""

        _ = cancellation
        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        handle.complete_failed(RuntimeError("task failed"))
        return handle
