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

"""Test persistent-cache adapter import boundaries."""

from __future__ import annotations

import json
import textwrap
from typing import cast

import pytest

from substitute.domain.model_metadata import CivitaiImage

from .support import (
    run_isolated_import_probe,
)


def test_lazy_model_thumbnail_store_defers_thumbnail_caching_imports() -> None:
    """Startup model metadata wiring should not load thumbnail caching machinery."""

    code = textwrap.dedent(
        """
        import json
        import sys
        from substitute.app.bootstrap.persistent_cache_composition import (
            LazyModelThumbnailStore,
        )

        store = LazyModelThumbnailStore()
        forbidden = {
            "requests",
            "substitute.infrastructure.persistence.model_thumbnail_store",
            "substitute.infrastructure.persistence.thumbnail_banner_cropper",
            "substitute.shared.qt_thumbnail_codec",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden)
        print(json.dumps([store.__class__.__name__, loaded]))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["LazyModelThumbnailStore", []]'


def test_lazy_model_catalog_snapshot_store_defers_sqlite_setup() -> None:
    """Snapshot-store injection should not initialize the SQLite cache at startup."""

    code = textwrap.dedent(
        """
        import json
        import sys
        import tempfile
        from pathlib import Path

        from substitute.app.bootstrap.persistent_cache_composition import (
            LazyModelCatalogSnapshotStore,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = LazyModelCatalogSnapshotStore(root)
            module_name = (
                "substitute.infrastructure.persistence."
                "sqlite_model_catalog_snapshot_store"
            )
            print(json.dumps({
                "class": store.__class__.__name__,
                "module_loaded": module_name in sys.modules,
                "database_exists": (root / "model_catalog_snapshots.sqlite3").exists(),
            }))
        """
    )

    completed = run_isolated_import_probe(code)

    assert json.loads(completed.stdout.strip()) == {
        "class": "LazyModelCatalogSnapshotStore",
        "module_loaded": False,
        "database_exists": False,
    }


def test_lazy_model_thumbnail_store_cache_calls_do_not_evaluate_type_only_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lazy thumbnail cache casts should not require type-only imports at runtime."""

    from substitute.app.bootstrap.persistent_cache_composition import (
        LazyModelThumbnailStore,
    )

    remote_result = object()
    local_result = object()

    class _Store:
        """Return sentinels from the concrete thumbnail store surface."""

        def cache_thumbnail(
            self,
            *,
            sha256: str,
            image: object,
            selection_policy: str,
        ) -> object:
            """Return the remote thumbnail sentinel."""

            _ = sha256, image, selection_policy
            return remote_result

        def cache_local_thumbnail(
            self,
            *,
            sha256: str,
            image: object | None,
            source: str,
            source_label: str,
            source_path: str | None = None,
            source_width: int | None = None,
            source_height: int | None = None,
        ) -> object:
            """Return the local thumbnail sentinel."""

            _ = (
                sha256,
                image,
                source,
                source_label,
                source_path,
                source_width,
                source_height,
            )
            return local_result

    store = LazyModelThumbnailStore()
    monkeypatch.setattr(store, "_resolve", lambda: _Store())

    assert (
        store.cache_thumbnail(
            sha256="abc",
            image=cast(CivitaiImage, object()),
            selection_policy="first_sfw",
        )
        is remote_result
    )
    assert (
        store.cache_local_thumbnail(
            sha256="abc",
            image=None,
            source="output",
            source_label="Output",
        )
        is local_result
    )
