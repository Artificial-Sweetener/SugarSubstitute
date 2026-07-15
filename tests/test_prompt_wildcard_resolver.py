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

"""Tests for native prompt wildcard value resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.prompt_wildcards import (
    PromptWildcardResolutionContext,
    PromptWildcardResolver,
)
from substitute.domain.prompt import PromptWildcardSyntaxProfile
from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
    FilePromptWildcardCatalogGateway,
    _load_catalog,
)


@pytest.fixture(autouse=True)
def clear_wildcard_caches() -> None:
    """Clear process-wide wildcard caches around each resolver test."""

    _load_catalog.cache_clear()


def _write_text(path: Path, content: str) -> None:
    """Write one UTF-8 test fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _resolver(user_root: Path) -> PromptWildcardResolver:
    """Build a resolver pointed at one isolated user wildcard root."""

    gateway = FilePromptWildcardCatalogGateway(
        user_wildcards_root=user_root,
        comfy_custom_nodes_root=user_root.parent / "comfy_custom_nodes",
    )
    return PromptWildcardResolver(gateway)


def test_resolves_simple_txt_wildcard_from_user_root(tmp_path: Path) -> None:
    """Simple placeholders should resolve from Substitute-owned wildcard text files."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\nbear\n")

    result = _resolver(user_root).resolve("A {animal}", seed=1)

    assert result.resolved_text in {"A wolf", "A bear"}
    assert (
        result.resolved_text
        == _resolver(user_root)
        .resolve(
            "A {animal}",
            seed=1,
        )
        .resolved_text
    )


def test_resolves_nested_txt_wildcard(tmp_path: Path) -> None:
    """Forward-slash identifiers should resolve files in nested wildcard folders."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "pokemon" / "gen1" / "type.txt", "fire\nwater\n")

    result = _resolver(user_root).resolve("{pokemon/gen1/type} type", seed=2)

    assert result.resolved_text in {"fire type", "water type"}


def test_resolves_csv_column_case_insensitively(tmp_path: Path) -> None:
    """CSV column lookup should trim and lowercase headers and placeholder columns."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "monster.csv", " Color ,Size\nred,large\n")

    result = _resolver(user_root).resolve("{csv:monster:color}", seed=3)

    assert result.resolved_text == "red"


def test_csv_references_share_selected_row(tmp_path: Path) -> None:
    """Multiple columns from the same CSV source should use one selected row."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(
        user_root / "monster.csv",
        "color,size,texture\nred,large,scaly\nblue,small,furry\n",
    )

    result = _resolver(user_root).resolve(
        "{csv:monster:color} {csv:monster:size} {csv:monster:texture}",
        seed=4,
    )

    assert result.resolved_text in {"red large scaly", "blue small furry"}


def test_txt_references_share_selected_line(tmp_path: Path) -> None:
    """Repeated simple placeholders should use the same selected line."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\nbear\n")

    result = _resolver(user_root).resolve("{animal} and {animal}", seed=5)

    first, _, second = result.resolved_text.partition(" and ")
    assert first == second


def test_tag_offset_is_deterministic_with_seed(tmp_path: Path) -> None:
    """Tagged placeholders should apply a stable seed-derived offset."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\nbear\nfox\n")
    resolver = _resolver(user_root)

    first = resolver.resolve("{animal|variant}", seed=6).resolved_text
    second = resolver.resolve("{animal|variant}", seed=6).resolved_text

    assert first == second


def test_context_reuses_source_selection_across_prompt_resolutions(
    tmp_path: Path,
) -> None:
    """A shared context should keep wildcard choices stable across prompt fields."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "color.txt", "red\ngreen\nblue\n")
    _write_text(user_root / "animal.txt", "wolf\nbear\nfox\n")
    resolver = _resolver(user_root)
    context = PromptWildcardResolutionContext(seed=1)

    first = resolver.resolve("A {color} {animal}", context=context).resolved_text
    second = resolver.resolve("B {animal}", context=context).resolved_text

    _, _, animal = first.partition(" ")
    _, _, animal = animal.partition(" ")
    assert second == f"B {animal}"


def test_context_uses_independent_choices_for_new_pass_seed(tmp_path: Path) -> None:
    """New pass seeds should produce independent wildcard rolls."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\nbear\nfox\n")
    resolver = _resolver(user_root)

    first = resolver.resolve(
        "{animal}",
        context=PromptWildcardResolutionContext(seed=0),
    ).resolved_text
    second = resolver.resolve(
        "{animal}",
        context=PromptWildcardResolutionContext(seed=1),
    ).resolved_text

    assert first != second


def test_nested_substitutions_resolve_until_stable(tmp_path: Path) -> None:
    """Wildcard values containing placeholders should resolve in later passes."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "{color} fox\n")
    _write_text(user_root / "color.txt", "red\n")

    result = _resolver(user_root).resolve("{animal}", seed=7)

    assert result.resolved_text == "red fox"


def test_missing_csv_column_leaves_placeholder_unchanged(tmp_path: Path) -> None:
    """Missing CSV columns should not remove or modify the source placeholder."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "monster.csv", "color\nred\n")

    result = _resolver(user_root).resolve("{csv:monster:size}", seed=8)

    assert result.resolved_text == "{csv:monster:size}"


def test_legacy_disabled_manifest_is_ignored(tmp_path: Path) -> None:
    """Legacy disabled-file manifests should not suppress wildcard resolution."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\n")
    _write_text(
        user_root / ".substitute_wildcards.json",
        '{"disabled_files":["animal.txt"]}',
    )

    result = _resolver(user_root).resolve("{animal}", seed=9)

    assert result.resolved_text == "wolf"


def test_double_underscore_syntax_resolves_when_profile_enabled(
    tmp_path: Path,
) -> None:
    """Double-underscore activators should resolve with the configured profile."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\n")
    gateway = FilePromptWildcardCatalogGateway(
        user_wildcards_root=user_root,
        comfy_custom_nodes_root=user_root.parent / "comfy_custom_nodes",
    )
    resolver = PromptWildcardResolver(
        gateway,
        syntax_profile=PromptWildcardSyntaxProfile.double_underscore(),
    )

    assert resolver.resolve("__animal__", seed=10).resolved_text == "wolf"
