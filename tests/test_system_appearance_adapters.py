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

"""Tests for isolated platform system-appearance adapters."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from substitute.domain.appearance import (
    RgbColor,
    SystemColorScheme,
)
from substitute.infrastructure.appearance.linux_system_appearance import (
    LinuxSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.macos_system_appearance import (
    MacOsSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
    QtSystemAppearanceReader,
    _infer_palette_color_scheme,
)
from substitute.infrastructure.appearance.system_appearance_factory import (
    build_system_appearance_provider,
)
from substitute.infrastructure.appearance.window_material_probe import (
    probe_window_material_capabilities,
)
from substitute.infrastructure.appearance.windows_system_appearance import (
    WindowsSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.xdg_settings_portal import (
    XdgSettingsPortalClient,
    read_portal_accent_color,
    read_portal_color_scheme,
)


def test_qt_provider_normalizes_style_hint_and_palette_sources() -> None:
    """Expose normalized Qt values without leaking toolkit types."""

    provider = QtSystemAppearanceProvider(
        reader=_StubQtReader(SystemColorScheme.DARK, RgbColor(10, 20, 30))
    )

    probe = provider.probe()

    assert probe.snapshot.color_scheme is SystemColorScheme.DARK
    assert probe.snapshot.accent_color == RgbColor(10, 20, 30)
    assert probe.color_scheme_source == "qt_style_hints"
    assert probe.accent_color_source == "qt_palette"


@pytest.mark.parametrize(
    ("window_color", "expected"),
    [("#202020", SystemColorScheme.DARK), ("#F8F8F8", SystemColorScheme.LIGHT)],
)
def test_qt_palette_scheme_fallback(
    window_color: str,
    expected: SystemColorScheme,
) -> None:
    """Infer a stable scheme when a platform plugin lacks explicit style hints."""

    assert _infer_palette_color_scheme(QColor(window_color)) is expected


def test_windows_provider_prefers_native_fields_and_fills_missing_accent() -> None:
    """Keep Windows native and Qt fallback responsibilities field-specific."""

    qt_provider = QtSystemAppearanceProvider(
        reader=_StubQtReader(SystemColorScheme.LIGHT, RgbColor(1, 2, 3))
    )
    provider = WindowsSystemAppearanceProvider(
        scheme_reader=lambda: SystemColorScheme.DARK,
        accent_reader=lambda: None,
        qt_provider=qt_provider,
    )

    probe = provider.probe()

    assert probe.snapshot.color_scheme is SystemColorScheme.DARK
    assert probe.snapshot.accent_color == RgbColor(1, 2, 3)
    assert probe.color_scheme_source == "windows_registry"
    assert probe.accent_color_source == "qt_palette"


def test_linux_provider_prefers_portal_fields_and_fills_missing_scheme() -> None:
    """Prefer XDG accent while retaining Qt as a per-field fallback."""

    portal = _StubPortalClient(
        {
            ("org.freedesktop.appearance", "color-scheme"): 0,
            ("org.freedesktop.appearance", "accent-color"): (1.0, 0.5, 0.0),
        }
    )
    qt_provider = QtSystemAppearanceProvider(
        reader=_StubQtReader(SystemColorScheme.LIGHT, RgbColor(9, 9, 9))
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

    client = _StubPortalClient(
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

    client = _StubPortalClient(
        {("org.freedesktop.appearance", "accent-color"): raw_value}
    )

    assert read_portal_accent_color(client) is None


def test_macos_provider_preserves_qt_values_and_relabels_adapter() -> None:
    """Report Qt Cocoa values through the isolated macOS adapter."""

    qt_provider = QtSystemAppearanceProvider(
        reader=_StubQtReader(SystemColorScheme.DARK, RgbColor(4, 5, 6))
    )

    probe = MacOsSystemAppearanceProvider(qt_provider).probe()

    assert probe.adapter_name == "macos"
    assert probe.snapshot.accent_color == RgbColor(4, 5, 6)


def test_factory_selects_one_adapter_per_platform() -> None:
    """Keep platform branching at the infrastructure composition boundary."""

    assert type(build_system_appearance_provider("win32")).__name__ == (
        "WindowsSystemAppearanceProvider"
    )
    assert type(build_system_appearance_provider("darwin")).__name__ == (
        "MacOsSystemAppearanceProvider"
    )
    assert type(build_system_appearance_provider("linux")).__name__ == (
        "LinuxSystemAppearanceProvider"
    )


def test_window_material_probe_is_independent_and_windows_only() -> None:
    """Gate native shell effects without changing system color support."""

    linux = probe_window_material_capabilities("linux", "6.8")
    windows_10 = probe_window_material_capabilities("win32", "10.0.19045")
    windows_11 = probe_window_material_capabilities("win32", "10.0.26100")

    assert linux.backdrop_available is False
    assert windows_10.acrylic_available is True
    assert windows_10.mica_alt_available is False
    assert windows_11.mica_alt_available is True


class _StubQtReader(QtSystemAppearanceReader):
    """Return deterministic normalized Qt appearance values."""

    def __init__(
        self,
        color_scheme: SystemColorScheme | None,
        accent_color: RgbColor | None,
    ) -> None:
        """Store values returned by reader methods."""

        self._color_scheme = color_scheme
        self._accent_color = accent_color

    def read_color_scheme(self) -> tuple[SystemColorScheme | None, str | None]:
        """Return the configured color scheme and deterministic source."""

        return self._color_scheme, (
            "qt_style_hints" if self._color_scheme is not None else None
        )

    def read_accent_color(self) -> RgbColor | None:
        """Return the configured accent color."""

        return self._accent_color


class _StubPortalClient(XdgSettingsPortalClient):
    """Return deterministic portal payloads without a D-Bus session."""

    def __init__(self, values: dict[tuple[str, str], object]) -> None:
        """Store values keyed by portal namespace and setting."""

        super().__init__()
        self._values = values

    def read_one(self, namespace: str, key: str) -> object | None:
        """Return the configured portal value."""

        return self._values.get((namespace, key))
