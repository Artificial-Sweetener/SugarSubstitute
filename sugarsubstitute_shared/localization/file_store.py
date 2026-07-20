#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Persist the shared localization preference through atomic replacement."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import cast

from sugarsubstitute_shared.localization.manifest import load_language_manifest
from sugarsubstitute_shared.localization.models import (
    LanguageManifest,
    LanguagePreference,
)

LOCALIZATION_PREFERENCE_SCHEMA_VERSION = 1
_LOGGER = logging.getLogger("sugarsubstitute.localization.preference_store")


class LocalizationPreferenceStore:
    """Own the one preference file shared by setup, launcher, splash, and app."""

    def __init__(
        self,
        path: Path,
        *,
        manifest: LanguageManifest | None = None,
    ) -> None:
        """Bind persistence to one authoritative installation settings path."""

        self._path = path
        self._manifest = manifest or load_language_manifest()

    @classmethod
    def for_install_root(
        cls,
        install_root: Path,
        *,
        manifest: LanguageManifest | None = None,
    ) -> LocalizationPreferenceStore:
        """Construct the store at the durable user settings location."""

        return cls(
            install_root / "user" / "settings" / "localization.json",
            manifest=manifest,
        )

    @property
    def path(self) -> Path:
        """Return the durable preference path for composition and diagnostics."""

        return self._path

    @property
    def temporary_path(self) -> Path:
        """Return the same-directory staging path used for atomic promotion."""

        return self._path.with_name(f"{self._path.name}.tmp")

    def load(self) -> LanguagePreference:
        """Load a strict preference or recover once to automatic selection."""

        if not self._path.is_file():
            return LanguagePreference.system()
        try:
            payload = cast(
                object,
                json.loads(self._path.read_text(encoding="utf-8")),
            )
            return self._decode(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            _LOGGER.warning(
                "Failed to load localization preference; using system selection. "
                "path=%s error=%r",
                self._path,
                error,
            )
            return LanguagePreference.system()

    def save(self, preference: LanguagePreference) -> None:
        """Flush and atomically promote one validated requested language."""

        self._validate_preference(preference)
        payload = {
            "schema_version": LOCALIZATION_PREFERENCE_SCHEMA_VERSION,
            "language": preference.storage_value,
        }
        serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.temporary_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as temporary_file:
                temporary_file.write(serialized)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(self.temporary_path, self._path)
        except OSError:
            self.temporary_path.unlink(missing_ok=True)
            raise

    def _decode(self, payload: object) -> LanguagePreference:
        """Decode schema-1 JSON without coercing malformed field types."""

        if not isinstance(payload, dict):
            raise ValueError("Localization preference root must be an object.")
        schema_version = payload.get("schema_version")
        if type(schema_version) is not int or (
            schema_version != LOCALIZATION_PREFERENCE_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported localization preference schema.")
        language_value = payload.get("language")
        if not isinstance(language_value, str):
            raise ValueError("Localization preference language must be a string.")
        if language_value == "system":
            return LanguagePreference.system()
        self._manifest.language(language_value)
        return LanguagePreference.explicit(language_value)

    def _validate_preference(self, preference: LanguagePreference) -> None:
        """Reject unsupported values before replacing a known-good preference."""

        if preference.is_system:
            return
        language = self._manifest.language(preference.language_identifier)
        if not language.release_enabled:
            raise ValueError(
                f"Language is not release-enabled: {preference.language_identifier!r}"
            )


__all__ = [
    "LOCALIZATION_PREFERENCE_SCHEMA_VERSION",
    "LocalizationPreferenceStore",
]
