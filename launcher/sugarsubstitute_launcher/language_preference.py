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

"""Persist installer language selection into the prepared application root."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.localization import (
    LanguagePreference,
    LocalizationPreferenceStore,
)


def persist_launcher_language_preference(
    install_root: Path,
    preference: LanguagePreference,
) -> None:
    """Persist the selected language into the installation being prepared."""

    LocalizationPreferenceStore.for_install_root(install_root).save(preference)


__all__ = ["persist_launcher_language_preference"]
