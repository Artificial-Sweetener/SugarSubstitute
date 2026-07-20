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

"""Synchronize Qt TS sources and compile active application catalogs."""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.localization_catalog import (
    ExtractedMessage,
    extract_application_messages,
    pseudo_localize,
)

_APP_CONTEXT = "AppText"
_CATALOGS = ("app_zh_CN.ts", "app_ja_JP.ts")


def main(argv: list[str] | None = None) -> int:
    """Update release and pseudo TS files, then optionally compile QMs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    messages = extract_application_messages(project_root)
    translations_root = project_root / "translations"
    for filename in _CATALOGS:
        _synchronize_catalog(translations_root / filename, messages)
    pseudo_path = translations_root / "app_qps_ploc.ts"
    _write_pseudo_catalog(pseudo_path, messages)
    if args.compile:
        _compile_catalogs(project_root)
    return 0


def _synchronize_catalog(
    path: Path,
    messages: tuple[ExtractedMessage, ...],
) -> None:
    """Merge extracted AppText messages without disturbing explicit contexts."""

    tree = ET.parse(path)
    root = tree.getroot()
    context = _find_or_create_context(root, _APP_CONTEXT)
    existing = {
        source.text or "": message
        for message in context.findall("message")
        if (source := message.find("source")) is not None
    }
    expected_sources = {message.source for message in messages}
    for source, element in tuple(existing.items()):
        if source not in expected_sources:
            context.remove(element)
    for message in messages:
        element = existing.get(message.source)
        if element is None:
            element = ET.SubElement(context, "message")
            ET.SubElement(element, "source").text = message.source
            translation = ET.SubElement(element, "translation")
            translation.set("type", "unfinished")
        location = element.find("location")
        if location is None:
            location = ET.Element("location")
            element.insert(0, location)
        location.set("filename", f"../{message.filename}")
        location.set("line", str(message.line))
    _sort_messages(context)
    _write_ts(path, root)


def _write_pseudo_catalog(
    path: Path,
    messages: tuple[ExtractedMessage, ...],
) -> None:
    """Generate a deterministic expanded pseudo-locale for layout testing."""

    root = ET.Element(
        "TS",
        {"version": "2.1", "language": "qps_ploc", "sourcelanguage": "en_US"},
    )
    context = _find_or_create_context(root, _APP_CONTEXT)
    for extracted in messages:
        message = ET.SubElement(context, "message")
        ET.SubElement(message, "source").text = extracted.source
        ET.SubElement(message, "translation").text = pseudo_localize(extracted.source)
    _write_ts(path, root)


def _find_or_create_context(root: ET.Element, name: str) -> ET.Element:
    """Return one named context, creating it when absent."""

    for context in root.findall("context"):
        if context.findtext("name") == name:
            return context
    context = ET.SubElement(root, "context")
    ET.SubElement(context, "name").text = name
    return context


def _sort_messages(context: ET.Element) -> None:
    """Sort generated messages by stable English source text."""

    messages = context.findall("message")
    for message in messages:
        context.remove(message)
    context.extend(sorted(messages, key=lambda item: item.findtext("source") or ""))


def _write_ts(path: Path, root: ET.Element) -> None:
    """Write deterministic UTF-8 Qt TS XML."""

    ET.indent(root, space="  ")
    payload = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n{payload}\n',
        encoding="utf-8",
        newline="\n",
    )


def _compile_catalogs(project_root: Path) -> None:
    """Compile release TS catalogs into their package-owned QM paths."""

    executable = project_root / ".venv" / "Scripts" / "pyside6-lrelease.exe"
    output_root = project_root / "substitute" / "presentation" / "resources" / "i18n"
    for source_name, output_name in (
        ("app_zh_CN.ts", "sugarsubstitute_zh_CN.qm"),
        ("app_ja_JP.ts", "sugarsubstitute_ja_JP.qm"),
    ):
        subprocess.run(
            [
                str(executable),
                str(project_root / "translations" / source_name),
                "-qm",
                str(output_root / output_name),
            ],
            check=True,
        )


if __name__ == "__main__":
    sys.exit(main())
