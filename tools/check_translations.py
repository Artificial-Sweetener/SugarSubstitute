"""Validate release Qt catalogs against extracted application messages."""

from __future__ import annotations

import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.localization_catalog import extract_application_messages, placeholders

_APP_CONTEXT = "AppText"
_IDENTITY_ALLOWED = frozenset(
    {
        "ComfyUI",
        "PySide6",
        "PySide6-Fluent-Widgets",
        "QPane",
        "Qt for Python",
        "Python: %1",
        "Sugar-DSL",
        "Sugar Substitute",
        "SugarCubes",
        "SugarSubstitute",
        "TAESD",
        "https://github.com/owner/repository",
    }
)
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def main() -> int:
    """Report missing, unfinished, extra, and placeholder-invalid translations."""

    project_root = Path(__file__).resolve().parents[1]
    expected = {
        message.source for message in extract_application_messages(project_root)
    }
    failures: list[str] = []
    for filename in ("app_zh_CN.ts", "app_ja_JP.ts"):
        path = project_root / "translations" / filename
        catalog = _app_text_messages(path)
        missing = sorted(expected - catalog.keys())
        extra = sorted(catalog.keys() - expected)
        failures.extend(f"{filename}: missing: {source}" for source in missing)
        failures.extend(f"{filename}: stale: {source}" for source in extra)
        for source, (translation, unfinished) in sorted(catalog.items()):
            if unfinished or not translation.strip():
                failures.append(f"{filename}: unfinished: {source}")
            elif sorted(placeholders(source)) != sorted(placeholders(translation)):
                failures.append(f"{filename}: placeholder mismatch: {source}")
            elif (
                source == translation
                and _LATIN_LETTER.search(source)
                and source not in _IDENTITY_ALLOWED
            ):
                failures.append(f"{filename}: untranslated: {source}")
    failures.extend(_validate_parallel_catalogs(project_root, "launcher"))
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Validated {len(expected)} AppText messages in Chinese and Japanese.")
    return 0


def _validate_parallel_catalogs(project_root: Path, prefix: str) -> list[str]:
    """Validate non-app catalog parity, completion, and placeholders."""

    paths = (
        project_root / "translations" / f"{prefix}_zh_CN.ts",
        project_root / "translations" / f"{prefix}_ja_JP.ts",
    )
    catalogs = [_all_messages(path) for path in paths]
    failures: list[str] = []
    if catalogs[0].keys() != catalogs[1].keys():
        failures.append(f"{prefix}: Chinese and Japanese source sets differ")
    for path, catalog in zip(paths, catalogs, strict=True):
        for (context, source), (translation, unfinished) in sorted(catalog.items()):
            label = f"{path.name}:{context}:{source}"
            if unfinished or not translation.strip():
                failures.append(f"{label}: unfinished")
            elif sorted(placeholders(source)) != sorted(placeholders(translation)):
                failures.append(f"{label}: placeholder mismatch")
    return failures


def _app_text_messages(path: Path) -> dict[str, tuple[str, bool]]:
    """Read source, translation, and completion state for AppText."""

    root = ET.parse(path).getroot()
    for context in root.findall("context"):
        if context.findtext("name") != _APP_CONTEXT:
            continue
        result: dict[str, tuple[str, bool]] = {}
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            if translation is None:
                result[source] = ("", True)
            else:
                result[source] = (
                    translation.text or "",
                    translation.get("type") == "unfinished",
                )
        return result
    return {}


def _all_messages(path: Path) -> dict[tuple[str, str], tuple[str, bool]]:
    """Read all contexts from one Qt TS file for cross-language parity."""

    root = ET.parse(path).getroot()
    result: dict[tuple[str, str], tuple[str, bool]] = {}
    for context in root.findall("context"):
        context_name = context.findtext("name") or ""
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            result[(context_name, source)] = (
                "" if translation is None else translation.text or "",
                translation is None or translation.get("type") == "unfinished",
            )
    return result


if __name__ == "__main__":
    sys.exit(main())
