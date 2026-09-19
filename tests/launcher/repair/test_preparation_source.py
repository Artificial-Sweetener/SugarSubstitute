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

"""Verify exact repair source identity across the inert worker request boundary."""

from pathlib import Path
from typing import Never

import pytest

from launcher.sugarsubstitute_launcher.release_sources import (
    LocalFolderReleaseSource,
    VersionBoundReleaseSource,
)
from launcher.sugarsubstitute_launcher.repair_preparation_source import (
    RepairPreparationSource,
)


def test_local_source_round_trip_keeps_the_selected_folder(tmp_path: Path) -> None:
    """Resolve the parent's relative path before a worker changes working directory."""
    source = LocalFolderReleaseSource(tmp_path / "synthetic release")
    restored = RepairPreparationSource.from_json(
        RepairPreparationSource.capture(source).to_json()
    )
    assert restored.source == source
    assert not source.root.exists()


def test_bound_source_round_trip_retains_version_channel_and_update_feed() -> None:
    """Keep exact repair identity separate from the ongoing channel update URL."""
    source = VersionBoundReleaseSource(
        "https://example.invalid/v1.2.3/manifest.json",
        "1.2.3",
        "canary",
        "https://example.invalid/rolling/manifest.json",
    )
    restored = RepairPreparationSource.from_json(
        RepairPreparationSource.capture(source).to_json()
    )
    assert restored.source == source


def test_source_capture_does_not_fetch_an_unknown_provider() -> None:
    """Never turn serialization into an uninterruptible parent-side manifest fetch."""

    class UnexpectedSource:
        """Represent an unsupported source whose implementation must not execute."""

        def load_manifest(self) -> Never:
            """Reject any attempt to resolve arbitrary provider code in the parent."""
            raise AssertionError("Source capture attempted provider execution")

    with pytest.raises(TypeError, match="repair source"):
        RepairPreparationSource.capture(UnexpectedSource())


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"kind": "unknown"},
        {"kind": "local", "root": 42},
        {"kind": "local", "root": ""},
        {
            "kind": "version_bound",
            "manifest_url": "https://example.invalid/manifest.json",
        },
    ],
)
def test_malformed_source_is_rejected_before_provider_use(payload: object) -> None:
    """Reject incomplete or unsupported worker input instead of selecting defaults."""
    with pytest.raises(ValueError):
        RepairPreparationSource.from_json(payload)
