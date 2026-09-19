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

"""Parse the authoritative updater and persisted-data compatibility contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class HistoricalUpdateBoundary:
    """Name one published build that represents a compatibility transition."""

    identifier: str
    representative_version: str
    route: str
    platforms: tuple[str, ...]

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one exact historical boundary declaration."""

        if not isinstance(payload, dict):
            raise ValueError("Historical update boundary must be an object.")
        platforms = payload.get("platforms")
        if not isinstance(platforms, list) or not platforms:
            raise ValueError("Historical update boundary platforms must be a list.")
        normalized_platforms = tuple(_required_text(value) for value in platforms)
        if len(set(normalized_platforms)) != len(normalized_platforms):
            raise ValueError("Historical update boundary platforms must be unique.")
        return cls(
            identifier=_required_text(payload.get("id")),
            representative_version=_required_text(
                payload.get("representative_version")
            ),
            route=_required_text(payload.get("route")),
            platforms=normalized_platforms,
        )


@dataclass(frozen=True, slots=True)
class DataMigrationBoundary:
    """Name one persisted-data fixture required by update qualification."""

    identifier: str
    representative_version: str

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one exact persisted-data migration boundary."""

        if not isinstance(payload, dict):
            raise ValueError("Data migration boundary must be an object.")
        return cls(
            identifier=_required_text(payload.get("id")),
            representative_version=_required_text(
                payload.get("representative_version")
            ),
        )


@dataclass(frozen=True, slots=True)
class DataMigrationStep:
    """Declare one ordered, idempotent persisted-data migration."""

    identifier: str
    from_epoch: int
    to_epoch: int

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one contiguous migration edge."""

        if not isinstance(payload, dict):
            raise ValueError("Data migration step must be an object.")
        from_epoch = _required_nonnegative_int(
            payload.get("from_epoch"), "data_compatibility.migrations.from_epoch"
        )
        to_epoch = _required_positive_int(
            payload.get("to_epoch"), "data_compatibility.migrations.to_epoch"
        )
        if to_epoch != from_epoch + 1:
            raise ValueError("Data migration steps must advance exactly one epoch.")
        return cls(
            identifier=_required_text(payload.get("id")),
            from_epoch=from_epoch,
            to_epoch=to_epoch,
        )


@dataclass(frozen=True, slots=True)
class UpdateCompatibilityContract:
    """Own release admission and finite historical qualification boundaries."""

    schema_version: int
    delegation_protocol: int
    update_protocol: int
    minimum_direct_launcher_version: str
    supported_manifest_schema_versions: tuple[int, ...]
    historical_boundaries: tuple[HistoricalUpdateBoundary, ...]
    data_schema_epoch: int
    data_migrations: tuple[DataMigrationStep, ...]
    data_migration_boundaries: tuple[DataMigrationBoundary, ...]

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load the authoritative contract from a source or packaged asset."""

        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse and validate the complete compatibility contract."""

        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported launcher compatibility contract schema.")
        manifest_schemas = payload.get("supported_manifest_schema_versions")
        boundaries = payload.get("historical_boundaries")
        data = payload.get("data_compatibility")
        if (
            not isinstance(manifest_schemas, list)
            or not manifest_schemas
            or any(type(value) is not int or value <= 0 for value in manifest_schemas)
        ):
            raise ValueError("Supported manifest schemas must be positive integers.")
        if len(set(manifest_schemas)) != len(manifest_schemas):
            raise ValueError("Supported manifest schemas must be unique.")
        if not isinstance(boundaries, list) or not boundaries:
            raise ValueError("Historical update boundaries must be a non-empty list.")
        if not isinstance(data, dict):
            raise ValueError("Data compatibility contract must be an object.")
        migration_boundaries = data.get("migration_boundaries")
        migrations = data.get("migrations")
        if not isinstance(migration_boundaries, list):
            raise ValueError("Data migration boundaries must be a list.")
        if not isinstance(migrations, list):
            raise ValueError("Data migrations must be a list.")
        parsed_boundaries = tuple(
            HistoricalUpdateBoundary.from_json(value) for value in boundaries
        )
        parsed_migrations = tuple(
            DataMigrationBoundary.from_json(value) for value in migration_boundaries
        )
        parsed_steps = tuple(DataMigrationStep.from_json(value) for value in migrations)
        identifiers = [value.identifier for value in parsed_boundaries]
        identifiers.extend(value.identifier for value in parsed_migrations)
        identifiers.extend(value.identifier for value in parsed_steps)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Compatibility boundary identifiers must be unique.")
        schema_epoch = _required_positive_int(
            data.get("schema_epoch"), "data_compatibility.schema_epoch"
        )
        if tuple((step.from_epoch, step.to_epoch) for step in parsed_steps) != tuple(
            (epoch, epoch + 1) for epoch in range(schema_epoch)
        ):
            raise ValueError("Data migrations must define every epoch transition once.")
        return cls(
            schema_version=1,
            delegation_protocol=_required_positive_int(
                payload.get("delegation_protocol"), "delegation_protocol"
            ),
            update_protocol=_required_positive_int(
                payload.get("update_protocol"), "update_protocol"
            ),
            minimum_direct_launcher_version=_required_text(
                payload.get("minimum_direct_launcher_version")
            ),
            supported_manifest_schema_versions=tuple(manifest_schemas),
            historical_boundaries=parsed_boundaries,
            data_schema_epoch=schema_epoch,
            data_migrations=parsed_steps,
            data_migration_boundaries=parsed_migrations,
        )

    def qualification_versions(self) -> tuple[tuple[str, str], ...]:
        """Return deduplicated representative versions with joined boundary ids."""

        identifiers_by_version: dict[str, list[str]] = {}
        for update_boundary in self.historical_boundaries:
            identifiers_by_version.setdefault(
                update_boundary.representative_version, []
            ).append(update_boundary.identifier)
        for migration_boundary in self.data_migration_boundaries:
            identifiers_by_version.setdefault(
                migration_boundary.representative_version, []
            ).append(migration_boundary.identifier)
        return tuple(
            (version, "+".join(identifiers))
            for version, identifiers in identifiers_by_version.items()
        )


def load_repository_update_compatibility(
    repo_root: Path,
) -> UpdateCompatibilityContract:
    """Load the single source-owned launcher compatibility declaration."""

    return UpdateCompatibilityContract.load(
        repo_root.resolve() / "launcher" / "launcher-contract.json"
    )


def _required_text(value: object) -> str:
    """Return one non-empty compatibility string."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("Compatibility contract text must not be empty.")
    return value


def _required_positive_int(value: object, field: str) -> int:
    """Return one positive integer compatibility field."""

    if type(value) is not int or value <= 0:
        raise ValueError(f"Compatibility field must be a positive integer: {field}")
    return value


def _required_nonnegative_int(value: object, field: str) -> int:
    """Return one non-negative integer compatibility field."""

    if type(value) is not int or value < 0:
        raise ValueError(f"Compatibility field must be a non-negative integer: {field}")
    return value


__all__ = [
    "DataMigrationBoundary",
    "DataMigrationStep",
    "HistoricalUpdateBoundary",
    "UpdateCompatibilityContract",
    "load_repository_update_compatibility",
]
