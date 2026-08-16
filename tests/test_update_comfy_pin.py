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

"""Tests for managed-Comfy pin-update automation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.pinned_catalog import (
    DEFAULT_PIN_PATH,
    PinnedStandaloneEnvironmentCatalog,
)
from tools.update_comfy_pin import update_comfy_pin


class _Catalog:
    """Return deterministic releases for every standalone variant."""

    def __init__(self, releases: tuple[StandaloneEnvironmentRelease, ...]) -> None:
        """Index releases by their variant identity."""

        self._releases = {release.variant: release for release in releases}

    def resolve(self, variant: StandaloneVariantId) -> StandaloneEnvironmentRelease:
        """Return the configured release for one variant."""

        return self._releases[variant]


def test_pin_update_leaves_identical_pin_bytes_unchanged(tmp_path: Path) -> None:
    """A scheduled no-op must not create noisy automation commits."""

    pin_path = tmp_path / DEFAULT_PIN_PATH.name
    original = DEFAULT_PIN_PATH.read_bytes()
    pin_path.write_bytes(original)
    catalog = PinnedStandaloneEnvironmentCatalog.load(pin_path)

    result = update_comfy_pin(
        pin_path=pin_path,
        live_catalog=_Catalog(_releases(catalog)),
    )

    assert result.changed is False
    assert pin_path.read_bytes() == original


def test_pin_update_writes_complete_proposed_catalog(tmp_path: Path) -> None:
    """Any upstream change should produce one complete reviewable pin diff."""

    pin_path = tmp_path / DEFAULT_PIN_PATH.name
    pin_path.write_bytes(DEFAULT_PIN_PATH.read_bytes())
    current = PinnedStandaloneEnvironmentCatalog.load(pin_path)
    proposed = tuple(
        replace(
            release,
            release_tag="v0.30.0-env1",
            comfyui_version="v0.29.0",
        )
        for release in _releases(current)
    )

    result = update_comfy_pin(
        pin_path=pin_path,
        live_catalog=_Catalog(proposed),
    )

    updated = PinnedStandaloneEnvironmentCatalog.load(pin_path)
    assert result.changed is True
    assert result.previous_release_tags == ("v0.29.0-env1",)
    assert result.proposed_release_tags == ("v0.30.0-env1",)
    assert {
        updated.resolve(variant).comfyui_version for variant in StandaloneVariantId
    } == {"v0.29.0"}


def _releases(
    catalog: PinnedStandaloneEnvironmentCatalog,
) -> tuple[StandaloneEnvironmentRelease, ...]:
    """Return releases in authoritative variant order."""

    return tuple(catalog.resolve(variant) for variant in StandaloneVariantId)
