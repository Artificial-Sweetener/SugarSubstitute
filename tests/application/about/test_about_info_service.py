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

"""Verify About snapshot composition at its application owner boundary."""

from __future__ import annotations

from substitute.application.about import (
    AboutInfoService,
    AboutVersionRow,
    AboutVersionStatus,
)
from substitute.application.about.about_info_service import (
    AppVersionProvider,
    LocalPackageVersionResolver,
)
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
    """Return every available component in the stable display order."""

    service = _service(capabilities=_capabilities())

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
    """Own stable subtitles, authors, and external link targets."""

    rows = {
        row.label: row
        for row in _service(capabilities=_capabilities()).snapshot().versions
    }

    assert rows["SugarSubstitute"].subtitle == (
        "The desktop native Qt frontend for ComfyUI"
    )
    assert rows["SugarSubstitute"].authors == "Artificial Sweetener"
    assert rows["SugarSubstitute"].external_url == (
        "https://github.com/Artificial-Sweetener/SugarSubstitute"
    )
    assert rows["PySide6"].subtitle == "Qt for Python"
    assert rows["PySide6"].authors == "the Qt Company"
    assert rows["PySide6"].external_url == "https://pyside.org/"


def test_about_info_service_marks_disconnected_versions() -> None:
    """Mark remote-owned component versions not connected without capabilities."""

    rows = {
        row.label: row
        for row in _service(capabilities=None, runtime_info=None).snapshot().versions
    }

    for label in ("Substitute Backend", "SugarCubes", "Sugar-DSL", "ComfyUI"):
        assert rows[label].value == "Not connected"
        assert rows[label].status is AboutVersionStatus.NOT_CONNECTED


def test_about_info_service_preserves_unavailable_dependency_reasons() -> None:
    """Expose actionable reasons reported by unavailable runtime dependencies."""

    service = _service(
        capabilities=_capabilities(
            cube_library=BackendCubeLibraryCapabilities(
                available=False,
                unavailable_reason="SugarCubes is missing.",
            ),
            sugar_compile=BackendSugarCompileCapabilities(
                schema_version=1,
                available=False,
                unavailable_reason="Sugar-DSL is not installed.",
            ),
        ),
        runtime_info=ComfyRuntimeInfo(),
    )

    rows = {row.label: row for row in service.snapshot().versions}

    assert rows["SugarCubes"].value == "Unavailable"
    assert rows["SugarCubes"].status is AboutVersionStatus.UNAVAILABLE
    assert rows["SugarCubes"].detail == "SugarCubes is missing."
    assert rows["Sugar-DSL"].value == "Unavailable"
    assert rows["Sugar-DSL"].status is AboutVersionStatus.UNAVAILABLE
    assert rows["Sugar-DSL"].detail == "Sugar-DSL is not installed."
    assert rows["ComfyUI"].status is AboutVersionStatus.UNKNOWN


def test_about_info_service_treats_legacy_sugar_dsl_facts_as_unknown() -> None:
    """Treat an old Backend with no Sugar compile facts as unknown, not absent."""

    service = _service(
        capabilities=_capabilities(sugar_compile=BackendSugarCompileCapabilities())
    )

    row = _rows(service)["Sugar-DSL"]

    assert row.value == "Unknown"
    assert row.status is AboutVersionStatus.UNKNOWN


def test_about_info_service_marks_connected_sources_without_versions_unknown() -> None:
    """Distinguish connected sources with missing version facts from disconnection."""

    service = _service(
        capabilities=_capabilities(
            extension_version="",
            cube_library=BackendCubeLibraryCapabilities(
                schema_version=1,
                available=True,
                sugar_cubes_version="",
            ),
            sugar_compile=BackendSugarCompileCapabilities(
                schema_version=1,
                available=True,
                compile_route="/substitute/v1/sugar/compile",
                sugar_dsl_version="",
            ),
        ),
        runtime_info=ComfyRuntimeInfo(),
        local_versions=lambda _names, *, fallback: fallback,
    )

    rows = _rows(service)

    for label in (
        "ComfyUI",
        "SugarCubes",
        "Substitute Backend",
        "Sugar-DSL",
        "QPane",
        "PySide6-Fluent-Widgets",
        "PySide6",
    ):
        assert rows[label].value == "Unknown"
        assert rows[label].status is AboutVersionStatus.UNKNOWN


