from __future__ import annotations

import json

import httpx

settings = {
    "backend": "http://localhost:8000",
    "api_key": "",
}


def _headers() -> dict[str, str]:
    if not settings["api_key"]:
        return {}

    return {
        "X-API-Key": settings["api_key"],
    }


async def list_packages():
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{settings['backend']}/list",
            headers=_headers(),
        )

        response.raise_for_status()
        return response.json()


async def get_package(name: str):
    """
    Expected response example:

    {
        "name": "myapp",
        "version": "1.2.0",
        "arch": "amd64",

        "binary": {
            "filename": "myapp",
            "destination": "/usr/bin/myapp"
        },

        "files": [
            {
                "filename": "config.yaml",
                "destination": "/etc/myapp/config.yaml",
                "config": true,
                "mode": "0644"
            }
        ],

        "service": {
            "unit": "myapp.service"
        },

        "versions": [
            "1.2.0"
        ]
    }
    """

    async with httpx.AsyncClient(timeout=30) as client:
        # Nếu backend của bạn endpoint khác,
        # chỉ cần đổi dòng này.
        response = await client.get(
            f"{settings['backend']}/package/{name}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def publish(
    spec: dict,
    files: list[tuple[str, bytes]],
):
    return await _multipart_request(
        "POST",
        "/publish",
        spec,
        files,
    )


async def update_package(
    name: str,
    spec: dict,
    files: list[tuple[str, bytes]],
):
    return await _multipart_request(
        "POST",
        f"/update/{name}",
        spec,
        files,
    )


async def delete_package(name: str):
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.delete(
            f"{settings['backend']}/delete/{name}",
            headers=_headers(),
        )


async def _multipart_request(
    method: str,
    path: str,
    spec: dict,
    files: list[tuple[str, bytes]],
):
    form_files = [
        (
            "files",
            (
                filename,
                data,
                "application/octet-stream",
            ),
        )
        for filename, data in files
    ]

    async with httpx.AsyncClient(timeout=120) as client:
        return await client.request(
            method,
            f"{settings['backend']}{path}",
            data={
                "spec": json.dumps(spec),
            },
            files=form_files,
            headers=_headers(),
        )
