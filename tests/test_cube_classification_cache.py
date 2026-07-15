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

"""Contract tests for durable cube picker classification cache persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from substitute.application.ports import (
    CachedCubePickerClassification,
    CachedCubeSearchTerm,
    CubeClassificationCacheKey,
)
from substitute.infrastructure.persistence import SqliteCubeClassificationCache


def test_sqlite_cube_classification_cache_round_trips_payload(
    tmp_path: Path,
) -> None:
    """Written classifications should be readable with the same cache key."""

    cache = SqliteCubeClassificationCache(tmp_path, clock=_clock())
    key = _cache_key(cube_id="cube-a")
    payload = _classification(role="start")

    cache.write_classification(key, payload)
    loaded = cache.read_classification(key)

    assert loaded == payload


def test_sqlite_cube_classification_cache_missing_key_returns_none(
    tmp_path: Path,
) -> None:
    """Unknown cache keys should miss without raising."""

    cache = SqliteCubeClassificationCache(tmp_path)

    assert cache.read_classification(_cache_key(cube_id="missing")) is None


def test_sqlite_cube_classification_cache_replaces_same_key(tmp_path: Path) -> None:
    """Writing the same key twice should atomically replace the payload."""

    cache = SqliteCubeClassificationCache(tmp_path)
    key = _cache_key(cube_id="cube-a")

    cache.write_classification(key, _classification(role="start"))
    cache.write_classification(key, _classification(role="end"))

    assert cache.read_classification(key) == _classification(role="end")


def test_sqlite_cube_classification_cache_prunes_target_and_catalog(
    tmp_path: Path,
) -> None:
    """Target/catalog pruning should remove only matching stale rows."""

    cache = SqliteCubeClassificationCache(tmp_path)
    keep = _cache_key(cube_id="keep", catalog_revision="rev-2")
    stale = _cache_key(cube_id="stale", catalog_revision="rev-1")
    other_target = _cache_key(
        cube_id="other",
        target_key="other-target",
        catalog_revision="rev-1",
    )
    for key in (keep, stale, other_target):
        cache.write_classification(key, _classification(role="middle"))

    assert cache.delete_except_catalog_revision("target", "rev-2") == 1

    assert cache.read_classification(keep) is not None
    assert cache.read_classification(stale) is None
    assert cache.read_classification(other_target) is not None


def test_sqlite_cube_classification_cache_prunes_oldest_rows(tmp_path: Path) -> None:
    """Row pruning should remove least recently accessed rows first."""

    ticks = _clock()
    cache = SqliteCubeClassificationCache(tmp_path, clock=ticks)
    old = _cache_key(cube_id="old")
    new = _cache_key(cube_id="new")
    cache.write_classification(old, _classification(role="start"))
    cache.write_classification(new, _classification(role="middle"))
    assert cache.read_classification(old) is not None

    assert cache.prune(maximum_rows=1) == 1

    assert cache.read_classification(old) is not None
    assert cache.read_classification(new) is None


def test_sqlite_cube_classification_cache_algorithm_version_misses(
    tmp_path: Path,
) -> None:
    """Algorithm version changes should naturally miss old rows."""

    cache = SqliteCubeClassificationCache(tmp_path)
    key = _cache_key(cube_id="cube-a", algorithm_version=1)
    cache.write_classification(key, _classification(role="start"))

    assert (
        cache.read_classification(_cache_key(cube_id="cube-a", algorithm_version=2))
        is None
    )


def test_sqlite_cube_classification_cache_rejects_unknown_schema(
    tmp_path: Path,
) -> None:
    """Unsupported schema versions should fail clearly instead of corrupting rows."""

    database_path = tmp_path / "cube_classification_cache.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "create table cube_classification_cache_schema(key text primary key, value text not null)"
        )
        connection.execute(
            "insert into cube_classification_cache_schema(key, value) values('schema_version', 'future')"
        )
        connection.commit()

    with pytest.raises(RuntimeError) as error:
        SqliteCubeClassificationCache(tmp_path)

    assert "Unsupported cube classification cache SQLite schema version" in str(error)


def _cache_key(
    *,
    cube_id: str,
    target_key: str = "target",
    catalog_revision: str = "rev-1",
    algorithm_version: int = 1,
) -> CubeClassificationCacheKey:
    """Return one deterministic classification cache key."""

    return CubeClassificationCacheKey(
        target_key=target_key,
        catalog_revision=catalog_revision,
        cube_id=cube_id,
        cube_content_hash=f"hash-{cube_id}",
        cube_version="1.0.0",
        algorithm_version=algorithm_version,
    )


def _classification(*, role: str) -> CachedCubePickerClassification:
    """Return one cacheable picker classification payload."""

    return CachedCubePickerClassification(
        input_count=1,
        output_count=2,
        role=role,
        supported_models=("SDXL",),
        search_terms=("sampler",),
        search_targets=(CachedCubeSearchTerm(text="KSampler", kind="node"),),
    )


def _clock() -> Callable[[], str]:
    """Return a deterministic increasing timestamp callable."""

    values = iter(
        [
            "2026-01-01T00:00:00.000001+00:00",
            "2026-01-01T00:00:00.000002+00:00",
            "2026-01-01T00:00:00.000003+00:00",
            "2026-01-01T00:00:00.000004+00:00",
            "2026-01-01T00:00:00.000005+00:00",
            "2026-01-01T00:00:00.000006+00:00",
        ]
    )

    def _next() -> str:
        """Return the next deterministic timestamp."""

        return next(values)

    return _next
