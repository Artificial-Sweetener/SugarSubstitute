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

"""Verify startup CLI parsing and launch-command construction."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

import pytest

from substitute.app.bootstrap.startup_cli import (
    StartupCliArguments,
    StartupReadyAppLaunch,
    build_ready_app_launch_command,
    extract_handoff_geometry,
    extract_install_root,
    extract_locale_override,
    parse_startup_cli_arguments,
    prepare_ready_app_launch,
    trace_startup_cli_arguments,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_CLI_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_cli.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.process_manager",
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


def test_extract_install_root_returns_first_nonblank_override() -> None:
    """Install-root parsing should ignore blanks and return the first path."""

    assert extract_install_root(["main.py"]) is None
    assert extract_install_root(["main.py", "--install-root=   "]) is None
    assert extract_install_root(
        [
            "main.py",
            "--install-root=E:\\Substitute",
            "--install-root=E:\\Other",
        ]
    ) == Path("E:\\Substitute")


def test_extract_handoff_geometry_parses_valid_cli_rect() -> None:
    """Startup should accept installer handoff geometry from CLI args."""

    assert extract_handoff_geometry(
        ["main.py", "--handoff-geometry=10,20,1260,800"]
    ) == (10, 20, 1260, 800)


def test_extract_handoff_geometry_rejects_invalid_cli_rects() -> None:
    """Invalid handoff geometry should fail closed to normal placement."""

    assert extract_handoff_geometry(["main.py"]) is None
    assert (
        extract_handoff_geometry(["main.py", "--handoff-geometry=10,20,0,704"]) is None
    )


def test_extract_locale_override_normalizes_supported_handoff_values() -> None:
    """Startup should share one validated locale representation with the launcher."""

    assert extract_locale_override(["main.py"]) is None
    assert extract_locale_override(["main.py", "--locale=zh_CN"]) == "zh-Hans"
    assert extract_locale_override(["main.py", "--locale=ja-JP"]) == "ja"


def test_extract_locale_override_rejects_unsupported_handoff_values() -> None:
    """Malformed or unsupported locale handoffs should fail before composition."""

    with pytest.raises(ValueError, match="locale override"):
        extract_locale_override(["main.py", "--locale=zh-TW"])
    assert (
        extract_handoff_geometry(["main.py", "--handoff-geometry=10,20,1260"]) is None
    )
    assert (
        extract_handoff_geometry(["main.py", "--handoff-geometry=10,20,wide,704"])
        is None
    )


def test_parse_startup_cli_arguments_returns_immutable_bootstrap_inputs() -> None:
    """Startup CLI parsing should combine all startup argument decisions."""

    parsed = parse_startup_cli_arguments(
        [
            "main.py",
            "--no-comfy",
            "--install-root=E:\\Substitute",
            "--handoff-geometry=10,20,1260,800",
            "--locale=zh_CN",
        ]
    )

    assert parsed == StartupCliArguments(
        args=(
            "main.py",
            "--no-comfy",
            "--install-root=E:\\Substitute",
            "--handoff-geometry=10,20,1260,800",
            "--locale=zh_CN",
        ),
        argv_provided=True,
        no_comfy=True,
        handoff_geometry=(10, 20, 1260, 800),
        install_root=Path("E:\\Substitute"),
        locale_override="zh-Hans",
    )


def test_parse_startup_cli_arguments_uses_process_argv_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing explicit argv should parse the active Python process arguments."""

    monkeypatch.setattr(sys, "argv", ["main.py", "--no-comfy"])

    parsed = parse_startup_cli_arguments(None)

    assert parsed.args == ("main.py", "--no-comfy")
    assert parsed.argv_provided is False
    assert parsed.no_comfy is True
    assert parsed.handoff_geometry is None
    assert parsed.install_root is None
    assert parsed.locale_override is None


def test_trace_startup_cli_arguments_emits_prompt_safe_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parsed CLI tracing should live with CLI argument ownership."""

    import substitute.app.bootstrap.startup_cli as startup_cli

    trace_events: list[tuple[str, dict[str, object]]] = []

    def record_trace(event_name: str, **fields: object) -> None:
        """Record one startup CLI trace event."""

        trace_events.append((event_name, fields))

    monkeypatch.setattr(startup_cli, "trace_mark", record_trace)

    trace_startup_cli_arguments(
        StartupCliArguments(
            args=("main.py", "--no-comfy"),
            argv_provided=True,
            no_comfy=True,
            handoff_geometry=(1, 2, 3, 4),
            install_root=None,
            locale_override="ja",
        )
    )

    assert trace_events == [
        ("run_application.enter", {"argv_provided": True}),
        (
            "startup.args_parsed",
            {
                "no_comfy": True,
                "arg_count": 2,
                "handoff_geometry_present": True,
                "locale_override_present": True,
            },
        ),
    ]


def test_ready_app_launch_command_uses_current_runtime_and_install_root(
    tmp_path: Path,
) -> None:
    """In-app restarts should relaunch the same entrypoint under the active runtime."""

    entrypoint = tmp_path / "app" / "main.py"

    command = build_ready_app_launch_command(
        entrypoint_path=entrypoint,
        install_root=tmp_path,
    )

    assert command == [
        sys.executable,
        str(entrypoint),
        f"--install-root={tmp_path}",
    ]


def test_prepare_ready_app_launch_resolves_entrypoint_and_command(
    tmp_path: Path,
) -> None:
    """Startup CLI owner should pair app-layout lookup with restart command setup."""

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    entrypoint = app_dir / "main.py"
    entrypoint.write_text("print('ready')", encoding="utf-8")
    (app_dir / "requirements.txt").write_text("", encoding="utf-8")

    launch = prepare_ready_app_launch(install_root=tmp_path)

    assert launch == StartupReadyAppLaunch(
        entrypoint_path=entrypoint,
        restart_launch_command=[
            sys.executable,
            str(entrypoint),
            f"--install-root={tmp_path}",
        ],
    )


def test_startup_cli_imports_no_forbidden_runtime_boundaries() -> None:
    """Startup CLI parsing must stay free of Qt, presentation, and process launch."""

    imported_modules = _imported_module_names(STARTUP_CLI_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_startup_cli_parsing() -> None:
    """Startup should consume parsed CLI options instead of parsing flags inline."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "parse_startup_cli_arguments(" in source
    assert "import sys" not in source
    assert "extract_handoff_geometry(" not in source
    assert "extract_install_root(" not in source
    assert '"--no-comfy" in cli_args' not in source
    assert '"startup.args_parsed"' not in source
    assert '"run_application.enter"' not in source
    assert "resolve_app_layout(" not in source
    assert "build_ready_app_launch_command(" not in source
    assert "prepare_ready_app_launch(" in source
