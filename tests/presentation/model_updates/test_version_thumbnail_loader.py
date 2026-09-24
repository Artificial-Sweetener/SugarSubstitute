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

"""Verify model-version preview failures remain reported task outcomes."""

from __future__ import annotations

from dataclasses import replace

from substitute.presentation.model_updates.version_thumbnail_loader import (
    VersionThumbnailLoad,
)
from tests.presentation.model_updates.support import update_proposal


def test_unexpected_preview_failure_reports_fallback_and_finishes() -> None:
    """An untrusted transport exception must not escape a QRunnable boundary."""

    candidate = replace(
        update_proposal("a" * 64).candidate,
        thumbnail_url="https://example.invalid/preview",
    )

    def fail(_url: str) -> bytes:
        """Simulate an unexpected network adapter failure."""

        raise LookupError("synthetic preview adapter failure")

    job = VersionThumbnailLoad((candidate,), fetch=fail)
    failed: list[int] = []
    finished: list[bool] = []
    job.signals.failed.connect(failed.append)
    job.signals.finished.connect(lambda: finished.append(True))

    job.run()

    assert failed == [candidate.version_id]
    assert finished == [True]
