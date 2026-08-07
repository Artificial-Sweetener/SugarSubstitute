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

"""Materialize trusted tag archives as Comfy Registry-managed nodepacks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

from substitute.infrastructure.comfy.nodepack_manifest import (
    ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS,
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_registry_tracking import (
    read_registry_tracking_file,
    validate_registry_tracking_paths,
    write_registry_tracking_file,
)
from substitute.infrastructure.comfy.nodepack_source_identity import (
    validate_nodepack_source_identity,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    path_is_relative_to,
    tracked_source_files,
)
from substitute.shared.logging.logger import get_logger, log_info
from sugarsubstitute_shared.tls import SystemTrustTlsContext

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.pinned_nodepack_source")


class PinnedNodepackSourceInstaller:
    """Install trusted pinned releases while preserving mutable nodepack data."""

    def install_fallback(
        self,
        *,
        target_path: Path,
        nodepack: CoreComfyNodepack,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> None:
        """Install one pinned tag while preserving untracked runtime and user data."""

        _emit_log(
            on_log,
            f"[ComfyNodepacks] Downloading pinned {nodepack.display_name} source.",
        )
        with tempfile.TemporaryDirectory(
            prefix="substitute-nodepack-fallback-",
            dir=temp_dir_from_env(env),
        ) as temporary_directory:
            transaction_root = Path(temporary_directory)
            archive_path = transaction_root / "source.zip"
            extract_path = transaction_root / "source"
            backup_path = transaction_root / "previous"
            download_file(
                archive_url=nodepack.fallback_archive_url,
                target_path=archive_path,
            )
            source_path = extract_single_root_zip(
                archive_path=archive_path,
                target_path=extract_path,
            )
            validate_nodepack_source_identity(
                source_path,
                nodepack,
                require_version=True,
            )
            new_tracked_files = tracked_source_files(source_path)
            old_tracked_files = read_registry_tracking_file(target_path)
            if target_path.exists() and old_tracked_files is None:
                raise RuntimeError(
                    f"Refusing to replace unowned nodepack folder: {target_path}"
                )
            _apply_tracked_source_transaction(
                source_path=source_path,
                target_path=target_path,
                old_tracked_files=old_tracked_files or (),
                new_tracked_files=new_tracked_files,
                backup_path=backup_path,
            )
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Installed pinned {nodepack.display_name} "
                f"{nodepack.required_version} in Comfy Registry format."
            ),
        )


def download_file(*, archive_url: str, target_path: Path) -> None:
    """Download one trusted source archive with an explicit timeout."""

    request = urllib.request.Request(
        archive_url,
        headers={"User-Agent": "SugarSubstitute"},
    )
    with (
        urllib.request.urlopen(  # noqa: S310 - manifest owns trusted HTTPS URLs.
            request,
            timeout=ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS,
            context=SystemTrustTlsContext.create(),
        ) as response,
        target_path.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)


def extract_single_root_zip(*, archive_path: Path, target_path: Path) -> Path:
    """Extract a zip safely and return its only top-level directory."""

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


def temp_dir_from_env(env: Mapping[str, str] | None) -> Path | None:
    """Return a managed temporary-directory override when configured."""

    if env is None:
        return None
    raw_temp = env.get("TEMP") or env.get("TMP")
    if not raw_temp:
        return None
    temp_path = Path(raw_temp)
    temp_path.mkdir(parents=True, exist_ok=True)
    return temp_path


def _apply_tracked_source_transaction(
    *,
    source_path: Path,
    target_path: Path,
    old_tracked_files: tuple[Path, ...],
    new_tracked_files: tuple[Path, ...],
    backup_path: Path,
) -> None:
    """Replace only CNR-owned files and roll them back on any failure."""

    validate_registry_tracking_paths(source_path, new_tracked_files)
    validate_registry_tracking_paths(target_path, old_tracked_files)
    target_preexisted = target_path.exists()
    backup_path.mkdir(parents=True)
    for relative_path in old_tracked_files:
        installed_path = target_path / relative_path
        if installed_path.is_file():
            backup_file = backup_path / relative_path
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installed_path, backup_file)
    previous_tracking = (
        (target_path / ".tracking").read_bytes()
        if (target_path / ".tracking").is_file()
        else None
    )
    try:
        target_path.mkdir(parents=True, exist_ok=True)
        _remove_tracked_files(target_path, old_tracked_files)
        for relative_path in new_tracked_files:
            source_file = source_path / relative_path
            destination = target_path / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
        write_registry_tracking_file(
            target_path=target_path,
            tracked_files=new_tracked_files,
        )
    except Exception:
        _remove_tracked_files(target_path, new_tracked_files)
        for backup_file in backup_path.rglob("*"):
            if not backup_file.is_file():
                continue
            relative_path = backup_file.relative_to(backup_path)
            destination = target_path / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, destination)
        tracking_path = target_path / ".tracking"
        if previous_tracking is None:
            tracking_path.unlink(missing_ok=True)
        else:
            tracking_path.write_bytes(previous_tracking)
        if (
            not target_preexisted
            and target_path.exists()
            and not any(target_path.iterdir())
        ):
            target_path.rmdir()
        raise


def _remove_tracked_files(root: Path, tracked_files: tuple[Path, ...]) -> None:
    """Remove owned files and any empty owned parent directories."""

    for relative_path in tracked_files:
        installed_path = root / relative_path
        if installed_path.is_file() or installed_path.is_symlink():
            installed_path.unlink()
    parent_paths = sorted(
        {
            parent
            for relative_path in tracked_files
            for parent in (root / relative_path).parents
            if parent != root and path_is_relative_to(parent, root)
        },
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for parent in parent_paths:
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit fallback activity to structured and setup logs."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "PinnedNodepackSourceInstaller",
    "download_file",
    "extract_single_root_zip",
    "temp_dir_from_env",
]
