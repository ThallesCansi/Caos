"""Perturbação × dinâmica por célula (caderno 08), como fixado no pré-registro (D-010).

Células: terra observada ≥ 50% e área dentro da bacia ≥ 50% (v2). Exposição principal:
perda antecedente de floresta, 1 − floresta em 2000 (MapBiomas). Resposta: z dos
descritores primários contra as substitutas, janela 2001–2024. Associação: Spearman,
bruta e parcial, com IC por bootstrap em blocos de 1° e o I de Moran dos resíduos. Os
controles são a latitude, a fração de água e a altitude do relevo do modelo ERA5, já
prevista no pré-registro. Longitudinal: mudança do descritor entre 2001–2012 e 2013–2024
contra a perda de floresta de 2001 a 2012; como sensibilidade (D-015), só nas células em que
a dimensão de imersão m é a mesma nas duas metades.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import rankdata, spearmanr
from scipy.stats import t as student_t
from statsmodels.stats.multitest import multipletests

from amazon_chaos import regions
from amazon_chaos.features.disturbance import out_dir
from amazon_chaos.nonlinear import results as R

EXPOSURES = {
    "perda_antecedente": "Perda antecedente (1 − floresta em 2000)",
    "perda_2000_2024": "Perda de floresta 2000–2024",
    "focos_100km2_ano_2003_2024": "Focos de fogo por 100 km² por ano",
    "mb_frequencia_fogo_media_2024": "Frequência de fogo 1985–2024",
    "prodes_acumulado_2024_frac": "Desmatamento PRODES acumulado até 2024",
    "prodes_ate_2007_frac": "Desmatamento PRODES até 2007",
    "mb_perda_floresta_2001_2012": "Perda de floresta 2001–2012",
    "perda_1990_2000": "Perda de floresta 1990–2000",
}
ROLE = {"perda_antecedente": "principal", "perda_2000_2024": "secundária",
        "focos_100km2_ano_2003_2024": "secundária",
        "mb_frequencia_fogo_media_2024": "secundária",
        "prodes_acumulado_2024_frac": "sensibilidade", "prodes_ate_2007_frac": "sensibilidade",
        "mb_perda_floresta_2001_2012": "longitudinal", "perda_1990_2000": "complementar"}


def cell_table(cfg, spec) -> pd.DataFrame:
    """Uma linha por célula: perturbação, controles, elegibilidade e z dos descritores."""
    dist = pd.read_parquet(out_dir(cfg) / "celulas.parquet")
    dist["perda_antecedente"] = 1 - dist.floresta_frac_2000
    dist["perda_2000_2024"] = dist.floresta_frac_2000 - dist.floresta_frac_2024
    dist["focos_100km2_ano_2003_2024"] = (10 * dist.focos_100km2_ano_2003_2012
                                          + 12 * dist.focos_100km2_ano_2013_2024) / 22
    table = R.load(cfg, spec)
    cells = R.with_cells(cfg, table[["cell_id"]].drop_duplicates())
    cells = cells.drop_duplicates("cell_id").set_index("cell_id")
    out = dist.join(cells[["basin_fraction", "area_km2", "geometry"]])
    rule = spec["cells"]
    out["fracao_terra"] = out.terra_km2_2000 / out.celula_km2
    out["elegivel"] = ((out.fracao_terra >= rule["min_land_fraction"])
                       & (out.basin_fraction >= rule["min_basin_fraction"]))
    static = xr.open_dataset(regions.processed_dir(cfg) / "era5_estatico.nc")
    static = static[["altitude_m", "cvh", "cvl"]].to_dataframe().reset_index()
    static = static.rename(columns={"cvh": "era5_veg_alta", "cvl": "era5_veg_baixa"})
    out = (out.reset_index().merge(static, on=["latitude", "longitude"], how="left")
           .set_index("cell_id"))
    tests = table[table.kind == "teste"]
    full = tests[tests.window == "2001_2024"].pivot_table(
        index="cell_id", columns=["variable", "descriptor"], values="z")
    full.columns = [f"z_{v}_{d}" for v, d in full.columns]
    first = tests[tests.window == "2001_2012"].pivot_table(
        index="cell_id", columns=["variable", "descriptor"], values="z")
    first.columns = [f"z12_{v}_{d}" for v, d in first.columns]
    observed = tests[tests.window == "2001_2024"].pivot_table(
        index="cell_id", columns=["variable", "descriptor"], values="observed")
    observed.columns = [f"obs_{v}_{d}" for v, d in observed.columns]
    null = tests[tests.window == "2001_2024"].pivot_table(
        index="cell_id", columns=["variable", "descriptor"], values="null_mean")
    null.columns = [f"nulo_{v}_{d}" for v, d in null.columns]
    delta = half_changes(tests)
    # a regra do FNN escolhe m em cada metade; quando muda, os descritores que dependem do
    # espaço de fases (DET, LAM, D2, Lyapunov) saltam junto (D-015)
    dims = tests[tests.window.isin(["2001_2012", "2013_2024"])].pivot_table(
        index="cell_id", columns=["variable", "window"], values="m", aggfunc="first")
    dm = pd.DataFrame({f"dm_{v}": dims[(v, "2013_2024")] - dims[(v, "2001_2012")]
                       for v in dims.columns.get_level_values(0).unique()})
    out["perda_1990_2000"] = out.floresta_frac_1990 - out.floresta_frac_2000
    return out.join(full).join(first).join(observed).join(null).join(delta).join(dm)


def half_changes(tests: pd.DataFrame) -> pd.DataFrame:
    """Valor observado de 2013–2024 menos o de 2001–2012, por célula, variável e descritor."""
    halves = tests[tests.window.isin(["2001_2012", "2013_2024"])].pivot_table(
        index="cell_id", columns=["variable", "descriptor", "window"], values="observed")
    pairs = sorted({(v, d) for v, d, _ in halves.columns})
    return pd.DataFrame({
        f"delta_{v}_{d}": halves[(v, d, "2013_2024")] - halves[(v, d, "2001_2012")]
        for v, d in pairs if (v, d, "2001_2012") in halves and (v, d, "2013_2024") in halves},
        index=halves.index)


DRY = (6, 7, 8, 9)
HALVES = {"2001_2012": ("2001", "2012"), "2013_2024": ("2013", "2024")}


def surface_table(cfg) -> pd.DataFrame:
    """Temperatura da superfície vista pelo MODIS e máxima do ar no ERA5, por célula.

    O LST diurno do MODIS é medido perto das 10h30 local, então a comparação natural no
    ERA5 é a máxima diária do ar a 2 m. As duas são médias da estação seca (junho a
    setembro), na janela completa e em cada metade, para a comparação longitudinal.
    """
    from amazon_chaos.regional import summarize

    folder = out_dir(cfg)
    clim = pd.read_parquet(folder / "modis_lst.parquet")
    yearly = pd.read_parquet(folder / "modis_lst_seca_anual.parquet")
    yearly.columns = yearly.columns.astype(int)
    out = clim.copy()
    for half, (first, last) in HALVES.items():
        cols = [y for y in yearly.columns if int(first) <= y <= int(last)]
        out[f"lst_seca_{half}"] = yearly[cols].mean(axis=1)
    summary = summarize(cfg)
    tmax = summary.cell_tmax.where(summary.month.dt.month.isin(DRY), drop=True)
    cells = regions.cells(cfg).set_index("cell_id")[["latitude", "longitude"]]

    def per_cell(da):
        frame = da.mean("month").to_dataframe(name="v").reset_index()
        return cells.reset_index().merge(frame, on=["latitude", "longitude"]).set_index(
            "cell_id").v

    out["era5_tmax_seca"] = per_cell(tmax.sel(month=slice("2001", "2024")))
    for half, (first, last) in HALVES.items():
        out[f"era5_tmax_seca_{half}"] = per_cell(tmax.sel(month=slice(first, last)))
    out["delta_lst_seca"] = out.lst_seca_2013_2024 - out.lst_seca_2001_2012
    out["delta_era5_tmax_seca"] = out.era5_tmax_seca_2013_2024 - out.era5_tmax_seca_2001_2012
    # skt e t2m do ERA5 às 10h30 solares (F2e, D-027), quando `era5 overpass` já rodou
    if (folder / "era5_passagem.parquet").exists():
        out = out.join(pd.read_parquet(folder / "era5_passagem.parquet"))
    return out


def _residual_ranks(y, controls):
    """Postos de y menos a parte explicada linearmente pelos postos dos controles."""
    ry = rankdata(y)
    if controls is None or controls.shape[1] == 0:
        return ry - ry.mean()
    X = np.column_stack([np.ones(len(ry))] + [rankdata(c) for c in controls.T])
    beta, *_ = np.linalg.lstsq(X, ry, rcond=None)
    return ry - X @ beta


def partial_spearman(x, y, controls=None) -> float:
    """Correlação de Spearman entre x e y depois de remover, dos postos, os controles."""
    rx, ry = _residual_ranks(x, controls), _residual_ranks(y, controls)
    return float(np.corrcoef(rx, ry)[0, 1])


def blocks(frame: pd.DataFrame, size: float = 1.0) -> np.ndarray:
    return (np.floor(frame.latitude / size).astype(int).astype(str) + "_"
            + np.floor(frame.longitude / size).astype(int).astype(str)).to_numpy()


def bootstrap_values(frame, func, *, size=1.0, n=999, seed=20261021) -> np.ndarray:
    """`func` em `n` reamostras de blocos espaciais inteiros."""
    labels = blocks(frame, size)
    groups = {b: np.flatnonzero(labels == b) for b in np.unique(labels)}
    keys = list(groups)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n):
        idx = np.concatenate([groups[keys[k]] for k in rng.integers(0, len(keys), len(keys))])
        values.append(func(frame.iloc[idx]))
    return np.array(values)


def block_bootstrap(frame, func, *, size=1.0, n=999, seed=20261021):
    """IC 95% de `func(frame)` reamostrando blocos espaciais inteiros."""
    values = bootstrap_values(frame, func, size=size, n=n, seed=seed)
    return float(np.nanquantile(values, 0.025)), float(np.nanquantile(values, 0.975))


def bootstrap_p(values) -> float:
    """p bilateral que corresponde ao IC percentil: o lado de zero com menos reamostras (D-028)."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    tail = min((v <= 0).sum(), (v >= 0).sum())
    return float(min(1.0, 2 * (tail + 1) / (len(v) + 1)))


