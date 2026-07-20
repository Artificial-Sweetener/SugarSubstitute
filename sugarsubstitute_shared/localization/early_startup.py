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

"""Resolve the effective locale before heavyweight application bootstrap."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sugarsubstitute_shared.localization.cli import parse_locale_override
from sugarsubstitute_shared.localization.file_store import LocalizationPreferenceStore
from sugarsubstitute_shared.localization.models import ResolvedLocale
from sugarsubstitute_shared.localization.resolution import resolve_locale


def resolve_early_startup_locale(
    argv: Sequence[str],
    *,
    app_root: Path,
    ui_languages: Sequence[str],
) -> ResolvedLocale:
    """Resolve persisted, machine, and handoff language before splash creation."""

    install_root = _extract_install_root(argv) or _infer_install_root(app_root)
    preference = LocalizationPreferenceStore.for_install_root(install_root).load()
    return resolve_locale(
        preference,
        ui_languages=ui_languages,
        process_override=_extract_locale_override(argv),
    )


def _extract_locale_override(argv: Sequence[str]) -> str | None:
    """Read the process-only locale argument without importing app CLI modules."""

    prefix = "--locale="
    for argument in argv:
        if argument.startswith(prefix):
            return parse_locale_override(argument[len(prefix) :].strip())
    return None


def _extract_install_root(argv: Sequence[str]) -> Path | None:
    """Read the install root needed to locate durable user settings."""

    prefix = "--install-root="
    for argument in argv:
        if argument.startswith(prefix):
            value = argument[len(prefix) :].strip()
            if value:
                return Path(value)
    return None


def _infer_install_root(app_root: Path) -> Path:
    """Distinguish a source root from an installed `<root>/app` payload."""

    parent = app_root.parent
    if app_root.name.casefold() == "app" and (
        (parent / "launcher").exists() or (parent / "user").exists()
    ):
        return parent
    return app_root


__all__ = ["resolve_early_startup_locale"]
