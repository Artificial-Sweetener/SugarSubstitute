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

"""Verify Output transfer-format defaults and fallback policy."""

from __future__ import annotations

import json
from pathlib import Path


from substitute.domain.generation import (
    effective_output_transfer_format,
    JpegOutputSettings,
    OutputPreferences,
    OutputTransferFormat,
    OutputTransferSettings,
)
from substitute.infrastructure.persistence import (
    FileOutputPreferenceRepository,
)


def test_jpeg_quality_defaults_to_100_without_overwriting_persisted_values(
    tmp_path: Path,
) -> None:
    """Missing quality should use 100 while an explicit older value remains intact."""

    preferences_path = tmp_path / "output_organization.json"
    preferences_path.write_text(
        json.dumps({"schema_version": "2", "jpeg": {"enabled": True}}),
        encoding="utf-8",
    )

    assert FileOutputPreferenceRepository(tmp_path).load().jpeg.quality == 100

    preferences_path.write_text(
        json.dumps(
            {
                "schema_version": "2",
                "jpeg": {"enabled": True, "quality": 90},
            }
        ),
        encoding="utf-8",
    )

    assert FileOutputPreferenceRepository(tmp_path).load().jpeg.quality == 90


def test_jpeg_transfer_preference_falls_back_without_companion_generation() -> None:
    """JPEG transfer selection should remain stored but inactive until JPEG exists."""

    preferences = OutputPreferences(
        transfer=OutputTransferSettings(
            preferred_format=OutputTransferFormat.COMPANION_JPEG
        )
    )

    assert (
        effective_output_transfer_format(preferences)
        is OutputTransferFormat.CANONICAL_PNG
    )
    assert (
        effective_output_transfer_format(
            OutputPreferences(
                jpeg=JpegOutputSettings(enabled=True),
                transfer=preferences.transfer,
            )
        )
        is OutputTransferFormat.COMPANION_JPEG
    )
