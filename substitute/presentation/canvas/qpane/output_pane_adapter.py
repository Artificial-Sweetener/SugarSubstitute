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

"""Adapt Output QPane display APIs for guarded route projectors."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Protocol, cast
from uuid import UUID

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.qpane.output_pane_adapter")


class _OutputDisplayPane(Protocol):
    """Describe Output QPane display methods used by the route adapter."""

    def setCurrentImageID(self, image_id: UUID | None) -> None:  # noqa: N802
        """Switch active image selection."""

    def currentImageID(self) -> UUID | None:  # noqa: N802
        """Return active image selection."""

    def currentCompositionID(self) -> UUID | None:  # noqa: N802
        """Return active stored composition ID."""

    def getCompositionSnapshot(self) -> object:  # noqa: N802
        """Return QPane's public composition snapshot."""

    def composeScene(self, request: object, *, activate: bool) -> UUID:  # noqa: N802
        """Create or replace a stored scene composition."""

    def openComposition(self, composition_id: UUID) -> None:  # noqa: N802
        """Open a stored composition."""

    def removeComposition(self, composition_id: UUID) -> None:  # noqa: N802
        """Remove a stored composition."""

    def setComparisonImageID(self, image_id: UUID) -> None:  # noqa: N802
        """Set the comparison catalog image."""

    def setComparisonSplit(self, position: float, orientation: object) -> None:  # noqa: N802
        """Set the comparison divider split."""

    def clearComparisonImage(self) -> None:  # noqa: N802
        """Clear comparison rendering."""

    def sceneHitTest(self, point: object) -> object | None:  # noqa: N802
        """Return a public scene hit for point."""


