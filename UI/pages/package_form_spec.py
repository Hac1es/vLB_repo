"""Pure spec assembly cho package form — không依赖 NiceGUI.

Tách khỏi package_form.py để có thể reason/test mà không cần browser.
"""

from __future__ import annotations

from typing import Any


def init_state(package: dict) -> dict:
    """State dict per-page (binary upload, extra files, service).

    File existing của package được seed với action="keep" để UI render
    đúng và build_spec biết đây là file đã có sẵn.
    """
    current_service = package.get("service") or {}

    state: dict[str, Any] = {
        "binary": None,
        "extra": [],
        "service_enabled": bool(current_service),
        "service_unit": None,
        "service_scripts": {},
        "original": _snapshot(package),
    }

    for item in package.get("files", []):
        state["extra"].append(
            {
                "existing": True,
                "filename": item.get(
                    "filename",
                    item.get("source", ""),
                ),
                "dest": item.get("destination", ""),
                "config": item.get("config", False),
                "mode": item.get("mode", "0644"),
                "size": item.get("size"),
                "action": "keep",
                "file": None,
            }
        )

    return state


def _snapshot(package: dict) -> dict:
    """Capture original values for dirty-check on update."""
    binary = package.get("binary") or {}
    return {
        "version": package.get("version"),
        "arch": package.get("arch"),
        "binary_destination": binary.get("destination"),
        "binary_filename": binary.get("filename"),
        "binary_size": binary.get("size"),
        "extra": [
            {
                "filename": f.get("filename", f.get("source", "")),
                "dest": f.get("destination"),
                "config": f.get("config"),
                "mode": f.get("mode"),
                "size": f.get("size"),
            }
            for f in package.get("files", [])
        ],
        "service_enabled": bool(package.get("service")),
        "service_unit": (package.get("service") or {}).get("unit"),
    }


def has_changes(
    state: dict,
    fields: dict,
) -> bool:
    """True nếu form state khác original snapshot (update mode only)."""
    orig = state.get("original") or {}
    if not orig:
        return True

    if fields["version"] != orig.get("version"):
        return True
    if fields["arch"] != orig.get("arch"):
        return True
    if fields["binary_destination"] != orig.get("binary_destination"):
        return True

    # Binary re-uploaded?
    if state["binary"]:
        return True

    # Extra files: action changed or new file added?
    for row in state["extra"]:
        if row["existing"]:
            if row["action"] != "keep":
                return True
        elif row["file"]:
            return True

    # Service changed?
    if state["service_enabled"] != orig.get("service_enabled"):
        return True
    if state["service_unit"]:
        return True
    if state["service_scripts"]:
        return True

    return False


def build_spec(
    mode: str,
    state: dict,
    fields: dict,
    current_service: dict | None = None,
) -> tuple[dict, list]:
    """Assemble (spec, files) gửi lên backend.

    fields: dict với keys name, version, arch,
    binary_destination (đọc từ widget .value ở orchestrator).
    current_service: package.get("service") or {} — chỉ dùng cho UPDATE
    để quyết định keep/remove service.
    """
    is_update = mode == "update"
    current_service = current_service or {}

    name = (fields["name"] or "").strip()
    version = (fields["version"] or "").strip()
    binary_destination = (fields["binary_destination"] or "").strip()

    if not name:
        raise ValueError("Package name required")

    if not version:
        raise ValueError("Version required")

    if not binary_destination:
        raise ValueError("Binary destination required")

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    if not is_update:
        if not state["binary"]:
            raise ValueError("Binary required")

        binary_name, binary_data = state["binary"]

        spec = {
            "name": name,
            "version": version,
            "arch": fields["arch"],
            "binary": binary_name,
            "binary_destination": binary_destination,
            "files": [],
        }

        files = [(binary_name, binary_data)]

        for row in state["extra"]:
            if not row["file"]:
                continue

            filename, data = row["file"]

            spec["files"].append(
                {
                    "source": filename,
                    "destination": row["dest"],
                    "config": row["config"],
                    "mode": row["mode"],
                }
            )

            files.append((filename, data))

        if state["service_enabled"]:
            if not state["service_unit"]:
                raise ValueError("Service enabled but no .service uploaded")

            unit_name, unit_data = state["service_unit"]

            service = {"unit": unit_name}

            files.append((unit_name, unit_data))

            for hook, value in state["service_scripts"].items():
                filename, data = value

                service[hook] = filename

                files.append((filename, data))

            spec["service"] = service

        return spec, files

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    spec = {
        "name": name,
        "version": version,
        "arch": fields["arch"],
        # Backend should preserve anything not explicitly
        # replaced/removed.
        "preserve_existing": True,
        "binary_destination": binary_destination,
        "files": [],
    }

    files = []

    # Binary replacement is optional

    if state["binary"]:
        filename, data = state["binary"]

        spec["binary"] = {
            "action": "replace",
            "source": filename,
            "destination": binary_destination,
        }

        files.append((filename, data))

    else:
        spec["binary"] = {
            "action": "keep",
            "destination": binary_destination,
        }

    # Additional files

    for row in state["extra"]:
        # Existing file
        if row["existing"]:
            entry = {
                "action": row["action"],
                "source": row["filename"],
                "destination": row["dest"],
                "config": row["config"],
                "mode": row["mode"],
            }

            if row["action"] == "replace":
                if not row["file"]:
                    raise ValueError(f"Replacement required for {row['filename']}")

                filename, data = row["file"]

                entry["source"] = filename

                files.append((filename, data))

            spec["files"].append(entry)

        # New file
        else:
            if not row["file"]:
                continue

            filename, data = row["file"]

            spec["files"].append(
                {
                    "action": "add",
                    "source": filename,
                    "destination": row["dest"],
                    "config": row["config"],
                    "mode": row["mode"],
                }
            )

            files.append((filename, data))

    # Service

    if not state["service_enabled"]:
        if current_service:
            spec["service"] = {"action": "remove"}

    elif state["service_unit"]:
        unit_name, unit_data = state["service_unit"]

        service = {
            "action": "replace",
            "unit": unit_name,
        }

        files.append((unit_name, unit_data))

        for hook, value in state["service_scripts"].items():
            filename, data = value

            service[hook] = filename

            files.append((filename, data))

        spec["service"] = service

    elif current_service:
        spec["service"] = {"action": "keep"}

    return spec, files
