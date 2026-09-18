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

"""Own durable selection of complete launcher generations beside the baseline."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
from uuid import uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord

from sugarsubstitute_shared.launcher_update.persistence import read_json_object
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget
from sugarsubstitute_shared.launcher_update.delegation_contract import (
    validate_launcher_successor,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SelectedLauncherBundle:
    """Describe the verified payload selected for one launch."""

    root: Path
    version: str | None
    generation: str | None


class LauncherBundleSelection:
    """Publish immutable generations and atomically select one runnable payload.

    The installation root remains a complete baseline. Selection is authoritative
    installation state; neither publication nor selection removes older payloads.
    The elected update owner must serialize activations for one installation.
    """

    def __init__(self, install_root: Path, target: LauncherBundleTarget) -> None:
        """Bind the baseline and target without creating installation state."""
        self._root = install_root.resolve()
        self._target = target
        self._paths = LauncherBundlePaths(self._root)
        self._bundles = self._paths.generations
        self._selection = self._paths.selection

    def publish(self, staged_bundle: Path, *, version: str) -> SelectedLauncherBundle:
        """Seal a verified complete copy before making it eligible for activation."""
        source = staged_bundle.resolve()
        if not any(
            source.is_relative_to(namespace)
            for namespace in (
                self._root / "launcher" / "updates",
                self._root / ".repair" / "staging",
            )
        ):
            raise ValueError("Launcher candidate must belong to installation staging.")
        if not version.strip():
            raise ValueError("Launcher generation version must not be empty.")
        validate_launcher_bundle(bundle_dir=source, target=self._target)
        fingerprints = _fingerprints(source)
        generation = uuid4().hex
        preparing = self._bundles / f".preparing-{generation}"
        destination = self._paths.generation(generation)
        preparing.mkdir(parents=True)
        payload = preparing / "payload"
        shutil.copytree(source, payload, symlinks=True)
        if _fingerprints(payload) != fingerprints:
            raise ValueError("Launcher candidate changed during publication.")
        validate_launcher_bundle(bundle_dir=payload, target=self._target)
        _write_record(
            preparing / "bundle.json",
            {
                "schema_version": 1,
                "target_key": self._target.key,
                "version": version,
                "files": fingerprints,
            },
        )
        preparing.replace(destination)
        return SelectedLauncherBundle(destination / "payload", version, generation)

    def activate(self, candidate: SelectedLauncherBundle) -> None:
        """Commit selection only after validating the candidate and retained fallback."""
        record = self._activation_record(candidate)
        if record is not None:
            _write_record(self._selection, record)

    def stage_activation(
        self, candidate: SelectedLauncherBundle, destination: Path
    ) -> None:
        """Prepare selection for promotion within an enclosing repair transaction."""
        destination = destination.resolve()
        if not destination.is_relative_to(self._root / ".repair" / "staging"):
            raise ValueError(
                "Prepared launcher selection must belong to repair staging."
            )
        record = self._activation_record(candidate)
        if record is None:
            raise ValueError("Launcher generation is already active.")
        _write_record(destination, record)

    def _activation_record(
        self, candidate: SelectedLauncherBundle
    ) -> dict[str, object] | None:
        """Validate and derive one authoritative current/previous transition."""
        generation = candidate.generation
        if generation is None:
            raise ValueError("The baseline is selected by recovery, not publication.")
        verified = self._read_generation(generation)
        if verified != candidate:
            raise ValueError("Launcher generation does not match this installation.")
        validate_launcher_successor(
            baseline=self._root, candidate=verified.root, target=self._target
        )
        current = self.resolve()
        if current.generation == generation:
            return None
        return {
            "schema_version": 1,
            "current": generation,
            "previous": current.generation,
        }

    def resolve(self) -> SelectedLauncherBundle:
        """Select a verified current, previous, or independently runnable baseline."""
        if self._selection.exists():
            try:
                record = read_json_object(self._selection)
                if record.get("schema_version") != 1:
                    raise ValueError("Unsupported launcher selection schema.")
                generations = (record.get("current"), record.get("previous"))
                for generation in generations:
                    if generation is None:
                        continue
                    try:
                        return self._read_generation(generation)
                    except (ValueError, OSError) as error:
                        _LOGGER.warning(
                            "Selected launcher generation is unavailable: %s", error
                        )
            except (ValueError, OSError) as error:
                _LOGGER.warning("Launcher selection is unreadable: %s", error)
        validate_launcher_bundle(
            bundle_dir=self._root,
            target=self._target,
            allow_installation_content=True,
        )
        return SelectedLauncherBundle(self._root, None, None)

    def installed_record(self) -> LauncherInstallationRecord | None:
        """Project the active version without overwriting the baseline version record."""
        from sugarsubstitute_shared.launcher_update.models import (
            LauncherInstallationRecord,
        )

        if self._selection.exists():
            selected = self.resolve()
            if selected.version is not None:
                return LauncherInstallationRecord(
                    version=selected.version, target_key=self._target.key
                )
        return LauncherInstallationRecord.load(
            self._root / "launcher" / "installation.json"
        )

    def reject(self, candidate: SelectedLauncherBundle) -> None:
        """Retire one failed generation without overwriting concurrent selection.

        Rejection belongs to the immutable generation identity. A concurrent
        activation of a different payload remains intact; readers fall through
        rejected identities to the retained previous generation or baseline.
        """
        generation = candidate.generation
        if generation is None:
            raise ValueError("The baseline cannot be rejected.")
        directory = self._paths.generation(generation)
        if candidate.root != directory / "payload":
            raise ValueError("Launcher generation does not match this installation.")
        _write_record(directory / "rejected.json", {"schema_version": 1})

    def _read_generation(self, generation: object) -> SelectedLauncherBundle:
        """Require canonical identity, target and every sealed payload fingerprint."""
        if not isinstance(generation, str):
            raise ValueError("Invalid launcher generation identifier.")
        directory = self._paths.generation(generation)
        if directory.resolve() != directory:
            raise ValueError("Launcher generation escapes its storage owner.")
        if (directory / "rejected.json").exists():
            raise ValueError("Launcher generation was retired after launch failure.")
        record = read_json_object(directory / "bundle.json")
        version = record.get("version")
        if (
            record.get("schema_version") != 1
            or record.get("target_key") != self._target.key
            or not isinstance(version, str)
            or not version.strip()
        ):
            raise ValueError("Invalid launcher generation record.")
        payload = directory / "payload"
        if _fingerprints(payload) != record.get("files"):
            raise ValueError("Launcher generation is incomplete or modified.")
        validate_launcher_bundle(bundle_dir=payload, target=self._target)
        return SelectedLauncherBundle(payload, version, generation)


def _fingerprints(root: Path) -> dict[str, str]:
    """Hash the complete regular-file tree without following external references."""
    resolved = root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Launcher payload must be a complete directory.")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.resolve().is_relative_to(resolved):
            raise ValueError("Launcher payload contains an external linked path.")
        if path.is_symlink():
            files[path.relative_to(root).as_posix()] = "link:" + os.readlink(path)
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Launcher payload contains a nonregular file.")
        with path.open("rb") as stream:
            files[path.relative_to(root).as_posix()] = hashlib.file_digest(
                stream, "sha256"
            ).hexdigest()
    return files


def _write_record(path: Path, record: dict[str, object]) -> None:
    """Flush one record and replace its selection point without a missing-file gap."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
