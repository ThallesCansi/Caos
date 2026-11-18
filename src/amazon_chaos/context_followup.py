"""Aprofundamentos exploratórios locais: coorte de duas janelas e recortes históricos.

Escolhas anteriores à estimação: até 1,5 mês → 6–12 meses; LAI principal e NDMI de
sensibilidade; bootstrap conjunto de células, 999 sorteios, semente 20261117.
Não modifica os testes confirmatórios e não identifica efeitos causais.
"""

from __future__ import annotations

from itertools import combinations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from amazon_chaos import territorial_comparison as T

EARLY, LATE = "Até 1,5 mês", "6–12 meses"
GROUPS = ["Até 10%", "10–30%", "Mais de 30%"]
COVARIATES = ["ano", "vpd_pre_60d", "vegetacao_pre"]
TARGETS = {"inicial": "Déficit inicial", "posterior": "Déficit em 6–12 meses",
           "mudanca": "Mudança: posterior − inicial"}
COLORS = ["#24645b", "#b97c4b", "#627baf"]
ZONE_COLORS = {"Área da UC atual": "#24645b", "Entorno de 25 km": "#b97c4b"}


def paired_episodes(curves: pd.DataFrame, value: str = "delta") -> pd.DataFrame:
    """Interseção de duas janelas, sem exigir cobertura nas outras cinco."""
    means = T.window_means(curves, value)
    keys = [k for k in ("bacia", "variavel", "episodio") if k in curves]
    part = means[means.janela.isin([EARLY, LATE])]
    values = part.pivot(index=keys, columns="janela", values=value).reindex(
        columns=[EARLY, LATE]).dropna().rename(columns={EARLY: "inicial", LATE: "posterior"})
    metadata = curves[keys + ["cell_id", "ano", "contexto_agro", "vpd_pre_60d"]]
    out = values.reset_index().merge(metadata.drop_duplicates(keys), on=keys,
                                    validate="one_to_one")
    pre = curves[curves.k.lt(0)].groupby(keys).valor.mean().rename("vegetacao_pre")
    out = out.merge(pre.reset_index(), on=keys, validate="one_to_one")
    out["mudanca"] = out.posterior - out.inicial
    return out


def balance_table(pairs: pd.DataFrame) -> pd.DataFrame:
    """Disponibilidade e distribuição das covariáveis, sem teste de equilíbrio."""
    rows = []
    for (variable, group), part in pairs.groupby(["variavel", "contexto_agro"], observed=True):
        for covariate in COVARIATES:
            x = part[covariate].dropna()
            rows.append({"Indicador": variable.upper(), "Contexto": str(group),
                         "Covariável": covariate, "Episódios": len(part),
                         "Células": part.cell_id.nunique(), "Válidos": len(x),
                         "Mínimo": x.min(), "P10": x.quantile(.1), "Mediana": x.median(),
                         "P90": x.quantile(.9), "Máximo": x.max()})
    return pd.DataFrame(rows)


