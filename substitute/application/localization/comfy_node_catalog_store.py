#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Publish active-only Comfy server node catalogs atomically."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from substitute.domain.localization import NodeTextCatalog, NodeTextCatalogSnapshot


@dataclass(frozen=True, slots=True)
class ComfyNodeCatalogSelection:
    """Hold English plus one active Comfy server catalog generation."""

    effective_language_identifier: str
    revision: int
    active_catalog: NodeTextCatalog | None
    english_catalog: NodeTextCatalog | None


class ActiveComfyNodeCatalogStore:
    """Retain one immutable Comfy locale selection behind a lock."""

    def __init__(self) -> None:
        """Create an empty active-only store with monotonic revisions."""

        self._lock = RLock()
        self._selection: ComfyNodeCatalogSelection | None = None
        self._revision = 0

    def publish(
        self,
        *,
        effective_language_identifier: str,
        active_catalog: NodeTextCatalog | None,
        english_catalog: NodeTextCatalog | None,
    ) -> ComfyNodeCatalogSelection:
        """Atomically replace the prior language generation and release its catalogs."""

        with self._lock:
            self._revision += 1
            selection = ComfyNodeCatalogSelection(
                effective_language_identifier=effective_language_identifier,
                revision=self._revision,
                active_catalog=active_catalog,
                english_catalog=english_catalog,
            )
            self._selection = selection
            return selection

    def clear_for_language(
        self,
        effective_language_identifier: str,
    ) -> ComfyNodeCatalogSelection:
        """Drop an obsolete generation while a new language branch is loading."""

        return self.publish(
            effective_language_identifier=effective_language_identifier,
            active_catalog=None,
            english_catalog=None,
        )

    def snapshot(self, effective_language_identifier: str) -> NodeTextCatalogSnapshot:
        """Return the matching server generation or one empty fallback snapshot."""

        with self._lock:
            selection = self._selection
            revision = self._revision
        if (
            selection is None
            or selection.effective_language_identifier != effective_language_identifier
        ):
            return NodeTextCatalogSnapshot(
                effective_language_identifier=effective_language_identifier,
                revision=revision,
                active_layers=(),
                english_layers=(),
            )
        return NodeTextCatalogSnapshot(
            effective_language_identifier=effective_language_identifier,
            revision=selection.revision,
            active_layers=(
                (selection.active_catalog,)
                if selection.active_catalog is not None
                else ()
            ),
            english_layers=(
                (selection.english_catalog,)
                if selection.english_catalog is not None
                else ()
            ),
        )

    def selection(self) -> ComfyNodeCatalogSelection | None:
        """Return the current immutable selection for diagnostics and tests."""

        with self._lock:
            return self._selection


__all__ = ["ActiveComfyNodeCatalogStore", "ComfyNodeCatalogSelection"]
