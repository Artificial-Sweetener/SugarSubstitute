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

"""Enforce structural README parity for every release-enabled locale."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from sugarsubstitute_shared.localization import load_language_manifest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_AUTHORITY_PATH = _PROJECT_ROOT / "README.md"
_EXTERNAL_URL_PATTERN = re.compile(r"https://[^\s\)\"]+")
_CODE_BLOCK_PATTERN = re.compile(r"^```[^\r\n]*\r?\n.*?^```$", re.MULTILINE | re.DOTALL)
_IMAGE_SOURCE_PATTERN = re.compile(r'<img\s+src="([^"]+)"')
_HEADING_PATTERN = re.compile(r"^(#{2,4}) ", re.MULTILINE)


def test_every_release_locale_has_a_complete_readme_counterpart() -> None:
    """Require each registry locale to retain the authority's verifiable structure."""

    authority = _AUTHORITY_PATH.read_text(encoding="utf-8")
    manifest = load_language_manifest()

    for language in manifest.release_languages:
        path = (
            _AUTHORITY_PATH
            if language.identifier == manifest.default_language.identifier
            else _PROJECT_ROOT / f"README.{language.identifier}.md"
        )
        assert path.is_file(), f"Missing localized README: {path.name}"
        localized = path.read_text(encoding="utf-8")
        assert _heading_depths(localized) == _heading_depths(authority), path.name
        assert _code_blocks(localized) == _code_blocks(authority), path.name
        assert _image_sources(localized) == _image_sources(authority), path.name
        assert _external_urls(localized) == _external_urls(authority), path.name


def test_every_readme_selector_lists_all_release_languages() -> None:
    """Keep every language discoverable from every localized README."""

    manifest = load_language_manifest()
    readme_names = {
        language.identifier: (
            "README.md"
            if language.identifier == manifest.default_language.identifier
            else f"README.{language.identifier}.md"
        )
        for language in manifest.release_languages
    }

    for current_identifier, current_name in readme_names.items():
        content = (_PROJECT_ROOT / current_name).read_text(encoding="utf-8")
        for language in manifest.release_languages:
            assert language.native_display_name in content, (
                f"{current_name} omits {language.native_display_name}"
            )
            target_name = readme_names[language.identifier]
            if language.identifier != current_identifier:
                assert f'href="{target_name}"' in content, (
                    f"{current_name} does not link to {target_name}"
                )


def _heading_depths(content: str) -> tuple[int, ...]:
    """Return semantic heading depths without coupling translated headings."""

    return tuple(len(match) for match in _HEADING_PATTERN.findall(content))


def _code_blocks(content: str) -> tuple[str, ...]:
    """Return commands and other fenced technical content in source order."""

    return tuple(_CODE_BLOCK_PATTERN.findall(content))


def _image_sources(content: str) -> tuple[str, ...]:
    """Return image sources whose product evidence must remain aligned."""

    return tuple(_IMAGE_SOURCE_PATTERN.findall(content))


def _external_urls(content: str) -> Counter[str]:
    """Return external destinations while allowing localized link labels."""

    return Counter(_EXTERNAL_URL_PATTERN.findall(content))
