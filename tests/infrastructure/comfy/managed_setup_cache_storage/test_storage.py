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

"""Verify governed storage and legacy recovery for managed-setup evidence."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_MANAGED_SETUP_EVIDENCE,
)
from substitute.infrastructure.cache_lifecycle import SemanticSourceFingerprintService
from substitute.infrastructure.comfy import managed_setup_cache_storage
from substitute.infrastructure.comfy.managed_setup_cache_storage import (
    build_managed_setup_cache_registration,
    prepare_managed_setup_cache,
)


def test_setup_evidence_uses_a_catalog_owned_compatibility_generation(
    tmp_path: Path,
) -> None:
    """Store disposable setup evidence below a catalog-owned cache namespace."""

    session = prepare_managed_setup_cache(tmp_path)
    try:
        record_path = session.record_path
    finally:
        session.close()

    cache_root = (tmp_path / ".substitute" / "cache").resolve()
    assert record_path.is_relative_to(cache_root)
    assert record_path.name == "record.json"
    assert (record_path.parent / "generation.json").is_file()
    assert not (tmp_path / ".substitute" / "managed_setup_freshness.json").exists()


def test_setup_evidence_adopts_valid_legacy_data_without_deleting_it(
    tmp_path: Path,
) -> None:
    """Adopt valid legacy evidence while retaining the original record."""

    legacy_path = tmp_path / ".substitute" / "managed_setup_freshness.json"
    legacy_path.parent.mkdir(parents=True)
    payload = {"schema_version": 5, "success": True, "key": {"value": 1}}
    legacy_path.write_text(json.dumps(payload), encoding="utf-8")

    session = prepare_managed_setup_cache(tmp_path)
    try:
        adopted = json.loads(session.record_path.read_text(encoding="utf-8"))
    finally:
        session.close()

    assert adopted == payload
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == payload


def test_setup_evidence_treats_corrupt_legacy_data_as_a_cache_miss(
    tmp_path: Path,
) -> None:
    """Treat corrupt legacy evidence as a cache miss without deleting it."""

    legacy_path = tmp_path / ".substitute" / "managed_setup_freshness.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text("{not-json", encoding="utf-8")

    session = prepare_managed_setup_cache(tmp_path)
    try:
        assert not session.record_path.exists()
    finally:
        session.close()
    assert legacy_path.read_text(encoding="utf-8") == "{not-json"


def test_setup_evidence_registration_declares_semantics_and_retention() -> None:
    """Declare source-based compatibility and bounded generation retention."""

    source_root = Path(managed_setup_cache_storage.__file__).resolve().parents[3]
    registration = build_managed_setup_cache_registration(
        source_root=source_root,
        fingerprints=SemanticSourceFingerprintService(),
    )

    assert registration.cache_id == CACHE_ID_MANAGED_SETUP_EVIDENCE
    assert registration.compatibility.storage_schema == "5"
    assert registration.compatibility.producer_fingerprint
    assert registration.retention.maximum_generations == 3
    assert registration.retention.maximum_age_days == 45