def moran_i(values, latitude, longitude, radius=0.26) -> float:
    """I de Moran com vizinhança das 4 células ortogonais (distância ≤ 0,26°).

    A diagonal fica a 0,354°; com as 8 adjacentes (radius=0.36) o I cai cerca de 0,05 nos
    resultados do caderno 08, sem mudar a leitura.
    """
    v = np.asarray(values, float) - np.nanmean(values)
    lat, lon = np.asarray(latitude), np.asarray(longitude)
    d = np.hypot(lat[:, None] - lat[None, :], lon[:, None] - lon[None, :])
    w = ((d > 0) & (d <= radius)).astype(float)
    return float(len(v) / w.sum() * (v @ w @ v) / (v @ v))


CONTROLS = ("latitude", "agua_frac_2000", "altitude_m")


def associate(frame, exposure, response, controls=CONTROLS, *, block=1.0) -> dict:
    """Spearman bruto e parcial, IC por blocos e Moran dos resíduos da regressão nos postos."""
    data = frame[[exposure, response, "latitude", "longitude", *controls]].dropna()
    data = data.loc[:, ~data.columns.duplicated()]
    ctrl = data[list(controls)].to_numpy()
    rho = spearmanr(data[exposure], data[response]).statistic
    partial = partial_spearman(data[exposure].to_numpy(), data[response].to_numpy(), ctrl)

    def stat(sub):
        return partial_spearman(sub[exposure].to_numpy(), sub[response].to_numpy(),
                                sub[list(controls)].to_numpy())

    boot = bootstrap_values(data, stat, size=block)
    lo, hi = np.nanquantile(boot, 0.025), np.nanquantile(boot, 0.975)
    rx = _residual_ranks(data[exposure].to_numpy(), ctrl)
    ry = _residual_ranks(data[response].to_numpy(), ctrl)
    slope = (rx @ ry) / (rx @ rx)
    moran = moran_i(ry - slope * rx, data.latitude, data.longitude)
    return {"exposicao": exposure, "resposta": response, "celulas": len(data),
            "rho_bruto": float(rho), "rho_parcial": partial, "ic_inf": float(lo),
            "ic_sup": float(hi), "exclui_zero": bool(lo > 0 or hi < 0),
            "p_blocos": bootstrap_p(boot), "moran_residuos": moran}


