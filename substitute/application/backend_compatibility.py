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

"""Evaluate Substitute BackEnd and SugarCubes runtime compatibility."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from substitute.application.runtime_mode import ApplicationRuntimeModeService
from substitute.domain.comfy_nodepacks import (
    SUGARCUBES_REQUIRED_MINIMUM_VERSION,
    SUBSTITUTE_BACKEND_REQUIRED_MINIMUM_VERSION,
)
from substitute.domain.model_metadata import BackendCapabilities


class BackendCapabilityProvider(Protocol):
    """Describe the capabilities client used by compatibility readiness."""

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return parsed backend capabilities when the target responds."""


class RuntimeCompatibilityStatus(Enum):
    """Classify runtime compatibility failures with stable status codes."""

    COMPATIBLE = "compatible"
    BACKEND_UNREACHABLE = "backend_unreachable"
    BACKEND_VERSION_UNKNOWN = "backend_version_unknown"
    BACKEND_TOO_OLD = "backend_too_old"
    BACKEND_TOO_NEW = "backend_too_new"
    BACKEND_API_MISMATCH = "backend_api_mismatch"
    BACKEND_FEATURE_MISSING = "backend_feature_missing"
    SUGARCUBES_MISSING = "sugarcubes_missing"
    SUGARCUBES_VERSION_UNKNOWN = "sugarcubes_version_unknown"
    SUGARCUBES_TOO_OLD = "sugarcubes_too_old"
    SUGARCUBES_TOO_NEW = "sugarcubes_too_new"
    SUGARCUBES_DEV_VERSION_RELEASE_BLOCKED = "sugarcubes_dev_version_release_blocked"


@dataclass(frozen=True)
class VersionRange:
    """Represent an inclusive lower and exclusive upper semver policy."""

    minimum: str
    maximum_exclusive: str

    def contains(self, version: str) -> bool:
        """Return whether `version` satisfies this semver range."""

        parsed = _semver_key(version)
        return parsed >= _semver_key(self.minimum) and parsed < _semver_key(
            self.maximum_exclusive
        )


@dataclass(frozen=True)
class RuntimeCompatibilityPolicy:
    """Define the runtime contracts required by this Substitute build."""

    required_backend_version: VersionRange = VersionRange(
        SUBSTITUTE_BACKEND_REQUIRED_MINIMUM_VERSION,
        "2.0.0",
    )
    required_backend_api_version: int = 1
    required_backend_features: tuple[str, ...] = (
        "cube-library",
        "prompt-queue-facade",
        "visual-routing",
    )
    required_sugarcubes_version: VersionRange = VersionRange(
        SUGARCUBES_REQUIRED_MINIMUM_VERSION,
        "2.0.0",
    )
    allow_missing_sugarcubes_version_in_dev: bool = True
    allow_dev_sugarcubes_version_in_dev: bool = True


@dataclass(frozen=True)
class BackendCompatibilityResult:
    """Represent compatibility status and user-facing version facts."""

    status: RuntimeCompatibilityStatus
    summary: str
    installed_backend_version: str = ""
    required_backend_version: str = ""
    installed_sugarcubes_version: str = ""
    required_sugarcubes_version: str = ""
    repairable: bool = False
    restart_required_after_repair: bool = False

    @property
    def compatible(self) -> bool:
        """Return whether launch can continue."""

        return self.status is RuntimeCompatibilityStatus.COMPATIBLE


