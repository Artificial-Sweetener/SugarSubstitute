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

"""Tests for deterministic GUI shell resource ownership."""

from __future__ import annotations

import pytest

from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
    ShellResourceShutdownError,
)


def test_shell_resource_lifecycle_releases_in_reverse_construction_order() -> None:
    """Shutdown should unwind resources once in reverse registration order."""

    calls: list[str] = []
    lifecycle = ShellResourceLifecycle()
    lifecycle.register("first", lambda: calls.append("first"))
    lifecycle.register("second", lambda: calls.append("second"))

    lifecycle.shutdown_or_raise()
    lifecycle.shutdown_or_raise()

    assert calls == ["second", "first"]
    assert lifecycle.is_shutdown is True


def test_shell_resource_lifecycle_retries_only_failed_cleanups() -> None:
    """A failed cleanup should remain available without repeating successful work."""

    calls: list[str] = []
    failure_count = 0

    def fail_once() -> None:
        """Fail the first cleanup attempt and succeed on retry."""

        nonlocal failure_count
        calls.append("retryable")
        failure_count += 1
        if failure_count == 1:
            raise RuntimeError("busy")

    lifecycle = ShellResourceLifecycle()
    lifecycle.register("stable", lambda: calls.append("stable"))
    lifecycle.register("retryable", fail_once)

    with pytest.raises(ShellResourceShutdownError, match="retryable"):
        lifecycle.shutdown_or_raise()
    lifecycle.shutdown_or_raise()

    assert calls == ["retryable", "stable", "retryable"]
    assert lifecycle.is_shutdown is True
