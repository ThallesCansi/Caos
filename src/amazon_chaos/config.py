"""Configurações versionadas: `configs/study.yaml` (comum) + `configs/regions/<slug>.yaml`."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from amazon_chaos.paths import project_root


def load_config(path: str | Path) -> dict[str, Any]:
    """Lê um YAML que precisa conter um mapeamento."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"A configuração precisa ser um mapeamento: {path}")
    return data


def merge(base: dict, override: dict) -> dict:
    """Mescla recursiva; o valor de `override` vence, e listas são substituídas inteiras."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def regions_dir(root: str | Path | None = None) -> Path:
    return Path(root or project_root()) / "configs" / "regions"


def list_regions(root: str | Path | None = None) -> list[str]:
    return sorted(p.stem for p in regions_dir(root).glob("*.yaml") if not p.stem.startswith("_"))


def load_region(region: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    """Configuração completa de uma região, pelo slug (`xingu`) ou pelo caminho do YAML.

    Preenche os caminhos padrão `data/external/<slug>/limite.geojson` e
    `data/external/<slug>/contexto`, a menos que o YAML da região os defina.
    """
    root = Path(root or project_root())
    path = Path(region)
    if path.suffix not in {".yaml", ".yml"}:
        path = regions_dir(root) / f"{region}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Região desconhecida: {region}. Disponíveis: {', '.join(list_regions(root))}"
        )
    cfg = merge(load_config(root / "configs" / "study.yaml"), load_config(path))
    slug = cfg.setdefault("slug", path.stem)
    cfg.setdefault("region_name", cfg.get("name", slug))
    for key in ("name", "experiment_id", "boundary", "spatial"):
        if key not in cfg:
            raise ValueError(f"{path}: campo obrigatório ausente: {key}")
    for key in ("area", "pilot_point"):
        if key not in cfg["spatial"]:
            raise ValueError(f"{path}: campo obrigatório ausente: spatial.{key}")
    spatial = cfg["spatial"]
    if cfg["boundary"]["source"] == "bhb250":
        spatial.setdefault("basin_source", f"data/external/{slug}/limite.geojson")
    elif cfg["boundary"]["source"] != "bbox":
        raise ValueError(f"{path}: boundary.source deve ser 'bhb250' ou 'bbox'")
    spatial.setdefault("context_dir", f"data/external/{slug}/contexto")
    return cfg
