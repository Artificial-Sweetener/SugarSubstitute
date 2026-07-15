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

"""Verify launch splash presentation policy."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.startup_splash_controller import (
    StartupCancelBridge,
    create_startup_cancel_bridge,
    create_startup_splash_ports,
    launch_splash_backdrop_mode_value,
    start_or_adopt_launch_splash,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.domain.appearance import AppearanceBackdropMode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)
SPLASH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_splash_controller.py"
)
FORBIDDEN_SPLASH_IMPORT_PREFIXES = (
    "substitute.infrastructure",
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


def test_launch_splash_backdrop_mode_value_uses_plain_mica_for_mica_alt() -> None:
    """Splash should use plain Mica even when the shell preference is Mica Alt."""

    assert (
        launch_splash_backdrop_mode_value(
            SimpleNamespace(effective_backdrop_mode=AppearanceBackdropMode.MICA_ALT)
        )
        == "mica"
    )
    assert (
        launch_splash_backdrop_mode_value(
            SimpleNamespace(effective_backdrop_mode=AppearanceBackdropMode.ACRYLIC)
        )
        == "acrylic"
    )
    assert (
        launch_splash_backdrop_mode_value(SimpleNamespace(effective_backdrop_mode=None))
        == "none"
    )


def test_startup_cancel_bridge_emits_cancel_requests() -> None:
    """Startup cancel bridge should publish helper-thread cancel requests."""

    bridge = StartupCancelBridge()
    calls: list[str] = []

    bridge.cancel_requested.connect(lambda: calls.append("cancel"))
    bridge.cancel_requested.emit()

    assert calls == ["cancel"]


def test_create_startup_cancel_bridge_returns_cancel_signal_bridge() -> None:
    """Cancel bridge factory should provide the Qt signal bridge."""

    bridge = create_startup_cancel_bridge()
    calls: list[str] = []

    bridge.cancel_requested.connect(lambda: calls.append("cancel"))
    bridge.cancel_requested.emit()

    assert calls == ["cancel"]


def test_create_startup_splash_ports_groups_splash_adapters() -> None:
    """Splash ports should expose cancel-bridge and start/adopt adapters."""

    ports = create_startup_splash_ports()

    bridge = ports.create_cancel_bridge()
    calls: list[str] = []
    bridge.cancel_requested.connect(lambda: calls.append("cancel"))
    bridge.cancel_requested.emit()

    assert calls == ["cancel"]
    assert ports.start_or_adopt_launch_splash is start_or_adopt_launch_splash


def test_start_or_adopt_launch_splash_starts_with_resolved_appearance() -> None:
    """Launch splash startup should pass resolved appearance and cancel callback."""

    splash = cast(LaunchSplashClient, _Splash())
    timer = cast(StartupTimer, object())

    def cancel_callback() -> None:
        """Accept cancel wiring."""

    launched: dict[str, object] = {}
    appearance = SimpleNamespace(
        effective_theme_mode=SimpleNamespace(value="dark"),
        effective_accent_color="#ff00ff",
        effective_backdrop_mode=AppearanceBackdropMode.MICA_ALT,
    )

    result = start_or_adopt_launch_splash(
        splash=None,
        startup_timer=timer,
        resolved_appearance=appearance,
        on_cancel_requested=cancel_callback,
        process_pump_task_factory=cast(Any, _process_pump_task_factory),
        launch_splash=lambda **kwargs: _record_launch(launched, splash, kwargs),
    )

    assert result is splash
    assert launched["startup_timer"] is timer
    assert isinstance(launched["cwd"], Path)
    assert launched["theme_mode"] == "dark"
    assert launched["accent_color"] == "#ff00ff"
    assert launched["backdrop_mode"] == "mica"
    assert launched["on_cancel_requested"] is cancel_callback
    assert launched["process_pump_task_factory"] is _process_pump_task_factory


def test_start_or_adopt_launch_splash_returns_existing_splash() -> None:
    """Existing launch splash clients should be adopted without relaunch."""

    splash = cast(LaunchSplashClient, _Splash())

    result = start_or_adopt_launch_splash(
        splash=splash,
        startup_timer=cast(StartupTimer, object()),
        resolved_appearance=SimpleNamespace(
            effective_theme_mode=SimpleNamespace(value="dark"),
            effective_accent_color="#ff00ff",
            effective_backdrop_mode=None,
        ),
        on_cancel_requested=lambda: None,
        process_pump_task_factory=cast(Any, _process_pump_task_factory),
        launch_splash=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("launch should not run")
        ),
    )

    assert result is splash


def test_startup_splash_controller_imports_no_forbidden_boundaries() -> None:
    """Splash presentation policy should not import infrastructure or subprocess."""

    imported_modules = _imported_module_names(SPLASH_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SPLASH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_splash_backdrop_policy() -> None:
    """The startup facade should delegate launch splash backdrop policy."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")

    assert "class _StartupCancelBridge" not in source
    assert "StartupCancelBridge()" not in source
    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_splash_ports()" not in source
    assert "startup_splash_ports.create_cancel_bridge()" not in source
    assert "create_startup_splash_ports()" in support_graph_source
    assert "startup_splash_ports.create_cancel_bridge()" in support_graph_source
    assert "create_startup_cancel_bridge()" not in source
    assert "startup_splash_ports.start_or_adopt_launch_splash" not in source
    assert (
        "startup_support_graph.startup_splash_ports.start_or_adopt_launch_splash"
        in shell_flow_source
    )
    assert "start_or_adopt_launch_splash=start_or_adopt_launch_splash" not in source
    assert "def _launch_splash_backdrop_mode_value" not in source
    assert "start_launch_splash(" not in source
    assert "Path(__file__).resolve().parents[3]" not in source
    assert "AppearanceBackdropMode.ACRYLIC" not in source


def _process_pump_task_factory(*_args: object, **_kwargs: object) -> object:
    """Provide a sentinel process-pump task factory."""

    return object()


class _Splash:
    """Minimal splash test double."""


def _record_launch(
    launched: dict[str, object],
    splash: LaunchSplashClient,
    kwargs: dict[str, object],
) -> LaunchSplashClient:
    """Record launch kwargs and return the fake splash."""

    launched.update(kwargs)
    return splash
