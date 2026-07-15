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

"""Verify Output route request presentation before QPane application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from substitute.presentation.canvas.output.output_canvas_route_presenter import (
    OutputCanvasRoutePresenter,
)


def test_route_presenter_accepts_already_cached_scene_layers() -> None:
    """Scene requests should pass when every layer is already cached."""

    image_id = uuid4()
    catalog = _Catalog(cached={image_id})
    registrar = _Registrar()
    presenter = _presenter(catalog=catalog, registrar=registrar)
    request = SimpleNamespace(layers=(SimpleNamespace(image_id=image_id),))

    assert presenter.ensure_scene_request_images_cached(request) is True
    assert registrar.registered == ()


def test_route_presenter_registers_missing_scene_layer_payload() -> None:
    """Missing scene layer payloads should be registered before route application."""

    image_id = uuid4()
    image = object()
    path = Path("E:/outputs/image.png")
    catalog = _Catalog(cached=set())
    registrar = _Registrar()
    layer = SimpleNamespace(image_id=image_id)
    presenter = _presenter(
        catalog=catalog,
        registrar=registrar,
        payloads={id(layer): image},
        paths={id(layer): path},
    )
    request = SimpleNamespace(layers=(layer,))

    assert presenter.ensure_scene_request_images_cached(request) is True
    assert registrar.registered == ((image_id, image, path),)


def test_route_presenter_rejects_missing_scene_layer_payload() -> None:
    """Route application should stop when a layer payload cannot be resolved."""

    image_id = uuid4()
    catalog = _Catalog(cached=set())
    registrar = _Registrar()
    layer = SimpleNamespace(
        image_id=image_id,
        role="scene-output",
        metadata={"grid_kind": "scene", "scene_key": "scene-a"},
    )
    presenter = _presenter(catalog=catalog, registrar=registrar)
    request = SimpleNamespace(layers=(layer,))

    assert presenter.ensure_scene_request_images_cached(request) is False
    assert registrar.registered == ()


def test_route_presenter_rejects_invalid_layer_collection() -> None:
    """Scene requests must expose an iterable layer collection."""

    presenter = _presenter(catalog=_Catalog(cached=set()), registrar=_Registrar())
    request = SimpleNamespace(layers=object())

    assert presenter.ensure_scene_request_images_cached(request) is False


@dataclass(slots=True)
class _Catalog:
    """Record image cache availability for presenter tests."""

    cached: set[UUID]

    def contains(self, image_id: UUID) -> bool:
        """Return whether ``image_id`` is already cached."""

        return image_id in self.cached


@dataclass(slots=True)
class _Registrar:
    """Record image registration calls made by the route presenter."""

    registered: tuple[tuple[UUID, object, Path | None], ...] = ()

    def register_image(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Record one catalog registration."""

        self.registered = (*self.registered, (image_id, image, path))


def _presenter(
    *,
    catalog: _Catalog,
    registrar: _Registrar,
    payloads: dict[int, object] | None = None,
    paths: dict[int, Path | None] | None = None,
) -> OutputCanvasRoutePresenter:
    """Return a route presenter with deterministic lookup dictionaries."""

    payload_lookup = payloads or {}
    path_lookup = paths or {}
    return OutputCanvasRoutePresenter(
        catalog=lambda: catalog,
        image_registrar=lambda: registrar,
        layer_payload=lambda layer: payload_lookup.get(id(layer)),
        layer_path=lambda layer: path_lookup.get(id(layer)),
    )