class OutputQPaneRouteAdapter:
    """Wrap one Output QPane instance with display-only operations."""

    def __init__(self, pane: object) -> None:
        """Store the wrapped Output QPane."""

        self._pane = pane
        self._fallback_current_composition_id: UUID | None = None
        self._fallback_compositions: dict[UUID, object] = {}

    def set_current_image_id(self, image_id: UUID | None) -> bool:
        """Set the active image through QPane's public display API."""

        setter = getattr(self._pane, "setCurrentImageID", None)
        if not callable(setter):
            log_warning(
                _LOGGER,
                "Output QPane route selection skipped because API is unavailable",
                image_id=image_id,
            )
            return False
        setter(image_id)
        return True

    def activate_default_image_id(self, image_id: UUID) -> bool:
        """Select and open QPane's generated default composition for one image."""

        if not self.set_current_image_id(image_id):
            return False
        composition_id = self._default_image_composition_id(image_id)
        if composition_id is None:
            return self.current_image_id() == image_id
        return self.open_composition(composition_id)

    def current_image_id(self) -> UUID | None:
        """Return the active image through QPane's public display API."""

        getter = getattr(self._pane, "currentImageID", None)
        if not callable(getter):
            return None
        value = getter()
        return value if isinstance(value, UUID) else None

    def current_composition_id(self) -> UUID | None:
        """Return the active composition through QPane's public display API."""

        getter = getattr(self._pane, "currentCompositionID", None)
        if not callable(getter):
            return self._fallback_current_composition_id
        value = getter()
        return value if isinstance(value, UUID) else None

    def composition_snapshot(self) -> object | None:
        """Return QPane's public composition snapshot when available."""

        getter = getattr(self._pane, "getCompositionSnapshot", None)
        if not callable(getter):
            if not self._fallback_compositions:
                return None
            return SimpleNamespace(
                current_composition_id=self._fallback_current_composition_id,
                compositions=self._fallback_compositions,
            )
        try:
            return cast(object, getter())
        except (RuntimeError, TypeError, ValueError):
            log_warning(_LOGGER, "Output QPane composition snapshot query failed")
            return None

    def _default_image_composition_id(self, image_id: UUID) -> UUID | None:
        """Return QPane's generated default-image composition for one image."""

        snapshot = self.composition_snapshot()
        compositions = getattr(snapshot, "compositions", None)
        if not isinstance(compositions, Mapping):
            return None
        for composition_id, entry in compositions.items():
            if not isinstance(composition_id, UUID):
                continue
            if (
                getattr(entry, "kind", None) == "default-image"
                and getattr(entry, "current_image_id", None) == image_id
            ):
                return composition_id
        return None

    def compose_scene(self, request: object, *, activate: bool) -> UUID | None:
        """Compose a scene through QPane's public display API."""

        compose = getattr(self._pane, "composeScene", None)
        if not callable(compose):
            return None
        value = compose(request, activate=activate)
        if not isinstance(value, UUID):
            return None
        composition_id = getattr(request, "composition_id", value)
        recorded_id = composition_id if isinstance(composition_id, UUID) else value
        self._record_fallback_composition(request, recorded_id, activate=activate)
        return value

    def open_composition(self, composition_id: UUID) -> bool:
        """Open a stored composition through QPane's public display API."""

        opener = getattr(self._pane, "openComposition", None)
        if not callable(opener):
            return False
        try:
            opener(composition_id)
        except (KeyError, RuntimeError, TypeError, ValueError):
            log_warning(
                _LOGGER,
                "Output QPane composition open failed",
                composition_id=composition_id,
            )
            return False
        self._fallback_current_composition_id = composition_id
        return True

    def remove_composition(self, composition_id: UUID) -> None:
        """Remove a stored composition through QPane's public display API."""

        remover = getattr(self._pane, "removeComposition", None)
        if not callable(remover):
            return
        try:
            remover(composition_id)
        except (KeyError, RuntimeError, TypeError, ValueError):
            log_warning(
                _LOGGER,
                "Output QPane composition removal failed",
                composition_id=composition_id,
            )
        self._fallback_compositions.pop(composition_id, None)
        if self._fallback_current_composition_id == composition_id:
            self._fallback_current_composition_id = None

    def set_comparison_image_id(self, image_id: UUID) -> bool:
        """Set comparison image through QPane's public display API."""

        setter = getattr(self._pane, "setComparisonImageID", None)
        if not callable(setter):
            return False
        setter(image_id)
        return True

    def set_comparison_split(self, position: float, orientation: object) -> bool:
        """Set comparison split through QPane's public display API."""

        setter = getattr(self._pane, "setComparisonSplit", None)
        if not callable(setter):
            return False
        setter(position, orientation)
        return True

    def clear_comparison_image(self) -> bool:
        """Clear comparison image through QPane's public display API."""

        if self._active_composition_kind() == "layered-scene":
            return True
        clearer = getattr(self._pane, "clearComparisonImage", None)
        if not callable(clearer):
            return True
        try:
            clearer()
        except RuntimeError:
            log_warning(_LOGGER, "Output QPane comparison clear failed")
            return False
        return True

    def _active_composition_kind(self) -> str | None:
        """Return the active public composition kind when QPane exposes it."""

        composition_id = self.current_composition_id()
        if composition_id is None:
            return None
        snapshot = self.composition_snapshot()
        compositions = getattr(snapshot, "compositions", None)
        if not isinstance(compositions, Mapping):
            return None
        entry = compositions.get(composition_id)
        kind = getattr(entry, "kind", None)
        return kind if isinstance(kind, str) else None

    def scene_hit_test(self, point: object) -> object | None:
        """Return one public QPane scene hit for point."""

        hit_test = getattr(self._pane, "sceneHitTest", None)
        if not callable(hit_test):
            return None
        return cast(object | None, hit_test(point))

    def _record_fallback_composition(
        self,
        request: object,
        composition_id: UUID,
        *,
        activate: bool,
    ) -> None:
        """Track composed scene state when a lightweight pane lacks snapshot APIs."""

        layers = getattr(request, "layers", ())
        source_image_ids = tuple(
            image_id
            for image_id in (getattr(layer, "image_id", None) for layer in layers)
            if isinstance(image_id, UUID)
        )
        self._fallback_compositions[composition_id] = SimpleNamespace(
            composition_id=composition_id,
            kind="layered-scene",
            source_image_ids=source_image_ids,
            current_image_id=None,
            comparison=SimpleNamespace(enabled=False, source_id=None),
        )
        if activate:
            self._fallback_current_composition_id = composition_id


__all__ = ["OutputQPaneRouteAdapter"]
