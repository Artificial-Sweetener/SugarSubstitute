#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Translate fixed splash IPC text before the parent QApplication exists."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTranslator

from sugarsubstitute_shared.localization import load_language_manifest


def translate_early_splash_text(
    *,
    app_root: Path,
    language_identifier: str,
    source_text: str,
) -> str:
    """Translate one fixed startup sentence directly from the app QM catalog."""

    language = load_language_manifest().language(language_identifier)
    if language.app_qm is None:
        return source_text
    catalog_path = (
        app_root
        / "substitute"
        / "presentation"
        / "resources"
        / "i18n"
        / language.app_qm
    )
    translator = QTranslator()
    if not catalog_path.is_file() or not translator.load(str(catalog_path)):
        raise RuntimeError(
            f"Early splash translation catalog could not be loaded: {catalog_path}"
        )
    return translator.translate("AppText", source_text) or source_text


__all__ = ["translate_early_splash_text"]
