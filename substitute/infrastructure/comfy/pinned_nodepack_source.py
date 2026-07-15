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

"""Apply pinned source archives for Comfy nodepacks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

from substitute.infrastructure.comfy.local_nodepack_source import (
    clear_readonly_and_retry,
    copy_local_nodepack_source,
)
from substitute.infrastructure.comfy.nodepack_git_maintenance import (
    checkout_pinned_git_tag,
    try_backup_git_nodepack_before_replacement,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS,
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    nodepack_has_git_metadata,
    nodepack_has_registry_metadata,
    path_is_relative_to,
    source_contains_sentinels,
    tracked_source_files,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.pinned_nodepack_source")


def apply_pinned_source_fallback(
    *,
    backend_root: Path,
    archive_url: str,
    target_path: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> None:
    """Apply pinned source without changing the nodepack management shape."""

    if nodepack_has_git_metadata(backend_root):
        checkout_pinned_git_tag(
            target_path=backend_root,
            nodepack=nodepack,
            on_log=on_log,
            env=env,
        )
        return
    overlay_pinned_source_archive(
        archive_url=archive_url,
        target_path=target_path,
        nodepack=nodepack,
        write_registry_tracking=nodepack_has_registry_metadata(backend_root),
        on_log=on_log,
        temp_dir=temp_dir_from_env(env),
    )


def overlay_pinned_source_archive(
    *,
    archive_url: str,
    target_path: Path,
    nodepack: CoreComfyNodepack,
    write_registry_tracking: bool,
    on_log: LogCallback | None,
    temp_dir: Path | None = None,
) -> None:
    """Overlay one pinned source archive into the normal custom-node folder."""

    _emit_log(
        on_log,
        f"[ComfyNodepacks] Downloading pinned {nodepack.display_name} source.",
    )
    with tempfile.TemporaryDirectory(
        prefix="substitute-nodepack-",
        dir=temp_dir,
    ) as temporary_directory:
        temp_root = Path(temporary_directory)
        archive_path = temp_root / "source.zip"
        extract_path = temp_root / "source"
        download_file(archive_url=archive_url, target_path=archive_path)
        source_path = extract_single_root_zip(
            archive_path=archive_path,
            target_path=extract_path,
        )
        if not source_contains_sentinels(source_path, nodepack):
            raise RuntimeError(
                f"Pinned {nodepack.display_name} archive did not contain required files."
            )
        tracked_files = tracked_source_files(source_path)
        copy_local_nodepack_source(
            source_path=source_path,
            target_path=target_path,
            allow_existing=True,
        )
        if write_registry_tracking:
            write_registry_tracking_file(
                target_path=target_path,
                tracked_files=tracked_files,
            )


def replace_with_pinned_source_archive(
    *,
    archive_url: str,
    target_path: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> None:
    """Replace an unmergeable managed nodepack with the pinned required source."""

    _emit_log(
        on_log,
        (
            f"[ComfyNodepacks] Replacing unmergeable {nodepack.display_name} "
            f"with pinned source {nodepack.minimum_python_distribution_version}."
        ),
    )
    with tempfile.TemporaryDirectory(
        prefix="substitute-nodepack-replace-",
        dir=temp_dir_from_env(env),
    ) as temporary_directory:
        temp_root = Path(temporary_directory)
        archive_path = temp_root / "source.zip"
        extract_path = temp_root / "source"
        replacement_path = temp_root / "replacement"
        download_file(archive_url=archive_url, target_path=archive_path)
        source_path = extract_single_root_zip(
            archive_path=archive_path,
            target_path=extract_path,
        )
        if not source_contains_sentinels(source_path, nodepack):
            raise RuntimeError(
                f"Pinned {nodepack.display_name} archive did not contain required files."
            )
        copy_local_nodepack_source(
            source_path=source_path,
            target_path=replacement_path,
        )
        if target_path.exists():
            try_backup_git_nodepack_before_replacement(
                target_path=target_path,
                nodepack=nodepack,
                reason="git_fast_forward_failed",
                on_log=on_log,
                env=env,
            )
            shutil.rmtree(target_path, onexc=clear_readonly_and_retry)
        shutil.move(str(replacement_path), str(target_path))


def download_file(*, archive_url: str, target_path: Path) -> None:
    """Download one source archive with an explicit timeout."""

    request = urllib.request.Request(
        archive_url,
        headers={"User-Agent": "SugarSubstitute"},
    )
    with (
        urllib.request.urlopen(  # noqa: S310 - pinned HTTPS source archive.
            request,
            timeout=ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response,
        target_path.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)


def extract_single_root_zip(*, archive_path: Path, target_path: Path) -> Path:
    """Extract a zip archive safely and return its single top-level folder."""

    target_path.mkdir(parents=True, exist_ok=True)
    resolved_target = target_path.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        roots: set[str] = set()
        for member in archive.infolist():
            member_path = Path(member.filename)
            if not member_path.parts:
                continue
            roots.add(member_path.parts[0])
            destination = (target_path / member.filename).resolve()
            if not path_is_relative_to(destination, resolved_target):
                raise RuntimeError("Pinned source archive contains an unsafe path.")
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    if len(roots) != 1:
        raise RuntimeError("Pinned source archive did not contain one root folder.")
    return target_path / next(iter(roots))


def write_registry_tracking_file(
    *,
    target_path: Path,
    tracked_files: tuple[Path, ...],
) -> None:
    """Write Comfy Registry tracking metadata for an overlaid source archive."""

    tracking_text = "\n".join(path.as_posix() for path in tracked_files)
    (target_path / ".tracking").write_text(tracking_text, encoding="utf-8")


def temp_dir_from_env(env: Mapping[str, str] | None) -> Path | None:
    """Return a temporary directory override from a managed subprocess env."""

    if env is None:
        return None
    raw_temp = env.get("TEMP") or env.get("TMP")
    if not raw_temp:
        return None
    temp_path = Path(raw_temp)
    temp_path.mkdir(parents=True, exist_ok=True)
    return temp_path


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one pinned-source line to logs and optional setup output."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "apply_pinned_source_fallback",
    "download_file",
    "extract_single_root_zip",
    "overlay_pinned_source_archive",
    "replace_with_pinned_source_archive",
    "temp_dir_from_env",
    "write_registry_tracking_file",
]
