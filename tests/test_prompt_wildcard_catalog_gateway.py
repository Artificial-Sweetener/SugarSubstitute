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

"""Tests for the filesystem-backed prompt wildcard catalog gateway."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from substitute.application.ports import PromptWildcardReference
from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
    FilePromptWildcardCatalogGateway,
    _load_catalog,
)


@pytest.fixture(autouse=True)
def clear_catalog_cache() -> Iterator[None]:
    """Clear the process-wide wildcard catalog cache around each test."""

    _load_catalog.cache_clear()
    yield
    _load_catalog.cache_clear()


def _write_text(path: Path, content: str) -> None:
    """Write one UTF-8 text file after creating its parent directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _gateway(
    *,
    user_root: Path | None = None,
    comfy_root: Path,
) -> FilePromptWildcardCatalogGateway:
    """Build one gateway pointed at deterministic temporary wildcard roots."""

    return FilePromptWildcardCatalogGateway(
        user_wildcards_root=user_root or comfy_root.parent / "user_wildcards",
        comfy_custom_nodes_root=comfy_root,
    )


def test_gateway_ignores_root_custom_nodes_directory(tmp_path: Path) -> None:
    """Root custom nodes should no longer provide wildcard metadata."""

    root_custom_nodes = tmp_path / "custom_nodes"
    comfy_root = tmp_path / "comfy_custom_nodes"
    data_root = root_custom_nodes / "comfyui-csvwildcards" / "data"
    _write_text(data_root / "animal.txt", "wolf\nbear\n")

    gateway = _gateway(comfy_root=comfy_root)
    resolutions = gateway.resolve_references(
        (PromptWildcardReference(identifier="animal", wildcard_form="simple"),)
    )

    assert resolutions[0].exists is False


def test_gateway_scans_active_comfy_custom_nodes_root(tmp_path: Path) -> None:
    """Active Comfy custom nodes should provide simple and CSV wildcard metadata."""

    comfy_root = tmp_path / "comfy_custom_nodes"
    data_root = comfy_root / "comfyui-csvwildcards" / "data"
    _write_text(data_root / "animal.txt", "wolf\nbear\n")
    _write_text(
        data_root / "pokemon" / "gen1" / "moves.csv", "Name, Effect\nTackle,Hit\n"
    )

    gateway = _gateway(comfy_root=comfy_root)
    resolutions = gateway.resolve_references(
        (
            PromptWildcardReference(identifier="animal", wildcard_form="simple"),
            PromptWildcardReference(
                identifier="pokemon/gen1/moves",
                wildcard_form="csv",
                csv_column="effect",
            ),
        )
    )

    assert [resolution.exists for resolution in resolutions] == [True, True]
    assert resolutions[1].matched_csv_column == "Effect"
    assert resolutions[1].available_csv_columns == ("Name", "Effect")


def test_gateway_scans_user_wildcards_root_first(tmp_path: Path) -> None:
    """Substitute-owned wildcard files should resolve from the user data root."""

    user_root = tmp_path / "user" / "wildcards"
    comfy_root = tmp_path / "comfy_custom_nodes"
    _write_text(user_root / "artist.csv", "Name,Style\nTove,Linework\n")

    gateway = _gateway(
        user_root=user_root,
        comfy_root=comfy_root,
    )
    resolution = gateway.resolve_references(
        (
            PromptWildcardReference(
                identifier="artist",
                wildcard_form="csv",
                csv_column="style",
            ),
        )
    )[0]

    assert resolution.exists is True
    assert resolution.matched_csv_column == "Style"


def test_gateway_searches_wildcard_files_for_autocomplete(tmp_path: Path) -> None:
    """Wildcard autocomplete should list enabled TXT and CSV wildcard files."""

    user_root = tmp_path / "user" / "wildcards"
    comfy_root = tmp_path / "comfy_custom_nodes"
    _write_text(user_root / "animal.txt", "wolf\n")
    _write_text(user_root / "monster.csv", "Color,Size\nred,big\n")

    gateway = _gateway(
        user_root=user_root,
        comfy_root=comfy_root,
    )

    suggestions = gateway.search_wildcards("", limit=10)

    assert [
        (suggestion.tag, suggestion.source_label, suggestion.source_kind)
        for suggestion in suggestions
    ] == [
        ("animal", "TXT wildcard", "wildcard"),
        ("csv:monster:Color", "CSV wildcard", "wildcard"),
        ("csv:monster:Size", "CSV wildcard", "wildcard"),
    ]


def test_gateway_scans_managed_comfy_custom_nodes_root(tmp_path: Path) -> None:
    """Managed Comfy custom nodes should be scanned when the workspace root is empty."""

    comfy_root = tmp_path / "comfy_custom_nodes"
    data_root = comfy_root / "comfyui-csvwildcards" / "data"
    _write_text(data_root / "monster.txt", "dragon\n")

    gateway = _gateway(comfy_root=comfy_root)
    resolutions = gateway.resolve_references(
        (PromptWildcardReference(identifier="monster", wildcard_form="simple"),)
    )

    assert resolutions == (
        type(resolutions[0])(
            identifier="monster",
            wildcard_form="simple",
            csv_column=None,
            exists=True,
            matched_csv_column=None,
            available_csv_columns=(),
        ),
    )