def overlap_table(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variable, part in pairs.groupby("variavel"):
        for a, b in combinations(GROUPS, 2):
            x, y = part[part.contexto_agro == a], part[part.contexto_agro == b]
            shared = sorted(set(x.ano) & set(y.ano))
            for covariate in COVARIATES:
                u, v = x[covariate].dropna(), y[covariate].dropna()
                lo, hi = max(u.min(), v.min()), min(u.max(), v.max())
                rows.append({"Indicador": variable.upper(), "Grupo A": a, "Grupo B": b,
                             "Covariável": covariate, "Anos compartilhados": len(shared),
                             "Lista de anos": ", ".join(str(int(z)) for z in shared),
                             "Interseção mínima": lo, "Interseção máxima": hi,
                             "Fração A na interseção": u.between(lo, hi).mean()
                             if len(u) and len(v) else np.nan,
                             "Fração B na interseção": v.between(lo, hi).mean()
                             if len(u) and len(v) else np.nan})
    return pd.DataFrame(rows)


def _design(frame: pd.DataFrame) -> np.ndarray:
    # Covariáveis centradas: o ano entra como tendência linear, não efeitos fixos anuais.
    cov = frame[COVARIATES].to_numpy(float)
    cov = cov - cov.mean(axis=0)
    scale = cov.std(axis=0)
    cov = cov / np.where(scale > 0, scale, 1)
    return np.column_stack([np.ones(len(frame)),
                            *(frame.contexto_agro.eq(g).astype(float) for g in GROUPS[1:]), cov])


def _bootstrap(frame: pd.DataFrame, adjusted: bool, draws: int):
    """Sorteia uma única lista de células para todos os grupos e respostas em cada réplica.

    Células que contribuem a vários contextos mantêm todas as suas linhas juntas.
    Réplicas sem grupo, ou de desenho sem posto completo, não viram estimativas.
    """
    cells = frame.cell_id.drop_duplicates().tolist()
    y = frame[list(TARGETS)].to_numpy(float)
    groups = np.column_stack([frame.contexto_agro.eq(g) for g in GROUPS]).astype(float)
    x = _design(frame) if adjusted else groups
    membership = pd.Categorical(frame.cell_id, categories=cells).codes
    rng = np.random.default_rng(20261117)
    boot = np.full((draws, 3, len(TARGETS)), np.nan)
    point = np.full((3, len(TARGETS)), np.nan)
    eligible = all(frame.loc[frame.contexto_agro == g, "cell_id"].nunique() >= 5
                   for g in GROUPS)
    if not eligible:
        return point, boot, "Menos de cinco células em algum grupo"
    if adjusted and (len(cells) < 10 or len(frame) < 5 * x.shape[1]
                     or np.linalg.matrix_rank(x) < x.shape[1]):
        return point, boot, "Amostra ou posto insuficiente para o ajuste"

    def fit(weights):
        w = np.sqrt(weights)
        wx, wy = x * w[:, None], y * w[:, None]
        if np.linalg.matrix_rank(wx) < x.shape[1]:
            return None
        beta = np.linalg.lstsq(wx, wy, rcond=None)[0]
        # Médias ajustadas com as covariáveis na média dos casos completos.
        return (np.vstack([beta[0], beta[0] + beta[1], beta[0] + beta[2]])
                if adjusted else beta)

    point = fit(np.ones(len(frame)))
    for i in range(draws):
        frequency = np.bincount(rng.integers(0, len(cells), len(cells)), minlength=len(cells))
        estimate = fit(frequency[membership])
        if estimate is not None:
            boot[i] = estimate
    return point, boot, "Exploratório: IC pontual, sem correção múltipla"


def context_comparison(pairs: pd.DataFrame, draws: int = 999):
    """Bruto, bruto nos casos completos e ajuste linear nos MESMOS casos completos.

    Sem seleção por resposta: apenas cobertura, covariáveis observadas e guardas de
    disponibilidade (não são cálculo de poder). O ajuste é associativo e pode extrapolar.
    """
    summaries, contrasts = [], []
    for variable, data in pairs.groupby("variavel"):
        complete = data.dropna(subset=COVARIATES)
        for model, frame, adjusted in [("Bruto", data, False),
                                        ("Bruto: casos completos", complete, False),
                                        ("Ajuste linear", complete, True)]:
            point, boot, status = _bootstrap(frame, adjusted, draws)
            for i, group in enumerate(GROUPS):
                part = frame[frame.contexto_agro == group]
                for j, target in enumerate(TARGETS):
                    valid = np.isfinite(boot[:, i, j])
                    ci = np.quantile(boot[valid, i, j], [.025, .975]) if (
                        valid.mean() >= .95 and valid.any()) else [np.nan, np.nan]
                    summaries.append({"Indicador": variable.upper(), "Modelo": model,
                                      "Contexto": group, "Medida": target,
                                      "Estimativa": point[i, j], "IC inferior": ci[0],
                                      "IC superior": ci[1], "Episódios": len(part),
                                      "Células": part.cell_id.nunique(), "Réplicas válidas":
                                      int(valid.sum()), "Situação": status})
            for a, b in combinations(range(3), 2):
                for j, target in enumerate(TARGETS):
                    delta = boot[:, b, j] - boot[:, a, j]
                    valid = np.isfinite(delta)
                    ci = np.quantile(delta[valid], [.025, .975]) if (
                        valid.mean() >= .95 and valid.any()) else [np.nan, np.nan]
                    contrasts.append({"Indicador": variable.upper(), "Modelo": model,
                                      "Contraste": f"{GROUPS[b]} menos {GROUPS[a]}",
                                      "Medida": target, "Estimativa": point[b, j] - point[a, j],
                                      "IC inferior": ci[0], "IC superior": ci[1],
                                      "Episódios": len(frame), "Células": frame.cell_id.nunique(),
                                      "Réplicas válidas": int(valid.sum()), "Situação": status})
    return pd.DataFrame(summaries), pd.DataFrame(contrasts)


def paired_plot(summary: pd.DataFrame, variable: str, title: str):
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    shown = summary[(summary.Indicador == variable.upper()) & (summary.Modelo == "Bruto")]
    for group, color in zip(GROUPS, COLORS, strict=True):
        frame = shown[shown.Contexto == group].set_index("Medida").reindex(["inicial", "posterior"])
        ax.plot([0, 1], frame.Estimativa, "o-", label=group, color=color)
        ax.fill_between([0, 1], frame["IC inferior"], frame["IC superior"], color=color, alpha=.15)
    ax.axhline(0, color="grey", lw=1)
    ax.set_xticks([0, 1], [EARLY, LATE])
    ax.set(ylabel=f"Diferença ajustada de {variable.upper()}", title=title)
    ax.legend(title="Agropecuária anterior", fontsize=9)
    return fig


def paired_basins_plot(summaries: dict[str, pd.DataFrame], variable: str):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained", sharey=True)
    for ax, (slug, summary) in zip(axes, summaries.items(), strict=True):
        shown = summary[(summary.Indicador == variable.upper()) & (summary.Modelo == "Bruto")]
        for group, color in zip(GROUPS, COLORS, strict=True):
            frame = shown[shown.Contexto == group].set_index("Medida").reindex(
                ["inicial", "posterior"])
            ax.plot([0, 1], frame.Estimativa, "o-", label=group, color=color)
            ax.fill_between([0, 1], frame["IC inferior"], frame["IC superior"],
                            color=color, alpha=.15)
        ax.axhline(0, color="grey", lw=1)
        ax.set_xticks([0, 1], [EARLY, LATE], fontsize=11)
        ax.set_title(T.NAMES[slug], fontsize=13)
    axes[0].set_ylabel(f"Diferença ajustada de {variable.upper()}", fontsize=12)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center",
               ncol=3, fontsize=11, title="Agropecuária anterior", frameon=False)
    return fig


