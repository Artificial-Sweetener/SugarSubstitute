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

"""Select and archive the application runtime source payload."""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from pathlib import Path

from tools.release_assets.zip_support import iter_directory_files, write_file_to_zip


APP_PAYLOAD_PREFIX = "SugarSubstitute-app-v"
RUNTIME_REQUIRED_ROOTS: tuple[str, ...] = (
    "main.py",
    "requirements.txt",
    "sitecustomize.py",
    "substitute",
    "sugarsubstitute_shared",
    "third_party",
)
EXCLUDED_ROOT_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".pytest-tmp",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "app",
        "app_next",
        "app_previous",
        "appdata",
        "artifacts",
        "build",
        "dist",
        "log",
        "logs",
        "runtime",
        "tests",
        "user",
    }
)
EXCLUDED_ANYWHERE_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
    }
)
EXCLUDED_SUFFIXES = (
    ".bak",
    ".ckpt",
    ".log",
    ".onnx",
    ".orig",
    ".pt",
    ".pyc",
    ".pyo",
    ".tmp",
)


def build_app_payload_zip(*, repo_root: Path, output_path: Path) -> Path:
    """Write the runtime source payload ZIP for one checkout."""

    resolved_repo_root = repo_root.resolve()
    resolved_output_path = output_path.resolve()
    validate_repo_root(resolved_repo_root)
    if resolved_output_path.is_relative_to(resolved_repo_root):
        ensure_output_not_inside_payload(
            repo_root=resolved_repo_root,
            output_path=resolved_output_path,
        )
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        resolved_output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source_path, archive_name in iter_payload_entries(resolved_repo_root):
            write_file_to_zip(
                archive=archive,
                source_path=source_path,
                archive_name=archive_name,
            )
    return resolved_output_path


def iter_payload_entries(repo_root: Path) -> Iterable[tuple[Path, str]]:
    """Yield deterministic source-file entries for the app payload ZIP."""

    for root_name in RUNTIME_REQUIRED_ROOTS:
        root_path = repo_root / root_name
        if root_path.is_file():
            yield root_path, root_name
            continue
        for file_path in iter_directory_files(root_path):
            relative_path = file_path.relative_to(repo_root)
            if not is_excluded(relative_path):
                yield file_path, relative_path.as_posix()


def inspect_payload_zip(zip_path: Path) -> list[str]:
    """Return sorted archive names from an app payload ZIP."""

    with zipfile.ZipFile(zip_path) as archive:
        return sorted(archive.namelist())


def validate_repo_root(repo_root: Path) -> None:
    """Require every source root owned by the runtime payload."""

    missing_roots = [
        root_name
        for root_name in RUNTIME_REQUIRED_ROOTS
        if not (repo_root / root_name).exists()
    ]
    if missing_roots:
        raise FileNotFoundError(
            f"Repository root is missing payload roots: {', '.join(missing_roots)}"
        )


def validate_output_dir(*, repo_root: Path, output_dir: Path) -> None:
    """Keep local release-channel output inside the current repository."""

    if not output_dir.is_relative_to(repo_root):
        raise ValueError(f"Release channel output must stay inside repo: {output_dir}")


def ensure_output_not_inside_payload(*, repo_root: Path, output_path: Path) -> None:
    """Reject output paths that payload discovery would consume as input."""

    for root_name in RUNTIME_REQUIRED_ROOTS:
        payload_root = (repo_root / root_name).resolve()
        if output_path == payload_root or output_path.is_relative_to(payload_root):
            raise ValueError(
                f"Payload ZIP output cannot live inside runtime payload: {output_path}"
            )


def is_excluded(relative_path: Path) -> bool:
    """Return whether one relative payload path is release-only noise."""

    parts = relative_path.parts
    if parts and parts[0] in EXCLUDED_ROOT_NAMES:
        return True
    if any(part in EXCLUDED_ANYWHERE_NAMES for part in parts):
        return True
    return relative_path.name.endswith(EXCLUDED_SUFFIXES)
