"""Leitura e resumo do lote de descritores por célula (cadernos 07 e 08).

A correção para múltiplos testes segue o pré-registro (D-010): Benjamini–Hochberg dentro
de cada descritor, sobre as células, separadamente por região × variável × janela. A
comparação com α usa uma tolerância numérica: com 39 substitutas, o menor p bilateral é
exatamente 2/40 = 0,05, e o arredondamento da correção (0,05000000001) não pode decidir o
resultado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from amazon_chaos import regions
from amazon_chaos.nonlinear.batch import output_dir
from amazon_chaos.nonlinear.suite import load_spec

TOLERANCE = 1e-9
NAMES = {"lyapunov": "Lyapunov (Rosenstein)", "rqa_det": "RQA · determinismo",
         "rqa_lam": "RQA · laminaridade", "d2": "Dimensão de correlação",
         "pe_entropy": "Entropia de permutação", "pe_complexity": "Complexidade estatística",
         "asymmetry": "Assimetria temporal", "prediction": "Erro de previsão não linear",
         "variance": "Variância (EWS)", "ar1": "Autocorrelação (EWS)"}
VARIABLES = {"t2m": "temperatura", "vpd": "déficit de pressão de vapor"}
WINDOWS = {"2001_2024": "2001–2024", "2001_2012": "2001–2012", "2013_2024": "2013–2024"}


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    out = np.full(len(p), np.nan)
    ok = np.isfinite(p)
    if ok.any():
        out[ok] = multipletests(p[ok], method="fdr_bh")[1]
    return out


def load(cfg, spec=None) -> pd.DataFrame:
    """Todas as linhas do lote da região, com q de BH e o indicador de rejeição."""
    spec = spec or load_spec()
    table = pd.read_parquet(output_dir(cfg, spec) / "descritores.parquet")
    alpha = spec["surrogates"]["alpha"]
    keys = ["variable", "window", "kind", "descriptor"]
    tested = table.kind.isin(["teste", "ews"])
    table.loc[tested, "q"] = table[tested].groupby(keys).pvalue.transform(
        lambda s: benjamini_hochberg(s.to_numpy()))
    table["rejects"] = table.q <= alpha + TOLERANCE
    families = {d: f for f, ds in spec["families"].items() for d in ds}
    table["family"] = table.descriptor.map(families).fillna("ews")
    table["region"] = cfg["slug"]
    return table


def with_cells(cfg, table: pd.DataFrame):
    """Junta as linhas à geometria (recortada) e à fração da célula dentro da bacia."""
    cells = regions.cells(cfg)[["cell_id", "latitude", "longitude", "weight_km2", "area_km2",
                                "geometry"]]
    cells = cells.assign(basin_fraction=cells.weight_km2 / cells.area_km2)
    return cells.merge(table, on="cell_id")


def summary(table: pd.DataFrame) -> pd.DataFrame:
    """Fração de células que rejeitam H0 e z mediano, por descritor, variável e janela."""
    tests = table[table.kind == "teste"]
    out = (tests.groupby(["family", "descriptor", "variable", "window"])
           .agg(celulas=("cell_id", "nunique"), rejeitam=("rejects", "mean"),
                z_mediano=("z", "median"), z_p10=("z", lambda z: z.quantile(0.1)),
                z_p90=("z", lambda z: z.quantile(0.9)))
           .reset_index())
    order = {"primary": 0, "secondary": 1, "exploratory": 2}
    return out.sort_values(["family", "descriptor"], key=lambda s: s.map(order).fillna(s))


def sensitivity(table: pd.DataFrame) -> pd.DataFrame:
    """Valor de cada descritor na grade (τ, m) relativo ao valor com os parâmetros da regra."""
    base = table[(table.kind == "teste") & (table.window == "2001_2024")][
        ["cell_id", "variable", "descriptor", "tau", "m", "observed"]]
    grid = table[table.kind == "sensibilidade"][
        ["cell_id", "variable", "descriptor", "tau", "m", "observed"]]
    merged = grid.merge(base, on=["cell_id", "variable", "descriptor"], suffixes=("", "_base"))
    merged["variante"] = np.where(merged.tau != merged.tau_base,
                                  "τ = " + merged.tau.astype(int).astype(str),
                                  "m = m₀ " + np.where(merged.m > merged.m_base, "+ 1", "− 1"))
    return merged


def block_bootstrap(cells: pd.DataFrame, column: str, *, block: float = 1.0, n: int = 999,
                    seed: int = 20261021) -> tuple[float, float, float]:
    """Média de `column` sobre as células e IC 95% por bootstrap em blocos espaciais.

    Análise complementar (D-013): células vizinhas são correlacionadas, então reamostramos
    blocos de `block` graus inteiros, não células isoladas.
    """
    blocks = (np.floor(cells.latitude / block).astype(int).astype(str) + "_"
              + np.floor(cells.longitude / block).astype(int).astype(str))
    values = cells[column].astype(float).to_numpy()
    groups = pd.Series(values).groupby(blocks.to_numpy())
    sums, counts = groups.sum().to_numpy(), groups.size().to_numpy()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(sums), size=(n, len(sums)))
    boot = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return float(values.mean()), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def global_rejection(table: pd.DataFrame, cfg, alpha: float = 0.05) -> pd.DataFrame:
    """Fração de células com p ≤ α (sem correção), com IC por blocos, por descritor."""
    g = with_cells(cfg, table[table.kind.isin(["teste", "ews"])])
    g["raw"] = g.pvalue <= alpha + TOLERANCE
    rows = []
    for (kind, desc, var, win), part in g.groupby(["kind", "descriptor", "variable", "window"]):
        mean, lo, hi = block_bootstrap(part, "raw")
        rows.append({"kind": kind, "descriptor": desc, "variable": var, "window": win,
                     "fracao": mean, "ic_inf": lo, "ic_sup": hi,
                     "acima_do_acaso": lo > alpha, "celulas": len(part)})
    return pd.DataFrame(rows)
