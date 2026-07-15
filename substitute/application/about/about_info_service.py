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

"""Build the About Settings snapshot from local and runtime metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.about.models import (
    ABOUT_PROJECT_SUMMARY,
    ABOUT_SPECIAL_THANKS,
    ABOUT_SUPPORTERS,
    AboutInfoSnapshot,
    AboutVersionRow,
    AboutVersionStatus,
)
from substitute.application.about.app_version import current_app_version
from substitute.domain.comfy_runtime import ComfyRuntimeInfo
from substitute.domain.model_metadata import BackendCapabilities
from substitute.domain.runtime_versions import (
    QPANE_DISTRIBUTION_NAMES,
    PYSIDE6_DISTRIBUTION_NAMES,
    PYSIDE6_FLUENT_WIDGETS_DISTRIBUTION_NAMES,
    SUGARSUBSTITUTE_DISTRIBUTION_NAMES,
)

_UNKNOWN = "Unknown"
_UNAVAILABLE = "Unavailable"
_NOT_CONNECTED = "Not connected"
_SOURCE_CHECKOUT = "source checkout"


@dataclass(frozen=True, slots=True)
class _VersionComponentInfo:
    """Describe stable About display metadata for one versioned component."""

    label: str
    subtitle: str
    authors: str
    external_url: str


_SUGARSUBSTITUTE_INFO = _VersionComponentInfo(
    label="SugarSubstitute",
    subtitle="The desktop native Qt frontend for ComfyUI",
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/SugarSubstitute",
)
_COMFYUI_INFO = _VersionComponentInfo(
    label="ComfyUI",
    subtitle="The most powerful and modular diffusion model GUI, api and backend",
    authors="Comfy Org",
    external_url="https://github.com/Comfy-Org/ComfyUI",
)
_BACKEND_INFO = _VersionComponentInfo(
    label="Substitute Backend",
    subtitle="Allow communication between ComfyUI deployments & Substitute",
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/Substitute-Backend",
)
_SUGAR_CUBES_INFO = _VersionComponentInfo(
    label="SugarCubes",
    subtitle="Composable workflow units for ComfyUI",
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/SugarCubes",
)
_SUGAR_DSL_INFO = _VersionComponentInfo(
    label="Sugar-DSL",
    subtitle="The scripting language for composing ComfyUI workflows with SugarCubes",
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/Sugar-DSL",
)
_QPANE_INFO = _VersionComponentInfo(
    label="QPane",
    subtitle="High-performance PySide6 image viewer",
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/QPane",
)
_PYSIDE_FLUENT_WIDGETS_INFO = _VersionComponentInfo(
    label="PySide6-Fluent-Widgets",
    subtitle="A fluent design widgets library for PySide6",
    authors="zhiyiYo",
    external_url="https://github.com/zhiyiYo/PyQt-Fluent-Widgets",
)
_PYSIDE_INFO = _VersionComponentInfo(
    label="PySide6",
    subtitle="Qt for Python",
    authors="the Qt Company",
    external_url="https://pyside.org/",
)


class BackendCapabilityProvider(Protocol):
    """Describe the Backend capability source used by About metadata."""

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return parsed backend capabilities when the target responds."""


class ComfyRuntimeInfoProvider(Protocol):
    """Describe a provider for Comfy runtime facts."""

    def __call__(self) -> ComfyRuntimeInfo | None:
        """Return Comfy runtime information or None when unavailable."""


class LocalPackageVersionResolver(Protocol):
    """Describe local Python package version resolution."""

    def __call__(
        self,
        distribution_names: tuple[str, ...],
        *,
        fallback: str,
    ) -> str:
        """Return a package version or the provided fallback."""


class AppVersionProvider(Protocol):
    """Describe a provider for the SugarSubstitute source payload version."""

    def __call__(self) -> str:
        """Return the current app version."""