def comparison_plot(contrasts: pd.DataFrame, variable: str, title: str):
    shown = contrasts[(contrasts.Indicador == variable.upper())
                       & (contrasts.Contraste == "Mais de 30% menos Até 10%")
                       & (contrasts.Medida == "mudanca")]
    fig, ax = plt.subplots(figsize=(9, 3.2), layout="constrained")
    for i, row in enumerate(shown.itertuples(index=False, name=None)):
        _, model, _, _, estimate, lower, upper, *_ = row
        ax.plot(estimate, i, "o", color="#24645b")
        ax.hlines(i, lower, upper, color="#24645b")
    ax.axvline(0, color="grey", lw=1)
    ax.set_yticks(range(len(shown)), shown.Modelo)
    ax.invert_yaxis()
    ax.set(title=title, xlabel=f"Contraste na mudança de {variable.upper()} (IC pontual 95%)")
    return fig


def history_sensitivity(slug: str, table: pd.DataFrame) -> pd.DataFrame:
    """Janelas simétricas 1..máximo disponível (até 3); remove um ano por vez em ambas zonas.

    O ano do decreto é sempre excluído. Não calcula p ou IC com apenas 1–3 anos prévios.
    """
    event = pd.Timestamp(T.EVENTS[slug]["date"]).year
    available = set(table.ano)
    rows = []
    for width in range(1, 4):
        before, after = set(range(event - width, event)), set(range(event + 1, event + width + 1))
        if not (before | after).issubset(available):
            continue
        omitted = [None] + sorted(before | after) if width > 1 else [None]
        for excluded in omitted:
            prior, post = sorted(before - {excluded}), sorted(after - {excluded})
            zone_changes = {}
            for zone, frame in table.groupby("zona"):
                pre = frame[frame.ano.isin(prior)].focos_100km2.mean()
                later = frame[frame.ano.isin(post)].focos_100km2.mean()
                zone_changes[zone] = later - pre
                rows.append({"Bacia": T.NAMES[slug], "Zona": zone, "Largura": width,
                             "Ano retirado": excluded, "Anos antes": ", ".join(map(str, prior)),
                             "Anos depois": ", ".join(map(str, post)), "Média antes": pre,
                             "Média depois": later, "Mudança": later - pre})
            if set(ZONE_COLORS).issubset(zone_changes):
                rows.append({"Bacia": T.NAMES[slug], "Zona": "Mudança UC menos entorno",
                             "Largura": width, "Ano retirado": excluded,
                             "Anos antes": ", ".join(map(str, prior)),
                             "Anos depois": ", ".join(map(str, post)),
                             "Média antes": np.nan, "Média depois": np.nan,
                             "Mudança": zone_changes["Área da UC atual"]
                             - zone_changes["Entorno de 25 km"]})
    return pd.DataFrame(rows)


