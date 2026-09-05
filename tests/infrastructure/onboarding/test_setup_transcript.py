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

"""Verify durable onboarding setup transcript ownership."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.onboarding.setup_transcript import (
    OnboardingSetupTranscript,
)


def test_transcript_retains_every_flushed_line_across_reopen(tmp_path: Path) -> None:
    """Keep complete setup output independently of the bounded presentation view."""

    transcript = OnboardingSetupTranscript.open(tmp_path)
    assert transcript is not None
    transcript.append("Preparing runtime")
    transcript.append("Installing ComfyUI")
    path = transcript.path
    transcript.close()

    reopened = OnboardingSetupTranscript.open(tmp_path)
    assert reopened is not None
    reopened.append("Validating setup")
    reopened.close()

    assert path.read_text(encoding="utf-8").splitlines() == [
        "Preparing runtime",
        "Installing ComfyUI",
        "Validating setup",
    ]
