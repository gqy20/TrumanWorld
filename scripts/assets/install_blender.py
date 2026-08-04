#!/usr/bin/env python3
"""Install the pinned official Blender toolchain into the repository-local tools directory."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERSION = "5.2.0"
ARCHIVE_NAME = f"blender-{VERSION}-linux-x64.tar.xz"
ARCHIVE_URL = f"https://download.blender.org/release/Blender5.2/{ARCHIVE_NAME}"
ARCHIVE_SHA256 = "96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48"
TOOLS_ROOT = REPOSITORY_ROOT / ".tools"
DOWNLOAD_PATH = TOOLS_ROOT / "downloads" / ARCHIVE_NAME
INSTALL_PATH = TOOLS_ROOT / f"blender-{VERSION}-linux-x64"
ACTIVE_PATH = TOOLS_ROOT / "blender"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download() -> None:
    DOWNLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = DOWNLOAD_PATH.with_suffix(DOWNLOAD_PATH.suffix + ".part")
    with (
        urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response,
        temporary.open("wb") as output,
    ):
        shutil.copyfileobj(response, output, length=1024 * 1024)
    temporary.replace(DOWNLOAD_PATH)


def main() -> None:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise SystemExit("the pinned Blender package supports Linux x86_64 only")
    if not DOWNLOAD_PATH.is_file() or _sha256(DOWNLOAD_PATH) != ARCHIVE_SHA256:
        _download()
    actual_sha256 = _sha256(DOWNLOAD_PATH)
    if actual_sha256 != ARCHIVE_SHA256:
        raise SystemExit(f"Blender archive checksum mismatch: {actual_sha256}")
    if not (INSTALL_PATH / "blender").is_file():
        TOOLS_ROOT.mkdir(parents=True, exist_ok=True)
        with tarfile.open(DOWNLOAD_PATH, mode="r:xz") as archive:
            archive.extractall(TOOLS_ROOT, filter="data")
    if ACTIVE_PATH.is_symlink() or ACTIVE_PATH.is_file():
        ACTIVE_PATH.unlink()
    elif ACTIVE_PATH.exists():
        raise SystemExit(f"cannot replace non-link directory: {ACTIVE_PATH}")
    os.symlink(INSTALL_PATH.name, ACTIVE_PATH, target_is_directory=True)
    print(
        json.dumps(
            {
                "ok": True,
                "version": VERSION,
                "executable": str(ACTIVE_PATH / "blender"),
                "sha256": actual_sha256,
            }
        )
    )


if __name__ == "__main__":
    main()
