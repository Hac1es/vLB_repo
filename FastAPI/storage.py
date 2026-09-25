"""Storage ops lên /etc/repo/<name>/.

Layout:
  /etc/repo/<name>/spec.json   # clean manifest
  /etc/repo/<name>/src/        # source files (flat)
  /etc/repo/<name>/package.deb
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from builder import build_deb
from config import settings


class PackageExists(Exception):
    pass


class PackageNotFound(Exception):
    pass


def pkg_dir(name: str) -> Path:
    return settings.repo_root / name


def src_dir(name: str) -> Path:
    return pkg_dir(name) / "src"


def deb_path(name: str) -> Path:
    return pkg_dir(name) / "package.deb"


def spec_path(name: str) -> Path:
    return pkg_dir(name) / "spec.json"


# -----------------------------------------------------------------
# Read
# -----------------------------------------------------------------


def list_packages() -> list[dict]:
    root = settings.repo_root
    if not root.exists():
        return []
    out = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        spec = _read_spec(sub.name)
        if spec is None:
            continue
        out.append(
            {
                "name": spec.get("name", sub.name),
                "version": spec.get("version", "—"),
                "arch": spec.get("arch", "—"),
            }
        )
    return out


def read_spec(name: str) -> dict | None:
    return _read_spec(name)


def _read_spec(name: str) -> dict | None:
    p = spec_path(name)
    if not p.exists():
        return None
    return json.loads(p.read_text())


# -----------------------------------------------------------------
# Write
# -----------------------------------------------------------------


def save_new(name: str, spec: dict, uploaded: dict[str, bytes]) -> dict:
    d = pkg_dir(name)
    if d.exists():
        raise PackageExists(name)

    manifest = _normalize_create(spec)
    d.mkdir(parents=True)
    (d / "src").mkdir()

    _write_uploaded(name, uploaded)
    _stamp_sizes(name, manifest)
    _write_manifest(name, manifest)
    build_deb(manifest, src_dir(name), deb_path(name))
    return manifest


def update(name: str, spec: dict, uploaded: dict[str, bytes]) -> dict:
    old = _read_spec(name)
    if old is None:
        raise PackageNotFound(name)

    manifest = _merge_update(old, spec)

    _write_uploaded(name, uploaded)
    _stamp_sizes(name, manifest)
    _write_manifest(name, manifest)
    build_deb(manifest, src_dir(name), deb_path(name))
    return manifest


def delete_all(name: str) -> None:
    d = pkg_dir(name)
    if d.exists():
        shutil.rmtree(d)


# -----------------------------------------------------------------
# Spec normalization
# -----------------------------------------------------------------


def _normalize_create(spec: dict) -> dict:
    """CREATE spec (từ UI) → clean manifest."""
    binary = None
    if spec.get("binary"):
        binary = {
            "filename": spec["binary"],
            "destination": spec["binary_destination"],
        }

    files = [
        {
            "filename": f["source"],
            "destination": f["destination"],
            "config": f.get("config", False),
            "mode": f.get("mode", "0644"),
        }
        for f in spec.get("files", [])
    ]

    service = _clean_service(spec.get("service"))

    return {
        "name": spec["name"],
        "version": spec["version"],
        "arch": spec["arch"],
        "binary": binary,
        "files": files,
        "service": service,
    }


def _merge_update(old: dict, spec: dict) -> dict:
    """UPDATE spec (có action) + old manifest → new clean manifest."""
    # Binary
    b = spec.get("binary") or {}
    baction = b.get("action")
    binary = None
    if baction == "replace":
        binary = {"filename": b["source"], "destination": b["destination"]}
    elif baction == "keep" and old.get("binary"):
        binary = {
            "filename": old["binary"]["filename"],
            "destination": b.get("destination", old["binary"]["destination"]),
        }

    # Files — bỏ remove, giữ rest (source đã là filename đúng cho keep/replace/add)
    files = []
    for f in spec.get("files", []):
        if f.get("action") == "remove":
            continue
        files.append(
            {
                "filename": f["source"],
                "destination": f["destination"],
                "config": f.get("config", False),
                "mode": f.get("mode", "0644"),
            }
        )

    # Service
    s = spec.get("service") or {}
    saction = s.get("action")
    service = None
    if saction == "remove":
        service = None
    elif saction == "keep":
        service = old.get("service")
    elif saction == "replace":
        service = _clean_service(s)
    else:
        # CREATE-shape service (có unit, không action)
        service = _clean_service(s)

    return {
        "name": spec["name"],
        "version": spec["version"],
        "arch": spec["arch"],
        "binary": binary,
        "files": files,
        "service": service,
    }


def _clean_service(s: dict | None) -> dict | None:
    if not s:
        return None
    out = {k: v for k, v in s.items() if k != "action"}
    if not out.get("unit"):
        return None
    return out


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------


def _stamp_sizes(name: str, manifest: dict) -> None:
    """Ghi file size (bytes) vào manifest cho binary + files.

    Frontend dùng size để detect "upload same file" (same name + same size
    → no-op, skip).
    """
    sd = src_dir(name)
    b = manifest.get("binary")
    if b:
        p = sd / b["filename"]
        if p.exists():
            b["size"] = p.stat().st_size
    for f in manifest.get("files", []):
        p = sd / f["filename"]
        if p.exists():
            f["size"] = p.stat().st_size


def _write_uploaded(name: str, uploaded: dict[str, bytes]) -> None:
    sd = src_dir(name)
    sd.mkdir(parents=True, exist_ok=True)
    for filename, data in uploaded.items():
        (sd / filename).write_bytes(data)


def _write_manifest(name: str, manifest: dict) -> None:
    spec_path(name).write_text(json.dumps(manifest, indent=2))
