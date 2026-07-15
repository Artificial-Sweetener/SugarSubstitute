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

"""Contract tests for the output canvas QPane catalog presenter boundary."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_pane_catalog_port import (
    CanvasCatalogMutation,
)
from substitute.presentation.canvas.qpane.output_qpane_presenter import (
    OutputCanvasQPanePresenter,
)
from substitute.presentation.canvas.qpane import CanvasPaneCatalog


class _CatalogDouble:
    """Record catalog adapter calls made by the presenter."""

    def __init__(self) -> None:
        """Initialize catalog call recording."""

        self.calls: list[tuple[str, object]] = []

    def ensure_image_cached(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> CanvasCatalogMutation:
        """Record image cache requests."""

        self.calls.append(("cache", (image_id, image, path)))
        return CanvasCatalogMutation.ADDED

    def contains(self, image_id: UUID) -> bool:
        """Return whether image_id is considered cached by the double."""

        return False

    def remove_unreferenced_image(self, image_id: UUID) -> bool:
        """Record removal requests."""

        self.calls.append(("remove", image_id))
        return True

    def payload_for_route_preparation(self, image_id: UUID) -> object | None:
        """Return no route-preparation payloads."""

        return None

    def snapshot_for_cache_diagnostics(self) -> object | None:
        """Return no diagnostics snapshot."""

        return None


class _PaneDouble:
    """Record QPane public catalog API calls made by the adapter."""

    def __init__(self) -> None:
        """Initialize catalog state."""

        self.images: dict[UUID, tuple[object, Path | None]] = {}
        self.add_calls: list[tuple[UUID, object, Path | None]] = []

    def addImage(self, image_id: UUID, image: object, path: Path | None) -> None:  # noqa: N802
        """Record catalog additions and replacements."""

        self.add_calls.append((image_id, image, path))
        self.images[image_id] = (image, path)

    def removeImageByID(self, image_id: UUID) -> None:  # noqa: N802
        """Remove one catalog entry."""

        self.images.pop(image_id, None)

    def imageIDs(self) -> list[UUID]:  # noqa: N802
        """Return catalog image IDs."""

        return list(self.images)


def test_presenter_routes_only_catalog_mutations() -> None:
    """Presenter should delegate cache and removal operations to the catalog."""

    catalog = _CatalogDouble()
    presenter = OutputCanvasQPanePresenter(catalog=catalog)
    image_id = uuid4()
    image = object()
    path = Path("output.png")

    presenter.register_image(image_id, image, path)
    presenter.remove_image(image_id)

    assert catalog.calls == [
        ("cache", (image_id, image, path)),
        ("remove", image_id),
    ]


def test_shared_catalog_identity_prevents_duplicate_presenter_and_service_binds() -> (
    None
):
    """One shared catalog adapter should suppress duplicate cross-owner binds."""

    pane = _PaneDouble()
    catalog = CanvasPaneCatalog(pane)
    presenter = OutputCanvasQPanePresenter(catalog=catalog)
    image_id = uuid4()
    image = object()
    path = Path("output.png")

    presenter.register_image(image_id, image, path)
    mutation = catalog.ensure_image_cached(image_id, image, path)

    assert mutation is CanvasCatalogMutation.UNCHANGED
    assert pane.add_calls == [(image_id, image, path)]
