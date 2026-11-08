"""Episódios de fogo em floresta e os seus controles (D-031, etapa 3).

1. `episodes`: no MCD64A1 da bacia, pixels de floresta com a primeira queima depois de
   ao menos 2 anos sem queima, que continuam floresta por 2 anos e não queimam de novo em
   3 anos (as reincidências ficam marcadas); sorteio estratificado por ano.
2. `candidates`: para cada episódio, 10 pixels de floresta persistente nunca queimados na
   mesma célula ERA5, sorteados; o pareamento pelos 2 anos anteriores (D-031) é feito
   depois, com a vegetação desses pontos.
3. `point_payloads`: os pedidos de pontos ao AppEEARS (LAI e refletâncias) para episódios e
   candidatos, em grupos de anos de queima, cada um só com a janela que a análise usa.
4. `point_series`, `match` e `panels`: séries por ponto, os 3 controles pareados e as
   tabelas da Δ(k) e do painel de resposta.

Variante local (emenda de 02/11, só pela fila do AppEEARS, que deixou os pedidos de pontos
parados por mais de 40 h): `episodes(..., only=...)` sorteia episódios e candidatos só nas
células da subamostra das etapas 1 e 2, e `cube_series` lê a vegetação desses pontos nos
cubos de área já baixados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.features import vegetation as V

RULES = {"version": 1, "quiet_years_before": 2, "forest_years_after": 2,
         "reburn_years": 3, "years": [2003, 2021], "per_basin": 300, "candidates": 10,
         "controls": 3, "seed": 20261031, "pre_composites": 46, "post_composites": 138}
LOCAL_RULES = RULES | {"version": 2, "frame": "subamostra"}


def _fire_grid(cfg):
    import xarray as xr

    from amazon_chaos.io.appeears import task_dir

    files = sorted(task_dir(cfg, "fogo").glob("*.nc"))
    return xr.open_mfdataset(files, combine="by_coords")


def _annual_forest(cfg, lat, lon) -> dict[int, np.ndarray]:
    """Floresta por ano na grade do fogo: MCD12Q1 (classe 2, IGBP), a máscara disponível
    na mesma grade de 500 m; o MapBiomas, se acessível, entra como confirmação."""
    import xarray as xr

    from amazon_chaos.io.appeears import task_dir

    files = sorted(task_dir(cfg, "cobertura").glob("*.nc"))
    out = {}
    with xr.open_mfdataset(files, combine="by_coords") as ds:
        rows, cols = V._nearest(lat, ds.lat.values), V._nearest(lon, ds.lon.values)
        for k in range(ds.sizes["time"]):
            year = V._when(ds.time.values[k]).year
            out[year] = (ds.LC_Type1.isel(time=k).values == V.EVERGREEN_FOREST)[
                np.ix_(rows, cols)]
    return out


def burn_history(cfg) -> tuple[np.ndarray, list[pd.Timestamp], np.ndarray, np.ndarray]:
    """(queimou[t, i, j], meses, lat, lon) do MCD64A1."""
    with _fire_grid(cfg) as ds:
        months = [V._when(t) for t in ds.time.values]
        stack = np.zeros((len(months), ds.sizes["lat"], ds.sizes["lon"]), bool)
        for k in range(len(months)):
            step = ds.isel(time=k).load()
            stack[k] = V.burned(step.Burn_Date.values, step.QA.values)
        return stack, months, ds.lat.values, ds.lon.values


def episodes(cfg, rules=RULES, only=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(episódios sorteados, candidatos a controle), com célula ERA5, ponto e mês.
    `only`: se dado, só os pixels dessas células ERA5 entram (variante local)."""
    from amazon_chaos.preprocess.zonal import grid_cell_index

    stack, months, lat, lon = burn_history(cfg)
    forest = _annual_forest(cfg, lat, lon)
    first_year, last_year = min(forest), max(forest)
    cells = regions.cells(cfg).reset_index(drop=True)
    ids, _ = grid_cell_index(cells, lat, lon)
    if only is not None:
        allowed = np.r_[False, cells.cell_id.isin(list(only)).to_numpy()]
        ids = np.where(allowed[ids], ids, 0)
    years = np.array([m.year for m in months])
    quiet = 12 * rules["quiet_years_before"]
    rows = []
    for k in np.flatnonzero((years >= rules["years"][0]) & (years <= rules["years"][1])):
        y = years[k]
        hit = stack[k] & (ids > 0)
        if k >= quiet:
            hit &= ~stack[k - quiet:k].any(axis=0)
        else:
            continue
        before = forest.get(y - 1, forest[first_year])
        hit &= before
        if not hit.any():
            continue
        after = np.ones_like(hit)
        for j in range(1, rules["forest_years_after"] + 1):
            after &= forest.get(min(y + j, last_year), forest[last_year])
        reburn = stack[k + 1:k + 1 + 12 * rules["reburn_years"]].any(axis=0)
        for i, j in zip(*np.nonzero(hit), strict=True):
            rows.append({"lat": lat[i], "lon": lon[j], "i": i, "j": j, "mes": months[k],
                         "ano": y, "cell_id": cells.cell_id[ids[i, j] - 1],
                         "continua_floresta": bool(after[i, j]), "requeima": bool(reburn[i, j])})
    found = pd.DataFrame(rows)
    valid = found[found.continua_floresta & ~found.requeima]
    rng = np.random.default_rng(rules["seed"])
    per_year = max(1, rules["per_basin"] // max(1, valid.ano.nunique()))
    picks = [g.sample(min(len(g), per_year), random_state=rng.integers(1e9))
             for _, g in valid.groupby("ano")]
    chosen = pd.concat(picks).head(rules["per_basin"]).reset_index(drop=True)
    chosen.insert(0, "episodio", [f"{cfg['slug']}_{k:04d}" for k in range(len(chosen))])
    never = ~stack.any(axis=0)
    persistent = forest[first_year] & forest[last_year] & never & (ids > 0)
    pool = []
    for ep in chosen.itertuples():
        same = np.argwhere(persistent & (ids == ids[ep.i, ep.j]))
        if not len(same):
            continue
        pick = same[rng.choice(len(same), min(rules["candidates"], len(same)), replace=False)]
        pool += [{"episodio": ep.episodio, "candidato": f"{ep.episodio}_c{n}",
                  "lat": lat[a], "lon": lon[b], "cell_id": ep.cell_id}
                 for n, (a, b) in enumerate(pick)]
    summary = {"encontrados": len(found), "validos": len(valid),
               "requeima": int(found.requeima.sum()),
               "perdem_floresta": int((~found.continua_floresta).sum())}
    chosen.attrs["resumo"] = summary
    return chosen, pd.DataFrame(pool)


# o AppEEARS limita os valores por pedido (pontos × camadas × datas, ~3,5 milhões): cada
# grupo de anos de queima pede só de 2 anos antes (pareamento e linha de base) a 3 anos
# depois (k ≤ 138) da queima
MAX_VALUES = 1_500_000
YEARS_BEFORE, YEARS_AFTER = 2, 3


def point_groups(chosen: pd.DataFrame, pool: pd.DataFrame,
                 max_values: int = MAX_VALUES) -> list[tuple[int, int]]:
    """Anos de queima consecutivos agrupados enquanto o pedido cabe em `max_values`."""
    points = chosen.ano.value_counts().add(
        pool.merge(chosen[["episodio", "ano"]]).ano.value_counts(), fill_value=0)
    layers = len(V.VEGETATION_LAYERS)

    def values(years):
        span = years[-1] - years[0] + YEARS_BEFORE + YEARS_AFTER + 1
        return points[years].sum() * layers * 46 * span

    groups = [[]]
    for year in sorted(points.index):
        if groups[-1] and values([*groups[-1], year]) > max_values:
            groups.append([])
        groups[-1].append(year)
    return [(g[0], g[-1]) for g in groups if g]


def point_payloads(cfg, chosen: pd.DataFrame, pool: pd.DataFrame,
                   max_values: int = MAX_VALUES) -> dict[str, dict]:
    """Um pedido de pontos por grupo de anos de queima, com a chave `primeiro_último`."""
    out = {}
    for first, last in point_groups(chosen, pool, max_values):
        mine = chosen[chosen.ano.between(first, last)]
        theirs = pool[pool.episodio.isin(mine.episodio)]
        coords = [{"id": r.episodio, "category": "queimado", "latitude": float(r.lat),
                   "longitude": float(r.lon)} for r in mine.itertuples()]
        coords += [{"id": r.candidato, "category": "controle", "latitude": float(r.lat),
                    "longitude": float(r.lon)} for r in theirs.itertuples()]
        start = max(first - YEARS_BEFORE, 2001)
        end = min(last + YEARS_AFTER, 2024)
        out[f"{first}_{last}"] = {
            "task_type": "point", "task_name": f"tcc-caos-{cfg['slug']}-fogo-{first}-{last}",
            "params": {"dates": [{"startDate": f"01-01-{start}", "endDate": f"12-31-{end}"}],
                       "layers": [{"product": p, "layer": layer}
                                  for p, layer in V.VEGETATION_LAYERS],
                       "coordinates": coords}}
    return out


# ── depois do pedido de pontos ───────────────────────────────────────────────


def _column(frame: pd.DataFrame, layer: str) -> pd.Series:
    """A coluna do AppEEARS que termina no nome da camada (ex.: MOD15A2H_061_Lai_500m)."""
    match = [c for c in frame.columns if c.endswith(layer)]
    if not match:
        raise KeyError(layer)
    return pd.to_numeric(frame[match[0]], errors="coerce")


def point_series(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """LAI e NDMI filtrados por ponto e composição, dos CSV de pontos do AppEEARS."""
    out = []
    for f in frames:
        f = f.rename(columns=str)
        base = pd.DataFrame({"id": f["ID"], "data": pd.to_datetime(f["Date"])})
        if any(c.endswith("Lai_500m") for c in f.columns):
            lai = _column(f, "Lai_500m")
            ok = V.lai_ok(_column(f, "FparLai_QC")) & (lai <= 10)
            out.append(base.assign(variavel="lai", valor=lai.where(ok)))
        if any(c.endswith("sur_refl_b02") for c in f.columns):
            ok = V.reflectance_ok(_column(f, "sur_refl_state_500m"),
                                  _column(f, "sur_refl_qc_500m"), _column(f, "sur_refl_vzen"))
            index = V.ndmi(_column(f, "sur_refl_b02"), _column(f, "sur_refl_b06"))
            out.append(base.assign(variavel="ndmi", valor=np.where(ok, index, np.nan),
                                   dia_obs=_column(f, "sur_refl_day_of_year")))
    return pd.concat(out, ignore_index=True)


def cube_series(cfg, points: pd.DataFrame, strict: bool = False) -> pd.DataFrame:
    """LAI e NDMI filtrados de cada ponto (`id`, `lat`, `lon`) nos cubos de área das etapas 1
    e 2, no mesmo formato de `point_series`. Com `strict`, os filtros estritos da D-033."""
    lai_ok = V.lai_ok_strict if strict else V.lai_ok
    reflectance_ok = V.reflectance_ok_strict if strict else V.reflectance_ok
    refl, lai = V._open(cfg, "MOD09A1*.nc"), V._open(cfg, "MOD15A2H*.nc")
    ri, rj = V._nearest(points.lat.to_numpy(), refl.lat.values), V._nearest(
        points.lon.to_numpy(), refl.lon.values)
    li, lj = V._nearest(points.lat.to_numpy(), lai.lat.values), V._nearest(
        points.lon.to_numpy(), lai.lon.values)
    lai_times = {V._when(t): k for k, t in enumerate(lai.time.values)}
    ids, out = points.id.to_numpy(), []
    for k in range(refl.sizes["time"]):
        step = refl.isel(time=k).load()
        when = V._when(step.time.values)

        def at(name, s=step):
            return s[name].values[ri, rj]

        ok = reflectance_ok(at("sur_refl_state_500m"), at("sur_refl_qc_500m"),
                            at("sur_refl_vzen"))
        out.append(pd.DataFrame({"id": ids, "data": when, "variavel": "ndmi",
                                 "valor": np.where(ok, V.ndmi(at("sur_refl_b02"),
                                                              at("sur_refl_b06")), np.nan),
                                 "dia_obs": at("sur_refl_day_of_year").astype(float)}))
        if when in lai_times:
            s = lai.isel(time=lai_times[when]).load()
            value = s.Lai_500m.values[li, lj].astype(float)
            ok = lai_ok(s.FparLai_QC.values[li, lj]) & (value <= 10)
            out.append(pd.DataFrame({"id": ids, "data": when, "variavel": "lai",
                                     "valor": np.where(ok, value, np.nan)}))
    return pd.concat(out, ignore_index=True)


def _ordinal(dates) -> np.ndarray:
    """Posição da composição no calendário do MODIS (46 por ano, recomeçando em 1º de
    janeiro): a última do ano tem só 5 ou 6 dias, então contar dias / 8 repete k."""
    d = pd.DatetimeIndex(pd.to_datetime(dates))
    return (d.year * 46 + (d.dayofyear - 1) // 8).to_numpy()


def composite_index(dates, event) -> np.ndarray:
    """k: número de composições de 8 dias desde a primeira que começa no mês da queima
    (k = 0). `event` pode ser um mês só ou um por linha de `dates`."""
    start = pd.DatetimeIndex(pd.to_datetime(event) if np.ndim(event) else [event])
    start = start.to_period("M").to_timestamp()
    first = _ordinal(start) + ((start.dayofyear - 1) % 8 != 0)
    return _ordinal(dates) - np.asarray(first)


def burn_dates(cfg, chosen: pd.DataFrame) -> pd.Series:
    """Dia da queima de cada episódio (D-033): o `Burn_Date` do MCD64A1 no pixel (i, j) e
    no mês do episódio, como data."""
    with _fire_grid(cfg) as ds:
        position = {V._when(t): k for k, t in enumerate(ds.time.values)}
        days = [int(ds.Burn_Date.isel(time=position[pd.Timestamp(e.mes)], lat=int(e.i),
                                      lon=int(e.j)).values) for e in chosen.itertuples()]
    days = np.asarray(days)
    if not ((days >= 1) & (days <= 366)).all():
        raise ValueError("episódio sem dia de queima válido no MCD64A1")
    out = (pd.to_datetime(chosen.ano.astype(str), format="%Y")
           + pd.to_timedelta(days - 1, unit="D"))
    return pd.Series(out.to_numpy(), index=chosen.episodio, name="data_queima")


def event_index(dates, burn) -> np.ndarray:
    """k: composições MODIS desde a que contém o dia da queima (k = 0; D-033). `burn` pode
    ser uma data só ou uma por linha de `dates`."""
    burn = pd.DatetimeIndex(pd.to_datetime(burn) if np.ndim(burn) else [burn])
    return _ordinal(dates) - _ordinal(burn)


def match(chosen: pd.DataFrame, pool: pd.DataFrame, series: pd.DataFrame,
          controls: int = RULES["controls"]) -> pd.DataFrame:
    """Os `controls` candidatos mais próximos de cada episódio na média e na amplitude
    sazonal (percentis 90 − 10) de LAI e NDMI nos 2 anos antes do mês da queima,
    padronizadas entre os pontos do episódio."""
    rows = []
    for ep in chosen.itertuples():
        cands = pool[pool.episodio == ep.episodio].candidato.tolist()
        ids = [ep.episodio, *cands]
        start = pd.Timestamp(ep.mes) - pd.DateOffset(years=2)
        pre = series[series.id.isin(ids) & (series.data >= start)
                     & (series.data < pd.Timestamp(ep.mes))]
        stats = pre.groupby(["id", "variavel"]).valor.agg(
            media="mean", amplitude=lambda v: v.quantile(0.9) - v.quantile(0.1)).unstack()
        stats = stats.reindex(ids).dropna()
        if ep.episodio not in stats.index or len(stats) < 2:
            continue
        z = (stats - stats.mean()) / stats.std().replace(0, 1)
        dist = np.sqrt(((z.drop(index=ep.episodio) - z.loc[ep.episodio]) ** 2).sum(axis=1))
        best = dist.nsmallest(controls)
        rows += [{"episodio": ep.episodio, "controle": c, "distancia": d}
                 for c, d in best.items()]
    return pd.DataFrame(rows)


def delta_tables(chosen, matched, series, variable: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(queimados, controles) com episodio, k e v, prontos para `coupling.baci`."""
    burned, controls = [], []
    lo, hi = -RULES["pre_composites"], RULES["post_composites"]
    s = series[series.variavel == variable]
    for ep in chosen.itertuples():
        mine = s[s.id == ep.episodio]
        mine = mine.assign(k=composite_index(mine.data, ep.mes))
        burned.append(mine[mine.k.between(lo, hi)].assign(episodio=ep.episodio))
        for c in matched[matched.episodio == ep.episodio].controle:
            theirs = s[s.id == c]
            theirs = theirs.assign(k=composite_index(theirs.data, ep.mes))
            controls.append(theirs[theirs.k.between(lo, hi)].assign(episodio=ep.episodio))
    cols = ["episodio", "k", "valor"]
    return (pd.concat(burned)[cols].rename(columns={"valor": "v"}),
            pd.concat(controls)[cols].rename(columns={"valor": "v"}))
