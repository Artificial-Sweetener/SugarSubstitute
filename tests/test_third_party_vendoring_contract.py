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

"""Contract tests for vendored third-party asset provenance."""

from __future__ import annotations

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_third_party_manifest_references_existing_licenses_and_assets() -> None:
    """Vendored components should record license text and runtime file paths."""

    manifest_path = REPO_ROOT / "third_party" / "manifest.toml"
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    for component in manifest["component"]:
        license_path = REPO_ROOT / component["license_file"]
        assert license_path.is_file()
        license_text = license_path.read_text(encoding="utf-8")
        assert license_text.strip()
        if component["license"] == "MIT":
            assert "MIT License" in license_text

        for vendored_file in component["vendored_files"]:
            assert (REPO_ROOT / vendored_file).is_file()


def test_high_contrast_emoji_icons_record_fluent_emoji_provenance() -> None:
    """High contrast emoji icons should trace to their Fluent Emoji source assets."""

    manifest = tomllib.loads(
        (REPO_ROOT / "third_party" / "manifest.toml").read_text(encoding="utf-8")
    )
    components = {component["name"]: component for component in manifest["component"]}

    fluent_emoji = components["Microsoft Fluent UI Emoji"]

    assert fluent_emoji["source_paths"] == [
        "assets/Game die/High Contrast/game_die_high_contrast.svg",
        "assets/Infinity/High Contrast/infinity_high_contrast.svg",
        "assets/Locked/High Contrast/locked_high_contrast.svg",
    ]
    assert fluent_emoji["vendored_files"] == [
        "substitute/presentation/resources/icons/GameDieHighContrast_black.svg",
        "substitute/presentation/resources/icons/GameDieHighContrast_white.svg",
        "substitute/presentation/resources/icons/InfinityHighContrast_black.svg",
        "substitute/presentation/resources/icons/InfinityHighContrast_white.svg",
        "substitute/presentation/resources/icons/LockedHighContrast_black.svg",
        "substitute/presentation/resources/icons/LockedHighContrast_white.svg",
    ]


def test_qt_logo_records_trademark_guideline_provenance() -> None:
    """The vendored Qt logo should trace to Qt's brand and trademark guidance."""

    manifest = tomllib.loads(
        (REPO_ROOT / "third_party" / "manifest.toml").read_text(encoding="utf-8")
    )
    components = {component["name"]: component for component in manifest["component"]}

    qt_logo = components["Qt Development Logo"]

    assert qt_logo["license"] == "Qt Trademark Usage Guidelines"
    assert qt_logo["source"] == "https://www.qt.io/brand/development/logo"
    assert qt_logo["source_paths"] == [
        "https://www.qt.io/hs-fs/hubfs/Qt-logo-neon_900px.png?width=150&height=107&name=Qt-logo-neon_900px.png",
    ]
    assert qt_logo["vendored_files"] == [
        "substitute/presentation/resources/icons/QtLogoNeon.png",
    ]


def test_platform_icons_record_font_awesome_provenance() -> None:
    """Installer platform marks should retain source and license ownership."""

    manifest = tomllib.loads(
        (REPO_ROOT / "third_party" / "manifest.toml").read_text(encoding="utf-8")
    )
    components = {component["name"]: component for component in manifest["component"]}

    platform_icons = components["Font Awesome Free Brand Icons"]

    assert platform_icons["license"] == "CC BY 4.0"
    assert platform_icons["revision"] == ("2a840f82d5b82fc95226a1621cbf3d2ba789115e")
    assert platform_icons["source_paths"] == [
        "svgs/brands/windows.svg",
        "svgs/brands/apple.svg",
        "svgs/brands/linux.svg",
    ]
    assert platform_icons["vendored_files"] == [
        "docs/release/platforms/windows.svg",
        "docs/release/platforms/apple.svg",
        "docs/release/platforms/linux.svg",
    ]
