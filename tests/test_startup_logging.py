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

"""Verify startup logging policy helpers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.app.bootstrap.startup_logging import (
    PROMPT_OBSERVABILITY_ENV,
    StartupObservabilityPaths,
    configure_startup_observability,
    process_startup_events,
    prompt_observability_enabled,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_LOGGING_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_logging.py"
)
FORBIDDEN_LOGGING_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


class _AppWithEvents:
    """Record startup event pumping calls."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.processed = 0

    def processEvents(self) -> None:
        """Record one Qt-compatible processEvents call."""

        self.processed += 1


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


def test_prompt_observability_is_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt observability logging should be disabled unless explicitly requested."""

    monkeypatch.delenv(PROMPT_OBSERVABILITY_ENV, raising=False)
    assert prompt_observability_enabled() is False

    monkeypatch.setenv(PROMPT_OBSERVABILITY_ENV, "1")
    assert prompt_observability_enabled() is True

    monkeypatch.setenv(PROMPT_OBSERVABILITY_ENV, "false")
    assert prompt_observability_enabled() is False


def test_configure_startup_observability_configures_logs_and_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Startup observability setup should own file logs and trace readiness."""

    import substitute.app.bootstrap.startup_logging as startup_logging

    log_path = tmp_path / "substitute.log"
    prompt_log_path = tmp_path / "prompt.log"
    trace_path = tmp_path / "startup_trace.jsonl"
    log_calls: list[Path] = []
    prompt_log_calls: list[Path] = []
    trace_calls: list[Path] = []
    info_logs: list[dict[str, object]] = []
    trace_marks: list[tuple[str, dict[str, object]]] = []

    def configure_log(logs_dir: Path) -> Path:
        """Record normal log setup and return the configured log path."""

        log_calls.append(logs_dir)
        return log_path

    def configure_prompt_log(logs_dir: Path) -> Path:
        """Record prompt log setup and return the configured prompt log path."""

        prompt_log_calls.append(logs_dir)
        return prompt_log_path

    def configure_trace(logs_dir: Path) -> Path:
        """Record trace setup and return the configured trace path."""

        trace_calls.append(logs_dir)
        return trace_path

    def record_info_log(_logger: object, message: str, **fields: object) -> None:
        """Record one structured info log from startup observability setup."""

        info_logs.append({"message": message, **fields})

    def record_trace_mark(event: str, **fields: object) -> None:
        """Record one startup trace mark."""

        trace_marks.append((event, fields))

    monkeypatch.setenv(PROMPT_OBSERVABILITY_ENV, "1")
    monkeypatch.setattr(
        startup_logging,
        "configure_file_logging",
        configure_log,
    )
    monkeypatch.setattr(
        startup_logging,
        "configure_prompt_observability_logging",
        configure_prompt_log,
    )
    monkeypatch.setattr(
        startup_logging,
        "configure_startup_trace",
        configure_trace,
    )
    monkeypatch.setattr(startup_logging, "log_info", record_info_log)
    monkeypatch.setattr(startup_logging, "trace_mark", record_trace_mark)

    result = configure_startup_observability(tmp_path)

    assert result == StartupObservabilityPaths(
        log_path=log_path,
        prompt_observability_log_path=prompt_log_path,
        trace_path=trace_path,
    )
    assert log_calls == [tmp_path]
    assert prompt_log_calls == [tmp_path]
    assert trace_calls == [tmp_path]
    assert info_logs == [
        {
            "message": "Runtime file logging initialized",
            "log_path": str(log_path),
            "prompt_observability_log_path": str(prompt_log_path),
        }
    ]
    assert trace_marks == [
        (
            "startup.trace.ready",
            {
                "trace_path": trace_path,
                "log_path": log_path,
            },
        )
    ]


def test_process_startup_events_uses_optional_qt_event_pump() -> None:
    """Startup event pumping should tolerate lightweight non-Qt test doubles."""

    app = _AppWithEvents()

    process_startup_events(app)
    process_startup_events(object())

    assert app.processed == 1


def test_startup_logging_imports_no_forbidden_boundaries() -> None:
    """Startup logging policy should stay free of Qt, presentation, and subprocess."""

    imported_modules = _imported_module_names(STARTUP_LOGGING_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_LOGGING_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_logging_policy_helpers() -> None:
    """The startup facade should delegate prompt logging and event pumping helpers."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "def _prompt_observability_enabled" not in source
    assert "def _process_startup_events" not in source
    assert PROMPT_OBSERVABILITY_ENV not in source
    assert "configure_file_logging(" not in source
    assert "configure_prompt_observability_logging(" not in source
    assert "configure_startup_trace(" not in source
    assert "Runtime file logging initialized" not in source
    assert "startup.trace.ready" not in source
