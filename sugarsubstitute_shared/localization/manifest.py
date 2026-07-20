#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Load and strictly validate the packaged runtime language registry."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import cast

from sugarsubstitute_shared.localization.models import (
    FluentCatalogSource,
    LanguageDefinition,
    LanguageManifest,
    TextDirection,
)

_MANIFEST_SCHEMA_VERSION = 1
_RESOURCE_PACKAGE = "sugarsubstitute_shared.localization.resources"


@cache
def load_language_manifest() -> LanguageManifest:
    """Load the immutable packaged manifest once for the process lifetime."""

    try:
        manifest_text = (
            files(_RESOURCE_PACKAGE)
            .joinpath("languages.json")
            .read_text(encoding="utf-8")
        )
    except (AttributeError, ModuleNotFoundError):
        manifest_text = (
            Path(__file__).resolve().parent / "resources" / "languages.json"
        ).read_text(encoding="utf-8")
    payload = cast(object, json.loads(manifest_text))
    root = _require_object(payload, "language manifest")
    if root.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported language manifest schema version.")
    default_identifier = _require_string(root, "default_language")
    language_values = _require_array(root, "languages")
    languages = tuple(
        _decode_language(value, index=index)
        for index, value in enumerate(language_values)
    )
    return LanguageManifest(
        languages,
        default_language_identifier=default_identifier,
    )


def _decode_language(value: object, *, index: int) -> LanguageDefinition:
    """Decode one language record while retaining its manifest index in failures."""

    payload = _require_object(value, f"languages[{index}]")
    text_direction = _require_string(payload, "text_direction")
    if text_direction not in ("left-to-right", "right-to-left"):
        raise ValueError(f"languages[{index}].text_direction is invalid.")
    fluent_catalog_source = _require_string(payload, "fluent_catalog_source")
    if fluent_catalog_source not in ("none", "shared", "upstream"):
        raise ValueError(f"languages[{index}].fluent_catalog_source is invalid.")
    accepted_system_tags = _require_string_array(payload, "accepted_system_tags")
    if not accepted_system_tags:
        raise ValueError(f"languages[{index}].accepted_system_tags must not be empty.")
    release_enabled = payload.get("release_enabled")
    if not isinstance(release_enabled, bool):
        raise ValueError(f"languages[{index}].release_enabled must be a boolean.")
    return LanguageDefinition(
        identifier=_require_string(payload, "id"),
        native_display_name=_require_string(payload, "native_display_name"),
        qt_locale_candidates=_require_nonempty_string_array(
            payload,
            "qt_locale_candidates",
            context=f"languages[{index}]",
        ),
        accepted_system_tags=accepted_system_tags,
        comfy_catalog_aliases=_require_nonempty_string_array(
            payload,
            "comfy_catalog_aliases",
            context=f"languages[{index}]",
        ),
        app_qm=_optional_string(payload, "app_qm"),
        launcher_qm=_optional_string(payload, "launcher_qm"),
        qtbase_qm=_optional_string(payload, "qtbase_qm"),
        fluent_qm=_optional_string(payload, "fluent_qm"),
        fluent_catalog_source=cast(FluentCatalogSource, fluent_catalog_source),
        text_direction=cast(TextDirection, text_direction),
        font_profile=_require_string(payload, "font_profile"),
        release_enabled=release_enabled,
    )


def _require_object(value: object, context: str) -> dict[str, object]:
    """Return a string-keyed JSON object or identify the invalid context."""

    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be a JSON object.")
    return cast(dict[str, object], value)


def _require_array(payload: dict[str, object], key: str) -> list[object]:
    """Return one JSON array without accepting strings or objects."""

    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a JSON array.")
    return cast(list[object], value)


def _require_string(payload: dict[str, object], key: str) -> str:
    """Return one nonempty JSON string field."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string.")
    return value


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    """Return one nullable catalog resource name."""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be null or a nonempty string.")
    return value


def _require_string_array(
    payload: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    """Return one JSON array whose values are all nonempty strings."""

    values = _require_array(payload, key)
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(f"{key} must contain only nonempty strings.")
    return tuple(cast(list[str], values))


def _require_nonempty_string_array(
    payload: dict[str, object],
    key: str,
    *,
    context: str,
) -> tuple[str, ...]:
    """Return a required string array used by runtime resource selection."""

    values = _require_string_array(payload, key)
    if not values:
        raise ValueError(f"{context}.{key} must not be empty.")
    return values


__all__ = ["load_language_manifest"]
