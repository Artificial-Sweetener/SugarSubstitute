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

"""Adapt the authoritative backend model catalog to shared local inventory."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from substitute.application.model_metadata.ports import BackendModelMetadataGateway
from substitute.domain.model_metadata import FingerprintStatus
from sugarsubstitute_shared.model_discovery import LocalModel, ModelCategory


class BackendModelInventory:
    """List Comfy-visible models across every backend-configured model root."""

    def __init__(self, gateway: BackendModelMetadataGateway) -> None:
        """Store the target-owned model catalog gateway."""

        self._gateway = gateway

    def list_models(
        self,
        categories: Collection[ModelCategory],
    ) -> tuple[LocalModel, ...]:
        """Return visible models without exposing or reconstructing absolute roots."""

        ordered_categories = tuple(
            category for category in ModelCategory if category in categories
        )
        if not ordered_categories:
            return ()
        entries = self._gateway.list_models(
            tuple(category.value for category in ordered_categories)
        )
        allowed = set(ordered_categories)
        models: list[LocalModel] = []
        for entry in entries:
            try:
                category = ModelCategory(entry.kind)
            except ValueError:
                continue
            if category not in allowed:
                continue
            sha256 = (
                entry.fingerprint.sha256
                if entry.fingerprint.status is FingerprintStatus.READY
                else None
            )
            models.append(
                LocalModel(
                    category=category,
                    path=Path(entry.source.root_id) / entry.source.relative_path,
                    sha256=sha256,
                )
            )
        return tuple(models)


__all__ = ["BackendModelInventory"]
