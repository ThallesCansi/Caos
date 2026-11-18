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


# ── memória e sensibilidade depois do fogo (D-033) ───────────────────────────

STEP_YEARS = 8 / 365.25
PRE_MEAN = (-46, -1)
PRE_SEASONAL = (-92, -1)
POST_BINS = ((1, 6), (7, 23), (24, 46), (47, 92), (93, 138))
TERMS = ("dif", "h", "d", "P_dif", "P_h", "P_d")


def baseline_change(diff: pd.DataFrame, *, seasonal: bool = False) -> pd.DataFrame:
    """Δₑ(k) = δₑ(k) − linha de base anterior ao fogo. `diff`: episodio, data, k, dif.
    Base: média de δ em k ∈ [−46, −1] ou, com `seasonal`, a média no mesmo mês do
    calendário em k ∈ [−92, −1]. Devolve episodio, data, k, delta (= Δ)."""
    f = diff.copy()
    if seasonal:
        f["mes_cal"] = pd.to_datetime(f.data).dt.month
        pre = f[f.k.between(*PRE_SEASONAL)]
        base = pre.groupby(["episodio", "mes_cal"]).dif.mean().rename("base")
        f = f.join(base, on=["episodio", "mes_cal"])
    else:
        base = f[f.k.between(*PRE_MEAN)].groupby("episodio").dif.mean()
        f["base"] = f.episodio.map(base)
    f["delta"] = f.dif - f.base
    return f[["episodio", "data", "k", "delta"]].dropna(subset=["delta"])


def memory_metrics(change: pd.DataFrame, *, post=(1, 138), first=(1, 46),
                   residual=(47, 138), min_post: float = 0.3,
                   min_residual: float = 0.3) -> pd.DataFrame:
    """Por episódio: déficit acumulado A = −Δt Σ min(Δ, 0) (calculado com a média dos k
    válidos vezes o número de composições), o líquido A_liq (sem o min), o do primeiro ano
    A1 e a diferença residual R (média de Δ nos anos 2 e 3)."""
    def window(d, lo, hi):
        return d[(d.index >= lo) & (d.index <= hi)].dropna()

    rows = []
    for episode, g in change.groupby("episodio"):
        d = g.set_index("k").delta
        row = {"episodio": episode}
        n = post[1] - post[0] + 1
        p = window(d, *post)
        if len(p) >= min_post * n:
            row["A"] = -STEP_YEARS * n * np.minimum(p, 0).mean()
            row["A_liq"] = -STEP_YEARS * n * p.mean()
        n1 = first[1] - first[0] + 1
        f1 = window(d, *first)
        if len(f1) >= min_post * n1:
            row["A1"] = -STEP_YEARS * n1 * np.minimum(f1, 0).mean()
        r = window(d, *residual)
        if len(r) >= min_residual * (residual[1] - residual[0] + 1):
            row["R"] = r.mean()
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=["episodio", "A", "A_liq", "A1", "R"])


def cluster_draws(clusters: np.ndarray, n: int, seed: int):
    """Índices de `n` reamostras de grupos inteiros (com o número da cópia de cada grupo)."""
    labels, codes = np.unique(np.asarray(clusters), return_inverse=True)
    members = [np.flatnonzero(codes == c) for c in range(len(labels))]
    rng = np.random.default_rng(seed)
    for _ in range(n):
        pick = rng.integers(0, len(labels), len(labels))
        parts = [members[c] for c in pick]
        yield (np.concatenate(parts),
               np.concatenate([np.full(len(p), j) for j, p in enumerate(parts)]))


def _two_sided(values) -> float:
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return np.nan
    tail = min((v <= 0).sum(), (v >= 0).sum())
    return float(min(1.0, 2 * (tail + 1) / (len(v) + 1)))


def cluster_mean(values, clusters, *, n: int = 999, seed: int = 20261107) -> dict:
    """Média com IC 95% e p bilateral por bootstrap de grupos (células ERA5)."""
    v = np.asarray(values, float)
    c = np.asarray(clusters)
    ok = np.isfinite(v)
    v, c = v[ok], c[ok]
    if len(v) < 3:
        return {"media": np.nan, "ic_inf": np.nan, "ic_sup": np.nan, "p": np.nan, "n": len(v)}
    boot = [v[rows].mean() for rows, _ in cluster_draws(c, n, seed)]
    return {"media": float(v.mean()), "ic_inf": float(np.quantile(boot, 0.025)),
            "ic_sup": float(np.quantile(boot, 0.975)), "p": _two_sided(boot), "n": len(v),
            "grupos": len(np.unique(c))}


