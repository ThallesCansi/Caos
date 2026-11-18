"""A floresta depois do fogo (D-031, etapa 3): alteração, recuperação e resposta ao clima.

Lê os episódios e candidatos de `features.fire_episodes`, os pontos baixados do AppEEARS
(`fogo_pontos`), pareia 3 controles por episódio, calcula Δ(k) com o IC por bootstrap de
episódios agrupados por célula ERA5 e estima a mudança na resposta da vegetação à chuva
acumulada e ao VPD depois do fogo.

Chamado por `amazon-chaos vegetation fire <região>`; com `--local`, lê a variante da
subamostra (`fogo_subamostra/`, pontos tirados dos cubos de área).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.features import fire_episodes as F
from amazon_chaos.io.appeears import task_dir
from amazon_chaos.nonlinear import coupling as C
from amazon_chaos.nonlinear.batch import _commit


def folder(cfg, local: bool = False) -> Path:
    base = regions.processed_dir(cfg) / "vegetacao"
    return base / "fogo_subamostra" if local else base


def points(chosen: pd.DataFrame, pool: pd.DataFrame) -> pd.DataFrame:
    """Episódios e candidatos como pontos (`id`, `lat`, `lon`)."""
    return pd.concat([chosen.rename(columns={"episodio": "id"})[["id", "lat", "lon"]],
                      pool.rename(columns={"candidato": "id"})[["id", "lat", "lon"]]],
                     ignore_index=True)


def _anomaly(frame: pd.DataFrame, column: str) -> pd.Series:
    slot = (frame.data.dt.dayofyear - 1) // 8
    g = frame.groupby([frame.id, slot])[column]
    # o LAI vem em passos de 0,1: um pixel pode repetir o valor em todos os anos de uma
    # composição, e o desvio nulo daria infinito
    return (frame[column] - g.transform("mean")) / g.transform("std").replace(0, np.nan)


def panel(cfg, chosen, matched, series, variable: str, burn: pd.Series | None = None,
          atm: pd.DataFrame | None = None) -> pd.DataFrame:
    """Pixel × composição com v, v(t+1), chuva de 96 dias e VPD em anomalia, queimado e
    depois (k > 0), para `coupling.response_change`.

    Correção da D-033: v(t+1) só existe entre composições consecutivas do mesmo lado da
    queima (antes, era tomado antes de retirar k = 0, e a transição de k = −1 levava a
    própria queima como resposta). Com `burn` (episódio → dia da queima), k conta desde a
    composição que contém esse dia; sem ele, desde a primeira do mês (regra da D-031)."""
    from amazon_chaos.nonlinear.vegetation_dynamics import atmosphere

    s = series[series.variavel == variable].copy()
    ndmi = series[series.variavel == "ndmi"][["id", "data", "dia_obs"]]
    s = s.drop(columns="dia_obs", errors="ignore").merge(ndmi, on=["id", "data"], how="left")
    pairs = pd.concat([chosen[["episodio", "cell_id", "mes"]].assign(id=chosen.episodio,
                                                                      queimado=1),
                       matched.merge(chosen[["episodio", "cell_id", "mes"]], on="episodio")
                       .rename(columns={"controle": "id"}).assign(queimado=0)])
    s = s.merge(pairs[["id", "episodio", "cell_id", "mes", "queimado"]], on="id")
    day = pd.to_datetime(s.data.dt.year.astype(str), format="%Y") + pd.to_timedelta(
        s.dia_obs - 1, unit="D")
    s["dia"] = day.where(s.dia_obs.notna() & (day >= s.data - pd.Timedelta(days=1)),
                         s.data + pd.Timedelta(days=4))
    if atm is None:
        cells = regions.cells(cfg).set_index("cell_id").loc[s.cell_id.unique()].reset_index()
        keys = s[["cell_id", "data", "dia"]].drop_duplicates(["cell_id", "data"]).rename(
            columns={"data": "composicao"})
        atm = atmosphere(cfg, cells, keys).rename(columns={"composicao": "data"})
    s = s.merge(atm[["cell_id", "data", "vpd", "chuva_96d"]], on=["cell_id", "data"],
                how="left")
    s["v"] = _anomaly(s, "valor")
    s["h"] = _anomaly(s, "chuva_96d")
    s["d"] = _anomaly(s, "vpd")
    if burn is None:
        s["k"] = F.composite_index(s.data, s.mes)
    else:
        s["k"] = F.event_index(s.data, s.episodio.map(burn))
    s = s[s.k.between(-F.RULES["pre_composites"], F.RULES["post_composites"]) & (s.k != 0)]
    s = s.sort_values(["id", "episodio", "k"])
    nxt = s.groupby(["id", "episodio"])[["k", "v"]].shift(-1)
    same_side = np.sign(s.k) == np.sign(nxt.k)
    s["v_next"] = nxt.v.where((nxt.k == s.k + 1) & same_side)
    return s.assign(depois=(s.k > 0).astype(int), pixel=s.id, celula=s.cell_id)


def run(cfg, report=print, local: bool = False) -> Path:
    out = folder(cfg, local)
    chosen = pd.read_parquet(out / "episodios.parquet")
    pool = pd.read_parquet(out / "candidatos.parquet")
    if local:
        series = pd.read_parquet(out / "pontos.parquet").drop_duplicates(
            ["id", "data", "variavel"])  # extraídos antes de `vegetation.unique_time`
    else:
        files = sorted(task_dir(cfg, "fogo_pontos").glob("*/*results.csv"))
        if not files:
            raise FileNotFoundError("pontos ausentes: rode `amazon-chaos vegetation "
                                    "fetch-points`")
        series = F.point_series([pd.read_csv(f) for f in files])
    matched = F.match(chosen, pool, series)
    matched.to_parquet(out / "pareamento.parquet")
    clusters = chosen.set_index("episodio").cell_id
    summaries, recoveries, responses = [], {}, []
    for variable in ("lai", "ndmi"):
        burned, controls = F.delta_tables(chosen, matched, series, variable)
        delta = C.baci(burned, controls)
        summary, recovery = C.baci_summary(delta, clusters)
        summaries.append(summary.assign(variavel=variable))
        recoveries[variable] = recovery
        p = panel(cfg, chosen, matched, series, variable)
        responses.append(C.response_change(p).assign(variavel=variable))
        frame = ", subamostra" if local else ""
        report(f"🔥 Fogo (D-031{frame}) · {cfg['name']} · {variable}: "
               f"recuperação em k = {recovery}")
    pd.concat(summaries).to_parquet(out / "delta.parquet")
    pd.concat(responses).to_parquet(out / "resposta.parquet")
    (out / "fogo_execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "rules": F.LOCAL_RULES if local else F.RULES,
        "episodios": len(chosen),
        "pareados": int(matched.episodio.nunique()), "recuperacao_k": recoveries,
        "commit": _commit(), "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, default=str))
    return out


# ── memória e sensibilidade (D-033) ──────────────────────────────────────────

MEMORY_RULES = {"version": 1, "window": [-138, 138], "min_controls": 2,
                "placebo_shift": 92, "bootstrap_curves": 999, "bootstrap_model": 499,
                "bootstrap_means": 999, "seed": 20261107, "drought_days": 60,
                "rain_days": 96, "year_groups": [[2003, 2009], [2010, 2015], [2016, 2021]]}
# variante → (série, controles, tempo, k excluídos, deslocamento do placebo de data)
VARIANTS = {
    "principal": ("pontos", "pareados", "queima", (0,), 0),
    "margem": ("pontos", "pareados", "queima", (-1, 0, 1), 0),
    "regra_antiga": ("pontos", "pareados", "mes", (0,), 0),
    "estrita": ("pontos_estrito", "pareados", "queima", (0,), 0),
    "sorteados": ("pontos", "sorteados", "queima", (0,), 0),
    "placebo_unidade": ("pontos", "unidade", "queima", (0,), 0),
    "placebo_data": ("pontos", "pareados", "queima", (0,), MEMORY_RULES["placebo_shift"]),
}


def memory_dir(cfg) -> Path:
    return folder(cfg, local=True) / "memoria"


def _wide(series: pd.DataFrame, variable: str) -> pd.DataFrame:
    s = series[series.variavel == variable]
    return s.pivot_table(index="data", columns="id", values="valor", aggfunc="first")


def pairings(chosen, matched, pool, seed=MEMORY_RULES["seed"]) -> dict[str, dict]:
    """Por arranjo: episódio → (pixel tratado como queimado, controles)."""
    rng = np.random.default_rng(seed)
    out = {"pareados": {}, "sorteados": {}, "unidade": {}}
    for ep in chosen.episodio:
        m = matched[matched.episodio == ep].sort_values("distancia").controle.tolist()
        if not m:
            continue
        out["pareados"][ep] = (ep, m)
        cands = pool[pool.episodio == ep].candidato.tolist()
        out["sorteados"][ep] = (ep, list(rng.choice(cands, min(3, len(cands)), replace=False)))
        if len(m) == 3:
            out["unidade"][ep] = (m[0], m[1:])
    return out


def differences(wide: pd.DataFrame, pairs: dict, events: dict, *, timing: str = "queima",
                shift: int = 0, exclude=(0,), min_controls: int = 2) -> pd.DataFrame:
    """δ = queimado − média dos controles por episódio e composição, com k."""
    lo, hi = MEMORY_RULES["window"]
    dates = wide.index
    rows = []
    for ep, (treated, controls) in pairs.items():
        controls = [c for c in controls if c in wide]
        if treated not in wide or not controls:
            continue
        if timing == "queima":
            k = F.event_index(dates, events["queima"][ep])
        else:
            k = F.composite_index(dates, events["mes"][ep])
        sel = (k >= lo) & (k <= hi)
        k = k[sel] + shift
        m = wide[controls].to_numpy()[sel]
        n = np.isfinite(m).sum(axis=1)
        with np.errstate(invalid="ignore"):
            vc = np.where(n > 0, np.nansum(m, axis=1) / np.maximum(n, 1), np.nan)
        vq = wide[treated].to_numpy()[sel]
        need = min(min_controls, len(controls))
        rows.append(pd.DataFrame({"episodio": ep, "data": dates[sel], "k": k,
                                  "dif": np.where(n >= need, vq - vc, np.nan)}))
    out = pd.concat(rows, ignore_index=True)
    out = out[~out.k.isin(exclude)]
    return out.dropna(subset=["dif"])


def composite_atmosphere(cfg, cell_ids, dates) -> pd.DataFrame:
    """Chuva de 32 e 96 dias e VPD de 8 dias no meio de cada composição, em anomalia
    padronizada por célula e posição no ano (2001–2024)."""
    from amazon_chaos.nonlinear.vegetation_dynamics import atmosphere

    cells = regions.cells(cfg).set_index("cell_id").loc[list(cell_ids)].reset_index()
    keys = pd.DataFrame([(c, d) for c in cell_ids for d in dates],
                        columns=["cell_id", "composicao"])
    keys["dia"] = keys.composicao + pd.Timedelta(days=4)
    atm = atmosphere(cfg, cells, keys).rename(columns={"composicao": "data"})
    slot = (atm.data.dt.dayofyear - 1) // 8
    for col in ("vpd", "chuva_32d", "chuva_96d"):
        g = atm.groupby([atm.cell_id, slot])[col]
        atm[f"{col}_z"] = (atm[col] - g.transform("mean")) / g.transform("std")
    return atm


def antecedent_drought(cfg, chosen, burn: pd.Series) -> pd.DataFrame:
    """Sₑ: anomalia diária do VPD (por célula e mês do calendário, 2001–2024) média nos 60
    dias antes da queima; e a anomalia da chuva do CHIRPS acumulada nos 96 dias antes."""
    from amazon_chaos.nonlinear.batch import load_cubes
    from amazon_chaos.nonlinear.precip import load_series

    cube = load_cubes(cfg, {"vpd": "vpd_kpa_mean"})["vpd"]
    rain = load_series(cfg, "precip_chirps")
    cells = regions.cells(cfg).set_index("cell_id")
    days, window = MEMORY_RULES["drought_days"], MEMORY_RULES["rain_days"]
    rows = []
    for cell, eps in chosen.groupby("cell_id"):
        c = cells.loc[cell]
        vpd = cube.sel(latitude=c.latitude, longitude=c.longitude).to_series()
        vpd.index = pd.DatetimeIndex(vpd.index).normalize()
        vpd = vpd["2001":"2024"]
        g = vpd.groupby(vpd.index.month)
        vz = (vpd - g.transform("mean")) / g.transform("std")
        acc = rain[cell].rolling(window, min_periods=int(0.8 * window)).sum()["2001":"2024"]
        ga = acc.groupby(acc.index.month)
        az = (acc - ga.transform("mean")) / ga.transform("std")
        for ep in eps.episodio:
            day = pd.Timestamp(burn[ep])
            before = day - pd.Timedelta(days=1)
            rows.append({"episodio": ep,
                         "seca_vpd": vz[day - pd.Timedelta(days=days):before].mean(),
                         "seca_chuva": az.get(before, np.nan)})
    return pd.DataFrame(rows)


def _curve_rows(change, clusters, n, label):
    summary, recovery = C.baci_summary(change[["episodio", "k", "delta"]], clusters, n=n,
                                       seed=MEMORY_RULES["seed"])
    return summary.assign(**label, recuperacao_k=recovery)


def memory_run(cfg, report=print) -> Path:
    """D-033 numa bacia: datas da queima, curvas, métricas por episódio, modelo de
    sensibilidade com as variantes, seca antecedente e o painel da D-031 corrigido."""
    base = folder(cfg, local=True)
    out = memory_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    chosen = pd.read_parquet(base / "episodios.parquet")
    pool = pd.read_parquet(base / "candidatos.parquet")
    matched = pd.read_parquet(base / "pareamento.parquet")
    started = datetime.now(UTC)

    dates_path = out / "datas_queima.parquet"
    if dates_path.exists():
        burn = pd.read_parquet(dates_path).set_index("episodio").data_queima
    else:
        burn = F.burn_dates(cfg, chosen)
        burn.reset_index().to_parquet(dates_path)
    shift = pd.Series(F.composite_index(burn.to_numpy(), chosen.set_index("episodio")
                                        .mes.reindex(burn.index).to_numpy()),
                      index=burn.index, name="k_antigo_da_queima")
    report(f"🔥 Memória do fogo (D-033) · {cfg['name']}: {len(burn)} datas de queima; "
           f"composição da queima no k antigo: {shift.value_counts().sort_index().to_dict()}")

    series = {"pontos": pd.read_parquet(base / "pontos.parquet").drop_duplicates(
        ["id", "data", "variavel"])}
    strict = base / "pontos_estrito.parquet"
    if strict.exists():
        series["pontos_estrito"] = pd.read_parquet(strict).drop_duplicates(
            ["id", "data", "variavel"])
    events = {"queima": burn, "mes": chosen.set_index("episodio").mes}
    arrangements = pairings(chosen, matched, pool)
    clusters = chosen.set_index("episodio").cell_id
    year = chosen.set_index("episodio").ano

    all_dates = pd.DatetimeIndex(sorted(series["pontos"].data.unique()))
    atm_path = out / "atmosfera.parquet"
    if atm_path.exists():
        atm = pd.read_parquet(atm_path)
    else:
        atm = composite_atmosphere(cfg, chosen.cell_id.unique(), all_dates)
        atm.to_parquet(atm_path)
    report(f"🌦️ Memória do fogo · {cfg['name']}: atmosfera alinhada às composições")

    curves, metrics, models = [], [], []
    for variable in ("lai", "ndmi"):
        wides = {k: _wide(v, variable) for k, v in series.items()}
        for name, (source, arrangement, timing, exclude, pshift) in VARIANTS.items():
            if source not in wides:
                continue
            diff = differences(wides[source], arrangements[arrangement], events,
                               timing=timing, shift=pshift,
                               exclude=exclude)
            if name == "placebo_data":
                diff = diff[diff.k.between(-46, 46)]
            diff = diff.assign(cell_id=diff.episodio.map(clusters))
            label = {"variavel": variable, "variante": name}
            for seasonal in (False, True):
                bl = "sazonal" if seasonal else "media_pre"
                change = C.baseline_change(diff, seasonal=seasonal)
                if name in ("principal", "placebo_unidade", "placebo_data", "regra_antiga"):
                    curves.append(_curve_rows(change, clusters,
                                              MEMORY_RULES["bootstrap_curves"],
                                              label | {"linha_base": bl}))
                m = C.memory_metrics(change).assign(**label, linha_base=bl)
                metrics.append(m)
            panel_frame = diff.merge(atm[["cell_id", "data", "vpd_z", "chuva_96d_z",
                                          "chuva_32d_z"]], on=["cell_id", "data"], how="left")
            panel_frame = panel_frame.rename(columns={"vpd_z": "d", "chuva_96d_z": "h"})
            specs = {name: {}}
            if name == "principal":
                specs |= {"depois_1o_ano": {"post_start": 47},
                          "chuva_32d": {"rain": "chuva_32d_z"}}
            if name == "placebo_data":
                specs = {name: {"window": (-46, 46), "bins": C.POST_BINS[:3]}}
            for spec_name, kw in specs.items():
                f = panel_frame
                if kw.pop("rain", None):
                    f = f.drop(columns="h").rename(columns={"chuva_32d_z": "h"})
                res = C.sensitivity_model(f, n_boot=MEMORY_RULES["bootstrap_model"],
                                          seed=MEMORY_RULES["seed"], **kw)
                models.append(res.assign(variavel=variable, variante=spec_name))
            report(f"📊 Memória do fogo · {cfg['name']} · {variable}: variante {name} pronta")

    metrics = pd.concat(metrics, ignore_index=True)
    metrics["cell_id"] = metrics.episodio.map(clusters)
    metrics["ano"] = metrics.episodio.map(year)
    drought = antecedent_drought(cfg, chosen, burn)
    v_pre = {}
    for variable in ("lai", "ndmi"):
        w = _wide(series["pontos"], variable)
        v_pre[variable] = pd.Series({ep: w[ep][(w.index < burn[ep])
                                               & (w.index >= burn[ep] - pd.DateOffset(years=1))]
                                     .mean() for ep in burn.index if ep in w})
    drought.to_parquet(out / "seca.parquet")
    metrics = metrics.merge(drought, on="episodio", how="left")
    metrics["v_pre"] = [v_pre[v].get(e, np.nan) for v, e in zip(metrics.variavel,
                                                                 metrics.episodio, strict=True)]
    metrics["estacao_seca"] = metrics.episodio.map(burn).dt.month.between(7, 10).astype(float)
    metrics["bacia"] = cfg["slug"]
    metrics.to_parquet(out / "metricas.parquet")
    pd.concat(curves, ignore_index=True).to_parquet(out / "curvas.parquet")
    pd.concat(models, ignore_index=True).to_parquet(out / "sensibilidade.parquet")
    report(f"🧮 Memória do fogo · {cfg['name']}: refazendo o painel da D-031 com as correções")

    fixed = []
    for variable in ("lai", "ndmi"):
        for label, b in (("corrigido", burn), ("so_transicoes", None)):
            p = panel(cfg, chosen, matched, series["pontos"], variable, burn=b)
            fixed.append(C.response_change(p).assign(variavel=variable, versao=label))
    pd.concat(fixed, ignore_index=True).to_parquet(out / "painel_corrigido.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "rules": MEMORY_RULES, "variants": list(VARIANTS),
        "estrita": "pontos_estrito" in series, "k_antigo_da_queima":
            shift.value_counts().sort_index().to_dict(), "commit": _commit(),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds")}, indent=2,
        default=str))
    return out


def strict_points(cfg) -> Path:
    """Os pontos de episódios e candidatos de novo dos cubos, com a qualidade estrita."""
    base = folder(cfg, local=True)
    chosen = pd.read_parquet(base / "episodios.parquet")
    pool = pd.read_parquet(base / "candidatos.parquet")
    target = base / "pontos_estrito.parquet"
    F.cube_series(cfg, points(chosen, pool), strict=True).to_parquet(target)
    return target
