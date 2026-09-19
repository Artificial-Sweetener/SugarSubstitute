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

"""Resolve optional source provenance for prompt-editor qualification reports."""

from __future__ import annotations

import logging
import subprocess
from typing import Protocol, cast


_LOGGER = logging.getLogger(__name__)


class RevisionCommandRunner(Protocol):
    """Run the bounded read-only Git provenance command."""

    def __call__(
        self,
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        """Return the completed Git command."""


def resolve_git_revision(*, runner: RevisionCommandRunner | None = None) -> str:
    """Return bounded Git provenance without making qualification depend on Git."""

    command_runner = runner or cast(RevisionCommandRunner, subprocess.run)
    try:
        completed = command_runner(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        _LOGGER.debug("Git revision provenance is unavailable: %s", error)
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


__all__ = ["resolve_git_revision", "RevisionCommandRunner"]
