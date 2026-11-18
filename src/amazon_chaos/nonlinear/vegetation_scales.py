"""Escalas de tempo e estado compacto do acoplamento floresta–atmosfera (D-032).

Ampliação da etapa 2 da D-031, com os mesmos dados (LAI e NDMI da subamostra, VPD do ERA5,
chuva do CHIRPS acumulada em 32 e 96 dias). Em vez de prever só V(t+1) com o mesmo número de
atrasos para todas as variáveis, compara, para cada horizonte h de 1, 2, 4 e 8 composições:

- a vegetação isolada, X = [V(t), V(t − 1)];
- o estado conjunto compacto, X = [V(t), V(t − 1), H(t − k_H), D(t − k_D)], com H a chuva de
  32 ou de 96 dias e k_H, k_D ∈ {0, 2, 4, 8}, escolhidos só no treino;
- e a direção inversa: D(t + h) por [D(t), D(t − 1)] contra [D(t), D(t − 1), V(t − k)].

Cada conjunto é ajustado por regressão linear (S-map com θ = 0), vizinhos próximos e S-map
com θ escolhido no treino. A validação é cronológica em três blocos de quatro anos
(2013–16, 2017–20, 2021–24), sempre treinando com os anos anteriores; a climatologia da
anomalia é estimada só nos anos de treino; os atrasos, o θ e a chuva são escolhidos nos três
últimos anos do treino (validação interna) e o modelo é reajustado no treino inteiro.

Lacunas: os preditores são preenchidos só com o passado (o último valor válido por até duas
composições, depois a climatologia), e só os alvos observados entram no ajuste e no erro
(variante "estrita", a principal). A variante "d031" repete o tratamento da D-031
(interpolação, que usa o futuro, e alvos preenchidos); a "media" prevê a média de V nas h
composições seguintes, o que reduz o ruído de recuperação.

Controle: os anos do bloco que não é o alvo (a atmosfera, ou a vegetação na direção inversa)
são permutados inteiros nos valores brutos, com a mesma permutação em todas as células da
bacia; todo o procedimento (climatologia, escolha, ajuste) é refeito em cada uma.

Chamado por `amazon-chaos vegetation scales <região>`.
"""

from __future__ import annotations

import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from amazon_chaos import regions
from amazon_chaos.nonlinear.coupling import refill
from amazon_chaos.nonlinear.smap import diebold_mariano
from amazon_chaos.nonlinear.suite import spec_hash

VEGETATION = ("lai", "ndmi")
RAIN = ("chuva_32d", "chuva_96d")
DEFICIT = "vpd"
COLUMNS = (*VEGETATION, DEFICIT, *RAIN)
HORIZONS = (1, 2, 4, 8)
LAGS = (0, 2, 4, 8)
MAX_LAG = max(LAGS)
FOLDS = ((2013, 2016), (2017, 2020), (2021, 2024))
FIRST_YEAR, LAST_YEAR = 2001, 2024
VALIDATION_YEARS = 3
THETAS = (0, 0.25, 0.5, 1, 2, 4, 8)
NEIGHBORS = 5
CARRY = 2
SLOTS = 46
N_SURROGATES = 39
SEED = 20261107
VARIANTS = ("estrita", "media", "d031")
SURROGATE_VARIANTS = ("estrita", "media")
MAX_MISSING, PRIMARY_MAX_MISSING = 0.35, 0.2
MODELS = ("linear", "vizinhos", "smap")
DIRECTIONS = ("atmosfera→vegetação", "vegetação→atmosfera")

RULES = {"version": 1, "horizons": list(HORIZONS), "lags": list(LAGS), "rain": list(RAIN),
         "folds": [list(f) for f in FOLDS], "validation_years": VALIDATION_YEARS,
         "thetas": list(THETAS), "neighbors": NEIGHBORS, "carry": CARRY,
         "surrogates": N_SURROGATES, "seed": SEED, "variants": list(VARIANTS),
         "surrogate_variants": list(SURROGATE_VARIANTS), "max_missing": MAX_MISSING,
         "primary_max_missing": PRIMARY_MAX_MISSING}


