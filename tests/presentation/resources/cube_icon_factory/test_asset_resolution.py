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

"""Contract tests for Cube Library presentation icon resolution."""

from __future__ import annotations


from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from substitute.domain.cube_library import CubeIconDescriptor
from substitute.application.ports import (
    CubeIconAsset,
)
from substitute.presentation.resources.cube_icon_factory import (
    CubeIconFactory,
)


from tests.presentation.resources.cube_icon_factory.support import (
    _PNG_BYTES,
    _FakeAssetFetcher,
    _ensure_qapp,
)


def test_asset_icon_response_with_valid_png_returns_asset_icon() -> None:
    """Valid target-relative PNG descriptors should load the fetched asset icon."""

    _ensure_qapp()
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        display_name="Text to Image",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=Text%20to%20Image",
            media_type="image/png",
        ),
    )

    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    assert icon.actualSize(QSize(48, 48)) == QSize(48, 48)
    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=Text%20to%20Image"]


def test_asset_icon_fetch_failure_returns_fallback_icon() -> None:
    """Icon fetch failures should fail closed to the generated fallback."""

    _ensure_qapp()

    fetcher = _FakeAssetFetcher(asset=None, calls=[])
    factory = CubeIconFactory(asset_fetcher=fetcher)

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Image to Image.cube",
        display_name="Image to Image",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=Image%20to%20Image",
            media_type="image/png",
        ),
    )

    assert not icon.isNull()
    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=Image%20to%20Image"]


def test_unsupported_or_external_asset_icon_descriptor_returns_fallback() -> None:
    """Only target-relative PNG/SVG asset descriptors should be fetched."""

    _ensure_qapp()
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)

    unsupported = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=Inpaint",
            media_type="image/gif",
        ),
    )
    external = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=CubeIconDescriptor(
            kind="asset",
            url="https://example.invalid/icon.png",
            media_type="image/png",
        ),
    )

    assert not unsupported.isNull()
    assert not external.isNull()
    assert fetcher.calls == []
