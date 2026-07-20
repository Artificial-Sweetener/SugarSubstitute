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

from sugarsubstitute_shared.localization import ApplicationText, app_text

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

_UNKNOWN = app_text("Unknown")
_UNAVAILABLE = app_text("Unavailable")
_NOT_CONNECTED = app_text("Not connected")
_SOURCE_CHECKOUT = app_text("source checkout")


@dataclass(frozen=True, slots=True)
class _VersionComponentInfo:
    """Describe stable About display metadata for one versioned component."""

    key: str
    label: ApplicationText
    subtitle: ApplicationText
    authors: str
    external_url: str


_SUGARSUBSTITUTE_INFO = _VersionComponentInfo(
    key="SugarSubstitute",
    label=app_text("SugarSubstitute"),
    subtitle=app_text("The desktop native Qt frontend for ComfyUI"),
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/SugarSubstitute",
)
_COMFYUI_INFO = _VersionComponentInfo(
    key="ComfyUI",
    label=app_text("ComfyUI"),
    subtitle=app_text(
        "The most powerful and modular diffusion model GUI, api and backend"
    ),
    authors="Comfy Org",
    external_url="https://github.com/Comfy-Org/ComfyUI",
)
_BACKEND_INFO = _VersionComponentInfo(
    key="SubstituteBackend",
    label=app_text("Substitute Backend"),
    subtitle=app_text("Allow communication between ComfyUI deployments & Substitute"),
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/Substitute-Backend",
)
_SUGAR_CUBES_INFO = _VersionComponentInfo(
    key="SugarCubes",
    label=app_text("SugarCubes"),
    subtitle=app_text("Composable workflow units for ComfyUI"),
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/SugarCubes",
)
_SUGAR_DSL_INFO = _VersionComponentInfo(
    key="SugarDSL",
    label=app_text("Sugar-DSL"),
    subtitle=app_text(
        "The scripting language for composing ComfyUI workflows with SugarCubes"
    ),
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/Sugar-DSL",
)
_QPANE_INFO = _VersionComponentInfo(
    key="QPane",
    label=app_text("QPane"),
    subtitle=app_text("High-performance PySide6 image viewer"),
    authors="Artificial Sweetener",
    external_url="https://github.com/Artificial-Sweetener/QPane",
)
_PYSIDE_FLUENT_WIDGETS_INFO = _VersionComponentInfo(
    key="PySide6FluentWidgets",
    label=app_text("PySide6-Fluent-Widgets"),
    subtitle=app_text("A fluent design widgets library for PySide6"),
    authors="zhiyiYo",
    external_url="https://github.com/zhiyiYo/PyQt-Fluent-Widgets",
)
_PYSIDE_INFO = _VersionComponentInfo(
    key="PySide6",
    label=app_text("PySide6"),
    subtitle=app_text("Qt for Python"),
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
        project_summary: ApplicationText = ABOUT_PROJECT_SUMMARY,
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
                _version_row(
                    _SUGARSUBSTITUTE_INFO,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                ),
                _version_row(
                    _COMFYUI_INFO,
                    value=_NOT_CONNECTED,
                    status=AboutVersionStatus.NOT_CONNECTED,
                ),
                _version_row(
                    _SUGAR_CUBES_INFO,
                    value=_NOT_CONNECTED,
                    status=AboutVersionStatus.NOT_CONNECTED,
                ),
                _version_row(
                    _BACKEND_INFO,
                    value=_NOT_CONNECTED,
                    status=AboutVersionStatus.NOT_CONNECTED,
                ),
                _version_row(
                    _SUGAR_DSL_INFO,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                ),
                _version_row(
                    _QPANE_INFO,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                ),
                _version_row(
                    _PYSIDE_FLUENT_WIDGETS_INFO,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
                ),
                _version_row(
                    _PYSIDE_INFO,
                    value=_UNKNOWN,
                    status=AboutVersionStatus.UNKNOWN,
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
            return _version_row(
                _BACKEND_INFO,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
            )
        if not capabilities.extension_version:
            return _version_row(
                _BACKEND_INFO,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
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
            return _version_row(
                _SUGAR_CUBES_INFO,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
            )
        cube_library = capabilities.cube_library
        if not cube_library.available:
            return _version_row(
                _SUGAR_CUBES_INFO,
                value=_UNAVAILABLE,
                status=AboutVersionStatus.UNAVAILABLE,
                detail=cube_library.unavailable_reason,
            )
        if not cube_library.sugar_cubes_version:
            return _version_row(
                _SUGAR_CUBES_INFO,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
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
            return _version_row(
                _SUGAR_DSL_INFO,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
            )
        sugar_compile = capabilities.sugar_compile
        if (
            sugar_compile.schema_version == 0
            and not sugar_compile.available
            and not sugar_compile.unavailable_reason
        ):
            return _version_row(
                _SUGAR_DSL_INFO,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
            )
        if not sugar_compile.available:
            return _version_row(
                _SUGAR_DSL_INFO,
                value=_UNAVAILABLE,
                status=AboutVersionStatus.UNAVAILABLE,
                detail=sugar_compile.unavailable_reason,
            )
        if not sugar_compile.sugar_dsl_version:
            return _version_row(
                _SUGAR_DSL_INFO,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
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
            return _version_row(
                _COMFYUI_INFO,
                value=_NOT_CONNECTED,
                status=AboutVersionStatus.NOT_CONNECTED,
            )
        if not runtime_info.comfy_version:
            return _version_row(
                _COMFYUI_INFO,
                value=_UNKNOWN,
                status=AboutVersionStatus.UNKNOWN,
            )
        return _version_row(
            _COMFYUI_INFO,
            value=runtime_info.comfy_version,
            status=AboutVersionStatus.AVAILABLE,
        )


def _version_row(
    component: _VersionComponentInfo,
    *,
    value: ApplicationText,
    status: AboutVersionStatus,
    detail: ApplicationText = "",
) -> AboutVersionRow:
    """Return a version row with stable component display metadata attached."""

    return AboutVersionRow(
        component_key=component.key,
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
