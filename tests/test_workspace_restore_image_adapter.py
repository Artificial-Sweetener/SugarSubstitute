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

"""Cover restored workspace image replay outside MainWindow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from pytest import MonkeyPatch

from substitute.application.workflows import ImageMeta
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
)
from substitute.presentation.shell import workspace_restore_image_adapter as adapter_mod
from substitute.presentation.shell.workspace_restore_image_adapter import (
    WorkspaceRestoreImageAdapter,
)


class _DecodedImage:
    """Expose QImage-like null state for preload tests."""

    def __init__(self, *, is_null: bool = False) -> None:
        """Store the null state."""

        self._is_null = is_null

    def isNull(self) -> bool:
        """Return whether decoding failed."""

        return self._is_null


def test_load_restored_input_image_prefers_preloaded_payload(
    monkeypatch: MonkeyPatch,
) -> None:
    """Preloaded restore bytes should avoid canvas IO fallback loading."""

    decoded = _DecodedImage()
    decode_calls: list[bytes] = []
    shell = SimpleNamespace(
        _restore_asset_preload=SimpleNamespace(
            image_bytes=lambda _path: b"encoded-image"
        ),
        canvas_io_service=SimpleNamespace(
            load_input_image=lambda _path: (_ for _ in ()).throw(
                AssertionError("fallback should not run")
            )
        ),
    )

    def from_data(payload: bytes) -> _DecodedImage:
        """Record decoded bytes and return the fake image."""

        decode_calls.append(payload)
        return decoded

    monkeypatch.setattr(adapter_mod, "QImage", SimpleNamespace(fromData=from_data))

    image = WorkspaceRestoreImageAdapter(shell).load_restored_input_image(
        Path("input.png")
    )

    assert image is decoded
    assert decode_calls == [b"encoded-image"]


def test_set_restore_asset_preload_attaches_preload_to_shell() -> None:
    """Restore image adapter should own preload attachment on the shell."""

    shell = SimpleNamespace(_restore_asset_preload=None)
    preload = object()

    WorkspaceRestoreImageAdapter(shell).set_restore_asset_preload(preload)

    assert shell._restore_asset_preload is preload


def test_load_restored_output_image_uses_canvas_io_without_preload() -> None:
    """Missing preload bytes should fall back to the normal output image loader."""

    calls: list[Path] = []
    output_image = object()

    def load_output_image(path: Path) -> object:
        """Record fallback output load and return the fake image."""

        calls.append(path)
        return output_image

    shell = SimpleNamespace(
        _restore_asset_preload=SimpleNamespace(image_bytes=lambda _path: None),
        canvas_io_service=SimpleNamespace(load_output_image=load_output_image),
    )

    image = WorkspaceRestoreImageAdapter(shell).load_restored_output_image(
        Path("output.png")
    )

    assert image is output_image
    assert calls == [Path("output.png")]


def test_restore_input_image_preserves_snapshot_uuid() -> None:
    """Restored input image references should be replayed under their saved UUID."""

    image_id = uuid4()
    calls: list[dict[str, object]] = []
    shell = SimpleNamespace(
        input_canvas_state_service=SimpleNamespace(
            restore_input_image=lambda **kwargs: calls.append(kwargs)
        ),
    )
    reference = InputImageReference(
        image_id=str(image_id),
        path=Path("input.png"),
        sequence=0,
    )
    image = object()

    WorkspaceRestoreImageAdapter(shell).restore_input_image(reference, image)

    assert calls == [{"image_id": image_id, "image": image, "path": Path("input.png")}]


def test_restore_input_mask_remaps_reference_through_workflow_canvas_state() -> None:
    """Restored input mask replay should locate the owning hydrated workflow."""

    image_id = uuid4()
    snapshot_mask_id = uuid4()
    live_mask_id = uuid4()
    association_key = ("CubeA", "MaskNode")
    workflow = WorkflowState()
    workflow.canvas.input_key_map["CubeA:ImageNode"] = image_id
    workflow.canvas.mask_associations[association_key] = snapshot_mask_id
    workflow.canvas.mask_to_image_map[snapshot_mask_id] = image_id
    restore_calls: list[dict[str, object]] = []

    def restore_input_mask(*args: object, **kwargs: object) -> UUID:
        """Record restored mask arguments and return a live mask id."""

        restore_calls.append({"args": args, "kwargs": kwargs})
        return live_mask_id

    shell = SimpleNamespace(
        _shell_restore_lifecycle="running",
        workflow_session_service=SimpleNamespace(workflows={"wf-a": workflow}),
        input_canvas_state_service=SimpleNamespace(
            restore_input_mask=restore_input_mask
        ),
    )
    reference = InputMaskReference(
        mask_id=str(snapshot_mask_id),
        image_id=str(image_id),
        path=Path("mask.png"),
        association_key=association_key,
    )

    restored = WorkspaceRestoreImageAdapter(shell).restore_input_mask(reference)

    assert restored is True
    assert restore_calls == [
        {
            "args": ("wf-a", workflow),
            "kwargs": {
                "snapshot_mask_id": snapshot_mask_id,
                "image_id": image_id,
                "path": Path("mask.png"),
                "association_key": association_key,
            },
        }
    ]


def test_restore_input_mask_defers_during_prehydration() -> None:
    """Prehydrated mask references should wait until hydrated workflows install."""

    reference = InputMaskReference(
        mask_id=str(uuid4()),
        image_id=str(uuid4()),
        path=Path("mask.png"),
        association_key=("CubeA", "MaskNode"),
    )
    shell = SimpleNamespace(_shell_restore_lifecycle="prehydrating")

    restored = WorkspaceRestoreImageAdapter(shell).restore_input_mask(reference)

    assert restored is True
    assert shell._deferred_prehydrated_input_masks == [reference]


def test_restore_deferred_prehydrated_input_masks_replays_and_clears() -> None:
    """Deferred mask replay should clear pending references after attempted restore."""

    image_id = uuid4()
    snapshot_mask_id = uuid4()
    workflow = WorkflowState()
    workflow.canvas.input_key_map["CubeA:ImageNode"] = image_id
    workflow.canvas.mask_to_image_map[snapshot_mask_id] = image_id
    reference = InputMaskReference(
        mask_id=str(snapshot_mask_id),
        image_id=str(image_id),
        path=Path("mask.png"),
    )
    calls: list[dict[str, object]] = []

    def restore_input_mask(*args: object, **kwargs: object) -> UUID:
        """Record restored mask arguments and return a generated mask id."""

        calls.append({"args": args, "kwargs": kwargs})
        return uuid4()

    shell = SimpleNamespace(
        _shell_restore_lifecycle="running",
        _deferred_prehydrated_input_masks=[reference],
        workflow_session_service=SimpleNamespace(workflows={"wf-a": workflow}),
        input_canvas_state_service=SimpleNamespace(
            restore_input_mask=restore_input_mask
        ),
    )

    WorkspaceRestoreImageAdapter(shell).restore_deferred_prehydrated_input_masks()

    assert calls[0]["args"] == ("wf-a", workflow)
    assert shell._deferred_prehydrated_input_masks == []


def test_restore_output_image_preserves_snapshot_uuid_and_metadata() -> None:
    """Restored output references should be replayed under their saved UUID."""

    image_id = uuid4()
    image = object()
    image_meta = ImageMeta("Workflow", "Cube", 1, "", "output.png")
    calls: list[dict[str, object]] = []
    shell = SimpleNamespace(
        output_canvas_state_service=SimpleNamespace(
            restore_output_image=lambda **kwargs: calls.append(kwargs)
        ),
    )
    reference = OutputImageReference(
        image_id=str(image_id),
        path=Path("output.png"),
        metadata=ImageMetaSnapshot("Workflow", "Cube", 1, "", Path("output.png")),
        sequence=0,
    )

    WorkspaceRestoreImageAdapter(shell).restore_output_image(
        "wf-a",
        reference,
        image,
        image_meta,
    )

    assert calls == [
        {
            "workflow_id": "wf-a",
            "image_id": image_id,
            "image": image,
            "image_meta": image_meta,
        }
    ]
