from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(directory: str | Path) -> pd.DataFrame:
    root = Path(directory)
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != ".gitkeep"):
        stat = path.stat()
        rows.append(
            {
                "relative_path": str(path.relative_to(root)),
                "size_bytes": stat.st_size,
                "sha256": sha256_file(path),
                "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return pd.DataFrame(rows)
