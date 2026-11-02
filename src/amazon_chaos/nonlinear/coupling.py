"""Floresta e atmosfera como sistema acoplado (D-031, etapas 2 e 3).

- `lagged`: vetores de atraso de várias séries no mesmo instante;
- `predictor_sets` e `compare_forecasts`: previsão de V(t+1) só pela vegetação, só pela
  atmosfera e pelo conjunto, por modelo linear, vizinhos e S-map, fora da amostra;
- `ccm` e `ccm_test`: convergent cross mapping (Sugihara et al., 2012) contra substitutas
  sazonais em blocos de um ano (Deyle et al., 2016);
- `state_dependence`: no S-map conjunto, quanto o coeficiente de um forçante varia com o
  estado da vegetação;
- `refill`: o tratamento das lacunas da D-031, aplicado igual aos dados e às substitutas;
- `baci` e `response_change`: alteração e recuperação depois do fogo e mudança na resposta
  da vegetação ao clima.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from amazon_chaos.nonlinear.multivariate import _nn, _smap
from amazon_chaos.nonlinear.smap import _weighted_fit, diebold_mariano

TRAIN_FRACTION = 0.6
STEP_PER_YEAR = 46


# ── lacunas (D-031) ──────────────────────────────────────────────────────────


def refill(x: np.ndarray, missing: np.ndarray, interpolate_max: int = 2) -> np.ndarray:
    """Interpola linearmente lacunas de até `interpolate_max` composições e preenche as mais
    longas com 0 (a climatologia, em anomalia). Aplicado aos dados e, nas mesmas posições,
    a cada substituta."""
    y = np.asarray(x, dtype=float).copy()
    missing = np.asarray(missing, dtype=bool)
    y[missing] = np.nan
    n, i = len(y), 0
    while i < n:
        if not missing[i]:
            i += 1
            continue
        j = i
        while j < n and missing[j]:
            j += 1
        if j - i <= interpolate_max and i > 0 and j < n:
            y[i:j] = np.interp(np.arange(i, j), [i - 1, j], [y[i - 1], y[j]])
        else:
            y[i:j] = 0.0
        i = j
    return y


# ── previsão com conjuntos de preditores ─────────────────────────────────────


def lagged(series: dict[str, np.ndarray], m: int, tau: int):
    """Matriz com x(t), x(t − τ), …, x(t − (m − 1)τ) de cada série e o índice t."""
    n = len(next(iter(series.values())))
    t = np.arange((m - 1) * tau, n - 1)
    cols = {f"{k}_{j}": np.asarray(v, float)[t - j * tau]
            for k, v in series.items() for j in range(m)}
    return pd.DataFrame(cols), t


def predictor_sets(vegetation: str, atmosphere: list[str]) -> dict[str, list[str]]:
    return {"vegetacao": [vegetation], "atmosfera": list(atmosphere),
            "conjunto": [vegetation, *atmosphere]}


def compare_forecasts(series: dict[str, np.ndarray], target: str, atmosphere: list[str], *,
                      m: int, tau: int, theiler: int, loo_step: int = 2) -> pd.DataFrame:
    """RMSE no teste (relativo ao desvio do treino) de cada conjunto × modelo, e o teste de
    Diebold–Mariano de cada um contra a vegetação isolada com o mesmo modelo."""
    frame, t = lagged(series, m, tau)
    y = np.asarray(series[target], float)[t + 1]
    cutoff = int(TRAIN_FRACTION * len(y))
    train = np.arange(len(y)) + 1 + theiler < cutoff
    test = np.arange(len(y)) >= cutoff
    sigma = y[train].std()
    errors, rows = {}, []
    for name, keys in predictor_sets(target, atmosphere).items():
        x = frame[[c for c in frame if c.rsplit("_", 1)[0] in keys]].to_numpy()
        design = np.column_stack([np.ones(len(x)), x])
        beta, *_ = np.linalg.lstsq(design[train], y[train], rcond=None)
        preds = {"linear": design[test] @ beta, "vizinhos": _nn(x[train], y[train], x[test])}
        preds["smap"], theta = _smap(x[train], y[train], t[train], x[test], theiler, loo_step)
        for model, pred in preds.items():
            errors[(name, model)] = pred - y[test]
            rows.append({"preditores": name, "modelo": model,
                         "rmse": float(np.sqrt(np.mean(errors[(name, model)] ** 2)) / sigma),
                         "theta": theta if model == "smap" else np.nan})
    out = pd.DataFrame(rows)
    for i, r in out.iterrows():
        base = errors[("vegetacao", r.modelo)]
        stat, p = diebold_mariano(base, errors[(r.preditores, r.modelo)], 1)
        out.loc[i, ["dm", "p_dm"]] = (stat, p) if r.preditores != "vegetacao" else (np.nan,
                                                                                     np.nan)
    ref = out[out.preditores == "vegetacao"].set_index("modelo").rmse
    out["ganho"] = ref.reindex(out.modelo).to_numpy() - out.rmse
    return out


def state_dependence(series: dict[str, np.ndarray], target: str, forcing: str, *, m: int,
                     tau: int, theta: float) -> float:
    """Correlação de Spearman entre o coeficiente do S-map conjunto para `forcing` (atraso 0)
    e o estado atual de `target`, em todos os pontos (biblioteca inteira, sem o próprio)."""
    frame, t = lagged(series, m, tau)
    y = np.asarray(series[target], float)[t + 1]
    x = frame.to_numpy()
    col = list(frame.columns).index(f"{forcing}_0")
    eps = 1e-3 * x[:, col].std()
    mask = ~np.eye(len(x), dtype=bool)
    shifted = x.copy()
    shifted[:, col] += eps
    base = _weighted_fit(x, y[:, None], x, theta, mask=mask)[:, 0]
    moved = _weighted_fit(x, y[:, None], shifted, theta, mask=mask)[:, 0]
    coefficient = (moved - base) / eps
    state = frame[f"{target}_0"].to_numpy()
    return float(pd.Series(coefficient).corr(pd.Series(state), method="spearman"))


# ── convergent cross mapping ─────────────────────────────────────────────────


def _shadow(x: np.ndarray, E: int, tau: int) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange((E - 1) * tau, len(x))
    return np.column_stack([x[t - j * tau] for j in range(E)]), t


def ccm(library: np.ndarray, target: np.ndarray, *, E: int, tau: int, theiler: int,
        sizes: np.ndarray, samples: int = 30, seed: int = 0, lag: int = 0) -> pd.DataFrame:
    """Habilidade ρ de `library` mapeando `target` (indica `target` → `library`) para cada
    tamanho de biblioteca, média de `samples` bibliotecas sorteadas. Com `lag` < 0, o alvo
    é `target(t + lag)`, o forçante de alguns passos antes (Ye et al., 2015)."""
    vectors, t = _shadow(np.asarray(library, float), E, tau)
    keep = (t + lag >= 0) & (t + lag < len(target))
    vectors, t = vectors[keep], t[keep]
    y = np.asarray(target, float)[t + lag]
    rng = np.random.default_rng(seed)
    rows = []
    for size in sizes:
        rhos = []
        for _ in range(samples):
            lib = np.sort(rng.choice(len(t), size=min(size, len(t)), replace=False))
            tree = cKDTree(vectors[lib])
            k = min(len(lib), E + 1 + 2 * theiler + 1)
            dist, idx = tree.query(vectors, k=k)
            dist, idx = np.atleast_2d(dist), np.atleast_2d(idx)
            far = np.abs(t[lib][idx] - t[:, None]) > theiler
            pred = np.full(len(t), np.nan)
            for i in range(len(t)):
                d, j = dist[i][far[i]][:E + 1], idx[i][far[i]][:E + 1]
                if len(j) < E + 1:
                    continue
                w = np.exp(-d / max(d[0], 1e-12))
                pred[i] = (w * y[lib][j]).sum() / w.sum()
            ok = np.isfinite(pred)
            rhos.append(np.corrcoef(pred[ok], y[ok])[0, 1] if ok.sum() > 2 else np.nan)
        rows.append({"biblioteca": int(size), "rho": float(np.nanmean(rhos))})
    return pd.DataFrame(rows)


def seasonal_surrogate(x: np.ndarray, rng: np.random.Generator,
                       period: int = STEP_PER_YEAR) -> np.ndarray:
    """Anomalias com os anos sorteados em blocos inteiros (o ciclo anual já foi retirado)."""
    x = np.asarray(x, float)
    years = [x[i:i + period] for i in range(0, len(x), period)]
    full = [y for y in years if len(y) == period]
    order = rng.permutation(len(full))
    out = np.concatenate([full[k] for k in order] + [y for y in years if len(y) < period])
    return out[:len(x)]


LAGS = (0, -1, -2)


def ccm_test(library, target, *, E, tau, theiler, n_surrogates=99, samples=30, seed=0,
             lags=LAGS) -> dict:
    """ρ na menor e na maior biblioteca, convergência e p contra substitutas sazonais do
    forçante (`target`). A defasagem é a de maior ρ entre `lags`, escolhida do mesmo modo em
    cada substituta, para que a escolha não favoreça os dados."""
    n = len(library) - (E - 1) * tau - max(-min(lags), 0)
    sizes = np.unique(np.linspace(0.1 * n, n, 5).astype(int))
    curves = {lag: ccm(library, target, E=E, tau=tau, theiler=theiler, sizes=sizes,
                       samples=samples, seed=seed, lag=lag) for lag in lags}
    best = max(lags, key=lambda lag: curves[lag].rho.iloc[-1])
    curve = curves[best]
    rho = curve.rho.iloc[-1]
    rng = np.random.default_rng(seed + 1)
    null = []
    for _ in range(n_surrogates):
        surrogate = seasonal_surrogate(target, rng)
        null.append(max(ccm(library, surrogate, E=E, tau=tau, theiler=theiler,
                            sizes=sizes[-1:], samples=1, seed=seed, lag=lag).rho.iloc[0]
                        for lag in lags))
    null = np.array(null)
    return {"rho": float(rho), "defasagem": int(best), "rho_min": float(curve.rho.iloc[0]),
            "convergencia": float(rho - curve.rho.iloc[0]),
            "rho_nulo": float(np.nanmean(null)),
            "pvalue": float((1 + np.sum(null >= rho)) / (len(null) + 1))}


# ── fogo (etapa 3) ───────────────────────────────────────────────────────────


def baci(burned: pd.DataFrame, controls: pd.DataFrame, pre=(-46, -1)) -> pd.DataFrame:
    """Δ(k) = [Vq(k) − Vq(pré)] − [Vc(k) − Vc(pré)] por episódio.

    `burned`: colunas `episodio`, `k`, `v`; `controls`: as mesmas, com vários controles
    por episódio (a média deles entra como Vc). A composição da queima (k = 0) é excluída.
    """
    c = controls.groupby(["episodio", "k"]).v.mean().rename("vc")
    frame = burned.set_index(["episodio", "k"]).v.rename("vq").to_frame().join(c, how="inner")
    frame = frame.reset_index()
    frame = frame[frame.k != 0]
    window = frame[frame.k.between(*pre)]
    base = window.groupby("episodio")[["vq", "vc"]].mean()
    frame = frame.join(base, on="episodio", rsuffix="_pre")
    frame["delta"] = (frame.vq - frame.vq_pre) - (frame.vc - frame.vc_pre)
    return frame[["episodio", "k", "delta"]]


def baci_summary(delta: pd.DataFrame, clusters: pd.Series, *, n: int = 999,
                 seed: int = 20261031, run: int = 6) -> tuple[pd.DataFrame, float]:
    """Média de Δ(k) com IC 95% por bootstrap de episódios agrupados (`clusters`: episódio →
    grupo) e o primeiro k > 0 a partir do qual o IC inclui zero por `run` composições."""
    wide = delta.pivot(index="episodio", columns="k", values="delta")
    groups = clusters.reindex(wide.index).to_numpy()
    labels = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in labels}
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n):
        pick = np.concatenate([members[g] for g in rng.choice(labels, len(labels))])
        boot.append(np.nanmean(wide.to_numpy()[pick], axis=0))
    boot = np.array(boot)
    out = pd.DataFrame({"k": wide.columns, "delta": np.nanmean(wide.to_numpy(), axis=0),
                        "ic_inf": np.nanquantile(boot, 0.025, axis=0),
                        "ic_sup": np.nanquantile(boot, 0.975, axis=0)})
    covers = (out.ic_inf <= 0) & (out.ic_sup >= 0)
    after = out[out.k > 0].reset_index(drop=True)
    cov = covers[out.k > 0].to_numpy()
    recovery = np.nan
    for i in range(len(after) - run + 1):
        if cov[i:i + run].all():
            recovery = float(after.k[i])
            break
    return out, recovery


def response_change(panel: pd.DataFrame) -> pd.DataFrame:
    """V(t+1) = a·V + b·H + c·D, com as interações de cada termo com queimado × depois,
    efeitos fixos de pixel (dentro de cada pixel) e erro agrupado por célula ERA5.

    `panel`: `pixel`, `celula`, `queimado` (0/1), `depois` (0/1), `v`, `v_next`, `h`, `d`.
    """
    import statsmodels.api as sm

    keep = np.isfinite(panel[["v", "v_next", "h", "d"]].to_numpy(float)).all(axis=1)
    p = panel[keep].copy()
    p["qd"] = p.queimado * p.depois
    terms = ["v", "h", "d"]
    for term in terms:
        p[f"{term}_depois"] = p[term] * p.depois
        p[f"{term}_qd"] = p[term] * p.qd
    cols = terms + [f"{t}_depois" for t in terms] + [f"{t}_qd" for t in terms] + ["depois", "qd"]
    demeaned = p[cols + ["v_next"]] - p.groupby("pixel")[cols + ["v_next"]].transform("mean")
    fit = sm.OLS(demeaned.v_next, demeaned[cols]).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(p.celula)[0]})
    ci = fit.conf_int()
    return pd.DataFrame({"termo": cols, "coeficiente": fit.params.to_numpy(),
                         "ic_inf": ci[0].to_numpy(), "ic_sup": ci[1].to_numpy(),
                         "p": fit.pvalues.to_numpy()})