def history_sensitivity_plot(table: pd.DataFrame, title: str):
    fig, ax = plt.subplots(figsize=(9, 4.3), layout="constrained")
    baseline = table[table["Ano retirado"].isna()]
    for i, (zone, color) in enumerate(ZONE_COLORS.items()):
        frame = baseline[baseline.Zona == zone].sort_values("Largura")
        x = frame.Largura.to_numpy() + (i - .5) * .09
        ax.plot(x, frame["Mudança"], "o-", label=zone, color=color)
        for position, width in zip(x, frame.Largura, strict=True):
            sensitivity = table[(table.Zona == zone) & (table.Largura == width)]
            ax.vlines(position, sensitivity["Mudança"].min(), sensitivity["Mudança"].max(),
                      color=color, alpha=.6, linewidth=3)
    ax.axhline(0, color="grey", lw=1)
    widths = sorted(baseline.Largura.unique())
    ax.set_xticks(widths, [f"{w} ano(s) de cada lado" for w in widths])
    ax.set(title=title, ylabel="Mudança: focos / 100 km² / ano")
    ax.legend(fontsize=9)
    return fig


def history_climate(slug: str, geo: dict, zones, years=range(2003, 2025)) -> pd.DataFrame:
    """Chuva CHIRPS e VPD ERA5 anuais ponderados pela interseção de células e polígonos.

    São aproximações na grade ERA5: a meteorologia não é observada exatamente nos
    polígonos como os focos. Cobertura: ≥90% dos dias por célula e da área por ano.
    """
    grid = geo["grid"]
    metric = grid.to_crs(6933)
    weights = {row.zona: shapely.area(shapely.intersection(
        metric.geometry.to_numpy(), row.geometry)) for row in zones.to_crs(6933).itertuples()}
    rain = pd.read_parquet(T.processed(slug) / "chirps/diario.parquet").reindex(columns=grid.index)
    rain.index = pd.to_datetime(rain.index)
    rows = []
    for year in years:
        path = T.processed(slug) / f"daily_{year}-01-01_{year}-12-31.nc"
        with xr.open_dataset(path) as data:
            vpd = data.vpd_kpa_mean.load().sel(
                latitude=xr.DataArray(grid.latitude.to_numpy(), dims="cell"),
                longitude=xr.DataArray(grid.longitude.to_numpy(), dims="cell")).to_pandas()
        rainfall = rain[rain.index.year == year]
        ndays = 366 if pd.Timestamp(year, 12, 31).dayofyear == 366 else 365
        values = {"VPD (kPa)": vpd.mean().where(vpd.count() >= .9 * ndays).to_numpy(),
                  "Chuva (mm/ano)": rainfall.sum(min_count=int(np.ceil(.9 * ndays))).to_numpy()}
        for zone, weight in weights.items():
            for variable, value in values.items():
                good = np.isfinite(value) & (weight > 0)
                coverage = weight[good].sum() / weight.sum()
                rows.append({"ano": year, "zona": zone, "Variável": variable,
                             "Valor": np.average(value[good], weights=weight[good])
                             if coverage >= .9 else np.nan,
                             "Fração de área válida": coverage,
                             "Células com interseção": int((weight > 0).sum())})
    return pd.DataFrame(rows)


def history_climate_plot(slug: str, climate: pd.DataFrame):
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), layout="constrained", sharex=True)
    year = pd.Timestamp(T.EVENTS[slug]["date"]).year
    for ax, variable in zip(axes, ["Chuva (mm/ano)", "VPD (kPa)"], strict=True):
        for zone, color in ZONE_COLORS.items():
            frame = climate[(climate.Variável == variable) & (climate.zona == zone)]
            ax.plot(frame.ano, frame.Valor, ".-", color=color, label=zone)
        ax.axvspan(year - .5, year + .5, color="grey", alpha=.15)
        ax.set_ylabel(variable)
    axes[0].set_title(f"{T.NAMES[slug]} · meteorologia nos recortes atuais, ponderada por área")
    axes[0].legend(fontsize=9)
    axes[1].set_xticks(range(2003, 2025))
    axes[1].tick_params(axis="x", labelrotation=60)
    return fig
