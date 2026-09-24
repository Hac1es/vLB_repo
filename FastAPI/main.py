"""FastAPI backend — quản lý .deb package trên disk."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import storage
from config import settings

log = logging.getLogger(__name__)
app = FastAPI(title="vLB package repo")


@app.get("/list")
async def list_packages():
    return storage.list_packages()


@app.get("/package/{name}")
async def get_package(name: str):
    spec = storage.read_spec(name)
    if spec is None:
        raise HTTPException(404, f"package {name} not found")
    return spec


@app.post("/publish")
async def publish(
    spec: str = Form(...),
    files: list[UploadFile] = File(default=[]),
):
    manifest = json.loads(spec)
    name = manifest["name"]
    uploaded = {f.filename: await f.read() for f in files if f.filename}
    try:
        result = storage.save_new(name, manifest, uploaded)
    except storage.PackageExists:
        raise HTTPException(409, f"package {name} already exists")
    return result


@app.post("/update/{name}")
async def update_package(
    name: str,
    spec: str = Form(...),
    files: list[UploadFile] = File(default=[]),
):
    manifest = json.loads(spec)
    uploaded = {f.filename: await f.read() for f in files if f.filename}
    try:
        result = storage.update(name, manifest, uploaded)
    except storage.PackageNotFound:
        raise HTTPException(404, f"package {name} not found")
    return result


@app.delete("/delete/{name}")
async def delete_package(name: str):
    storage.delete_all(name)
    return {"ok": True}


@app.get("/pull/{name}")
async def pull(name: str):
    p = storage.deb_path(name)
    if not p.exists():
        raise HTTPException(404, f"package {name} not found")
    return FileResponse(p, filename=p.name)


if __name__ == "__main__":
    import uvicorn

    settings.repo_root.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
