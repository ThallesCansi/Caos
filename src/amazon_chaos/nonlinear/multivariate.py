"""Temperatura e umidade específica juntas: estrutura conjunta além da linear (F2c, D-027).

Cada canal tem o seu (τ, m) pela regra, e o vetor conjunto concatena os dois atrasos.
Para cada alvo (t2m e q, horizonte 1), quatro previsores: só o próprio canal, só o outro,
os dois juntos e um VAR linear com os mesmos atrasos; os três primeiros por vizinhos (como
`statistics.nonlinear_prediction_error`) e por S-map (regras de F2g). As estatísticas são o
erro do previsor conjunto e o ganho (erro do melhor canal isolado − erro do conjunto).

As nulas preservam os dois espectros e o espectro cruzado: FT multivariada (Prichard e
Theiler, 1994; a mesma fase aleatória somada aos dois canais) e IAAFT multivariada
(Schreiber e Schmitz, 2000). Substitutas independentes por canal destruiriam a correlação
cruzada e rejeitariam por construção.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from amazon_chaos.nonlinear.smap import RULES as SMAP_RULES
from amazon_chaos.nonlinear.smap import _weighted_fit

NEIGHBORS = 5
TRAIN_FRACTION = 0.6


# ── substitutas multivariadas ───────────────────────────────────────────────


def multivariate_ft(data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """FT multivariada: a mesma fase aleatória em todos os canais (colunas)."""
    spectrum = np.fft.rfft(data, axis=0)
    n = len(data)
    stop = spectrum.shape[0] - 1 if n % 2 == 0 else spectrum.shape[0]
    phase = np.exp(1j * rng.uniform(0, 2 * np.pi, stop - 1))
    spectrum[1:stop] *= phase[:, None]
    return np.fft.irfft(spectrum, n=n, axis=0)


def multivariate_iaaft(data: np.ndarray, rng: np.random.Generator,
                       max_iter: int = 200) -> np.ndarray:
    """IAAFT multivariada (Schreiber e Schmitz, 2000).

    No passo espectral, cada frequência recebe as fases originais deslocadas por um mesmo
    ângulo α, o que mais se aproxima das fases atuais; isso fixa as amplitudes e as
    diferenças de fase (o espectro cruzado). No passo de postos, cada canal recebe os seus
    valores originais.
    """
    original = np.fft.rfft(data, axis=0)
    amplitude, phase0 = np.abs(original), np.angle(original)
    ordered = np.sort(data, axis=0)
    y = np.column_stack([rng.permutation(c) for c in data.T])
    for _ in range(max_iter):
        current = np.angle(np.fft.rfft(y, axis=0))
        num = (amplitude * np.sin(current - phase0)).sum(axis=1)
        den = (amplitude * np.cos(current - phase0)).sum(axis=1)
        alpha = np.arctan2(num, den)
        projected = amplitude * np.exp(1j * (phase0 + alpha[:, None]))
        projected[0] = original[0]
        z = np.fft.irfft(projected, n=len(data), axis=0)
        new = np.empty_like(y)
        for c in range(data.shape[1]):
            new[np.argsort(z[:, c], kind="stable"), c] = ordered[:, c]
        if np.array_equal(new, y):
            break
        y = new
    return y


# ── previsores ──────────────────────────────────────────────────────────────


def joint_vectors(data: np.ndarray, params: list[dict], horizon: int = 1):
    """Vetores de atraso de cada canal no mesmo instante t, e o índice t de cada linha."""
    span = max((p["m"] - 1) * p["tau"] for p in params)
    t = np.arange(span, len(data) - horizon)
    blocks = [np.column_stack([data[t - k * p["tau"], c] for k in range(p["m"])])
              for c, p in enumerate(params)]
    return blocks, t


def _nn(lib_x, lib_y, query):
    _, idx = cKDTree(lib_x).query(query, k=NEIGHBORS)
    return lib_y[np.asarray(idx).reshape(len(query), NEIGHBORS)].mean(axis=1)


def _smap(lib_x, lib_y, lib_t, query, theiler, loo_step):
    rows = np.arange(0, len(lib_x), loo_step)
    mask = np.abs(lib_t[rows][:, None] - lib_t[None, :]) > theiler
    scores = []
    for theta in SMAP_RULES["thetas"]:
        pred = _weighted_fit(lib_x, lib_y[:, None], lib_x[rows], theta, mask=mask)[:, 0]
        scores.append(np.sqrt(np.mean((pred - lib_y[rows]) ** 2)))
    scores = np.array(scores)
    theta = SMAP_RULES["thetas"][int(np.flatnonzero(scores <= scores.min())[0])]
    return _weighted_fit(lib_x, lib_y[:, None], query, theta)[:, 0], theta


def forecast_errors(data: np.ndarray, params: list[dict], theiler: int, *,
                    smap: bool = True, loo_step: int = 1) -> dict[str, float]:
    """Erros (RMSE / desvio do treino) de cada previsor, para cada alvo (canal)."""
    blocks, t = joint_vectors(data, params)
    cutoff = int(TRAIN_FRACTION * len(data))
    train = t + 1 + theiler < cutoff
    test = t >= cutoff
    out = {}
    for target in range(data.shape[1]):
        y = data[t + 1, target]
        sigma = data[:cutoff, target].std()
        other = 1 - target
        sets = {"proprio": blocks[target], "outro": blocks[other],
                "conjunto": np.column_stack(blocks)}
        name = f"alvo{target}"
        for label, x in sets.items():
            pred = _nn(x[train], y[train], x[test])
            out[f"{name}_nn_{label}"] = np.sqrt(np.mean((pred - y[test]) ** 2)) / sigma
            if smap:
                pred, theta = _smap(x[train], y[train], t[train], x[test], theiler, loo_step)
                out[f"{name}_smap_{label}"] = np.sqrt(np.mean((pred - y[test]) ** 2)) / sigma
                out[f"{name}_smap_{label}_theta"] = theta
        joint = np.column_stack([np.ones(train.sum()), sets["conjunto"][train]])
        beta, *_ = np.linalg.lstsq(joint, y[train], rcond=None)
        pred = np.column_stack([np.ones(test.sum()), sets["conjunto"][test]]) @ beta
        out[f"{name}_var"] = np.sqrt(np.mean((pred - y[test]) ** 2)) / sigma
        for method in ("nn", "smap") if smap else ("nn",):
            best = min(out[f"{name}_{method}_proprio"], out[f"{name}_{method}_outro"])
            out[f"{name}_{method}_ganho"] = best - out[f"{name}_{method}_conjunto"]
    return out


# ── lote: séries das bacias e subamostra ────────────────────────────────────

RULES = {"version": 1, "channels": {"t2m": "t2m_c_mean", "q": "q_gkg_mean"}, "horizon": 1,
         "neighbors": NEIGHBORS, "train_fraction": TRAIN_FRACTION, "smap": SMAP_RULES,
         "smap_loo_step": 4, "basin_surrogates": 199, "basin_nulls": ["FT", "IAAFT"],
         "subsample_surrogates": 39, "subsample_nulls": ["IAAFT"],
         "subsample": {"n": 60, "seed": 20261023}, "iaaft_max_iter": 200,
         "alternative": {"conjunto": "less", "ganho": "greater"}}


def surrogate(data: np.ndarray, method: str, seed: int, index: int) -> np.ndarray:
    child = np.random.SeedSequence(seed).spawn(index + 1)[index]
    rng = np.random.default_rng(child)
    if method == "FT":
        return multivariate_ft(data, rng)
    return multivariate_iaaft(data, rng, RULES["iaaft_max_iter"])


def _errors_task(args):
    data, params, theiler, method, seed, index = args
    x = data if index < 0 else surrogate(data, method, seed, index)
    return {"null": method, "surrogate": index,
            **forecast_errors(x, params, theiler, loo_step=RULES["smap_loo_step"])}


def multivariate_hash(spec) -> str:
    from amazon_chaos.nonlinear.suite import spec_hash

    return spec_hash({"rules": RULES, "series": spec["series"], "embedding": spec["embedding"]})


def output_dir(cfg, spec):
    from amazon_chaos import regions

    return regions.processed_dir(cfg) / "multivariado" / multivariate_hash(spec)


def _series_jobs(data, spec, seed, nulls, n):
    from amazon_chaos.nonlinear.suite import embedding_parameters

    params = [embedding_parameters(data[:, c], spec) for c in range(data.shape[1])]
    theiler = max(p["theiler"] for p in params)
    jobs = [(data, params, theiler, nulls[0], seed, -1)]
    jobs += [(data, params, theiler, method, seed, i) for method in nulls for i in range(n)]
    return jobs, params


def run(cfg, spec, cells, *, workers=None, report=print):
    """Série da bacia (FT e IAAFT multivariadas, 199) e subamostra (IAAFT, 39)."""
    import json
    import os
    from concurrent.futures import ProcessPoolExecutor
    from datetime import UTC, datetime

    import pandas as pd

    from amazon_chaos import regions
    from amazon_chaos.nonlinear.basin_test import _seed as basin_seed
    from amazon_chaos.nonlinear.basin_test import basin_series
    from amazon_chaos.nonlinear.batch import NORMAL, _commit, _seed, load_cubes, windows
    from amazon_chaos.nonlinear.sensitivity import subsample
    from amazon_chaos.regional import standardized_anomalies

    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        if not (out / "bacia.parquet").exists():
            data = np.column_stack([basin_series(cfg, v, spec).to_numpy(dtype=float)
                                    for v in RULES["channels"]])
            jobs, params = _series_jobs(data, spec, basin_seed(spec, cfg["slug"], "t2m+q",
                                                               "multivariado"),
                                        RULES["basin_nulls"], RULES["basin_surrogates"])
            rows = list(pool.map(_errors_task, jobs, chunksize=4))
            pd.DataFrame(rows).assign(region=cfg["slug"], tau_t2m=params[0]["tau"],
                                      m_t2m=params[0]["m"], tau_q=params[1]["tau"],
                                      m_q=params[1]["m"]).to_parquet(out / "bacia.parquet")
            report(f"🔗 T + q (F2c) · {cfg['name']}: série da bacia pronta")
        if not (out / "subamostra.parquet").exists():
            chosen = subsample(cells, RULES["subsample"]["n"], RULES["subsample"]["seed"])
            grid = regions.cells(cfg).set_index("cell_id").loc[chosen]
            cubes = load_cubes(cfg, RULES["channels"])
            start, end = windows(spec)["2001_2024"]
            parts = out / "celulas"  # uma por célula: o lote retoma de onde parou
            parts.mkdir(exist_ok=True)
            for k, cell in enumerate(grid.itertuples(), 1):
                if (parts / f"{cell.Index}.parquet").exists():
                    continue
                data = np.column_stack([
                    standardized_anomalies(cube.sel(latitude=cell.latitude,
                                                    longitude=cell.longitude).to_series(),
                                           NORMAL)[0].loc[start:end].to_numpy(dtype=float)
                    for cube in cubes.values()])
                jobs, _ = _series_jobs(data, spec, _seed(spec, cell.Index, "t2m+q",
                                                         "2001_2024", "multivariado"),
                                       RULES["subsample_nulls"],
                                       RULES["subsample_surrogates"])
                pd.DataFrame(list(pool.map(_errors_task, jobs))).assign(
                    cell_id=cell.Index).to_parquet(parts / f"{cell.Index}.parquet")
                if k % max(1, len(grid) // 5) == 0:
                    report(f"📊 T + q (F2c) · {cfg['name']}: {k}/{len(grid)} células")
            pd.concat([pd.read_parquet(parts / f"{c}.parquet") for c in grid.index],
                      ignore_index=True).to_parquet(out / "subamostra.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "multivariate_hash": multivariate_hash(spec), "rules": RULES,
        "commit": _commit(), "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return out


def pvalues(table):
    """p de Monte Carlo do erro conjunto (menor) e do ganho (maior), por série e nula."""
    import pandas as pd

    from amazon_chaos.nonlinear.surrogates import monte_carlo_pvalue

    key = "cell_id" if "cell_id" in table else "region"
    rows = []
    for series_id, part in table.groupby(key):
        observed = part[part.surrogate < 0].iloc[0]
        for null, sur in part[part.surrogate >= 0].groupby("null"):
            for target, name in enumerate(RULES["channels"]):
                for method in ("nn", "smap"):
                    for stat, alternative in RULES["alternative"].items():
                        col = f"alvo{target}_{method}_{stat}"
                        rows.append({key: series_id, "null": null, "alvo": name,
                                     "metodo": method, "estatistica": stat,
                                     "observado": observed[col],
                                     "nulo_media": sur[col].mean(),
                                     "pvalue": monte_carlo_pvalue(observed[col],
                                                                  sur[col].to_numpy(),
                                                                  alternative)})
    return pd.DataFrame(rows)
