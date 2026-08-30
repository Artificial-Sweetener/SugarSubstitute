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

"""Test Linux portal appearance validation and Qt fallback behavior."""

from __future__ import annotations

import pytest

from substitute.domain.appearance import RgbColor, SystemColorScheme
from substitute.infrastructure.appearance.linux_system_appearance import (
    LinuxSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.xdg_settings_portal import (
    read_portal_accent_color,
    read_portal_color_scheme,
)
from tests.infrastructure.appearance.support import (
    StubPortalClient,
    StubQtAppearanceReader,
)


def test_provider_prefers_portal_fields_and_fills_missing_scheme() -> None:
    """Prefer XDG accent while retaining Qt as a per-field fallback."""

    portal = StubPortalClient(
        {
            ("org.freedesktop.appearance", "color-scheme"): 0,
            ("org.freedesktop.appearance", "accent-color"): (1.0, 0.5, 0.0),
        }
    )
    qt_provider = QtSystemAppearanceProvider(
        reader=StubQtAppearanceReader(SystemColorScheme.LIGHT, RgbColor(9, 9, 9))
    )

    probe = LinuxSystemAppearanceProvider(
        portal_client=portal,
        qt_provider=qt_provider,
    ).probe()

    assert probe.snapshot.color_scheme is SystemColorScheme.LIGHT
    assert probe.snapshot.accent_color == RgbColor(255, 128, 0)
    assert probe.color_scheme_source == "qt_style_hints"
    assert probe.accent_color_source == "xdg_portal"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (1, SystemColorScheme.DARK),
        (2, SystemColorScheme.LIGHT),
        (0, None),
        (True, None),
        ("1", None),
    ],
)
def test_portal_color_scheme_validation(
    raw_value: object,
    expected: SystemColorScheme | None,
) -> None:
    """Accept only standardized integer XDG color-scheme values."""

    client = StubPortalClient(
        {("org.freedesktop.appearance", "color-scheme"): raw_value}
    )

    assert read_portal_color_scheme(client) is expected


@pytest.mark.parametrize(
    "raw_value",
    [
        (-0.1, 0.2, 0.3),
        (0.1, 0.2, 1.1),
        (0.1, float("nan"), 0.3),
        (0.1, True, 0.3),
        (0.1, 0.2),
        "0.1,0.2,0.3",
    ],
)
def test_portal_accent_rejects_malformed_values(raw_value: object) -> None:
    """Reject unsafe or non-standard XDG accent payloads."""

    client = StubPortalClient(
        {("org.freedesktop.appearance", "accent-color"): raw_value}
    )

    assert read_portal_accent_color(client) is None
