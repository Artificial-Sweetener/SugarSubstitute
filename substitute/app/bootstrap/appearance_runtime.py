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

"""Own runtime appearance probing and application at GUI lifecycle boundaries."""

from __future__ import annotations

from substitute.application.appearance import (
    AppearanceCapabilities,
    AppearanceResolver,
    ResolvedAppearance,
)
from substitute.application.appearance.appearance_preference_service import (
    AppearancePreferenceService,
)
from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
    SystemAppearanceProvider,
)
from substitute.app.bootstrap.theme import configure_accent_color, configure_theme
from substitute.domain.appearance import (
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("app.bootstrap.appearance_runtime")


class AppearanceRuntimeController:
    """Coordinate persisted preferences with one active system appearance probe."""

    def __init__(
        self,
        *,
        preference_service: AppearancePreferenceService,
        system_appearance_provider: SystemAppearanceProvider,
        resolver: AppearanceResolver | None = None,
    ) -> None:
        """Store appearance collaborators used for runtime application."""

        self._preference_service = preference_service
        self._system_appearance_provider = system_appearance_provider
        self._resolver = resolver if resolver is not None else AppearanceResolver()
        self._active_system_probe: SystemAppearanceProbe | None = None
        self._last_resolved: ResolvedAppearance | None = None

    def load_preferences(self) -> AppearancePreferences:
        """Load the current persisted appearance preferences."""

        return self._preference_service.load_preferences()

    def last_resolved(self) -> ResolvedAppearance | None:
        """Return the last appearance snapshot applied to QFluent."""

        return self._last_resolved

    def active_system_probe(self) -> SystemAppearanceProbe | None:
        """Return diagnostics for the active GUI appearance probe."""

        return self._active_system_probe

    def capabilities(self) -> AppearanceCapabilities:
        """Return capabilities resolved from the active system snapshot."""

        return self._resolver.capabilities(self._ensure_system_probe().snapshot)

    def resolve_preferences(
        self,
        preferences: AppearancePreferences | None = None,
    ) -> ResolvedAppearance:
        """Resolve preferences against the active GUI appearance snapshot."""

        current = preferences if preferences is not None else self.load_preferences()
        return self._resolver.resolve(
            current,
            system_appearance=self._ensure_system_probe().snapshot,
        )

    def apply_persisted_preferences(self) -> ResolvedAppearance:
        """Re-probe the host and apply persisted preferences for a new GUI shell."""

        return self.apply_preferences(self.load_preferences())

    def apply_preferences(
        self,
        preferences: AppearancePreferences,
    ) -> ResolvedAppearance:
        """Apply preferences after refreshing the one active system snapshot."""

        self._refresh_system_probe()
        resolved = self.resolve_preferences(preferences)
        configure_theme(
            theme_mode=resolved.effective_theme_mode,
            accent_color=resolved.effective_accent_color,
        )
        _configure_semantic_color_overrides(resolved.requested)
        self._last_resolved = resolved
        return resolved

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> ResolvedAppearance:
        """Persist one theme-mode update without mutating the running shell."""

        preferences = self._preference_service.set_theme_mode(theme_mode)
        return self.resolve_preferences(preferences)

    def set_accent_source(
        self,
        accent_source: AppearanceAccentSource,
    ) -> ResolvedAppearance:
        """Persist and apply one accent-source update."""

        preferences = self._preference_service.set_accent_source(accent_source)
        return self.apply_accent_preferences(preferences)

    def set_custom_accent_color(self, color: str) -> ResolvedAppearance:
        """Persist and apply one custom accent color update."""

        preferences = self._preference_service.set_custom_accent_color(color)
        return self.apply_accent_preferences(preferences)

    def set_custom_warning_color(self, color: str | None) -> ResolvedAppearance:
        """Persist and apply one warning color override update."""

        preferences = self._preference_service.set_custom_warning_color(color)
        return self.apply_semantic_color_preferences(preferences)

    def set_warning_color_mode(
        self,
        mode: AppearanceWarningColorMode,
    ) -> ResolvedAppearance:
        """Persist and apply one warning color mode update."""

        preferences = self._preference_service.set_warning_color_mode(mode)
        return self.apply_semantic_color_preferences(preferences)

    def set_custom_error_color(self, color: str | None) -> ResolvedAppearance:
        """Persist and apply one error color override update."""

        preferences = self._preference_service.set_custom_error_color(color)
        return self.apply_semantic_color_preferences(preferences)

    def set_error_color_mode(
        self,
        mode: AppearanceErrorColorMode,
    ) -> ResolvedAppearance:
        """Persist and apply one error color mode update."""

        preferences = self._preference_service.set_error_color_mode(mode)
        return self.apply_semantic_color_preferences(preferences)

    def apply_accent_preferences(
        self,
        preferences: AppearancePreferences,
    ) -> ResolvedAppearance:
        """Apply accent changes using the active GUI appearance snapshot."""

        resolved = self.resolve_preferences(preferences)
        configure_accent_color(accent_color=resolved.effective_accent_color)
        _configure_semantic_color_overrides(resolved.requested)
        self._last_resolved = resolved
        return resolved

    def apply_semantic_color_preferences(
        self,
        preferences: AppearancePreferences,
    ) -> ResolvedAppearance:
        """Apply semantic colors using the active GUI appearance snapshot."""

        resolved = self.resolve_preferences(preferences)
        _configure_semantic_color_overrides(resolved.requested)
        self._last_resolved = resolved
        return resolved

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> ResolvedAppearance:
        """Persist one backdrop update without mutating the running shell."""

        preferences = self._preference_service.set_backdrop_mode(backdrop_mode)
        return self.resolve_preferences(preferences)

    def _ensure_system_probe(self) -> SystemAppearanceProbe:
        """Return the active probe, creating it once when not yet applied."""

        if self._active_system_probe is None:
            self._refresh_system_probe()
        assert self._active_system_probe is not None
        return self._active_system_probe

    def _refresh_system_probe(self) -> None:
        """Replace the active probe at a GUI construction or reload boundary."""

        probe = self._system_appearance_provider.probe()
        self._active_system_probe = probe
        log_info(
            _LOGGER,
            "Probed system appearance",
            adapter=probe.adapter_name,
            color_scheme_source=probe.color_scheme_source,
            accent_color_source=probe.accent_color_source,
            color_scheme=(
                probe.snapshot.color_scheme.value
                if probe.snapshot.color_scheme is not None
                else "unavailable"
            ),
            accent_color=(
                probe.snapshot.accent_color.to_hex()
                if probe.snapshot.accent_color is not None
                else "unavailable"
            ),
        )


def _configure_semantic_color_overrides(preferences: AppearancePreferences) -> None:
    """Publish semantic color overrides to presentation color helpers."""

    from substitute.presentation.semantic_colors import (
        configure_semantic_color_overrides,
    )

    configure_semantic_color_overrides(
        warning_color_mode=preferences.warning_color_mode,
        error_color_mode=preferences.error_color_mode,
        custom_warning_color=preferences.custom_warning_color,
        custom_error_color=preferences.custom_error_color,
    )


__all__ = ["AppearanceRuntimeController"]