# ── calendário, anomalia e lacunas ──────────────────────────────────────────


def calendar(index) -> tuple[np.ndarray, np.ndarray]:
    """Ano e posição da composição no ano (0 a 45)."""
    idx = pd.DatetimeIndex(index)
    return idx.year.to_numpy(), ((idx.dayofyear.to_numpy() - 1) // 8).clip(0, SLOTS - 1)


def anomaly(raw: np.ndarray, slot: np.ndarray, fit: np.ndarray) -> np.ndarray:
    """Anomalia padronizada por posição no ano, com média e desvio só das linhas `fit`."""
    frame = pd.DataFrame(raw[fit]).groupby(slot[fit])
    mean = frame.mean().reindex(range(SLOTS)).to_numpy()
    sd = frame.std().reindex(range(SLOTS)).to_numpy()
    sd = np.where(sd > 0, sd, np.nan)
    return (raw - mean[slot]) / sd[slot]


def causal_fill(z: np.ndarray, carry: int = CARRY) -> np.ndarray:
    """Último valor válido por até `carry` composições, depois a climatologia (0)."""
    return pd.DataFrame(z).ffill(limit=carry).fillna(0.0).to_numpy()


def transform(raw, slot, fit, variant: str, target: int):
    """(preditores preenchidos, série do alvo) de um estágio da validação."""
    z = anomaly(raw, slot, fit)
    if variant == "d031":
        filled = np.column_stack([refill(z[:, j], ~np.isfinite(z[:, j]))
                                  for j in range(z.shape[1])])
        return filled, filled[:, target]
    return causal_fill(z), z[:, target]


def targets(series: np.ndarray, h: int, mean: bool) -> tuple[np.ndarray, np.ndarray]:
    """Tempos t (os mesmos para todas as configurações) e o alvo em t + h, ou a média de
    t + 1 a t + h com pelo menos metade das composições observadas."""
    t = np.arange(MAX_LAG, len(series) - h)
    if not mean:
        return t, series[t + h]
    window = np.column_stack([series[t + j] for j in range(1, h + 1)])
    count = np.isfinite(window).sum(axis=1)
    with np.errstate(invalid="ignore"):
        avg = np.nanmean(np.where(count[:, None] > 0, window, 0.0), axis=1)
    return t, np.where(count >= math.ceil(h / 2), avg, np.nan)


def permute_years(raw: np.ndarray, columns: list[int], year, slot,
                  order: dict[int, int]) -> np.ndarray:
    """Troca os anos inteiros das colunas `columns`: a composição (ano, posição) recebe o
    valor de (order[ano], posição). Anos fora de `order` ficam como estão."""
    where = {(y, s): i for i, (y, s) in enumerate(zip(year, slot, strict=True))}
    src = np.array([where.get((order.get(y, y), s), -1)
                    for y, s in zip(year, slot, strict=True)])
    out = raw.copy()
    for c in columns:
        out[:, c] = np.where(src >= 0, raw[np.maximum(src, 0), c], np.nan)
    return out


def derangement(k: int, seed: int) -> np.ndarray:
    """Permutação de 0..k−1 sem pontos fixos (nenhum ano fica no lugar)."""
    rng = np.random.default_rng(seed)
    while True:
        p = rng.permutation(k)
        if not np.any(p == np.arange(k)):
            return p


def year_orders(n: int = N_SURROGATES, seed: int = SEED) -> list[dict[int, int]]:
    years = np.arange(FIRST_YEAR, LAST_YEAR + 1)
    return [dict(zip(years.tolist(), years[derangement(len(years), seed + s)].tolist(),
                     strict=True)) for s in range(1, n + 1)]


# ── modelos ──────────────────────────────────────────────────────────────────


def smap_predictions(lib_x, lib_y, query, thetas=THETAS) -> dict[float, np.ndarray]:
    """S-map para cada θ, com as distâncias calculadas uma vez; θ = 0 é a regressão linear."""
    n, p = lib_x.shape
    design = np.column_stack([np.ones(n), lib_x])
    q = np.column_stack([np.ones(len(query)), query])
    d = np.sqrt(((query[:, None, :] - lib_x[None, :, :]) ** 2).sum(-1))
    scale = d.mean(axis=1, keepdims=True)
    scale[scale == 0] = 1.0
    ridge = 1e-8 * np.eye(p + 1)[None]
    out = {}
    for theta in thetas:
        w = np.exp(-theta * d / scale)
        a = np.einsum("qn,np,nr->qpr", w, design, design, optimize=True) + ridge
        b = np.einsum("qn,np,n->qp", w, design, lib_y, optimize=True)
        out[theta] = (q * np.linalg.solve(a, b[..., None])[..., 0]).sum(axis=1)
    return out


def neighbors(lib_x, lib_y, query, k: int = NEIGHBORS) -> np.ndarray:
    _, idx = cKDTree(lib_x).query(query, k=k)
    return lib_y[np.asarray(idx).reshape(len(query), k)].mean(axis=1)


def _rmse(e) -> float:
    return float(np.sqrt(np.mean(np.square(e))))


def label(config) -> str:
    return "+".join(f"{c}@{k}" for c, k in config)


# ── uma dobra ────────────────────────────────────────────────────────────────


def evaluate_fold(raw, cols: list[str], year, slot, target: str, base, joint, h: int,
                  variant: str, block: tuple[int, int], *, with_base=True, profile=True):
    """Escolha na validação interna e erros no bloco de teste de uma dobra."""
    index = {c: j for j, c in enumerate(cols)}
    first = block[0]
    stages = {"interno": (first - VALIDATION_YEARS, (first - VALIDATION_YEARS, first - 1)),
              "externo": (first, block)}
    data = {}
    for stage, (cut, (lo, hi)) in stages.items():
        filled, series = transform(raw, slot, year < cut, variant, index[target])
        t, y = targets(series, h, variant == "media")
        ty = year[t + h]
        ok = np.isfinite(y)
        lib, qry = ok & (ty < cut), ok & (ty >= lo) & (ty <= hi)
        data[stage] = (filled, t, y, lib, qry)

    def xy(stage, config):
        filled, t, y, lib, qry = data[stage]
        x = np.column_stack([filled[t - k, index[c]] for c, k in config])
        return x[lib], y[lib], x[qry], y[qry]

    configs = ([base] if with_base else []) + list(joint)
    inner = {}
    for config in configs:
        lx, ly, qx, qy = xy("interno", config)
        if len(ly) < 50 or len(qy) < 10:
            return None
        preds = smap_predictions(lx, ly, qx)
        inner[config] = ({th: _rmse(p - qy) for th, p in preds.items()},
                         _rmse(neighbors(lx, ly, qx) - qy))

    def best_theta(config):
        scores = inner[config][0]
        return min(THETAS, key=lambda th: (scores[th], th))

    choice = {"linear": min(joint, key=lambda c: inner[c][0][0]),
              "vizinhos": min(joint, key=lambda c: inner[c][1]),
              "smap": min(joint, key=lambda c: min(inner[c][0].values()))}
    theta_joint = best_theta(choice["smap"])
    errors, y_test = {}, None
    outer = {}
    needed = set(choice.values()) | ({base} if with_base else set())
    if profile:
        needed |= set(joint)
    for config in needed:
        lx, ly, qx, qy = xy("externo", config)
        y_test = qy
        thetas = {0}
        if config == choice["smap"]:
            thetas.add(theta_joint)
        if with_base and config == base:
            thetas.add(best_theta(base))
        outer[config] = (smap_predictions(lx, ly, qx, sorted(thetas)), lx, ly, qx, qy)
    if y_test is None or len(y_test) < 10:
        return None

    def err(config, theta):
        preds, *_, qy = outer[config]
        return preds[theta] - qy

    def nn_err(config):
        _, lx, ly, qx, qy = outer[config]
        return neighbors(lx, ly, qx) - qy

    if with_base:
        errors[("vegetacao", "linear")] = err(base, 0)
        errors[("vegetacao", "smap")] = err(base, best_theta(base))
        errors[("vegetacao", "vizinhos")] = nn_err(base)
        errors[("vegetacao", "smap0")] = err(base, 0)
    errors[("conjunto", "linear")] = err(choice["linear"], 0)
    errors[("conjunto", "smap")] = err(choice["smap"], theta_joint)
    errors[("conjunto", "smap0")] = err(choice["smap"], 0)
    errors[("conjunto", "vizinhos")] = nn_err(choice["vizinhos"])
    if profile:
        for config in joint:
            errors[("perfil", label(config))] = err(config, 0)
    selection = {"linear": label(choice["linear"]), "vizinhos": label(choice["vizinhos"]),
                 "smap": label(choice["smap"]), "theta_conjunto": theta_joint,
                 "theta_vegetacao": best_theta(base) if with_base else np.nan}
    return errors, y_test, selection


def evaluate(raw, cols, year, slot, target, base, joint, h, variant, **kwargs):
    """As três dobras, com os erros concatenados na ordem do tempo."""
    errors, ys, selections = {}, [], []
    for block in FOLDS:
        out = evaluate_fold(raw, cols, year, slot, target, base, joint, h, variant, block,
                            **kwargs)
        if out is None:
            continue
        e, y, s = out
        for k, v in e.items():
            errors.setdefault(k, []).append(v)
        ys.append(y)
        selections.append({"dobra": f"{block[0]}-{block[1]}", **s})
    if not ys:
        return None
    return ({k: np.concatenate(v) for k, v in errors.items()}, np.concatenate(ys),
            selections)


# ── uma célula ───────────────────────────────────────────────────────────────


def problems(v: str):
    """(direção, alvo, preditores da base, configurações conjuntas, colunas permutadas)."""
    yield (DIRECTIONS[0], v, ((v, 0), (v, 1)),
           [((v, 0), (v, 1), (w, kh), (DEFICIT, kd)) for w in RAIN for kh in LAGS
            for kd in LAGS], [DEFICIT, *RAIN])
    yield (DIRECTIONS[1], DEFICIT, ((DEFICIT, 0), (DEFICIT, 1)),
           [((DEFICIT, 0), (DEFICIT, 1), (v, k)) for k in LAGS], [v])


def _gain(errors, model, h, *, dm=True):
    base = errors[("vegetacao", model)]
    joint = errors[("conjunto", model)]
    row = {"modelo": model, "rmse_vegetacao": _rmse(base), "rmse_conjunto": _rmse(joint),
           "ganho": 1 - _rmse(joint) / _rmse(base)}
    if dm:
        row["dm"], row["p_dm"] = diebold_mariano(base, joint, h)
    return row


def cell_task(cell_id: str, frame: pd.DataFrame, missing: dict[str, float],
              orders: list[dict[int, int]], horizons=HORIZONS, variants=VARIANTS,
              surrogate_variants=SURROGATE_VARIANTS) -> pd.DataFrame:
    """Todas as comparações de uma célula. `frame`: composições × COLUMNS, valores brutos."""
    cols = list(COLUMNS)
    raw = frame[cols].to_numpy(float)
    year, slot = calendar(frame.index)
    rows = []
    for v in VEGETATION:
        if missing[v] > MAX_MISSING:
            continue
        for direction, target, base, joint, permuted in problems(v):
            perm_cols = [cols.index(c) for c in permuted]
            for variant in variants:
                for h in horizons:
                    if variant == "media" and h == 1:
                        continue
                    labels = {"cell_id": cell_id, "vegetacao": v, "lacunas": missing[v],
                              "sentido": direction, "variante": variant, "horizonte": h}
                    out = evaluate(raw, cols, year, slot, target, base, joint, h, variant)
                    if out is None:
                        continue
                    errors, y, selections = out
                    clim = _rmse(y)
                    for model in MODELS:
                        rows.append({**labels, "analise": "ganho", "substituta": 0,
                                     "rmse_clima": clim, **_gain(errors, model, h)})
                    for group in ("vegetacao", "conjunto"):
                        lin, nl = errors[(group, "smap0")], errors[(group, "smap")]
                        stat, p = diebold_mariano(lin, nl, h)
                        rows.append({**labels, "analise": "nao_linear", "substituta": 0,
                                     "preditores": group, "modelo": "smap",
                                     "rmse_linear": _rmse(lin), "rmse_smap": _rmse(nl),
                                     "ganho": 1 - _rmse(nl) / _rmse(lin), "dm": stat,
                                     "p_dm": p})
                    ref = _rmse(errors[("vegetacao", "linear")])
                    for (group, name), e in errors.items():
                        if group == "perfil":
                            rows.append({**labels, "analise": "perfil", "substituta": 0,
                                         "configuracao": name, "modelo": "linear",
                                         "ganho": 1 - _rmse(e) / ref})
                    rows.append({**labels, "analise": "escolha", "substituta": 0,
                                 "escolha": json.dumps(selections, default=float)})
                    if variant not in surrogate_variants:
                        continue
                    for s, order in enumerate(orders, 1):
                        shuffled = permute_years(raw, perm_cols, year, slot, order)
                        res = evaluate(shuffled, cols, year, slot, target, base, joint, h,
                                       variant, with_base=False, profile=False)
                        if res is None:
                            continue
                        e_s = res[0] | {k: e for k, e in errors.items() if k[0] == "vegetacao"}
                        for model in MODELS:
                            g = _gain(e_s, model, h, dm=False)
                            rows.append({**labels, "analise": "ganho", "substituta": s,
                                         "modelo": model, "ganho": g["ganho"]})
                        lin, nl = e_s[("conjunto", "smap0")], e_s[("conjunto", "smap")]
                        rows.append({**labels, "analise": "nao_linear", "substituta": s,
                                     "preditores": "conjunto", "modelo": "smap",
                                     "ganho": 1 - _rmse(nl) / _rmse(lin)})
    return pd.DataFrame(rows)


# ── checagem sintética ───────────────────────────────────────────────────────


def synthetic_frame(frame: pd.DataFrame, *, beta: float, lag: int = 4, phi: float = 0.8,
                    noise: float = 1.0, target: str = "lai", seed: int = 0) -> pd.DataFrame:
    """Troca a vegetação de uma célula real por u + ruído, com u(t + 1) = φ u(t) +
    β D(t − lag) + ε, sobre a atmosfera real e com as lacunas reais; o ciclo anual e a escala
    vêm da série observada. Com β = 0 não há acoplamento."""
    rng = np.random.default_rng(seed)
    year, slot = calendar(frame.index)
    raw = frame[[DEFICIT, target]].to_numpy(float)
    z = anomaly(raw, slot, np.ones(len(raw), bool))
    d = np.nan_to_num(z[:, 0])
    u = np.zeros(len(d))
    for t in range(1, len(d)):
        u[t] = phi * u[t - 1] + (beta * d[t - 1 - lag] if t - 1 - lag >= 0 else 0) \
            + np.sqrt(1 - phi**2) * rng.standard_normal()
    v = u + noise * rng.standard_normal(len(d))
    v /= v.std()
    stats = pd.DataFrame({"x": raw[:, 1], "s": slot}).groupby("s").x.agg(["mean", "std"])
    out = frame.copy()
    values = stats["mean"].to_numpy()[slot] + stats["std"].to_numpy()[slot] * v
    out[target] = np.where(np.isfinite(raw[:, 1]), values, np.nan)
    return out


# ── lote ─────────────────────────────────────────────────────────────────────


def scales_hash() -> str:
    from amazon_chaos.nonlinear.vegetation_dynamics import RULES as D031

    return spec_hash({"rules": RULES, "d031": D031})


def output_dir(cfg) -> Path:
    return regions.processed_dir(cfg) / "vegetacao" / f"escalas_{scales_hash()}"


def cell_frames(cfg) -> dict[str, tuple[pd.DataFrame, dict[str, float]]]:
    """Por célula: a tabela bruta (composições × COLUMNS) e a fração de lacunas de LAI e
    NDMI, contada como na D-031."""
    from amazon_chaos.nonlinear.vegetation_dynamics import joint_table

    wide = joint_table(cfg)
    out = {}
    for cell, frame in wide.groupby(level="cell_id"):
        frame = frame.droplevel("cell_id").sort_index()
        frame.index = pd.DatetimeIndex(frame.index)
        out[cell] = (frame[list(COLUMNS)],
                     {v: float(frame[v].isna().mean()) for v in VEGETATION})
    return out


def run(cfg, *, workers=None, report=print, limit=None) -> Path:
    """Executa (ou retoma, por célula) a D-032 na subamostra de uma bacia."""
    from amazon_chaos.nonlinear.batch import _commit

    out = output_dir(cfg)
    parts = out / "celulas"
    parts.mkdir(parents=True, exist_ok=True)
    frames = cell_frames(cfg)
    cells = sorted(frames)[:limit]
    todo = [c for c in cells if not (parts / f"{c}.parquet").exists()]
    orders = year_orders()
    report(f"🌳 Escalas (D-032) · {cfg['name']}: {len(todo)} de {len(cells)} células")
    started = datetime.now(UTC)
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        futures = {pool.submit(cell_task, c, *frames[c], orders): c for c in todo}
        for i, future in enumerate(as_completed(futures), 1):
            future.result().to_parquet(parts / f"{futures[future]}.parquet")
            if i % max(1, len(todo) // 5) == 0:
                hours = (datetime.now(UTC) - started).total_seconds() / 3600
                report(f"📊 Escalas · {cfg['name']}: {i}/{len(todo)} células · {hours:.1f} h")
    result = pd.concat([pd.read_parquet(p) for p in sorted(parts.glob("*.parquet"))],
                       ignore_index=True)
    result.to_parquet(out / "resultados.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "hash": scales_hash(), "rules": RULES, "commit": _commit(),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds")}, indent=2,
        default=str))
    return out