# ── Inferência espacial (D-028) ──────────────────────────────────────────────

CORRELOGRAM_EDGES = np.arange(0, 5.0001, 0.25)


def _distances(latitude, longitude) -> np.ndarray:
    lat, lon = np.asarray(latitude, float), np.asarray(longitude, float)
    return np.hypot(lat[:, None] - lat[None, :], lon[:, None] - lon[None, :])


def correlogram(values, latitude, longitude, edges=CORRELOGRAM_EDGES) -> pd.DataFrame:
    """I de Moran em cada classe de distância (graus), com o número de pares ordenados."""
    v = np.asarray(values, float) - np.nanmean(values)
    d = _distances(latitude, longitude)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        w = ((d > lo) & (d <= hi)).astype(float)
        pairs = w.sum()
        moran = len(v) / pairs * (v @ w @ v) / (v @ v) if pairs else np.nan
        rows.append({"distancia": (lo + hi) / 2, "pares": int(pairs), "moran": float(moran)})
    return pd.DataFrame(rows)


def moran_test(values, latitude, longitude, *, n=999, seed=20261029, radius=0.26):
    """I de Moran e p unilateral (I maior que o esperado) por permutação entre células."""
    v = np.asarray(values, float) - np.nanmean(values)
    d = _distances(latitude, longitude)
    w = ((d > 0) & (d <= radius)).astype(float)
    scale = len(v) / w.sum()
    observed = scale * (v @ w @ v) / (v @ v)
    rng = np.random.default_rng(seed)
    null = np.array([scale * (p @ w @ p) / (p @ p) for p in
                     (rng.permutation(v) for _ in range(n))])
    return float(observed), float(((null >= observed).sum() + 1) / (n + 1))


