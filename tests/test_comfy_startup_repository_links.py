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

"""Tests for startup diagnostics repository link normalization."""

from __future__ import annotations

from substitute.domain.comfy_startup_diagnostics import (
    normalize_repository_links,
    repository_links_from_github_id,
)


def test_github_id_becomes_repository_and_issues_urls() -> None:
    """Manager aux_id owner/repo values should become GitHub links."""

    links = repository_links_from_github_id(
        "kael558/ComfyUI-GGUF-FantasyTalking",
        source="manager_installed_aux_id",
    )

    assert links is not None
    assert (
        links.repository_url == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking"
    )
    assert (
        links.issues_url
        == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking/issues"
    )
    assert links.source == "manager_installed_aux_id"


def test_https_github_git_url_normalizes() -> None:
    """HTTPS GitHub clone URLs should normalize to repository URLs."""

    links = normalize_repository_links(
        "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git",
        source="local_git_remote",
    )

    assert links is not None
    assert links.repository_url == "https://github.com/ltdrdata/ComfyUI-Impact-Pack"
    assert links.issues_url == "https://github.com/ltdrdata/ComfyUI-Impact-Pack/issues"


def test_ssh_github_git_url_normalizes() -> None:
    """SSH GitHub clone URLs should normalize to repository URLs."""

    links = normalize_repository_links(
        "git@github.com:ltdrdata/ComfyUI-Manager.git",
        source="local_git_remote",
    )

    assert links is not None
    assert links.repository_url == "https://github.com/ltdrdata/ComfyUI-Manager"
    assert links.issues_url == "https://github.com/ltdrdata/ComfyUI-Manager/issues"


def test_malformed_github_urls_are_rejected() -> None:
    """GitHub URLs without owner/repo identity should not produce links."""

    assert (
        normalize_repository_links("https://github.com/ltdrdata", source="test") is None
    )
    assert repository_links_from_github_id("not-a-repo", source="test") is None


def test_non_github_https_url_keeps_repository_without_issues() -> None:
    """Non-GitHub HTTPS repositories can link to the repo but not issues."""

    links = normalize_repository_links(
        "https://example.com/extensions/custom-pack/",
        source="manager_catalog_repository",
    )

    assert links is not None
    assert links.repository_url == "https://example.com/extensions/custom-pack"
    assert links.issues_url is None


def test_local_paths_are_rejected() -> None:
    """Local paths should not be treated as external repositories."""

    assert (
        normalize_repository_links("E:\\ComfyUI\\custom_nodes\\Pack", source="test")
        is None
    )
    assert normalize_repository_links("./custom_nodes/Pack", source="test") is None
