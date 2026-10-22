"""Pacote de visualização: configurações e dados processados para rodar os cadernos fora do
repositório (molab, colaboradores sem os dados brutos).

Os cadernos leem cerca de 145 MB de arquivos derivados (resumos do ERA5, perturbação por
célula, descritores, substitutas, gate e cartografia); os brutos, de vários gigabytes,
ficam no HPC. `make bundle` empacota esses derivados com `configs/` num zip publicado no
ramo `gh-pages` do repositório. Quando a biblioteca é instalada sem o repositório (não há
`configs/` na raiz), `ensure()` baixa o zip uma vez para o cache do usuário e aponta
`AMAZON_CHAOS_ROOT` para ele. Num clone com os dados, não faz nada.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from amazon_chaos import __version__
from amazon_chaos.paths import project_root

URL = os.getenv("AMAZON_CHAOS_BUNDLE_URL",
                "https://raw.githubusercontent.com/ThallesCansi/Caos/gh-pages/dados/caos-dados.zip")
NAME = "caos-dados.zip"
CONTENTS = [
    "configs",
    "data/external/xingu", "data/external/tapajos", "data/external/ibge_estados_minima.geojson",
    "data/external/ibge_estados_minima.json",
]
PER_EXPERIMENT = ["summary_1990_2024.nc", "basin_grid.geojson", "era5_estatico.nc",
                  "perturbacao", "descritores", "substitutas_bacia"]
EXPERIMENTS = ["xingu-era5-1990-2024", "tapajos-bacia-era5-1990-2024"]


def cache_dir() -> Path:
    base = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "amazon-chaos" / f"pacote-{__version__}"


def ensure() -> Path:
    """Raiz utilizável: o repositório, se tiver `configs/`, ou o pacote baixado."""
    root = project_root()
    if (root / "configs" / "regions").is_dir():
        return root
    target = cache_dir()
    if not (target / "configs" / "regions").is_dir():
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / NAME
            if URL.startswith("file://"):
                shutil.copy(URL.removeprefix("file://"), archive)
            else:
                urllib.request.urlretrieve(URL, archive)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(target)
    os.environ["AMAZON_CHAOS_ROOT"] = str(target)
    return target


def build(root: Path | None = None, out: Path | None = None) -> Path:
    """Gera o zip a partir de um clone com os dados processados."""
    root = Path(root or project_root())
    out = Path(out or root / "site" / "dados" / NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    paths = [root / p for p in CONTENTS]
    paths += [root / "data/processed" / e / f for e in EXPERIMENTS for f in PER_EXPERIMENT]
    gate = sorted((root / "data/processed/gate").glob("[0-9a-f]*/descritores.csv"))
    paths += [g.parent for g in gate]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"Falta para o pacote: {path.relative_to(root)}")
            files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
            for f in files:
                zf.write(f, f.relative_to(root))
    return out


if __name__ == "__main__":
    print(build())
