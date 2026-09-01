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

"""Verify backend catalog adaptation across all configured model roots."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from substitute.application.model_discovery import BackendModelInventory
from substitute.application.model_metadata.ports import BackendModelMetadataGateway
from substitute.domain.model_metadata import BackendModelCatalogEntry, FingerprintStatus
from sugarsubstitute_shared.model_discovery import ModelCategory
from tests.application.model_metadata.catalog_service.support import _entry


class _Gateway:
    """Expose representative backend catalog records."""

    def __init__(self) -> None:
        """Build managed, external, and unsupported entries."""

        ready = _entry(
            "checkpoints",
            "base/model.safetensors",
            "a" * 64,
        )
        ready = replace(ready, source=replace(ready.source, root_id="managed"))
        stale = _entry(
            "loras",
            "style.safetensors",
            "b" * 64,
        )
        stale = replace(
            stale,
            source=replace(stale.source, root_id="external-1"),
            fingerprint=replace(stale.fingerprint, status=FingerprintStatus.STALE),
        )
        self.entries: tuple[BackendModelCatalogEntry, ...] = (ready, stale)
        self.kinds: tuple[str, ...] = ()

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Record the requested kinds and return representative entries."""

        assert not refresh
        self.kinds = kinds
        return self.entries


def test_inventory_uses_backend_visible_roots_and_only_ready_hashes() -> None:
    """Gating must see external roots while owned filtering requires ready evidence."""

    gateway = _Gateway()

    models = BackendModelInventory(
        cast(BackendModelMetadataGateway, gateway)
    ).list_models({ModelCategory.CHECKPOINTS, ModelCategory.LORAS})

    assert gateway.kinds == ("checkpoints", "loras")
    assert str(models[0].path).replace("\\", "/") == "managed/base/model.safetensors"
    assert models[0].sha256 == "a" * 64
    assert str(models[1].path).replace("\\", "/") == "external-1/style.safetensors"
    assert models[1].sha256 is None
