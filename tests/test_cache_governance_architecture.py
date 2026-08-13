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

"""Verify executable persistent-cache allocation policy diagnostics."""

from pathlib import Path

from tools.cache_governance import validate_cache_path_allocations


def test_direct_cache_root_child_allocation_is_rejected(tmp_path: Path) -> None:
    """Prevent new persistent caches from bypassing prepared namespaces."""

    source = tmp_path / "substitute" / "feature" / "cache.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'def build(context):\n    return context.cache_dir / "feature"\n',
        encoding="utf-8",
    )

    diagnostics = validate_cache_path_allocations(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        ("CACHE004", "substitute/feature/cache.py")
    ]


def test_runtime_model_metadata_alias_is_rejected(tmp_path: Path) -> None:
    """Prevent the legacy configuration alias from becoming a second allocator."""

    source = tmp_path / "substitute" / "feature" / "models.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def open_store(context):\n    return context.model_metadata_dir\n",
        encoding="utf-8",
    )

    diagnostics = validate_cache_path_allocations(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        ("CACHE005", "substitute/feature/models.py")
    ]


def test_configuration_repository_can_preserve_legacy_field(tmp_path: Path) -> None:
    """Allow persisted configuration compatibility without runtime cache authority."""

    source = (
        tmp_path
        / "substitute"
        / "infrastructure"
        / "onboarding"
        / "file_installation_repository.py"
    )
    source.parent.mkdir(parents=True)
    source.write_text(
        "def save(configuration):\n    return configuration.model_metadata_dir\n",
        encoding="utf-8",
    )

    assert validate_cache_path_allocations(tmp_path) == []


def test_sqlite_cache_literal_identity_is_rejected(tmp_path: Path) -> None:
    """Require cache recovery stores to derive identity from the catalog owner."""

    source = tmp_path / "substitute" / "feature" / "cache.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "initialize_recoverable_sqlite(path, cache_id='feature', "
        "initialize=initialize, select_database=select)\n",
        encoding="utf-8",
    )

    diagnostics = validate_cache_path_allocations(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        ("CACHE007", "substitute/feature/cache.py")
    ]


def test_prepared_namespace_access_outside_composition_is_rejected(
    tmp_path: Path,
) -> None:
    """Keep cache generation paths behind the reviewed composition boundary."""

    source = tmp_path / "substitute" / "feature" / "cache.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def build(prepared):\n    return prepared.namespace(CACHE_ID_FEATURE).path\n",
        encoding="utf-8",
    )

    diagnostics = validate_cache_path_allocations(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        ("CACHE008", "substitute/feature/cache.py")
    ]
