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

"""Tests for the authoritative managed-Comfy standalone pin."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneCatalogError,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.pinned_catalog import (
    DEFAULT_PIN_PATH,
    PinnedStandaloneEnvironmentCatalog,
    write_pinned_catalog,
)


def test_default_pin_covers_every_supported_standalone_variant() -> None:
    """Cover every supported variant without falling back to live data."""

    catalog = PinnedStandaloneEnvironmentCatalog.load_default()

    releases = tuple(catalog.resolve(variant) for variant in StandaloneVariantId)
    assert {release.variant for release in releases} == set(StandaloneVariantId)
    assert {release.release_tag for release in releases} == {"v0.29.0-env1"}
    assert {release.comfyui_version for release in releases} == {"v0.28.0"}
    assert all(release.artifacts for release in releases)
    assert all(
        artifact.url.startswith("https://github.com/") and len(artifact.sha256) == 64
        for release in releases
        for artifact in release.artifacts
    )


def test_pin_rejects_missing_variant() -> None:
    """Reject partial upstream catalogs before they become production pins."""

    payload = _default_pin_payload()
    del payload["releases"][StandaloneVariantId.MACOS_MPS.value]

    with pytest.raises(StandaloneCatalogError, match="incomplete"):
        PinnedStandaloneEnvironmentCatalog.from_json(payload)


def test_pin_rejects_insecure_artifact_url() -> None:
    """Require HTTPS artifact URLs before any managed download occurs."""

    payload = _default_pin_payload()
    payload["releases"][StandaloneVariantId.WINDOWS_CPU.value]["artifacts"][0][
        "url"
    ] = "http://example.invalid/environment.7z"

    with pytest.raises(StandaloneCatalogError, match="HTTPS"):
        PinnedStandaloneEnvironmentCatalog.from_json(payload)


def test_pin_rejects_malformed_sha256() -> None:
    """Reject malformed artifact integrity metadata before managed downloads."""

    payload = _default_pin_payload()
    payload["releases"][StandaloneVariantId.WINDOWS_CPU.value]["artifacts"][0][
        "sha256"
    ] = "not-a-digest"

    with pytest.raises(StandaloneCatalogError, match="SHA256"):
        PinnedStandaloneEnvironmentCatalog.from_json(payload)


def test_pin_writer_round_trips_deterministically(tmp_path: Path) -> None:
    """Write stable reviewable pin changes for automation."""

    catalog = PinnedStandaloneEnvironmentCatalog.load_default()
    releases = tuple(catalog.resolve(variant) for variant in StandaloneVariantId)
    output_path = tmp_path / "standalone_environment_pin.json"

    write_pinned_catalog(output_path, releases)

    assert PinnedStandaloneEnvironmentCatalog.load(output_path).to_json() == (
        catalog.to_json()
    )
    assert output_path.read_text(encoding="utf-8") == DEFAULT_PIN_PATH.read_text(
        encoding="utf-8"
    )


def _default_pin_payload() -> dict[str, Any]:
    """Return mutable decoded production pin data for failure tests."""

    payload = json.loads(DEFAULT_PIN_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return deepcopy(payload)
