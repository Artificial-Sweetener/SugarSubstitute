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

"""Exchange checksum-verified standalone artifacts with installer qualification."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
from threading import Event, Thread
import time
from uuid import uuid4

from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


@contextmanager
def qualification_standalone_artifact_cache(
    *,
    install_root: Path,
    external_cache_root: Path | None,
    timeout_seconds: float,
) -> Iterator[DeferredArtifactCacheStage | None]:
    """Stage CI artifacts after layout creation and retain verified results."""

    if external_cache_root is None:
        yield None
        return
    resolved_install_root = install_root.resolve()
    resolved_external_root = external_cache_root.resolve()
    if (
        resolved_external_root == resolved_install_root
        or resolved_external_root.is_relative_to(resolved_install_root)
    ):
        raise InstallerLifecycleError(
            "Qualification standalone cache must be outside the clean install root."
        )
    installed_cache_root = (
        resolved_install_root / ".sugarsubstitute-cache" / "standalone"
    )
    stage = DeferredArtifactCacheStage(
        ready_path=resolved_install_root / "launcher" / "config.json",
        source_root=resolved_external_root,
        destination_root=installed_cache_root,
        diagnostic_path=standalone_cache_diagnostic_path(resolved_install_root),
        timeout_seconds=timeout_seconds,
    )
    stage.start()
    succeeded = False
    try:
        yield stage
        succeeded = True
    finally:
        if succeeded:
            stage.wait_for_completion()
            stage.require_success()
        else:
            stage.cancel()
    if succeeded:
        _mirror_complete_files(
            source_root=installed_cache_root,
            destination_root=resolved_external_root,
        )


def standalone_cache_diagnostic_path(install_root: Path) -> Path:
    """Return the durable cache-exchange receipt beside one install root."""

    resolved_root = install_root.resolve()
    return resolved_root.parent / f".{resolved_root.name}-standalone-cache.json"


@dataclass(slots=True)
class DeferredArtifactCacheStage:
    """Stage restored artifacts after the installer owns its selected layout."""

    ready_path: Path
    source_root: Path
    destination_root: Path
    diagnostic_path: Path
    timeout_seconds: float
    _stop: Event = field(default_factory=Event, init=False)
    _completed: Event = field(default_factory=Event, init=False)
    _failure: str | None = field(default=None, init=False)
    _thread: Thread = field(init=False)

    def __post_init__(self) -> None:
        """Create the bounded background worker without starting it."""

        self._thread = Thread(
            target=self._run,
            name="qualification-standalone-cache",
            daemon=True,
        )

    def start(self) -> None:
        """Begin waiting for the installed launcher layout."""

        self._write_receipt(state="waiting_for_install_layout")
        self._thread.start()

    def wait_for_completion(self) -> None:
        """Wait for the bounded staging worker after a successful chain."""

        if not self._completed.wait(self.timeout_seconds):
            raise InstallerLifecycleError(
                "Qualification cache staging did not finish within its timeout."
            )

    def require_success(self) -> None:
        """Raise the staging failure after the foreground chain completes."""

        if self._failure is not None:
            raise InstallerLifecycleError(self._failure)

    def cancel(self) -> None:
        """Stop a worker whose foreground installer chain already failed."""

        self._stop.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        """Wait for layout ownership, then atomically expose restored artifacts."""

        try:
            deadline = time.monotonic() + self.timeout_seconds
            while not self.ready_path.is_file():
                if self._stop.wait(0.05):
                    self._write_receipt(state="cancelled_before_install_layout")
                    return
                if time.monotonic() >= deadline:
                    raise InstallerLifecycleError(
                        "Installed launcher layout was not prepared before cache staging."
                    )
            _mirror_complete_files(
                source_root=self.source_root,
                destination_root=self.destination_root,
            )
            staged_inventory = _cache_inventory(self.source_root)
            self._write_receipt(
                state="staged_after_install_layout",
                source_inventory=staged_inventory,
                destination_inventory=staged_inventory,
            )
        except Exception as error:
            self._failure = str(error).strip() or type(error).__name__
            self._write_receipt(
                state="staging_failed",
                error_type=type(error).__name__,
                error=self._failure,
            )
        finally:
            self._completed.set()

    def _write_receipt(
        self,
        *,
        state: str,
        source_inventory: dict[str, object] | None = None,
        destination_inventory: dict[str, object] | None = None,
        **fields: object,
    ) -> None:
        """Persist bounded evidence for the external and installed cache roots."""

        payload = {
            "schema_version": 1,
            "state": state,
            "ready_path_present": self.ready_path.is_file(),
            "source": source_inventory or _cache_inventory(self.source_root),
            "destination": destination_inventory
            or _cache_inventory(self.destination_root),
            **fields,
        }
        self.diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.diagnostic_path.with_name(
            f".{self.diagnostic_path.name}.{uuid4().hex}.tmp"
        )
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.diagnostic_path)
        finally:
            temporary.unlink(missing_ok=True)


def _cache_inventory(root: Path) -> dict[str, object]:
    """Describe complete artifact files without exposing machine-local roots."""

    files = (
        tuple(
            path
            for path in root.rglob("*")
            if path.is_file() and not path.name.endswith(".part")
        )
        if root.is_dir()
        else ()
    )
    return {
        "present": root.is_dir(),
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
    }


def _mirror_complete_files(*, source_root: Path, destination_root: Path) -> None:
    """Mirror complete cache files atomically, preferring same-volume hard links."""

    if not source_root.is_dir():
        return
    for source in source_root.rglob("*"):
        if not source.is_file() or source.name.endswith(".part"):
            continue
        if source.is_symlink():
            raise InstallerLifecycleError(
                f"Qualification standalone cache contains a symlink: {source}"
            )
        relative = source.relative_to(source_root)
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and os.path.samefile(source, destination):
            continue
        temporary = destination.with_name(
            f".{destination.name}.qualification-{os.getpid()}-{uuid4().hex}.tmp"
        )
        try:
            try:
                os.link(source, temporary)
            except OSError:
                shutil.copy2(source, temporary)
            temporary.replace(destination)
        except OSError as error:
            raise InstallerLifecycleError(
                "Could not stage the standalone artifact cache for qualification: "
                f"{source} -> {destination}: {error}"
            ) from error
        finally:
            temporary.unlink(missing_ok=True)


__all__ = [
    "DeferredArtifactCacheStage",
    "qualification_standalone_artifact_cache",
    "standalone_cache_diagnostic_path",
]
