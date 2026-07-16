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

"""Tests for central Substitute BackEnd compatibility policy."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.backend_compatibility import (
    BackendCompatibilityService,
    RuntimeCompatibilityStatus,
)
from substitute.application.runtime_mode import (
    ApplicationRuntimeMode,
    ApplicationRuntimeModeService,
)
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendCubeLibraryCapabilities,
)


@dataclass(frozen=True)
class _Provider:
    """Return one configured capabilities payload."""

    capabilities: BackendCapabilities | None

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return parsed capabilities."""

        return self.capabilities


def test_compatibility_accepts_matching_backend_and_sugarcubes() -> None:
    """Compatible BackEnd and SugarCubes versions should pass policy."""

    result = _service(_capabilities()).assess()

    assert result.status is RuntimeCompatibilityStatus.COMPATIBLE
    assert result.compatible is True


def test_compatibility_blocks_too_old_backend() -> None:
    """Backend semver is enforced centrally."""

    result = _service(_capabilities(extension_version="1.5.0")).assess()

    assert result.status is RuntimeCompatibilityStatus.BACKEND_TOO_OLD
    assert result.repairable is True
    assert result.required_backend_version == ">=1.7.0,<2.0.0"


def test_compatibility_blocks_sugarcubes_before_required_release() -> None:
    """SugarCubes releases below the application baseline should require repair."""

    result = _service(_capabilities(sugar_cubes_version="0.9.3")).assess()

    assert result.status is RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD
    assert result.repairable is True
    assert result.required_sugarcubes_version == ">=0.10.0,<2.0.0"


def test_compatibility_allows_missing_sugarcubes_version_only_in_dev() -> None:
    """Missing SugarCubes version is a dev-only allowance."""

    dev_result = _service(
        _capabilities(sugar_cubes_version=""),
        mode=ApplicationRuntimeMode.DEVELOPMENT,
    ).assess()
    release_result = _service(
        _capabilities(sugar_cubes_version=""),
        mode=ApplicationRuntimeMode.RELEASE,
    ).assess()

    assert dev_result.status is RuntimeCompatibilityStatus.COMPATIBLE
    assert (
        release_result.status is RuntimeCompatibilityStatus.SUGARCUBES_VERSION_UNKNOWN
    )


def test_compatibility_reports_missing_sugarcubes() -> None:
    """Unavailable Cube Library support should report SugarCubes as missing."""

    result = _service(_capabilities(sugarcubes_available=False)).assess()

    assert result.status is RuntimeCompatibilityStatus.SUGARCUBES_MISSING
    assert "SugarCubes" in result.summary


def _service(
    capabilities: BackendCapabilities | None,
    *,
    mode: ApplicationRuntimeMode = ApplicationRuntimeMode.RELEASE,
) -> BackendCompatibilityService:
    """Build a compatibility service for tests."""

    return BackendCompatibilityService(
        capability_provider=_Provider(capabilities),
        runtime_mode=ApplicationRuntimeModeService(mode),
    )


def _capabilities(
    *,
    extension_version: str = "1.7.0",
    sugar_cubes_version: str = "0.10.0",
    sugarcubes_available: bool = True,
) -> BackendCapabilities:
    """Return compatible capabilities with override hooks."""

    return BackendCapabilities(
        api_version=1,
        model_metadata_schema_version=1,
        supported_model_kinds=("checkpoints",),
        background_hashing=True,
        hash_lookup=True,
        local_preview_serving=True,
        sidecar_reading=True,
        extension_version=extension_version,
        features=("cube-library", "prompt-queue-facade", "visual-routing"),
        cube_library=BackendCubeLibraryCapabilities(
            schema_version=1,
            available=sugarcubes_available,
            unavailable_reason="SugarCubes is not available on this target.",
            sugar_cubes_version=sugar_cubes_version,
            catalog_supported=sugarcubes_available,
            artifact_load_supported=sugarcubes_available,
            pack_management_supported=sugarcubes_available,
            dependency_readiness_supported=sugarcubes_available,
            dependency_repair_supported=sugarcubes_available,
            versioned_dependency_readiness_supported=sugarcubes_available,
            sync_dependency_orchestration_supported=sugarcubes_available,
        ),
    )
