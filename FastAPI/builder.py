"""Build .deb từ manifest + src dir bằng dpkg-deb.

Manifest (clean, stored trong spec.json):
  {
    "name", "version", "arch",
    "binary": {"filename", "destination"} | None,
    "files": [{"filename", "destination", "config", "mode"}],
    "service": {"unit", "preinstall"?, "postinstall"?, "preremove"?, "postremove"?} | None
  }
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from config import settings

# Map tên hook trong spec → tên script Debian convention.
HOOK_TO_DEB = {
    "preinstall": "preinst",
    "postinstall": "postinst",
    "preremove": "prerm",
    "postremove": "postrm",
}


def build_deb(manifest: dict, src_dir: Path, out_path: Path) -> None:
    """Build .deb từ manifest + src_dir, ghi ra out_path."""
    src_dir = Path(src_dir)
    out_path = Path(out_path)

    with tempfile.TemporaryDirectory(prefix="vlb-build-") as tmp:
        tmp_root = Path(tmp)
        debian = tmp_root / "DEBIAN"
        debian.mkdir(parents=True, exist_ok=True)

        _write_control(debian, manifest)
        _place_binary(tmp_root, src_dir, manifest)
        _place_files(tmp_root, debian, src_dir, manifest)
        _place_service(tmp_root, debian, src_dir, manifest)

        # dpkg-deb cần owner root cho control; dùng --root-owner-group.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(tmp_root), str(out_path)],
            check=True,
            capture_output=True,
        )


def _write_control(debian: Path, manifest: dict) -> None:
    lines = [
        f"Package: {manifest['name']}",
        f"Version: {manifest['version']}",
        f"Architecture: {manifest['arch']}",
        "Section: misc",
        "Priority: optional",
    ]
    (debian / "control").write_text("\n".join(lines) + "\n")


def _place_binary(tmp_root: Path, src_dir: Path, manifest: dict) -> None:
    binary = manifest.get("binary")
    if not binary:
        return
    _install_file(
        src_dir / binary["filename"],
        tmp_root / _relative(binary["destination"]),
        mode=0o755,
    )


def _place_files(tmp_root: Path, debian: Path, src_dir: Path, manifest: dict) -> None:
    conffiles = []
    for f in manifest.get("files", []):
        dest = f["destination"]
        _install_file(
            src_dir / f["filename"],
            tmp_root / _relative(dest),
            mode=int(f.get("mode", "0644"), 8),
        )
        if f.get("config"):
            conffiles.append(dest)

    if conffiles:
        (debian / "conffiles").write_text("\n".join(conffiles) + "\n")


def _place_service(tmp_root: Path, debian: Path, src_dir: Path, manifest: dict) -> None:
    service = manifest.get("service")
    if not service:
        return

    unit = service.get("unit")
    if unit:
        unit_dest = tmp_root / "lib" / "systemd" / "system" / Path(unit).name
        _install_file(src_dir / unit, unit_dest, mode=0o644)

    for hook, deb_name in HOOK_TO_DEB.items():
        filename = service.get(hook)
        if filename:
            _install_file(
                src_dir / filename,
                debian / deb_name,
                mode=0o755,
            )


def _install_file(src: Path, dest: Path, mode: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    os.chmod(dest, mode)


def _relative(destination: str) -> Path:
    """'/usr/bin/myapp' → Path('usr/bin/myapp')."""
    return Path(destination.lstrip("/"))
