"""Settings cho backend."""
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.repo_root = Path(os.environ.get("VLB_REPO_ROOT", "/etc/repo"))
        self.build_tmp = Path(os.environ.get("VLB_BUILD_TMP", "/tmp/vlb-build"))


settings = Settings()
