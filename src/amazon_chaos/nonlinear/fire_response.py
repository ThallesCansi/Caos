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


def panel(cfg, chosen, matched, series, variable: str) -> pd.DataFrame:
    """Pixel × composição com v, v(t+1), chuva de 96 dias e VPD em anomalia, queimado e
    depois (k > 0), para `coupling.response_change`."""
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
    cells = regions.cells(cfg).set_index("cell_id").loc[s.cell_id.unique()].reset_index()
    keys = s[["cell_id", "data", "dia"]].drop_duplicates(["cell_id", "data"]).rename(
        columns={"data": "composicao"})
    atm = atmosphere(cfg, cells, keys)
    s = s.merge(atm.rename(columns={"composicao": "data"}), on=["cell_id", "data"], how="left")
    s = s.sort_values(["id", "data"])
    s["v"] = _anomaly(s, "valor")
    s["h"] = _anomaly(s, "chuva_96d")
    s["d"] = _anomaly(s, "vpd")
    s["v_next"] = s.groupby("id").v.shift(-1)
    s["k"] = F.composite_index(s.data, s.mes)
    s = s[s.k.between(-F.RULES["pre_composites"], F.RULES["post_composites"]) & (s.k != 0)]
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
