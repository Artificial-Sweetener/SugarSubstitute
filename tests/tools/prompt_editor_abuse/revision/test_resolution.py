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

"""Verify bounded optional Git provenance for prompt-editor qualification."""

from __future__ import annotations

from collections.abc import Callable
import subprocess
from typing import NoReturn

import pytest

from tools.prompt_editor_abuse import revision


def test_revision_resolver_returns_trimmed_revision() -> None:
    """Preserve available Git provenance without surrounding whitespace."""

    def succeed(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return one successful synthetic Git result."""

        return subprocess.CompletedProcess([], 0, stdout="abc123\n", stderr="")

    assert revision.resolve_git_revision(runner=succeed) == "abc123"


def test_revision_resolver_treats_nonzero_git_as_optional() -> None:
    """Keep qualification usable outside a Git checkout."""

    def fail(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return one unsuccessful synthetic Git result."""

        return subprocess.CompletedProcess([], 1, stdout="", stderr="missing")

    assert revision.resolve_git_revision(runner=fail) == "unknown"


@pytest.mark.parametrize(
    "failure",
    (
        lambda: subprocess.TimeoutExpired(["git"], 5),
        lambda: OSError("git unavailable"),
    ),
)
def test_revision_resolver_bounds_unavailable_git(
    failure: Callable[[], BaseException],
) -> None:
    """Make timeout and launch failure nonfatal to campaign evidence."""

    def raise_failure(*_args: object, **_kwargs: object) -> NoReturn:
        """Raise one controlled external-boundary failure."""

        raise failure()

    assert revision.resolve_git_revision(runner=raise_failure) == "unknown"
