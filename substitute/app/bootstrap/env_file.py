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

"""Load simple local environment files before application bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("app.bootstrap.env_file")
_EXPORT_PREFIX = "export "


@dataclass(frozen=True)
class EnvFileLoadResult:
    """Summarize one environment-file load attempt."""

    path: Path
    loaded: int
    skipped_existing: int
    malformed: int
    missing: bool


def load_env_file(path: Path) -> EnvFileLoadResult:
    """Load simple KEY=value entries into os.environ without overriding values."""

    if not path.exists():
        return EnvFileLoadResult(
            path=path,
            loaded=0,
            skipped_existing=0,
            malformed=0,
            missing=True,
        )

    loaded = 0
    skipped_existing = 0
    malformed = 0
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        if isinstance(parsed, _MalformedLineType):
            malformed += 1
            log_warning(
                _LOGGER,
                "Ignoring malformed .env line",
                path=str(path),
                line_number=line_number,
            )
            continue
        key, value = parsed
        if key in os.environ:
            skipped_existing += 1
            continue
        os.environ[key] = value
        loaded += 1

    return EnvFileLoadResult(
        path=path,
        loaded=loaded,
        skipped_existing=skipped_existing,
        malformed=malformed,
        missing=False,
    )


class _MalformedLineType:
    """Sentinel for non-empty .env lines that cannot be parsed."""


_MalformedLine = _MalformedLineType()


def _parse_env_line(raw_line: str) -> tuple[str, str] | _MalformedLineType | None:
    """Parse one simple .env line into a key/value pair."""

    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith(_EXPORT_PREFIX):
        line = line[len(_EXPORT_PREFIX) :].strip()
    if "=" not in line:
        return _MalformedLine

    key, value = line.split("=", 1)
    key = key.strip()
    if not key or any(character.isspace() for character in key):
        return _MalformedLine

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    elif (
        value.startswith("'")
        or value.startswith('"')
        or value.endswith("'")
        or value.endswith('"')
    ):
        return _MalformedLine

    return key, value


__all__ = ["EnvFileLoadResult", "load_env_file"]