def sensitivity_design(frame: pd.DataFrame, *, post_start: int = 1, window=(-92, 138),
                       bins=POST_BINS):
    """Transições válidas e a matriz do modelo de sensibilidade (D-033, item 3).

    `frame`: episodio, cell_id, data, k, dif, h, d, uma linha por composição. Só entram
    transições entre composições consecutivas (k → k + 1) do mesmo lado da queima; as
    composições com 0 < k < `post_start` ficam de fora (variante depois do primeiro ano)."""
    f = frame[frame.k.between(*window)].sort_values(["episodio", "k"]).reset_index(drop=True)
    nxt = f.groupby("episodio")[["k", "dif"]].shift(-1)

    def side(k):
        k = np.asarray(k, float)
        return np.where(k < 0, -1, np.where(k >= post_start, 1, 0))

    ok = ((nxt.k == f.k + 1) & np.isfinite(nxt.dif) & np.isfinite(f.dif)
          & np.isfinite(f.h) & np.isfinite(f.d))
    ok &= (side(f.k) == side(nxt.k)) & (side(f.k) != 0)
    f, y = f[ok], nxt.dif[ok]
    post = (f.k >= post_start).astype(float)
    x = {"dif": f.dif, "h": f.h, "d": f.d, "P_dif": post * f.dif, "P_h": post * f.h,
         "P_d": post * f.d}
    for lo, hi in bins:
        if hi >= post_start:
            x[f"k_{lo}_{hi}"] = f.k.between(max(lo, post_start), hi).astype(float)
    month = pd.to_datetime(f.data).dt.month
    for m in range(2, 13):
        x[f"mes_{m}"] = (month == m).astype(float)
        x[f"P_mes_{m}"] = post * (month == m)
    return (pd.DataFrame(x).astype(float), y.astype(float), f.episodio.to_numpy(),
            f.cell_id.to_numpy())


def _within(x: np.ndarray, y: np.ndarray, groups: np.ndarray):
    codes = pd.factorize(groups)[0]
    counts = np.bincount(codes)
    mx = np.vstack([np.bincount(codes, weights=x[:, j]) for j in range(x.shape[1])]).T
    my = np.bincount(codes, weights=y)
    return x - (mx / counts[:, None])[codes], y - (my / counts)[codes]


def _ols(x, y):
    keep = np.abs(x).sum(axis=0) > 1e-9
    beta = np.full(x.shape[1], np.nan)
    beta[keep] = np.linalg.lstsq(x[:, keep], y, rcond=None)[0]
    return beta


def sensitivity_model(frame: pd.DataFrame, *, n_boot: int = 499, seed: int = 20261107,
                      terms=TERMS, **design) -> pd.DataFrame:
    """δ(t+1) com efeitos fixos de episódio, erro agrupado por célula ERA5 e IC por bootstrap
    das células (episódios repetidos contam como distintos)."""
    import statsmodels.api as sm

    x, y, episodes, cells = sensitivity_design(frame, **design)
    names = list(x.columns)
    xd, yd = _within(x.to_numpy(), y.to_numpy(), episodes)
    keep = np.abs(xd).sum(axis=0) > 1e-9
    fit = sm.OLS(yd, xd[:, keep]).fit(cov_type="cluster",
                                      cov_kwds={"groups": pd.factorize(cells)[0]})
    kept = [n for n, k in zip(names, keep, strict=True) if k]
    beta = dict(zip(kept, fit.params, strict=True))
    se = dict(zip(kept, fit.bse, strict=True))
    pv = dict(zip(kept, fit.pvalues, strict=True))
    xa, ya = x.to_numpy(), y.to_numpy()
    codes = pd.factorize(episodes)[0]
    boot = []
    for rows, copy in cluster_draws(cells, n_boot, seed):
        bx, by = _within(xa[rows], ya[rows], codes[rows] * (copy.max() + 1) + copy)
        boot.append(_ols(bx, by))
    boot = np.array(boot)
    out = []
    for t in terms:
        if t not in beta:
            continue
        b = boot[:, names.index(t)]
        out.append({"termo": t, "coeficiente": beta[t], "ep_agrupado": se[t],
                    "p_agrupado": pv[t], "ic_inf": float(np.nanquantile(b, 0.025)),
                    "ic_sup": float(np.nanquantile(b, 0.975)), "p": _two_sided(b),
                    "transicoes": len(y), "episodios": len(np.unique(episodes)),
                    "celulas": len(np.unique(cells))})
    return pd.DataFrame(out)


def drought_model(table: pd.DataFrame, outcome: str, exposure: str, *,
                  categorical=("bacia", "ano"), numeric=("estacao_seca", "v_pre"),
                  cluster: str = "cell_id", n_boot: int = 999,
                  seed: int = 20261107) -> dict:
    """outcome = α + β·exposição padronizada + controles; IC e p por bootstrap de células."""
    cols = [outcome, exposure, *numeric, *categorical, cluster]
    t = table[[c for c in cols if c in table]].dropna()
    z = (t[exposure] - t[exposure].mean()) / t[exposure].std()
    parts = [pd.Series(1.0, index=t.index, name="const"), z.rename("exposicao")]
    parts += [t[c].astype(float) for c in numeric if c in t]
    for c in categorical:
        if c in t and t[c].nunique() > 1:
            parts.append(pd.get_dummies(t[c], prefix=c, drop_first=True, dtype=float))
    x = pd.concat(parts, axis=1).to_numpy()
    y = t[outcome].to_numpy(float)
    beta = _ols(x, y)[1]
    boot = [_ols(x[rows], y[rows])[1] for rows, _ in cluster_draws(t[cluster], n_boot, seed)]
    return {"desfecho": outcome, "exposicao": exposure, "beta": float(beta),
            "ic_inf": float(np.nanquantile(boot, 0.025)),
            "ic_sup": float(np.nanquantile(boot, 0.975)), "p": _two_sided(boot),
            "episodios": len(t), "celulas": t[cluster].nunique()}