# ── síntese ──────────────────────────────────────────────────────────────────


def basin_summary(table: pd.DataFrame, analysis: str = "ganho") -> pd.DataFrame:
    """Mediana do ganho entre as células e o p contra as medianas das mesmas permutações
    (a mesma em todas as células, o que preserva a dependência espacial), a fração de células
    acima do 95º percentil das suas próprias permutações e o p dessa fração."""
    t = table[table.analise == analysis]
    if analysis == "nao_linear":
        t = t[t.preditores == "conjunto"]
    keys = ["vegetacao", "sentido", "variante", "horizonte", "modelo"]
    rows = []
    for key, g in t.groupby(keys):
        obs = g[g.substituta == 0].set_index("cell_id").ganho
        null = g[g.substituta > 0].pivot_table(index="cell_id", columns="substituta",
                                               values="ganho")
        row = dict(zip(keys, key, strict=True)) | {"celulas": len(obs),
                                                    "ganho_mediano": obs.median()}
        if null.shape[1]:
            null = null.reindex(obs.index)
            medians = null.median(axis=0)
            row["nulo_mediano"] = medians.median()
            row["p_bacia"] = (1 + (medians >= obs.median()).sum()) / (1 + len(medians))
            q95 = null.quantile(0.95, axis=1)
            frac = (obs > q95).mean()
            row["frac_celulas"] = frac
            # a mesma fração em cada permutação, contra o 95º das demais
            fracs = [(null[s] > null.drop(columns=s).quantile(0.95, axis=1)).mean()
                     for s in null.columns]
            row["p_frac"] = (1 + np.sum(np.array(fracs) >= frac)) / (1 + len(fracs))
        rows.append(row)
    return pd.DataFrame(rows)