def test_about_info_service_prefers_embedded_app_version() -> None:
    """Use source payload metadata before installed-package metadata."""

    local_version_calls: list[tuple[str, ...]] = []

    def local_versions(
        distribution_names: tuple[str, ...],
        *,
        fallback: str,
    ) -> str:
        """Record local lookups and return a deterministic package version."""

        local_version_calls.append(distribution_names)
        return "installed" if "SugarSubstitute" in distribution_names else fallback

    service = _service(
        capabilities=None,
        runtime_info=None,
        local_versions=local_versions,
        app_version=lambda: "0.8.3",
    )

    row = service.snapshot().versions[0]

    assert row.value == "0.8.3"
    assert not any("SugarSubstitute" in names for names in local_version_calls)


def test_about_info_service_falls_back_when_embedded_app_version_is_empty() -> None:
    """Use installed package metadata when source payload metadata is unavailable."""

    service = _service(
        capabilities=None,
        runtime_info=None,
        local_versions=lambda names, *, fallback: (
            "0.7.9" if "SugarSubstitute" in names else fallback
        ),
        app_version=lambda: "",
    )

    row = service.snapshot().versions[0]

    assert row.value == "0.7.9"
    assert row.status is AboutVersionStatus.AVAILABLE


def test_about_info_placeholder_avoids_runtime_providers() -> None:
    """Build initial page content without touching remote or package providers."""

    def unexpected_runtime_info() -> ComfyRuntimeInfo | None:
        """Fail if placeholder composition reads runtime information."""

        raise AssertionError("placeholder snapshot accessed a runtime provider")

    def unexpected_local_version(
        distribution_names: tuple[str, ...],
        *,
        fallback: str,
    ) -> str:
        """Fail if placeholder composition reads installed package metadata."""

        raise AssertionError(
            "placeholder accessed package metadata: "
            f"names={distribution_names}, fallback={fallback}"
        )

    def unexpected_app_version() -> str:
        """Fail if placeholder composition reads source payload metadata."""

        raise AssertionError("placeholder accessed source payload metadata")

    service = AboutInfoService(
        backend_capabilities=_BackendProvider(None),
        comfy_runtime_info=unexpected_runtime_info,
        local_versions=unexpected_local_version,
        app_version=unexpected_app_version,
        project_summary="Summary",
        supporters=("Supporter",),
        special_thanks=("Contributor",),
    )

    snapshot = service.placeholder_snapshot()

    assert snapshot.project_summary == "Summary"
    assert snapshot.supporters == ("Supporter",)
    assert snapshot.special_thanks == ("Contributor",)
    assert [row.status for row in snapshot.versions] == [
        AboutVersionStatus.UNKNOWN,
        AboutVersionStatus.NOT_CONNECTED,
        AboutVersionStatus.NOT_CONNECTED,
        AboutVersionStatus.NOT_CONNECTED,
        AboutVersionStatus.UNKNOWN,
        AboutVersionStatus.UNKNOWN,
        AboutVersionStatus.UNKNOWN,
        AboutVersionStatus.UNKNOWN,
    ]


def _service(
    *,
    capabilities: BackendCapabilities | None,
    runtime_info: ComfyRuntimeInfo | None = ComfyRuntimeInfo(comfy_version="0.3.2"),
    local_versions: LocalPackageVersionResolver | None = None,
    app_version: AppVersionProvider | None = None,
) -> AboutInfoService:
    """Return an About service with explicit deterministic owner boundaries."""

    return AboutInfoService(
        backend_capabilities=_BackendProvider(capabilities),
        comfy_runtime_info=lambda: runtime_info,
        local_versions=_local_versions if local_versions is None else local_versions,
        app_version=(lambda: "0.5.0") if app_version is None else app_version,
    )


def _rows(service: AboutInfoService) -> dict[str, AboutVersionRow]:
    """Return snapshot rows keyed by their rendered labels."""

    return {str(row.label): row for row in service.snapshot().versions}


def _capabilities(
    *,
    extension_version: str = "1.4.0",
    cube_library: BackendCubeLibraryCapabilities | None = None,
    sugar_compile: BackendSugarCompileCapabilities | None = None,
) -> BackendCapabilities:
    """Return compatible Backend capabilities with focused override hooks."""

    return BackendCapabilities(
        api_version=1,
        model_metadata_schema_version=1,
        supported_model_kinds=("checkpoints", "loras"),
        background_hashing=True,
        hash_lookup=True,
        local_preview_serving=True,
        sidecar_reading=True,
        extension_version=extension_version,
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
