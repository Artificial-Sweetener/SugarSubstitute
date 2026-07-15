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

"""Tests for Phase 23 catalog-backed snapshot contract types."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from substitute.presentation.editor.prompt_editor.features import (
    PHASE23_CATALOG_FOREGROUND_INVENTORY,
    CatalogForegroundConsumer,
    CatalogLookupClassification,
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)


def test_catalog_snapshot_identity_carries_phase23_freshness_inputs() -> None:
    """Snapshot identity should include every Phase 23 freshness dimension."""

    identity = CatalogSnapshotIdentity(
        source_revision=12,
        editor_context_id="editor:prompt",
        panel_context_id="panel:workflow",
        feature_profile_id=("lora", True),
        catalog_revision=("loras", 7),
        prompt_context_token=("prompt", 12),
        cube_context_token=("cube", "Base"),
        scene_context_token=("scene", "intro"),
        query_identity=("wildcard", "ca", 10),
        request_identity=("request", 4),
    )

    assert identity.source_revision == 12
    assert identity.editor_context_id == "editor:prompt"
    assert identity.panel_context_id == "panel:workflow"
    assert identity.feature_profile_id == ("lora", True)
    assert identity.catalog_revision == ("loras", 7)
    assert identity.prompt_context_token == ("prompt", 12)
    assert identity.cube_context_token == ("cube", "Base")
    assert identity.scene_context_token == ("scene", "intro")
    assert identity.query_identity == ("wildcard", "ca", 10)
    assert identity.request_identity == ("request", 4)


def test_catalog_snapshot_identity_rejects_invalid_state() -> None:
    """Invalid freshness identity should fail before foreground code trusts it."""

    with pytest.raises(ValueError, match="source_revision"):
        CatalogSnapshotIdentity(source_revision=-1)

    with pytest.raises(ValueError, match="unavailable_reason"):
        CatalogSnapshotIdentity(unavailable_reason="")


def test_catalog_snapshot_identity_updates_stale_state_without_changing_inputs() -> (
    None
):
    """Stale publication should preserve catalog and context identity."""

    identity = CatalogSnapshotIdentity(
        source_revision=3,
        catalog_revision="catalog:1",
        query_identity=("lora", "mid"),
    )

    stale = identity.with_stale_state(
        stale=True,
        unavailable_reason="catalog_refresh_failed",
    )

    assert stale.source_revision == identity.source_revision
    assert stale.catalog_revision == identity.catalog_revision
    assert stale.query_identity == identity.query_identity
    assert stale.stale is True
    assert stale.unavailable_reason == "catalog_refresh_failed"


def test_catalog_snapshot_status_requires_reasons_for_non_ready_states() -> None:
    """Cold, stale, failure, disabled, and unavailable states are explicit."""

    assert CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM).consumable is True
    assert CatalogSnapshotStatus(CatalogSnapshotReadiness.STALE).consumable is True
    assert CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD).consumable is False
    assert (
        CatalogSnapshotStatus(
            CatalogSnapshotReadiness.UNAVAILABLE,
            unavailable_reason="catalog_unavailable",
        ).consumable
        is False
    )
    assert (
        CatalogSnapshotStatus(
            CatalogSnapshotReadiness.REFRESH_FAILED,
            unavailable_reason="refresh_failed",
        ).consumable
        is False
    )
    assert (
        CatalogSnapshotStatus(
            CatalogSnapshotReadiness.DISABLED,
            unavailable_reason="feature_disabled",
        ).consumable
        is False
    )

    with pytest.raises(ValueError, match="require a reason"):
        CatalogSnapshotStatus(CatalogSnapshotReadiness.DISABLED)
    with pytest.raises(ValueError, match="must not carry a reason"):
        CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM, "unexpected")


def test_phase23_inventory_assigns_every_foreground_consumer_to_subphase() -> None:
    """Every catalog-backed foreground consumer should have a Phase 23 owner."""

    consumers = {item.consumer for item in PHASE23_CATALOG_FOREGROUND_INVENTORY}

    assert consumers == set(CatalogForegroundConsumer)
    assert all(
        item.sub_phase.startswith("23.")
        for item in PHASE23_CATALOG_FOREGROUND_INVENTORY
    )
    assert all(item.snapshot_owner for item in PHASE23_CATALOG_FOREGROUND_INVENTORY)
    assert all(
        item.baseline_test.startswith("tests/")
        for item in PHASE23_CATALOG_FOREGROUND_INVENTORY
    )


def test_phase23_inventory_classifies_existing_lookup_tokens() -> None:
    """Phase 23.1 should classify each direct lookup family before extraction."""

    token_classification = {
        item.lookup_token: item.classification
        for item in PHASE23_CATALOG_FOREGROUND_INVENTORY
    }

    assert token_classification["refresh_loras("] is (
        CatalogLookupClassification.EXPLICIT_REFRESH
    )
    assert token_classification["list_loras("] is (
        CatalogLookupClassification.EXPLICIT_REFRESH
    )
    assert token_classification["search_wildcards("] is (
        CatalogLookupClassification.FORBIDDEN_FOREGROUND
    )
    assert token_classification["read_thumbnail_asset("] is (
        CatalogLookupClassification.BACKGROUND_WARMUP
    )


def test_catalog_snapshot_contract_types_are_passive_dataclasses() -> None:
    """Snapshot contracts should not import Qt, widgets, or application services."""

    contract_types = (CatalogSnapshotIdentity, CatalogSnapshotStatus)
    for contract_type in contract_types:
        assert is_dataclass(contract_type)
        assert fields(contract_type)

    source = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "presentation"
        / "editor"
        / "prompt_editor"
        / "features"
        / "catalog_snapshots.py"
    ).read_text(encoding="utf-8")
    forbidden_tokens = (
        "PySide6",
        "qfluentwidgets",
        "QWidget",
        "ModelCatalogService",
        "PromptLoraCatalogService",
    )

    assert not [token for token in forbidden_tokens if token in source]