def effective_n(x, y, latitude, longitude, width=0.5) -> float:
    """n efetivo da correlação entre x e y (Clifford, Richardson e Hémon, 1989).

    σ²(r) = Σ_k n_k ρ_x(k) ρ_y(k) / n², com classes de distância de largura `width` até a
    maior distância e o termo de distância zero (n_0 = n, ρ = 1); n' = 1 + 1/σ².
    """
    x = np.asarray(x, float) - np.mean(x)
    y = np.asarray(y, float) - np.mean(y)
    n = len(x)
    d = _distances(latitude, longitude)
    np.fill_diagonal(d, -1.0)
    var = float(n)
    sx, sy = x @ x / n, y @ y / n
    for lo in np.arange(0, d.max() + width, width):
        w = (d > lo) & (d <= lo + width)
        pairs = w.sum()
        if pairs:
            rx = (x @ (w * 1.0) @ x) / pairs / sx
            ry = (y @ (w * 1.0) @ y) / pairs / sy
            var += pairs * rx * ry
    var = max(var / n**2, 1 / n)
    return float(1 + 1 / var)


def spatial_inference(frame, exposure, response, controls=CONTROLS) -> dict:
    """Moran por permutação, n efetivo e p corrigido pela autocorrelação (D-028)."""
    data = frame[[exposure, response, "latitude", "longitude", *controls]].dropna()
    data = data.loc[:, ~data.columns.duplicated()]
    ctrl = data[list(controls)].to_numpy()
    rx = _residual_ranks(data[exposure].to_numpy(), ctrl)
    ry = _residual_ranks(data[response].to_numpy(), ctrl)
    r = float(np.corrcoef(rx, ry)[0, 1])
    slope = (rx @ ry) / (rx @ rx)
    moran, moran_p = moran_test(ry - slope * rx, data.latitude, data.longitude)
    n_eff = effective_n(rx, ry, data.latitude, data.longitude)
    t = r * np.sqrt(max(n_eff - 2, 1e-9) / (1 - r**2))
    p = float(2 * student_t.sf(abs(t), max(n_eff - 2, 1e-9)))
    return {"n_efetivo": n_eff, "p_n_efetivo": p, "moran_residuos": moran,
            "moran_p": moran_p}


def adjust(p, method: str) -> np.ndarray:
    """p ajustado para comparações múltiplas ("holm" ou "fdr_bh")."""
    return multipletests(np.asarray(p, float), method=method)[1]