class AboutInfoService:
    """Build the About Settings snapshot from local and runtime metadata."""

    def __init__(
        self,
        *,
        backend_capabilities: BackendCapabilityProvider,
        comfy_runtime_info: ComfyRuntimeInfoProvider,
        local_versions: LocalPackageVersionResolver,
        app_version: AppVersionProvider = current_app_version,
        project_summary: str = ABOUT_PROJECT_SUMMARY,
        supporters: tuple[str, ...] = ABOUT_SUPPORTERS,
        special_thanks: tuple[str, ...] = ABOUT_SPECIAL_THANKS,
    ) -> None:
        """Store the metadata providers used to build About snapshots."""

        self._backend_capabilities = backend_capabilities
        self._comfy_runtime_info = comfy_runtime_info
        self._local_versions = local_versions
        self._app_version = app_version
        self._project_summary = project_summary
        self._supporters = supporters
        self._special_thanks = special_thanks

    def snapshot(self) -> AboutInfoSnapshot:
        """Return the current About information snapshot."""

        capabilities = self._backend_capabilities.get_capabilities()
        runtime_info = self._comfy_runtime_info()
        return AboutInfoSnapshot(
            versions=(
                self._sugarsubstitute_version_row(),
                self._comfyui_version_row(runtime_info),
                self._sugar_cubes_version_row(capabilities),
                self._backend_version_row(capabilities),
                self._sugar_dsl_version_row(capabilities),
                self._local_version_row(
                    _QPANE_INFO,
                    QPANE_DISTRIBUTION_NAMES,
                    fallback=_UNKNOWN,
                ),
                self._local_version_row(
                    _PYSIDE_FLUENT_WIDGETS_INFO,
                    PYSIDE6_FLUENT_WIDGETS_DISTRIBUTION_NAMES,
                    fallback=_UNKNOWN,
                ),
                self._local_version_row(
                    _PYSIDE_INFO,
                    PYSIDE6_DISTRIBUTION_NAMES,
                    fallback=_UNKNOWN,
                ),
            ),
            project_summary=self._project_summary,
            supporters=self._supporters,
            special_thanks=self._special_thanks,
        )

    def _sugarsubstitute_version_row(self) -> AboutVersionRow:
        """Return the SugarSubstitute source payload version row."""

        value = self._app_version()
        if not value:
            value = self._local_versions(
                SUGARSUBSTITUTE_DISTRIBUTION_NAMES,
                fallback=_SOURCE_CHECKOUT,
            )
        return _version_row(
            _SUGARSUBSTITUTE_INFO,
            value=value,
            status=AboutVersionStatus.AVAILABLE,
        )

    def placeholder_snapshot(self) -> AboutInfoSnapshot:
        """Return a non-network placeholder snapshot for initial page construction."""

        return AboutInfoSnapshot(
            versions=(
                AboutVersionRow(
                    label=_SUGARSUBSTITUTE_INFO.label,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                    subtitle=_SUGARSUBSTITUTE_INFO.subtitle,
                    authors=_SUGARSUBSTITUTE_INFO.authors,
                    external_url=_SUGARSUBSTITUTE_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_COMFYUI_INFO.label,
                    value=_NOT_CONNECTED,
                    status=AboutVersionStatus.NOT_CONNECTED,
                    subtitle=_COMFYUI_INFO.subtitle,
                    authors=_COMFYUI_INFO.authors,
                    external_url=_COMFYUI_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_SUGAR_CUBES_INFO.label,
                    value=_NOT_CONNECTED,
                    status=AboutVersionStatus.NOT_CONNECTED,
                    subtitle=_SUGAR_CUBES_INFO.subtitle,
                    authors=_SUGAR_CUBES_INFO.authors,
                    external_url=_SUGAR_CUBES_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_BACKEND_INFO.label,
                    value=_NOT_CONNECTED,
                    status=AboutVersionStatus.NOT_CONNECTED,
                    subtitle=_BACKEND_INFO.subtitle,
                    authors=_BACKEND_INFO.authors,
                    external_url=_BACKEND_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_SUGAR_DSL_INFO.label,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                    subtitle=_SUGAR_DSL_INFO.subtitle,
                    authors=_SUGAR_DSL_INFO.authors,
                    external_url=_SUGAR_DSL_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_QPANE_INFO.label,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                    subtitle=_QPANE_INFO.subtitle,
                    authors=_QPANE_INFO.authors,
                    external_url=_QPANE_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_PYSIDE_FLUENT_WIDGETS_INFO.label,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                    subtitle=_PYSIDE_FLUENT_WIDGETS_INFO.subtitle,
                    authors=_PYSIDE_FLUENT_WIDGETS_INFO.authors,
                    external_url=_PYSIDE_FLUENT_WIDGETS_INFO.external_url,
                ),
                AboutVersionRow(
                    label=_PYSIDE_INFO.label,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                    subtitle=_PYSIDE_INFO.subtitle,
                    authors=_PYSIDE_INFO.authors,
                    external_url=_PYSIDE_INFO.external_url,
                ),
            ),
            project_summary=self._project_summary,
            supporters=self._supporters,
            special_thanks=self._special_thanks,
        )

    def _local_version_row(
        self,
        component: _VersionComponentInfo,
        distribution_names: tuple[str, ...],
        *,
        fallback: str,
    ) -> AboutVersionRow:
        """Return one local Python package version row."""

        value = self._local_versions(distribution_names, fallback=fallback)
        status = (
            AboutVersionStatus.UNKNOWN
            if value == _UNKNOWN
            else AboutVersionStatus.AVAILABLE
        )
        return _version_row(component, value=value, status=status)

    def _backend_version_row(
        self,
        capabilities: BackendCapabilities | None,
    ) -> AboutVersionRow:
        """Return the Substitute Backend version row."""

        if capabilities is None:
            return AboutVersionRow(
                label=_BACKEND_INFO.label,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
                subtitle=_BACKEND_INFO.subtitle,
                authors=_BACKEND_INFO.authors,
                external_url=_BACKEND_INFO.external_url,
            )
        if not capabilities.extension_version:
            return AboutVersionRow(
                label=_BACKEND_INFO.label,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
                subtitle=_BACKEND_INFO.subtitle,
                authors=_BACKEND_INFO.authors,
                external_url=_BACKEND_INFO.external_url,
            )
        return _version_row(
            _BACKEND_INFO,
            value=capabilities.extension_version,
            status=AboutVersionStatus.AVAILABLE,
        )

    def _sugar_cubes_version_row(
        self,
        capabilities: BackendCapabilities | None,
    ) -> AboutVersionRow:
        """Return the SugarCubes version row from Backend capabilities."""

        if capabilities is None:
            return AboutVersionRow(
                label=_SUGAR_CUBES_INFO.label,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
                subtitle=_SUGAR_CUBES_INFO.subtitle,
                authors=_SUGAR_CUBES_INFO.authors,
                external_url=_SUGAR_CUBES_INFO.external_url,
            )
        cube_library = capabilities.cube_library
        if not cube_library.available:
            return AboutVersionRow(
                label=_SUGAR_CUBES_INFO.label,
                value=_UNAVAILABLE,
                status=AboutVersionStatus.UNAVAILABLE,
                subtitle=_SUGAR_CUBES_INFO.subtitle,
                authors=_SUGAR_CUBES_INFO.authors,
                external_url=_SUGAR_CUBES_INFO.external_url,
                detail=cube_library.unavailable_reason,
            )
        if not cube_library.sugar_cubes_version:
            return AboutVersionRow(
                label=_SUGAR_CUBES_INFO.label,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
                subtitle=_SUGAR_CUBES_INFO.subtitle,
                authors=_SUGAR_CUBES_INFO.authors,
                external_url=_SUGAR_CUBES_INFO.external_url,
            )
        return _version_row(
            _SUGAR_CUBES_INFO,
            value=cube_library.sugar_cubes_version,
            status=AboutVersionStatus.AVAILABLE,
        )

    def _sugar_dsl_version_row(
        self,
        capabilities: BackendCapabilities | None,
    ) -> AboutVersionRow:
        """Return the Sugar-DSL version row from Backend capabilities."""

        if capabilities is None:
            return AboutVersionRow(
                label=_SUGAR_DSL_INFO.label,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
                subtitle=_SUGAR_DSL_INFO.subtitle,
                authors=_SUGAR_DSL_INFO.authors,
                external_url=_SUGAR_DSL_INFO.external_url,
            )
        sugar_compile = capabilities.sugar_compile
        if (
            sugar_compile.schema_version == 0
            and not sugar_compile.available
            and not sugar_compile.unavailable_reason
        ):
            return AboutVersionRow(
                label=_SUGAR_DSL_INFO.label,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
                subtitle=_SUGAR_DSL_INFO.subtitle,
                authors=_SUGAR_DSL_INFO.authors,
                external_url=_SUGAR_DSL_INFO.external_url,
            )
        if not sugar_compile.available:
            return AboutVersionRow(
                label=_SUGAR_DSL_INFO.label,
                value=_UNAVAILABLE,
                status=AboutVersionStatus.UNAVAILABLE,
                subtitle=_SUGAR_DSL_INFO.subtitle,
                authors=_SUGAR_DSL_INFO.authors,
                external_url=_SUGAR_DSL_INFO.external_url,
                detail=sugar_compile.unavailable_reason,
            )
        if not sugar_compile.sugar_dsl_version:
            return AboutVersionRow(
                label=_SUGAR_DSL_INFO.label,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
                subtitle=_SUGAR_DSL_INFO.subtitle,
                authors=_SUGAR_DSL_INFO.authors,
                external_url=_SUGAR_DSL_INFO.external_url,
            )
        return _version_row(
            _SUGAR_DSL_INFO,
            value=sugar_compile.sugar_dsl_version,
            status=AboutVersionStatus.AVAILABLE,
        )

    def _comfyui_version_row(
        self,
        runtime_info: ComfyRuntimeInfo | None,
    ) -> AboutVersionRow:
        """Return the ComfyUI version row from runtime system stats."""

        if runtime_info is None:
            return AboutVersionRow(
                label=_COMFYUI_INFO.label,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
                subtitle=_COMFYUI_INFO.subtitle,
                authors=_COMFYUI_INFO.authors,
                external_url=_COMFYUI_INFO.external_url,
            )
        if not runtime_info.comfy_version:
            return AboutVersionRow(
                label=_COMFYUI_INFO.label,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
                subtitle=_COMFYUI_INFO.subtitle,
                authors=_COMFYUI_INFO.authors,
                external_url=_COMFYUI_INFO.external_url,
            )
        return _version_row(
            _COMFYUI_INFO,
            value=runtime_info.comfy_version,
            status=AboutVersionStatus.AVAILABLE,
        )


def _version_row(
    component: _VersionComponentInfo,
    *,
    value: str,
    status: AboutVersionStatus,
    detail: str = "",
) -> AboutVersionRow:
    """Return a version row with stable component display metadata attached."""

    return AboutVersionRow(
        label=component.label,
        value=value,
        status=status,
        subtitle=component.subtitle,
        authors=component.authors,
        external_url=component.external_url,
        detail=detail,
    )


__all__ = [
    "AboutInfoService",
    "AppVersionProvider",
    "BackendCapabilityProvider",
    "ComfyRuntimeInfoProvider",
    "LocalPackageVersionResolver",
]