@dataclass(frozen=True)
class BackendCompatibilityService:
    """Evaluate target capabilities against centralized Substitute policy."""

    capability_provider: BackendCapabilityProvider
    runtime_mode: ApplicationRuntimeModeService
    policy: RuntimeCompatibilityPolicy = RuntimeCompatibilityPolicy()

    def assess(self) -> BackendCompatibilityResult:
        """Return compatibility status for the active target backend."""

        capabilities = self.capability_provider.get_capabilities()
        if capabilities is None:
            return BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.BACKEND_UNREACHABLE,
                summary="Substitute BackEnd capabilities could not be read.",
                repairable=True,
            )
        backend_result = self._assess_backend(capabilities)
        if backend_result is not None:
            return backend_result
        sugar_result = self._assess_sugarcubes(capabilities)
        if sugar_result is not None:
            return sugar_result
        return BackendCompatibilityResult(
            status=RuntimeCompatibilityStatus.COMPATIBLE,
            summary="Substitute BackEnd and SugarCubes are compatible.",
            installed_backend_version=capabilities.extension_version,
            required_backend_version=self._backend_range_text(),
            installed_sugarcubes_version=capabilities.cube_library.sugar_cubes_version,
            required_sugarcubes_version=self._sugarcubes_range_text(),
        )

    def _assess_backend(
        self,
        capabilities: BackendCapabilities,
    ) -> BackendCompatibilityResult | None:
        """Return a backend compatibility failure or ``None``."""

        if capabilities.api_version != self.policy.required_backend_api_version:
            return BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.BACKEND_API_MISMATCH,
                summary="Substitute BackEnd API version is incompatible.",
                installed_backend_version=str(capabilities.api_version),
                required_backend_version=str(self.policy.required_backend_api_version),
                repairable=True,
            )
        missing_features = tuple(
            feature
            for feature in self.policy.required_backend_features
            if feature not in capabilities.features
        )
        if missing_features:
            return BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.BACKEND_FEATURE_MISSING,
                summary=(
                    "Substitute BackEnd is missing required features: "
                    + ", ".join(missing_features)
                ),
                installed_backend_version=capabilities.extension_version,
                required_backend_version=self._backend_range_text(),
                repairable=True,
            )
        if not capabilities.extension_version:
            return BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.BACKEND_VERSION_UNKNOWN,
                summary="Substitute BackEnd did not report its extension version.",
                required_backend_version=self._backend_range_text(),
                repairable=True,
            )
        if (
            _is_prerelease(capabilities.extension_version)
            and self.runtime_mode.is_development()
        ):
            return None
        if not self.policy.required_backend_version.contains(
            capabilities.extension_version
        ):
            status = (
                RuntimeCompatibilityStatus.BACKEND_TOO_OLD
                if _semver_key(capabilities.extension_version)
                < _semver_key(self.policy.required_backend_version.minimum)
                else RuntimeCompatibilityStatus.BACKEND_TOO_NEW
            )
            return BackendCompatibilityResult(
                status=status,
                summary="Substitute BackEnd version is incompatible.",
                installed_backend_version=capabilities.extension_version,
                required_backend_version=self._backend_range_text(),
                repairable=True,
            )
        return None

    def _assess_sugarcubes(
        self,
        capabilities: BackendCapabilities,
    ) -> BackendCompatibilityResult | None:
        """Return a SugarCubes compatibility failure or ``None``."""

        cube_library = capabilities.cube_library
        if not cube_library.available:
            return BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.SUGARCUBES_MISSING,
                summary=cube_library.unavailable_reason
                or "SugarCubes is not available on this target.",
                installed_backend_version=capabilities.extension_version,
                required_sugarcubes_version=self._sugarcubes_range_text(),
                repairable=True,
            )
        if not cube_library.sugar_cubes_version:
            if (
                self.runtime_mode.is_development()
                and self.policy.allow_missing_sugarcubes_version_in_dev
            ):
                return None
            return BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.SUGARCUBES_VERSION_UNKNOWN,
                summary="SugarCubes did not report its runtime version.",
                installed_backend_version=capabilities.extension_version,
                required_sugarcubes_version=self._sugarcubes_range_text(),
                repairable=True,
            )
        if _is_prerelease(cube_library.sugar_cubes_version):
            if (
                self.runtime_mode.is_development()
                and self.policy.allow_dev_sugarcubes_version_in_dev
            ):
                return None
            return BackendCompatibilityResult(
                status=(
                    RuntimeCompatibilityStatus.SUGARCUBES_DEV_VERSION_RELEASE_BLOCKED
                ),
                summary="SugarCubes prerelease versions are not allowed in release mode.",
                installed_backend_version=capabilities.extension_version,
                installed_sugarcubes_version=cube_library.sugar_cubes_version,
                required_sugarcubes_version=self._sugarcubes_range_text(),
                repairable=True,
            )
        if not self.policy.required_sugarcubes_version.contains(
            cube_library.sugar_cubes_version
        ):
            status = (
                RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD
                if _semver_key(cube_library.sugar_cubes_version)
                < _semver_key(self.policy.required_sugarcubes_version.minimum)
                else RuntimeCompatibilityStatus.SUGARCUBES_TOO_NEW
            )
            return BackendCompatibilityResult(
                status=status,
                summary="SugarCubes version is incompatible.",
                installed_backend_version=capabilities.extension_version,
                installed_sugarcubes_version=cube_library.sugar_cubes_version,
                required_sugarcubes_version=self._sugarcubes_range_text(),
                repairable=True,
            )
        return None

    def _backend_range_text(self) -> str:
        """Return the configured backend version range."""

        return (
            f">={self.policy.required_backend_version.minimum},"
            f"<{self.policy.required_backend_version.maximum_exclusive}"
        )

    def _sugarcubes_range_text(self) -> str:
        """Return the configured SugarCubes version range."""

        return (
            f">={self.policy.required_sugarcubes_version.minimum},"
            f"<{self.policy.required_sugarcubes_version.maximum_exclusive}"
        )


def _semver_key(version: str) -> tuple[int, int, int, str]:
    """Return a sortable key for semver-like versions."""

    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?([-.+].*)?$", version)
    if match is None:
        return (0, 0, 0, version)
    return (
        int(match.group(1) or 0),
        int(match.group(2) or 0),
        int(match.group(3) or 0),
        match.group(4) or "",
    )


def _is_prerelease(version: str) -> bool:
    """Return whether a version has a prerelease/dev suffix."""

    return bool(re.search(r"(?:-|\.)(?:dev|alpha|beta|rc|pre)", version, re.IGNORECASE))
