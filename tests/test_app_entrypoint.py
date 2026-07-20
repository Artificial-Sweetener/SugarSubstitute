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

"""Characterize the root application entrypoint handoff behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

import main as app_entrypoint
from substitute.app.bootstrap.startup_timing import StartupTimingRecord


def test_main_starts_early_splash_and_passes_it_to_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root entrypoint should hand the early splash into app bootstrap."""

    calls: list[tuple[str, object]] = []
    splash = _Splash()
    relay = _CancelRelay()
    argv = ["main.py", "--install-root=E:\\SugarSubstitute"]

    env_file_module = ModuleType("substitute.app.bootstrap.env_file")
    env_file_module.load_env_file = lambda path: calls.append(("env", path))  # type: ignore[attr-defined]
    early_splash_module = ModuleType("substitute.app.bootstrap.early_launch_splash")

    def start_early_launch_splash(
        passed_argv: list[str],
        app_root: Path,
        language_identifier: str,
    ) -> tuple[_Splash, _CancelRelay]:
        """Record entrypoint splash startup arguments."""

        calls.append(("splash_argv", list(passed_argv)))
        calls.append(("splash_root", app_root))
        calls.append(("splash_locale", language_identifier))
        return splash, relay

    early_splash_module.start_early_launch_splash = start_early_launch_splash  # type: ignore[attr-defined]
    startup_module = ModuleType("substitute.app.bootstrap.startup")

    def run_application(passed_argv: list[str], **kwargs: object) -> int:
        """Record bootstrap arguments and return the app exit code."""

        calls.append(("run_argv", list(passed_argv)))
        calls.append(("initial_splash", kwargs["initial_splash"]))
        calls.append(("cancel_connector", kwargs["initial_splash_cancel_connector"]))
        timing_records = cast(
            tuple[StartupTimingRecord, ...],
            kwargs["prebootstrap_timing_records"],
        )
        calls.append(
            (
                "prebootstrap_phases",
                tuple(record.phase for record in timing_records),
            )
        )
        return 7

    startup_module.run_application = run_application  # type: ignore[attr-defined]

    monkeypatch.setitem(
        sys.modules, "substitute.app.bootstrap.env_file", env_file_module
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.app.bootstrap.early_launch_splash",
        early_splash_module,
    )
    monkeypatch.setitem(sys.modules, "substitute.app.bootstrap.startup", startup_module)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        app_entrypoint,
        "resolve_early_startup_locale",
        lambda *_args, **_kwargs: SimpleNamespace(
            effective_language=SimpleNamespace(identifier="ja")
        ),
    )

    with pytest.raises(SystemExit) as exit_info:
        app_entrypoint.main()

    assert exit_info.value.code == 7
    assert calls == [
        ("env", Path(app_entrypoint.__file__).resolve().parent / ".env"),
        ("splash_argv", argv),
        ("splash_root", Path(app_entrypoint.__file__).resolve().parent),
        ("splash_locale", "ja"),
        ("run_argv", argv),
        ("initial_splash", splash),
        ("cancel_connector", relay.connect),
        (
            "prebootstrap_phases",
            (
                "entrypoint.resolve_app_root",
                "entrypoint.load_env_file",
                "entrypoint.import_early_launch_splash",
                "entrypoint.start_early_launch_splash",
                "entrypoint.import_startup",
            ),
        ),
    ]
    assert splash.closed is False


def test_main_closes_early_splash_when_bootstrap_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root entrypoint should dispose the early splash on bootstrap failure."""

    splash = _Splash()
    relay = _CancelRelay()
    env_file_module = ModuleType("substitute.app.bootstrap.env_file")
    env_file_module.load_env_file = lambda _path: None  # type: ignore[attr-defined]
    early_splash_module = ModuleType("substitute.app.bootstrap.early_launch_splash")
    setattr(
        early_splash_module,
        "start_early_launch_splash",
        lambda _argv, _root, _locale: (splash, relay),
    )
    startup_module = ModuleType("substitute.app.bootstrap.startup")

    def run_application(*_args: object, **_kwargs: object) -> int:
        """Raise a startup failure after splash creation."""

        raise RuntimeError("startup failed")

    startup_module.run_application = run_application  # type: ignore[attr-defined]

    monkeypatch.setitem(
        sys.modules, "substitute.app.bootstrap.env_file", env_file_module
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.app.bootstrap.early_launch_splash",
        early_splash_module,
    )
    monkeypatch.setitem(sys.modules, "substitute.app.bootstrap.startup", startup_module)
    monkeypatch.setattr(sys, "argv", ["main.py"])

    with pytest.raises(RuntimeError, match="startup failed"):
        app_entrypoint.main()

    assert splash.closed is True


class _Splash:
    """Record close calls from the root entrypoint."""

    def __init__(self) -> None:
        """Initialize the splash as open."""

        self.closed = False

    def close(self) -> None:
        """Record that the splash was closed."""

        self.closed = True


class _CancelRelay:
    """Expose a stable cancel connector bound method."""

    def __init__(self) -> None:
        """Initialize without connected callbacks."""

        self.callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        """Record one connected callback."""

        self.callbacks.append(callback)
