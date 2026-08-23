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

"""Contract tests for the file-backed prompt autocomplete gateway."""

from __future__ import annotations

import importlib
from types import ModuleType
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch


def _import_gateway_module() -> ModuleType:
    """Import the file-backed prompt autocomplete gateway module."""

    return importlib.import_module(
        "substitute.infrastructure.persistence.file_prompt_autocomplete_gateway"
    )


def test_file_prompt_autocomplete_gateway_parses_search_results_from_bundled_asset(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway searches should return parsed suggestion rows from the asset text."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "solo,4904995 (danbooru:General)\nsolo_focus,123 (danbooru:General)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    results = gateway.search("solo")

    assert [result.tag for result in results] == ["solo", "solo focus"]
    assert results[0].popularity == 4_904_995


def test_file_prompt_autocomplete_gateway_treats_underscores_as_spaces_in_tags(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway rows should expose spaced display tags even when the asset uses underscores."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "long_hair,200 (danbooru:General)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    results = gateway.search("long ha")

    assert [result.tag for result in results] == ["long hair"]


def test_file_prompt_autocomplete_gateway_matches_space_and_underscore_prefixes(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway searches should treat spaces and underscores as equivalent input."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "long_hair,200 (danbooru:General)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    space_results = gateway.search("long ha")
    underscore_results = gateway.search("long_ha")

    assert [result.tag for result in space_results] == ["long hair"]
    assert [result.tag for result in underscore_results] == ["long hair"]


def test_file_prompt_autocomplete_gateway_sorts_by_popularity_then_length(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway searches should prefer popular tags before length tie-breaking."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "\n".join(
            (
                "1go,5 (danbooru:General)",
                "1ga,10 (danbooru:General)",
                "1gb,20 (danbooru:General)",
                "1girl,100 (danbooru:General)",
                "1goddess,500 (danbooru:General)",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    results = gateway.search("1g", limit=4)

    assert [result.tag for result in results] == ["1goddess", "1girl", "1gb", "1ga"]


def test_file_prompt_autocomplete_gateway_preserves_ranking_after_indexing(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Indexed gateway search should preserve the full-scan ranking contract."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "\n".join(
            (
                "Blue_Eyes,10 (danbooru:General)",
                "blue,1 (danbooru:General)",
                "blue_sky,100 (danbooru:General)",
                "bluebird,200 (danbooru:General)",
                "blue_archive,50 (danbooru:General)",
                "black_hair,999 (danbooru:General)",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    results = gateway.search("BLUE", limit=5)

    assert [result.tag for result in results] == [
        "bluebird",
        "blue sky",
        "blue archive",
        "Blue Eyes",
        "blue",
    ]


def test_file_prompt_autocomplete_gateway_truncates_to_requested_limit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway searches should truncate the ranked results to the requested limit."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "\n".join(
            (
                "tag_a,1 (danbooru:General)",
                "tag_b,2 (danbooru:General)",
                "tag_c,3 (danbooru:General)",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    results = gateway.search("tag", limit=2)

    assert [result.tag for result in results] == ["tag c", "tag b"]


def test_file_prompt_autocomplete_gateway_handles_empty_zero_and_no_match_cases(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway search should preserve empty-input and no-match behavior."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text("solo,10 (danbooru:General)\n", encoding="utf-8")
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    assert gateway.search("") == ()
    assert gateway.search("solo", limit=0) == ()
    assert gateway.search("missing") == ()


def test_file_prompt_autocomplete_gateway_exact_tag_membership_uses_full_lexicon(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exact membership should not depend on prefix search result truncation."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "\n".join(
            (
                "looking_at_viewer,100 (danbooru:General)",
                "looking_back,90 (danbooru:General)",
                "looking_down,80 (danbooru:General)",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    assert gateway.contains_prompt_tag("LOOKING AT VIEWER") is True
    assert gateway.contains_prompt_tag("looking_at_viewer") is True
    assert gateway.contains_prompt_tag("looking at view") is False


def test_file_prompt_autocomplete_gateway_reuses_cached_query_results(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repeated indexed searches should return stable cached result tuples."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "solo,10 (danbooru:General)\nsolo_focus,5 (danbooru:General)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    first_results = gateway.search("solo", limit=2)
    second_results = gateway.search("solo", limit=2)

    assert second_results is first_results


def test_file_prompt_autocomplete_gateway_returns_empty_tuple_when_asset_missing(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway searches should fail closed when the bundled fallback asset is missing."""

    mod = _import_gateway_module()
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    assert gateway.search("1g") == ()


def test_file_prompt_autocomplete_gateway_reads_asset_once_per_process(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway should reuse cached parsed rows after the first asset read."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "1girl,5889398 (danbooru:General)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    first_results = gateway.search("1g")
    asset_path.write_text(
        "1go,5 (danbooru:General)\n",
        encoding="utf-8",
    )
    second_results = gateway.search("1g")

    assert [result.tag for result in first_results] == ["1girl"]
    assert [result.tag for result in second_results] == ["1girl"]


def test_file_prompt_autocomplete_gateway_normalizes_missing_popularity_to_zero(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Gateway rows without parseable popularity should expose a zero popularity value."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text(
        "solo, (danbooru:General)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "files", lambda _package: tmp_path)
    gateway = mod.FilePromptAutocompleteGateway()

    results = gateway.search("solo")

    assert [result.tag for result in results] == ["solo"]
    assert results[0].popularity == 0


def test_file_prompt_autocomplete_gateway_warm_loads_asset_once(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Synchronous warmup should populate the cache before the first search."""

    mod = _import_gateway_module()
    asset_path = tmp_path / "prompt_autocomplete.txt"
    asset_path.write_text("solo,10 (danbooru:General)\n", encoding="utf-8")
    files_calls = 0

    def files_spy(_package: str) -> Path:
        nonlocal files_calls
        files_calls += 1
        return tmp_path

    monkeypatch.setattr(mod, "files", files_spy)
    gateway = mod.FilePromptAutocompleteGateway()

    gateway.warm()
    asset_path.write_text("changed,10 (danbooru:General)\n", encoding="utf-8")

    assert [result.tag for result in gateway.search("solo")] == ["solo"]
    assert gateway.search("changed") == ()
    assert files_calls == 1


def test_file_prompt_autocomplete_gateway_exposes_no_async_executor_lifecycle() -> None:
    """Gateway warmup ownership should live outside the persistence adapter."""

    mod = _import_gateway_module()
    gateway = mod.FilePromptAutocompleteGateway()

    assert not hasattr(gateway, "start_async_warmup")
    assert not hasattr(gateway, "shutdown_async_warmup")
