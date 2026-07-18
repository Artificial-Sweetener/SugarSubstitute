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

"""Contract tests for the shared QPane catalog adapter."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_pane_catalog_port import (
    CanvasCatalogMutation,
)
from substitute.presentation.canvas.qpane import CanvasPaneCatalog


class _PaneDouble:
    """Record public QPane catalog calls made by the adapter."""

    def __init__(self) -> None:
        """Initialize catalog and call recording state."""

        self.images: dict[UUID, tuple[object, Path | None]] = {}
        self.add_calls: list[tuple[UUID, object, Path | None]] = []
        self.remove_calls: list[UUID] = []
        self.display_calls: list[str] = []

    def addImage(self, image_id: UUID, image: object, path: Path | None) -> None:  # noqa: N802
        """Record catalog additions and replacements."""

        self.add_calls.append((image_id, image, path))
        self.images[image_id] = (image, path)

    def removeImageByID(self, image_id: UUID) -> None:  # noqa: N802
        """Record catalog removals."""

        self.remove_calls.append(image_id)
        self.images.pop(image_id, None)

    def imageIDs(self) -> list[UUID]:  # noqa: N802
        """Return current catalog image ids."""

        return list(self.images)

    def getCatalogSnapshot(self) -> object:  # noqa: N802
        """Return a QPane-like catalog snapshot."""

        return SimpleNamespace(
            catalog={
                image_id: SimpleNamespace(image=image, path=path)
                for image_id, (image, path) in self.images.items()
            },
        )

    def setCurrentImageID(self, image_id: UUID | None) -> None:  # noqa: N802
        """Fail if catalog code selects an image route."""

        self.display_calls.append(f"current:{image_id}")
        raise AssertionError("catalog adapter must not select image routes")

    def composeScene(self, request: object, *, activate: bool) -> UUID:  # noqa: N802
        """Fail if catalog code composes visible routes."""

        self.display_calls.append(f"compose:{request}:{activate}")
        raise AssertionError("catalog adapter must not compose routes")

    def openComposition(self, composition_id: UUID) -> None:  # noqa: N802
        """Fail if catalog code opens compositions."""

        self.display_calls.append(f"open:{composition_id}")
        raise AssertionError("catalog adapter must not open compositions")

    def setComparisonImageID(self, image_id: UUID) -> None:  # noqa: N802
        """Fail if catalog code changes compare routes."""

        self.display_calls.append(f"compare:{image_id}")
        raise AssertionError("catalog adapter must not compare images")


def test_catalog_adds_missing_payload_once() -> None:
    """A missing UUID should be added through QPane's catalog API once."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    image = object()

    mutation = catalog.ensure_image_cached(image_id, image, Path("image.png"))

    assert mutation is CanvasCatalogMutation.ADDED
    assert pane.add_calls == [(image_id, image, Path("image.png"))]
    assert pane.display_calls == []


def test_catalog_repeated_same_payload_is_idempotent() -> None:
    """Repeated binds of the same payload should not call QPane again."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    image = object()

    first = catalog.ensure_image_cached(image_id, image, None)
    second = catalog.ensure_image_cached(image_id, image, None)

    assert first is CanvasCatalogMutation.ADDED
    assert second is CanvasCatalogMutation.UNCHANGED
    assert pane.add_calls == [(image_id, image, None)]


def test_catalog_replaces_when_payload_identity_changes() -> None:
    """A changed payload object for the same UUID should replace the catalog entry."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    first_image = object()
    second_image = object()

    first = catalog.ensure_image_cached(image_id, first_image, None)
    second = catalog.ensure_image_cached(image_id, second_image, None)

    assert first is CanvasCatalogMutation.ADDED
    assert second is CanvasCatalogMutation.REPLACED
    assert pane.add_calls == [
        (image_id, first_image, None),
        (image_id, second_image, None),
    ]


def test_catalog_replaces_when_path_identity_changes() -> None:
    """A changed catalog path should replace the catalog entry for the same image."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    image = object()

    first = catalog.ensure_image_cached(image_id, image, Path("a.png"))
    second = catalog.ensure_image_cached(image_id, image, Path("b.png"))

    assert first is CanvasCatalogMutation.ADDED
    assert second is CanvasCatalogMutation.REPLACED
    assert pane.add_calls == [
        (image_id, image, Path("a.png")),
        (image_id, image, Path("b.png")),
    ]


def test_catalog_exposes_exact_loaded_path_for_snapshot_capture() -> None:
    """Input snapshot capture should read paths from the live catalog owner."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    image_path = Path("project/input_surfaces/regional.png")

    catalog.ensure_image_cached(image_id, object(), image_path)

    assert catalog.image_path(image_id) == image_path
    assert catalog.image_path(uuid4()) is None


def test_catalog_contains_uses_public_image_ids() -> None:
    """Availability queries should report only QPane catalog membership."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    pane.images[image_id] = (object(), None)

    assert catalog.contains(image_id) is True
    assert catalog.contains(uuid4()) is False


def test_catalog_snapshot_payload_is_route_preparation_only() -> None:
    """Route preparation can hydrate a missing payload from a catalog snapshot."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    image = object()
    pane.images[image_id] = (image, Path("warm.png"))

    assert catalog.payload_for_route_preparation(image_id) is image
    assert catalog.payload_for_route_preparation(uuid4()) is None
    assert catalog.snapshot_for_cache_diagnostics() is not None


def test_catalog_removal_prunes_identity_for_unreferenced_payloads() -> None:
    """Removing an unreferenced payload should clear its idempotency identity."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    image_id = uuid4()
    image = object()

    catalog.ensure_image_cached(image_id, image, None)
    removed = catalog.remove_unreferenced_image(image_id)
    mutation = catalog.ensure_image_cached(image_id, image, None)

    assert removed is True
    assert mutation is CanvasCatalogMutation.ADDED
    assert pane.remove_calls == [image_id]
    assert pane.add_calls == [
        (image_id, image, None),
        (image_id, image, None),
    ]