def test_gateway_normalizes_identifiers_case_insensitively(tmp_path: Path) -> None:
    """Catalog identifiers should resolve with forward-slash, case-insensitive matching."""

    comfy_root = tmp_path / "comfy_custom_nodes"
    data_root = comfy_root / "comfyui-csvwildcards" / "data"
    _write_text(data_root / "Pokemon" / "Gen1" / "Types.txt", "fire\n")

    gateway = _gateway(comfy_root=comfy_root)
    resolutions = gateway.resolve_references(
        (
            PromptWildcardReference(
                identifier="pokemon/gen1/types",
                wildcard_form="simple",
            ),
        )
    )

    assert resolutions[0].exists is True


def test_gateway_normalizes_csv_columns_case_insensitively_and_trims_lookup(
    tmp_path: Path,
) -> None:
    """CSV column matching should trim and lowercase lookup keys while preserving display text."""

    comfy_root = tmp_path / "comfy_custom_nodes"
    data_root = comfy_root / "comfyui-csvwildcards" / "data"
    _write_text(data_root / "monster.csv", " Color ,Power\nred,5\n")

    gateway = _gateway(comfy_root=comfy_root)
    resolution = gateway.resolve_references(
        (
            PromptWildcardReference(
                identifier="monster",
                wildcard_form="csv",
                csv_column=" power ",
            ),
        )
    )[0]

    assert resolution.exists is True
    assert resolution.matched_csv_column == "Power"
    assert resolution.available_csv_columns == ("Color", "Power")


def test_gateway_merges_duplicate_identifiers_across_roots(tmp_path: Path) -> None:
    """Duplicate CSV identifiers across roots should merge columns instead of overwriting."""

    user_root = tmp_path / "user" / "wildcards"
    comfy_root = tmp_path / "comfy_custom_nodes"
    _write_text(
        user_root / "monster.csv",
        "Color,Size\nred,large\n",
    )
    _write_text(
        comfy_root / "comfyui-csvwildcards" / "data" / "monster.csv",
        "Texture\nscaly\n",
    )

    gateway = _gateway(user_root=user_root, comfy_root=comfy_root)
    resolution = gateway.resolve_references(
        (
            PromptWildcardReference(
                identifier="monster",
                wildcard_form="csv",
                csv_column="texture",
            ),
        )
    )[0]

    assert resolution.exists is True
    assert resolution.available_csv_columns == ("Color", "Size", "Texture")


def test_gateway_skips_malformed_user_wildcard_csv(tmp_path: Path) -> None:
    """Malformed Substitute-owned CSV files should fail closed without blocking scans."""

    user_root = tmp_path / "user" / "wildcards"
    comfy_root = tmp_path / "comfy_custom_nodes"
    user_root.mkdir(parents=True)
    (user_root / "broken.csv").write_bytes(b"\xff\xff")
    _write_text(user_root / "animal.txt", "wolf\n")

    gateway = _gateway(
        user_root=user_root,
        comfy_root=comfy_root,
    )
    resolutions = gateway.resolve_references(
        (
            PromptWildcardReference(
                identifier="broken",
                wildcard_form="csv",
                csv_column="name",
            ),
            PromptWildcardReference(identifier="animal", wildcard_form="simple"),
        )
    )

    assert [resolution.exists for resolution in resolutions] == [False, True]


def test_gateway_returns_missing_status_without_raising(tmp_path: Path) -> None:
    """Missing wildcard references should resolve to false without throwing exceptions."""

    gateway = _gateway(
        comfy_root=tmp_path / "comfy_custom_nodes",
    )

    resolution = gateway.resolve_references(
        (
            PromptWildcardReference(
                identifier="missing/path",
                wildcard_form="simple",
            ),
        )
    )[0]

    assert resolution.exists is False
    assert resolution.available_csv_columns == ()


def test_gateway_fails_closed_when_path_validation_rejects_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path validation failures should skip catalog loading and return unresolved references."""

    comfy_root = tmp_path / "comfy_custom_nodes"
    data_root = comfy_root / "comfyui-csvwildcards" / "data"
    _write_text(data_root / "animal.txt", "wolf\n")

    def _raise_value_error(*_args: object, **_kwargs: object) -> Path:
        raise ValueError("blocked")

    monkeypatch.setattr(
        "substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway.ensure_within_root",
        _raise_value_error,
    )
    gateway = _gateway(comfy_root=comfy_root)

    resolution = gateway.resolve_references(
        (PromptWildcardReference(identifier="animal", wildcard_form="simple"),)
    )[0]

    assert resolution.exists is False
