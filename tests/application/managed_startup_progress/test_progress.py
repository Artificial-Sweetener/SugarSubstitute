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

"""Verify managed startup progress copy policy."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.managed_startup_progress import (
    managed_startup_progress_text,
)


@pytest.mark.parametrize(
    ("elapsed_seconds", "animation_frame", "expected"),
    (
        (0.0, 0, "Waiting for ComfyUI to become ready."),
        (1.0, 1, "Waiting for ComfyUI to become ready.."),
        (2.0, 2, "Waiting for ComfyUI to become ready..."),
        (120.0, 3, "ComfyUI is taking longer than usual."),
        (121.0, 4, "ComfyUI is taking longer than usual.."),
        (122.0, 5, "ComfyUI is taking longer than usual..."),
        (
            300.0,
            4,
            "Still waiting—custom nodes, slow storage, or a startup issue may be "
            "delaying ComfyUI..",
        ),
        (
            301.0,
            5,
            "Still waiting—custom nodes, slow storage, or a startup issue may be "
            "delaying ComfyUI...",
        ),
        (
            302.0,
            6,
            "Still waiting—custom nodes, slow storage, or a startup issue may be "
            "delaying ComfyUI.",
        ),
    ),
)
def test_managed_startup_progress_copy_escalates_at_owned_milestones(
    elapsed_seconds: float,
    animation_frame: int,
    expected: str,
) -> None:
    """Escalate concise progress copy at the owned 120 and 300 second milestones."""

    message = managed_startup_progress_text(
        elapsed_seconds=elapsed_seconds,
        animation_frame=animation_frame,
    )

    assert render_source_application_text(message) == expected
