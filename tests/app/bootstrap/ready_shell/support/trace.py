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

"""Capture deterministic ready-shell startup traces."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from substitute.app.bootstrap import (
    pre_show_restore_projection,
    ready_shell_controller,
    ready_shell_minimum_ready,
    ready_shell_reveal,
    ready_shell_restore_controller,
    startup_model_metadata,
    startup_warmup_controller,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def _patch_trace(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[str, dict[str, object]]],
) -> None:
    """Patch trace calls used by the ready-shell controller slice."""

    monkeypatch.setattr(
        ready_shell_controller,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        ready_shell_reveal,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        ready_shell_minimum_ready,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        startup_model_metadata,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        startup_warmup_controller,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        pre_show_restore_projection,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    @contextmanager
    def fake_span(name: str, **_fields: object) -> Iterator[None]:
        calls = getattr(_patch_trace, "calls")
        calls.append(f"span:start:{name}")
        yield
        calls.append(f"span:end:{name}")

    monkeypatch.setattr(ready_shell_controller, "trace_span", fake_span)
    monkeypatch.setattr(ready_shell_reveal, "trace_span", fake_span)
    monkeypatch.setattr(ready_shell_restore_controller, "trace_span", fake_span)
