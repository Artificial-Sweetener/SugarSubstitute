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

"""Tests for About Settings snapshot composition."""

from __future__ import annotations

from substitute.application.about import AboutInfoService, AboutVersionStatus
from substitute.domain.comfy_runtime import ComfyRuntimeInfo
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendCubeLibraryCapabilities,
    BackendSugarCompileCapabilities,
)


class _BackendProvider:
    """Return configured Backend capabilities for About tests."""

    def __init__(self, capabilities: BackendCapabilities | None) -> None:
        """Store the capabilities payload."""

        self._capabilities = capabilities

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return configured capabilities."""

        return self._capabilities


def test_about_info_service_combines_available_versions() -> None:
    """About service should return rows in the expected display order."""

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(_capabilities()),
        comfy_runtime_info=lambda: ComfyRuntimeInfo(comfy_version="0.3.2"),
        local_versions=_local_versions,
        app_version=lambda: "0.5.0",
    )

    snapshot = service.snapshot()

    assert [(row.label, row.value, row.status) for row in snapshot.versions] == [
        ("SugarSubstitute", "0.5.0", AboutVersionStatus.AVAILABLE),
        ("ComfyUI", "0.3.2", AboutVersionStatus.AVAILABLE),
        ("SugarCubes", "0.9.0", AboutVersionStatus.AVAILABLE),
        ("Substitute Backend", "1.4.0", AboutVersionStatus.AVAILABLE),
        ("Sugar-DSL", "0.2.0", AboutVersionStatus.AVAILABLE),
        ("QPane", "2.0.1", AboutVersionStatus.AVAILABLE),
        ("PySide6-Fluent-Widgets", "1.11.2", AboutVersionStatus.AVAILABLE),
        ("PySide6", "6.9.0", AboutVersionStatus.AVAILABLE),
    ]


def test_about_info_service_attaches_version_card_display_metadata() -> None:
    """About service should own subtitles, authors, and external link targets."""

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(_capabilities()),
        comfy_runtime_info=lambda: ComfyRuntimeInfo(comfy_version="0.3.2"),
        local_versions=_local_versions,
        app_version=lambda: "0.5.0",
    )

    rows = {row.label: row for row in service.snapshot().versions}

    assert (
        rows["SugarSubstitute"].subtitle == "The desktop native Qt frontend for ComfyUI"
    )
    assert rows["SugarSubstitute"].authors == "Artificial Sweetener"
    assert (
        rows["SugarSubstitute"].external_url
        == "https://github.com/Artificial-Sweetener/SugarSubstitute"
    )
    assert rows["PySide6"].subtitle == "Qt for Python"
    assert rows["PySide6"].authors == "the Qt Company"
    assert rows["PySide6"].external_url == "https://pyside.org/"


def test_about_info_service_marks_backend_versions_not_connected() -> None:
    """Missing Backend capabilities should mark Backend-owned versions offline."""

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(None),
        comfy_runtime_info=lambda: None,
        local_versions=_local_versions,
        app_version=lambda: "0.5.0",
    )

    rows = {row.label: row for row in service.snapshot().versions}

    assert rows["Substitute Backend"].status is AboutVersionStatus.NOT_CONNECTED
    assert rows["SugarCubes"].status is AboutVersionStatus.NOT_CONNECTED
    assert rows["Sugar-DSL"].status is AboutVersionStatus.NOT_CONNECTED
    assert rows["ComfyUI"].status is AboutVersionStatus.NOT_CONNECTED


def test_about_info_service_marks_unavailable_runtime_dependencies() -> None:
    """Unavailable Backend capabilities should preserve actionable details."""

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(
            _capabilities(
                cube_library=BackendCubeLibraryCapabilities(
                    available=False,
                    unavailable_reason="SugarCubes is missing.",
                ),
                sugar_compile=BackendSugarCompileCapabilities(
                    schema_version=1,
                    available=False,
                    unavailable_reason="Sugar-DSL is not installed.",
                ),
            )
        ),
        comfy_runtime_info=lambda: ComfyRuntimeInfo(),
        local_versions=_local_versions,
        app_version=lambda: "0.5.0",
    )

    rows = {row.label: row for row in service.snapshot().versions}

    assert rows["SugarCubes"].value == "Unavailable"
    assert rows["SugarCubes"].detail == "SugarCubes is missing."
    assert rows["Sugar-DSL"].value == "Unavailable"
    assert rows["Sugar-DSL"].detail == "Sugar-DSL is not installed."
    assert rows["ComfyUI"].status is AboutVersionStatus.UNKNOWN


def test_about_info_service_treats_old_backend_sugar_dsl_as_unknown() -> None:
    """Old Backends without Sugar compile facts should not render unavailable."""

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(
            _capabilities(sugar_compile=BackendSugarCompileCapabilities())
        ),
        comfy_runtime_info=lambda: ComfyRuntimeInfo(comfy_version="0.3.2"),
        local_versions=_local_versions,
        app_version=lambda: "0.5.0",
    )

    rows = {row.label: row for row in service.snapshot().versions}

    assert rows["Sugar-DSL"].value == "Unknown"
    assert rows["Sugar-DSL"].status is AboutVersionStatus.UNKNOWN


def test_about_info_service_uses_embedded_app_version_before_package_metadata() -> None:
    """SugarSubstitute version should come from the source payload metadata."""

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(None),
        comfy_runtime_info=lambda: None,
        local_versions=lambda _names, *, fallback: "source checkout",
        app_version=lambda: "0.8.3",
    )

    row = service.snapshot().versions[0]

    assert row.label == "SugarSubstitute"
    assert row.value == "0.8.3"
    assert row.status is AboutVersionStatus.AVAILABLE


def _capabilities(
    *,
    cube_library: BackendCubeLibraryCapabilities | None = None,
    sugar_compile: BackendSugarCompileCapabilities | None = None,
) -> BackendCapabilities:
    """Return a compatible capabilities object with override hooks."""

    return BackendCapabilities(
        api_version=1,
        model_metadata_schema_version=1,
        supported_model_kinds=("checkpoints", "loras"),
        background_hashing=True,
        hash_lookup=True,
        local_preview_serving=True,
        sidecar_reading=True,
        extension_version="1.4.0",
        cube_library=cube_library
        or BackendCubeLibraryCapabilities(
            schema_version=1,
            available=True,
            sugar_cubes_version="0.9.0",
        ),
        sugar_compile=sugar_compile
        or BackendSugarCompileCapabilities(
            schema_version=1,
            available=True,
            compile_route="/substitute/v1/sugar/compile",
            sugar_dsl_version="0.2.0",
        ),
    )


def _local_versions(
    distribution_names: tuple[str, ...],
    *,
    fallback: str,
) -> str:
    """Return deterministic local package versions for About tests."""

    if "qpane" in distribution_names:
        return "2.0.1"
    if "PySide6-Fluent-Widgets" in distribution_names:
        return "1.11.2"
    if "PySide6" in distribution_names:
        return "6.9.0"
    if "SugarSubstitute" in distribution_names:
        return "0.5.0"
    return fallback
