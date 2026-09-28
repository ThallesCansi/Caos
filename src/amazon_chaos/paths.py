from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def data_root() -> Path:
    configured = os.getenv("AMAZON_CHAOS_DATA_DIR")
    return Path(configured) if configured else project_root() / "data"


def ensure_data_dirs() -> dict[str, Path]:
    root = data_root()
    paths = {name: root / name for name in ["raw", "external", "interim", "processed", "cache"]}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
