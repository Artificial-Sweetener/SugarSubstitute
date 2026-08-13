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

"""Adopt validated legacy cache data into compatible governed generations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import json
import shutil
import sqlite3

from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_COMFY_I18N,
    CACHE_ID_CUBE_CLASSIFICATIONS,
    CACHE_ID_CUBE_ICONS,
    CACHE_ID_DANBOORU_IMAGES,
    CACHE_ID_DANBOORU_METADATA,
    CACHE_ID_MODEL_METADATA,
    CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
    CACHE_ID_MODEL_THUMBNAILS,
)
from substitute.application.cache_lifecycle import PreparedCacheCatalog
from substitute.domain.danbooru import DanbooruCachedImageAsset
from substitute.infrastructure.cache_lifecycle.legacy_model_cache_migration import (
    LegacyModelCacheMigrator,
)
from substitute.infrastructure.cache_lifecycle.legacy_sqlite_validation import (
    sqlite_tables,
    validate_sqlite,
)
from substitute.infrastructure.persistence.danbooru_image_cache_store import (
    SqliteDanbooruImageCacheStore,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("infrastructure.cache_lifecycle.legacy_migration")


class LegacyPersistentCacheMigrator:
    """Validate and copy known legacy caches without trusting unknown content."""

    def __init__(
        self,
        cache_root: Path,
        *,
        installation_root: Path | None,
        legacy_model_metadata_root: Path | None,
    ) -> None:
        """Store legacy roots needed for cache-specific adoption."""

        self._cache_root = cache_root.resolve()
        self._installation_root = (
            installation_root.resolve() if installation_root is not None else None
        )
        self._model_migrator = LegacyModelCacheMigrator(
            self._cache_root,
            installation_root=self._installation_root,
            legacy_model_metadata_root=legacy_model_metadata_root,
        )

    def migrate(self, prepared: PreparedCacheCatalog) -> None:
        """Attempt each cache migration independently so failures remain misses."""

        migrations: tuple[tuple[str, Callable[[], None]], ...] = (
            (CACHE_ID_CUBE_ICONS, lambda: self._migrate_cube_icons(prepared)),
            (
                CACHE_ID_CUBE_CLASSIFICATIONS,
                lambda: self._migrate_cube_classifications(prepared),
            ),
            (CACHE_ID_COMFY_I18N, lambda: self._migrate_comfy_i18n(prepared)),
        )
        prepared_ids = {namespace.cache_id for namespace in prepared.namespaces}
        for cache_id, migrate in migrations:
            if cache_id not in prepared_ids:
                continue
            try:
                migrate()
            except (OSError, sqlite3.DatabaseError, ValueError, TypeError) as error:
                log_warning(
                    _LOGGER,
                    "Ignored an invalid legacy persistent cache.",
                    cache_id=cache_id,
                    error=repr(error),
                )
        grouped_migrations: tuple[
            tuple[frozenset[str], str, Callable[[], None]], ...
        ] = (
            (
                frozenset({CACHE_ID_DANBOORU_METADATA, CACHE_ID_DANBOORU_IMAGES}),
                "danbooru",
                lambda: self._migrate_danbooru(prepared, prepared_ids=prepared_ids),
            ),
            (
                frozenset(
                    {
                        CACHE_ID_MODEL_METADATA,
                        CACHE_ID_MODEL_THUMBNAILS,
                        CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
                    }
                ),
                "models",
                lambda: self._model_migrator.migrate(prepared),
            ),
        )
        for required_ids, owner, migrate in grouped_migrations:
            if required_ids.isdisjoint(prepared_ids):
                continue
            try:
                migrate()
            except (OSError, sqlite3.DatabaseError, ValueError, TypeError) as error:
                log_warning(
                    _LOGGER,
                    "Ignored invalid grouped legacy persistent cache content.",
                    cache_owner=owner,
                    error=repr(error),
                )

    def _migrate_cube_icons(self, prepared: PreparedCacheCatalog) -> None:
        """Adopt a schema-1 cube icon database when the generation is empty."""

        destination = prepared.namespace(CACHE_ID_CUBE_ICONS).path / (
            "cube_icon_cache.sqlite3"
        )
        self._copy_first_valid_sqlite(
            self._cache_candidates(
                Path("cube/cube_icon_cache.sqlite3"),
                Path("state/cube_icon_cache.sqlite3"),
            ),
            destination,
            required_tables={"cube_icon_cache_schema", "rendered_cube_icons"},
            schema_table="cube_icon_cache_schema",
            expected_schema="1",
        )

    def _migrate_cube_classifications(self, prepared: PreparedCacheCatalog) -> None:
        """Adopt a schema-1 cube classification database when compatible."""

        destination = prepared.namespace(CACHE_ID_CUBE_CLASSIFICATIONS).path / (
            "cube_classification_cache.sqlite3"
        )
        self._copy_first_valid_sqlite(
            self._cache_candidates(
                Path("cube/cube_classification_cache.sqlite3"),
                Path("state/cube_classification_cache.sqlite3"),
            ),
            destination,
            required_tables={
                "cube_classification_cache_schema",
                "cube_picker_classifications",
            },
            schema_table="cube_classification_cache_schema",
            expected_schema="1",
        )

    def _migrate_comfy_i18n(self, prepared: PreparedCacheCatalog) -> None:
        """Adopt only bounded schema-2 Comfy localization JSON entries."""

        destination = prepared.namespace(CACHE_ID_COMFY_I18N).path
        if any(path.name != "generation.json" for path in destination.glob("*.json")):
            return
        source = self._cache_root / "comfy_i18n"
        if not source.is_dir():
            return
        migrated = 0
        for candidate in source.glob("*.json"):
            if (
                candidate.stat().st_size <= 0
                or candidate.stat().st_size > 16 * 1024 * 1024
            ):
                continue
            with candidate.open("r", encoding="utf-8", errors="strict") as stream:
                payload = json.load(stream)
            if not _valid_comfy_i18n_payload(payload):
                continue
            shutil.copy2(candidate, destination / candidate.name)
            migrated += 1
        self._log_migration(CACHE_ID_COMFY_I18N, migrated)

    def _migrate_danbooru(
        self,
        prepared: PreparedCacheCatalog,
        *,
        prepared_ids: set[str],
    ) -> None:
        """Split a valid combined Danbooru cache into governed metadata and images."""

        source = self._first_existing(
            self._cache_candidates(
                Path("danbooru/danbooru_cache.sqlite3"),
                Path("state/danbooru_cache.sqlite3"),
            )
        )
        if source is None:
            return
        required = {
            "danbooru_wiki_pages",
            "danbooru_tags",
            "danbooru_posts",
            "danbooru_post_searches",
        }
        validate_sqlite(source, required_tables=required)
        if CACHE_ID_DANBOORU_METADATA in prepared_ids:
            metadata_destination = (
                prepared.namespace(CACHE_ID_DANBOORU_METADATA).path
                / "danbooru_cache.sqlite3"
            )
            if not metadata_destination.exists():
                shutil.copy2(source, metadata_destination)
                self._log_migration(CACHE_ID_DANBOORU_METADATA, 1)
        if CACHE_ID_DANBOORU_IMAGES in prepared_ids:
            self._migrate_danbooru_images(
                source,
                prepared.namespace(CACHE_ID_DANBOORU_IMAGES).path,
            )

    def _migrate_danbooru_images(self, source: Path, destination: Path) -> None:
        """Copy readable legacy image rows through the current image-store contract."""

        with sqlite3.connect(source) as connection:
            if "danbooru_image_assets" not in sqlite_tables(connection):
                return
            connection.row_factory = sqlite3.Row
            rows = connection.execute("select * from danbooru_image_assets").fetchall()
        store = SqliteDanbooruImageCacheStore(destination)
        if store.summary()[0] > 0:
            return
        migrated = 0
        for row in rows:
            legacy_path = Path(str(row["local_path"]))
            if not legacy_path.is_file():
                migrated_path = self._find_legacy_danbooru_image(legacy_path.name)
                if migrated_path is None:
                    continue
                legacy_path = migrated_path
            asset = DanbooruCachedImageAsset(
                cache_key=str(row["cache_key"]),
                source_url=str(row["source_url"]),
                local_path=legacy_path,
                rating=_optional_str(row["rating"]),
                width=_optional_int(row["width"]),
                height=_optional_int(row["height"]),
                fetched_at=str(row["fetched_at"]),
                last_used_at=str(row["last_used_at"]),
                byte_size=int(row["byte_size"]),
            )
            store.save_cached_image_asset(asset, legacy_path.read_bytes())
            migrated += 1
        self._log_migration(CACHE_ID_DANBOORU_IMAGES, migrated)

    def _copy_first_valid_sqlite(
        self,
        candidates: tuple[Path, ...],
        destination: Path,
        *,
        required_tables: set[str],
        schema_table: str | None = None,
        expected_schema: str | None = None,
    ) -> None:
        """Copy the first valid database when the current generation is empty."""

        if destination.exists():
            return
        source = self._first_existing(candidates)
        if source is None:
            return
        validate_sqlite(
            source,
            required_tables=required_tables,
            schema_table=schema_table,
            expected_schema=expected_schema,
        )
        shutil.copy2(source, destination)
        self._log_migration(destination.stem, 1)

    def _cache_candidates(
        self,
        cache_relative: Path,
        legacy_state_relative: Path,
    ) -> tuple[Path, ...]:
        """Return current-cache and pre-layout-migration source candidates."""

        candidates = [self._cache_root / cache_relative]
        if self._installation_root is not None:
            candidates.append(self._installation_root / legacy_state_relative)
        return tuple(candidates)

    def _find_legacy_danbooru_image(self, name: str) -> Path | None:
        """Return a known legacy Danbooru image path by file name when present."""

        candidates = [
            self._cache_root / "danbooru" / "danbooru_images" / name,
            self._cache_root / "danbooru" / "images" / name,
        ]
        if self._installation_root is not None:
            candidates.append(
                self._installation_root / "state" / "danbooru_images" / name
            )
        return self._first_existing(tuple(candidates))

    @staticmethod
    def _first_existing(candidates: tuple[Path, ...]) -> Path | None:
        """Return the first existing file or directory candidate."""

        return next((candidate for candidate in candidates if candidate.exists()), None)

    @staticmethod
    def _log_migration(cache_id: str, migrated_entries: int) -> None:
        """Log a successful nonempty legacy cache adoption."""

        if migrated_entries <= 0:
            return
        log_info(
            _LOGGER,
            "Adopted validated legacy persistent cache content.",
            cache_id=cache_id,
            migrated_entries=migrated_entries,
        )


def _valid_comfy_i18n_payload(payload: object) -> bool:
    """Return whether one legacy Comfy localization payload is schema compatible."""

    return isinstance(payload, dict) and (
        payload.get("schema_version") == 2
        and isinstance(payload.get("active_alias"), str)
        and isinstance(payload.get("active_node_defs"), dict)
        and (
            payload.get("english_node_defs") is None
            or isinstance(payload.get("english_node_defs"), dict)
        )
    )


def _optional_int(value: object) -> int | None:
    """Return an optional SQLite integer."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"Expected integer-compatible SQLite value, got {type(value)!r}.")


def _optional_str(value: object) -> str | None:
    """Return an optional SQLite string."""

    return value if isinstance(value, str) else None


__all__ = ["LegacyPersistentCacheMigrator"]
