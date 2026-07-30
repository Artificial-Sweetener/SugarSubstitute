#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
"""Write Qt images through same-directory atomic replacement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QImageWriter

from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
)


class AtomicQtImageWriter:
    """Publish a complete encoded image without exposing a partial destination."""

    def write(self, path: Path, image: QImage) -> bool:
        """Encode one image and atomically replace its destination on success."""
        destination = operational_path(path)
        image_format = destination.suffix.removeprefix(".").encode("ascii", "ignore")
        if not image_format:
            return False
        encoded = QByteArray()
        buffer = QBuffer(encoded)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            return False
        writer = QImageWriter(buffer, image_format)
        if not writer.write(image):
            return False
        buffer.close()
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        try:
            temporary = os.fdopen(descriptor, "wb")
            descriptor = -1
            with temporary:
                temporary.write(encoded.data())
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, destination)
        except OSError:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            return False
        return True


__all__ = ["AtomicQtImageWriter"]
