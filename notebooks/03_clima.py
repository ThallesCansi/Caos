import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="03 · Clima 1990–2024")

with app.setup:
    import marimo as mo
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import xarray as xr
    from matplotlib.colors import TwoSlopeNorm
    from statsmodels.stats.multitest import multipletests

    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.regional import anomalies, daily_files, regional_frame, summarize, theil_sen
    from amazon_chaos.viz import COLORS, LABELS, MONTHS, map_cells

    book = nb.notebook("03_clima")
    BASE = ("1991-01-01", "2020-12-31")  # normal climatológica da OMM
    SCIENCE = ("2001-01-01", "2024-12-31")
    MONTHLY = {"precip": "sum"}  # o resto: média
    TREND_SERIES = [("t2m", "Temperatura média (°C)"), ("tmax", "Máxima média (°C)"),
                    ("vpd", "VPD médio (kPa)"), ("rh", "Umidade relativa (%)"),
                    ("precip", "Chuva anual (mm)"),
                    ("dry_spell", "Maior sequência seca (dias)")]


@app.cell(hide_code=True)
def _():
    nb.header(
        "03 · Clima diário 1990–2024",
        "Como é o clima de cada bacia, como ele muda no espaço e o que mudou em 35 anos?",
        stage="F2 · séries (gate: completude, unidades e calendário documentados)",
        inputs=["`data/processed/<experimento>/daily_<ano>.nc` (ERA5, dia local UTC−3)",
                "`summary_1990_2024.nc` (gerado por `amazon-chaos era5 summarize`)"],
        outputs=["`reports/figures/03_clima/<slug>/`", "`reports/tables/03_clima/<slug>/`"],
    )
    return


@app.cell
def _():
    picker = nb.region_picker()
    picker
    return (picker,)


@app.cell
def _(picker):
    cfg = load_region(picker.value)
    slug = cfg["slug"]
    try:
        daily_files(cfg, 1990, 2024)
    except FileNotFoundError:
        mo.stop(True, nb.missing([regions.processed_dir(cfg) / "daily_<ano>.nc"],
                                 f"make pull REGION={slug}   # ou, no HPC: "
                                 f"sbatch --export=ALL,REGION={slug} scripts/hpc/era5.sbatch"))
    with mo.status.spinner(f"Resumindo {cfg['name']} (na primeira vez lê os 35 anos)…"):
        summary = summarize(cfg, 1990, 2024)
    daily = regional_frame(summary)
    inside = summary.weight_km2 > 0
    cells = regions.cells(cfg)
    limit = regions.boundary(cfg)
    rivers = regions.load_context(cfg).get("rios")
    region = cfg["name"]
    nb.stats({"Células": int(inside.sum()), "Área (km²)": int(summary.weight_km2.sum()),
              "Dias": len(daily), "De": f"{daily.index[0]:%d/%m/%Y}",
              "Até": f"{daily.index[-1]:%d/%m/%Y}"},
             caption=f"{region} · normal 1991–2020 · janela científica 2001–2024")
    return cells, cfg, daily, inside, limit, region, rivers, slug, summary


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 1. De onde vêm os números

    **ERA5** (ECMWF/Copernicus) é uma reanálise: um modelo de previsão do tempo corrigido,
    hora a hora desde 1940, por milhões de observações. O resultado é um "mapa do tempo"
    completo numa grade de 0,25° (cerca de 28 km). **Não é a medição de um termômetro em
    cada célula**: é a melhor estimativa física consistente com as observações disponíveis.

    De seis variáveis horárias (temperatura e ponto de orvalho a 2 m, pressão, vento a 10 m
    e chuva) derivamos umidade relativa, umidade específica, déficit de pressão de vapor
    (VPD) e velocidade do vento, **hora a hora, antes de agregar**. As estatísticas diárias
    usam o dia local UTC−3 e só existem quando o dia tem as 24 horas completas.
    """)
    return


@app.cell(hide_code=True)
def _(inside, slug, summary):
    _possible = int(summary.days_in_year.sum()) * int(inside.sum())
    _quality = pd.DataFrame([
        {"Variável": LABELS[v], "Célula-dias completos": int(summary[f"complete_days_{v}"].sum()),
         "Possíveis": _possible}
        for v in ["t2m", "tmax", "rh", "vpd", "wind", "precip"]])
    _quality["Completude (%)"] = (100 * _quality["Célula-dias completos"]
                                  / _quality["Possíveis"]).round(4)
    mo.vstack([
        book.table(_quality, "completude", "Célula-dias com as 24 horas válidas, 1990–2024.",
                   region=slug, selection=None),
        nb.caveat("**Precisão do Earth Data Hub (D-007).** O espelho guarda cerca de 10 bits de "
                  "mantissa: erro relativo de até 0,05%, sem viés (até 0,125 °C numa hora). "
                  "Na média regional isso desaparece; para descritores sensíveis a ruído em "
                  "células individuais, a sensibilidade é testada nos cadernos 05 e 07."),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 2. Do cubo de dados à série da região

    Cada variável diária é um cubo `valor[dia, latitude, longitude]`. A **série regional**
    resume cada dia numa média ponderada pela área de cada célula dentro da bacia. Para a
    chuva, é a média espacial dos totais diários, não a soma de milímetros.
    """)
    return


@app.function
def plot_series(daily, region):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True, layout="constrained",
                                   height_ratios=[1.3, 1])
    ax1.fill_between(daily.index, daily.tmin, daily.tmax, color=COLORS["t2m"], alpha=0.12,
                     lw=0, label="mínima–máxima do dia")
    ax1.plot(daily.index, daily.t2m, color=COLORS["t2m"], lw=0.35, alpha=0.6,
             label="média do dia")
    ax1.plot(daily.t2m.rolling(365, center=True).mean(), color=COLORS["tmax"], lw=2.2,
             label="média móvel de 365 dias")
    ax1.set(ylabel="°C", title=f"Temperatura do ar a 2 m · média regional · {region}")
    ax1.legend(ncol=3, loc="upper left", fontsize=8.5)
    rain = daily.precip.resample("MS").sum()
    ax2.bar(rain.index, rain, width=25, color=COLORS["precip"], alpha=0.8)
    ax2.plot(rain.rolling(12, center=True).mean(), color="#123f5e", lw=1.8,
             label="média móvel de 12 meses")
    ax2.set(ylabel="mm/mês", title="Chuva mensal · média regional")
    ax2.legend(loc="upper left", fontsize=8.5)
    ax2.xaxis.set_major_locator(mdates.YearLocator(5))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return fig


@app.cell(hide_code=True)
def _(daily, region, slug):
    book.figure(plot_series(daily, region), "serie_35_anos",
                f"{region}: temperatura média diária regional (faixa: mínima–máxima; linha "
                "grossa: média móvel de 365 dias) e chuva mensal, 1990–2024. ERA5.", region=slug)
    return


@app.function
def plot_year(daily, region, year="2024"):
    sel = daily.loc[year]
    panels = [("t2m", "°C"), ("rh", "%"), ("vpd", "kPa"), ("wind", "m/s"), ("precip", "mm/dia")]
    fig, axes = plt.subplots(len(panels), 1, figsize=(13, 12), sharex=True, layout="constrained")
    for ax, (var, unit) in zip(axes, panels, strict=True):
        normal = anomalies(daily[var], BASE)[1]
        if var == "precip":
            ax.bar(sel.index, sel.precip, color=COLORS["precip"], width=1)
        else:
            ax.plot(sel.index, sel[var], color=COLORS[var], lw=1.4)
        ax.plot(sel.index, normal.reindex(sel.index.dayofyear).to_numpy(), color=COLORS["ink"],
                ls="--", lw=1.1, label="normal 1991–2020")
        ax.set(ylabel=unit, title=LABELS[var])
    axes[0].fill_between(sel.index, sel.tmin, sel.tmax, color=COLORS["t2m"], alpha=0.15, lw=0)
    axes[0].legend(loc="upper left", fontsize=8.5)
    axes[-1].set_xticks(pd.date_range(f"{year}-01-01", periods=12, freq="MS"), MONTHS)
    fig.suptitle(f"{region} · {year}, dia a dia", fontsize=14, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(daily, region, slug):
    _hot = anomalies(daily.t2m, BASE)[0].loc["2024"]
    mo.vstack([
        mo.md("### Um ano de perto: 2024 contra o ano normal\n\nA linha tracejada é o ciclo "
              "anual médio de 1991–2020 de cada dia do calendário, suavizado em 31 dias."),
        book.figure(plot_year(daily, region), "ano_2024",
                    f"{region}: 2024 dia a dia (temperatura, umidade relativa, VPD, vento e "
                    "chuva) contra o ciclo anual normal de 1991–2020.", region=slug),
        mo.md(nb.pt(f"Em 2024, **{int((_hot > 0).sum())} de {len(_hot)} dias** ficaram acima da "
                    f"normal de temperatura; anomalia média de **{_hot.mean():+.2f} °C**.")),
    ])
    return


@app.cell
def _(daily):
    agg = {c: MONTHLY.get(c, "mean") for c in daily.columns}
    monthly = daily.loc[BASE[0]:BASE[1]].resample("MS").agg(agg)
    normals = monthly.groupby(monthly.index.month).mean()
    p10 = monthly.groupby(monthly.index.month).quantile(0.1)
    p90 = monthly.groupby(monthly.index.month).quantile(0.9)
    dry = [MONTHS[m - 1] for m in normals.index[normals.precip < 100]]
    annual_rain = monthly.precip.groupby(monthly.index.year).sum()
    return agg, annual_rain, dry, normals, p10, p90


@app.function
def plot_climogram(normals, p10, p90, region):
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    ax.bar(MONTHS, normals.precip, alpha=0.9,
           color=[COLORS["precip"] if v >= 100 else "#9ec3dc" for v in normals.precip])
    ax.errorbar(MONTHS, normals.precip, fmt="none", ecolor="#123f5e", elinewidth=0.8, capsize=3,
                yerr=[normals.precip - p10.precip, p90.precip - normals.precip])
    ax.axhline(100, color="#123f5e", ls=":", lw=1)
    ax.set(ylabel="Chuva (mm/mês)", title=f"Climograma · {region} · 1991–2020")
    ax.grid(axis="x", visible=False)
    twin = ax.twinx()
    twin.plot(MONTHS, normals.tmax, color=COLORS["tmax"], ls="--", lw=1.2, label="máxima")
    twin.plot(MONTHS, normals.t2m, color=COLORS["t2m"], marker="o", lw=2.4, label="média")
    twin.plot(MONTHS, normals.tmin, color=COLORS["tmin"], ls="--", lw=1.2, label="mínima")
    twin.legend(loc="upper right", fontsize=8.5, title="Temperatura", title_fontsize=8.5)
    twin.set_ylabel("Temperatura (°C)", color=COLORS["t2m"])
    twin.grid(False)
    twin.spines["right"].set_visible(True)
    return fig


@app.function
def plot_cycles(normals, p10, p90):
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained", sharex=True)
    for ax, var in zip(axes.flat, ["rh", "vpd", "dtr", "wind"], strict=True):
        ax.fill_between(MONTHS, p10[var], p90[var], color=COLORS[var], alpha=0.18,
                        label="10º–90º percentil entre anos")
        ax.plot(MONTHS, normals[var], color=COLORS[var], marker="o", lw=2)
        ax.set(title=LABELS[var])
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("O ciclo anual das outras variáveis", fontsize=13, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(annual_rain, dry, normals, p10, p90, region, slug):
    _table = normals[["t2m", "tmin", "tmax", "precip", "rh", "vpd", "wind"]].copy()
    _table.index = MONTHS
    _table = _table.round(2).rename(columns={k: LABELS[k] for k in _table.columns}).T
    mo.vstack([
        mo.md("## 3. O ritmo do ano\n\nO climograma resume o ano típico da normal 1991–2020. "
              "Usamos o limiar operacional de **100 mm/mês** para mês seco, comum em estudos "
              "amazônicos: abaixo dele, a floresta tende a consumir mais água do que recebe."),
        book.figure(plot_climogram(normals, p10, p90, region), "climograma",
                    f"{region}: chuva mensal (barras; claras = mês seco < 100 mm; erro = 10º–90º "
                    "percentil entre anos) e temperaturas média, mínima e máxima, 1991–2020.",
                    region=slug),
        mo.md(nb.pt(f"Chuva anual normal: **{annual_rain.mean():,.0f} mm** (de "
                    f"{annual_rain.min():,.0f} a {annual_rain.max():,.0f} mm). Meses secos: "
                    f"**{', '.join(dry) if dry else 'nenhum'}**.")),
        book.figure(plot_cycles(normals, p10, p90), "ciclo_anual",
                    f"{region}: ciclo anual da umidade relativa, VPD, amplitude térmica e "
                    "vento, normal 1991–2020 (faixa: 10º–90º percentil entre anos).", region=slug),
        book.table(_table.reset_index(names="Variável"), "normais_mensais",
                   f"{region}: normais mensais 1991–2020 (médias regionais; chuva em mm/mês).",
                   region=slug, selection=None),
        nb.caveat("**Leitura.** Na estação seca a chuva despenca, a umidade relativa cai e o VPD "
                  "(a \"sede\" do ar) e a amplitude térmica sobem. O VPD é uma das variáveis mais "
                  "ligadas ao estresse da floresta e ao risco de fogo.", "info"),
    ])
    return


@app.cell
def _(inside, summary):
    by_month = (summary.sel(month=slice(*BASE))[
        [f"cell_{v}" for v in ["t2m", "precip", "vpd", "dtr", "wind", "rh"]]]
        .groupby("month.month").mean())
    fields = {
        "t2m": (by_month.cell_t2m.mean("month"), "YlOrRd", "Temperatura média (°C)"),
        "precip": (by_month.cell_precip.sum("month", min_count=12), "YlGnBu",
                   "Chuva anual (mm)"),
        "dry": ((by_month.cell_precip < 100).sum("month").where(inside), "OrRd",
                "Meses secos (< 100 mm)"),
        "vpd": (by_month.cell_vpd.mean("month"), "YlOrBr", "VPD médio (kPa)"),
        "dtr": (by_month.cell_dtr.mean("month"), "PuRd", "Amplitude térmica (°C)"),
        "wind": (by_month.cell_wind.mean("month"), "PuBu", "Vento médio (m/s)"),
    }
    return by_month, fields


@app.function
def plot_normal_maps(cells, fields, limit, rivers, region):
    fig, axes = plt.subplots(2, 3, figsize=(14, 14), layout="constrained")
    for ax, (field, cmap, label) in zip(axes.flat, fields.values(), strict=True):
        map_cells(ax, cells, field, cmap, label, outline=limit, lines=rivers)
        ax.set_title(label)
    fig.suptitle(f"Normal 1991–2020, célula a célula · {region}", fontsize=14, x=0.02,
                 ha="left")
    return fig


@app.function
def latitude_profile(summary, fields):
    w = summary.weight_km2
    keep = w.sum("longitude").values > 0
    return pd.DataFrame({
        key: ((field.fillna(0) * w).sum("longitude") / w.sum("longitude")).values[keep]
        for key, (field, _, _) in fields.items()
    }, index=summary.latitude.values[keep])


@app.function
def plot_profile(profile, region):
    fig, axes = plt.subplots(1, 4, figsize=(13, 6), sharey=True, layout="constrained")
    for ax, (key, color, label) in zip(axes, [
            ("t2m", COLORS["t2m"], "Temperatura (°C)"),
            ("precip", COLORS["precip"], "Chuva anual (mm)"),
            ("dry", "#b0523b", "Meses secos"), ("vpd", COLORS["vpd"], "VPD (kPa)")], strict=True):
        ax.plot(profile[key], profile.index, color=color, lw=2.4)
        ax.set(title=label)
    axes[0].set_ylabel("Latitude (°)")
    fig.suptitle(f"Perfil norte–sul · {region} · normal 1991–2020", fontsize=13, x=0.02,
                 ha="left")
    return fig


@app.cell(hide_code=True)
def _(cells, fields, limit, region, rivers, slug, summary):
    _profile = latitude_profile(summary, fields)
    _north, _south = _profile.iloc[:8].mean(), _profile.iloc[-8:].mean()
    mo.vstack([
        mo.md("## 4. A geografia do clima\n\nO mesmo resumo da normal, **célula por célula**. "
              "Cada cor é um polígono ERA5 recortado pelo limite da bacia; as escalas são "
              "próprias de cada painel."),
        book.figure(plot_normal_maps(cells, fields, limit, rivers, region), "mapas_normal",
                    f"{region}: normal 1991–2020 por célula ERA5 (temperatura, chuva anual, "
                    "meses secos, VPD, amplitude térmica e vento).", region=slug),
        mo.md("### O gradiente norte–sul\n\nAs duas bacias atravessam cerca de 13° de latitude, "
              "das cabeceiras no Cerrado de Mato Grosso à foz no Amazonas. A média de cada faixa "
              "de latitude, ponderada pela área, resume a geografia."),
        book.figure(plot_profile(_profile, region), "perfil_norte_sul",
                    f"{region}: médias por faixa de latitude (ponderadas pela área), normal "
                    "1991–2020.", region=slug),
        mo.md(nb.pt(
            f"Dois graus mais ao norte × dois graus mais ao sul: chuva "
            f"**{_north.precip:,.0f} × {_south.precip:,.0f} mm/ano**, meses secos "
            f"**{_north.dry:.1f} × {_south.dry:.1f}**, VPD **{_north.vpd:.2f} × "
            f"{_south.vpd:.2f} kPa**.")),
        nb.caveat("**A média da bacia mistura climas.** Por isso as comparações de perturbação "
                  "(caderno 08) controlam latitude e relevo, e não usam a bacia inteira."),
    ])
    return


@app.function
def plot_seasons(cells, by_month, normals, limit, rivers):
    rolling = pd.concat([normals.precip, normals.precip.iloc[:2]]).rolling(3).sum().iloc[2:]
    rolling.index = [(m - 3) % 12 + 1 for m in range(3, 15)]

    def quarter(start):
        return [(start + k - 1) % 12 + 1 for k in range(3)]

    starts = [int(rolling.idxmax()), int(rolling.idxmin())]
    fig, axes = plt.subplots(1, 4, figsize=(16, 7.8), layout="constrained")
    axes = np.reshape(axes, (2, 2))
    for row, start in enumerate(starts):
        sel = by_month.sel(month=quarter(start))
        name = "–".join(MONTHS[m - 1] for m in quarter(start))
        map_cells(axes[row, 0], cells, sel.cell_precip.sum("month") / 3, "YlGnBu", "mm/mês",
                  outline=limit, lines=rivers, vmin=0, vmax=float(by_month.cell_precip.max()))
        map_cells(axes[row, 1], cells, sel.cell_vpd.mean("month"), "YlOrBr", "kPa",
                  outline=limit, lines=rivers, vmin=0, vmax=float(by_month.cell_vpd.max()))
        axes[row, 0].set_title(f"Chuva · {name}")
        axes[row, 1].set_title(f"VPD · {name}")
    fig.suptitle("Trimestre mais chuvoso × mais seco · mesma escala de cor por variável",
                 fontsize=13, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(by_month, cells, limit, normals, region, rivers, slug):
    mo.vstack([
        mo.md("## 5. Duas estações, dois mapas\n\nO trimestre mais chuvoso e o mais seco da "
              "normal, escolhidos pela chuva média regional. Chuva e VPD se opõem: onde e quando "
              "falta água, o ar puxa mais vapor da vegetação."),
        book.figure(plot_seasons(cells, by_month, normals, limit, rivers), "estacoes",
                    f"{region}: chuva média mensal e VPD nos trimestres mais chuvoso e mais seco "
                    "da normal 1991–2020.", region=slug),
    ])
    return


@app.cell
def _(agg, daily, summary):
    annual = daily.resample("YS").agg(agg)
    annual.index = annual.index.year
    _w = summary.weight_km2
    annual["dry_spell"] = ((summary.longest_dry_spell * _w).sum(("latitude", "longitude"))
                           .values / float(_w.sum()))
    annual["hottest"] = daily.tmax.resample("YS").max().values
    anomaly = annual.t2m - annual.loc[1991:2020].t2m.mean()
    return annual, anomaly


@app.function
def plot_stripes(anomaly, region):
    fig, ax = plt.subplots(figsize=(13, 2.6), layout="constrained")
    lim = float(np.abs(anomaly).max())
    ax.bar(anomaly.index, 1, width=1, color=plt.cm.RdBu_r((anomaly + lim) / (2 * lim)))
    ax.set(xlim=(anomaly.index[0] - 0.5, anomaly.index[-1] + 0.5), yticks=[],
           title=f"Listras de temperatura · {region} · anomalia anual em relação a 1991–2020")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig


@app.function
def trend_table(annual):
    years = annual.index.values.astype(float)
    rows = []
    for var, label in TREND_SERIES:
        values = annual[var].values
        slope, p = theil_sen(values, years)
        recent = years >= 2001
        slope_r, p_r = theil_sen(values[recent], years[recent])
        rows.append({"Variável": label, "Tendência 1990–2024 (/década)": slope,
                     "p 1990–2024": p, "Tendência 2001–2024 (/década)": slope_r,
                     "p 2001–2024": p_r})
    return pd.DataFrame(rows)


@app.function
def plot_trends(annual, trends):
    years = annual.index.values.astype(float)
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True, layout="constrained")
    for ax, (var, label), (_, row) in zip(axes.flat, TREND_SERIES, trends.iterrows(),
                                          strict=True):
        values = annual[var].values
        slope = row["Tendência 1990–2024 (/década)"] / 10
        ax.plot(years, values, "o-", color=COLORS.get(var, "#b0523b"), ms=3.5, lw=1.2)
        middle = np.nanmedian(values) - slope * np.nanmedian(years)
        ax.plot(years, middle + slope * years, color=COLORS["ink"], ls="--", lw=1.3)
        ax.axvspan(1990, 2000.5, color="#eeeeee", zorder=0)
        ax.set_title(nb.pt(f"{label} · {10 * slope:+.3g}/década (p = {row['p 1990–2024']:.3f})"),
                     fontsize=10)
    fig.suptitle("Médias anuais · tracejado: Theil–Sen · p: Mann–Kendall corrigido (Hamed e "
                 "Rao) · cinza: arquivo 1990–2000", fontsize=12, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(annual, anomaly, region, slug):
    trends = trend_table(annual)
    mo.vstack([
        mo.md("## 6. 35 anos: o que mudou?\n\nAs listras (Ed Hawkins) mostram um ano por faixa: "
              "azul, mais frio que a normal; vermelho, mais quente."),
        book.figure(plot_stripes(anomaly, region), "listras",
                    f"{region}: anomalia anual da temperatura média regional em relação a "
                    "1991–2020.", region=slug),
        mo.md(nb.pt(f"Ano mais quente: **{anomaly.idxmax()}** ({anomaly.max():+.2f} °C); mais "
                    f"frio: **{anomaly.idxmin()}** ({anomaly.min():+.2f} °C).")),
        book.figure(plot_trends(annual, trends), "series_anuais",
                    f"{region}: médias anuais (chuva: total) com tendência de Theil–Sen e p de "
                    "Mann–Kendall corrigido para autocorrelação (Hamed e Rao, 1998).",
                    region=slug),
        book.table(trends.round(4), "tendencias",
                   f"{region}: tendências de Theil–Sen por década e p de Mann–Kendall com "
                   "correção de Hamed e Rao, em 1990–2024 e 2001–2024.", region=slug,
                   selection=None),
        nb.caveat("**Sobre as tendências.** Theil–Sen é a mediana das inclinações entre todos os "
                  "pares de anos, robusta a anos atípicos. O p de Mann–Kendall foi corrigido para "
                  "a autocorrelação entre anos (ENSO, ciclos decenais), que deixava o p antigo "
                  "otimista. Ainda assim, 35 anos é pouco para separar tendência de variabilidade "
                  "decenal, e tendência não é causa."),
    ])
    return (trends,)


@app.function
def trend_field(field, inside):
    """Inclinação por célula e máscara de q < 0,05 (Benjamini–Hochberg sobre as células)."""
    stacked = field.stack(cell=("latitude", "longitude"))
    years = stacked.year.values.astype(float)
    out = np.array([theil_sen(stacked[:, i].values, years)
                    for i in range(stacked.sizes["cell"])])
    slope = stacked.isel(year=0).copy(data=out[:, 0]).unstack("cell").where(inside)
    p = stacked.isel(year=0).copy(data=out[:, 1]).unstack("cell").where(inside)
    flat = p.values.ravel()
    ok = np.isfinite(flat)
    q = np.full(flat.shape, np.nan)
    q[ok] = multipletests(flat[ok], method="fdr_bh")[1]
    return slope, (p.copy(data=q.reshape(p.shape)) < 0.05) & inside


@app.cell
def _(inside, summary):
    _group = summary[["cell_t2m", "cell_vpd", "cell_precip"]].groupby("month.year")
    annual_cells = xr.merge([_group.mean()[["cell_t2m", "cell_vpd"]],
                             _group.sum(min_count=12)[["cell_precip"]],
                             summary[["hottest_day"]]])
    with mo.status.spinner("Tendência célula a célula…"):
        trend_maps = {var: trend_field(annual_cells[var], inside)
                      for var in ["cell_t2m", "hottest_day", "cell_vpd", "cell_precip"]}
    return (trend_maps,)


@app.function
def plot_trend_maps(cells, trend_maps, limit, rivers):
    meta = {"cell_t2m": ("Temperatura média", "°C/década", "RdBu_r"),
            "hottest_day": ("Dia mais quente do ano", "°C/década", "RdBu_r"),
            "cell_vpd": ("VPD médio", "kPa/década", "BrBG_r"),
            "cell_precip": ("Chuva anual", "mm/década", "BrBG")}
    fig, axes = plt.subplots(1, 4, figsize=(16, 7.8), layout="constrained")
    for ax, (var, (slope, significant)) in zip(axes, trend_maps.items(), strict=True):
        title, label, cmap = meta[var]
        lim = float(np.nanmax(np.abs(slope)))
        map_cells(ax, cells, slope, cmap, label, outline=limit, lines=rivers,
                  norm=TwoSlopeNorm(0, -lim, lim), stipple=significant)
        ax.set_title(title, fontsize=10.5)
    fig.suptitle("Tendências 1990–2024 por célula · pontos: q < 0,05 (Benjamini–Hochberg sobre "
                 "as células; p de Mann–Kendall corrigido)", fontsize=12, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(cells, limit, region, rivers, slug, trend_maps):
    _share = {v: float(s.sum() / np.isfinite(t).sum()) for v, (t, s) in trend_maps.items()}
    mo.vstack([
        mo.md("## 7. Onde mudou mais?\n\nA mesma tendência, célula por célula. Os pontos marcam "
              "células com **q < 0,05** depois de corrigir para o número de células testadas "
              "(Benjamini–Hochberg). Células vizinhas não são independentes, então mesmo o q "
              "é otimista: leia os mapas pelo padrão espacial, não por células isoladas."),
        book.figure(plot_trend_maps(cells, trend_maps, limit, rivers), "mapas_tendencia",
                    f"{region}: tendência de Theil–Sen 1990–2024 por célula; pontos: q < 0,05 "
                    "(BH sobre as células, p de Mann–Kendall corrigido para autocorrelação).",
                    region=slug),
        mo.md(nb.pt("Fração de células com q < 0,05: " + " · ".join(
            f"{name} {100 * _share[v]:.0f}%" for v, name in [
                ("cell_t2m", "temperatura"), ("hottest_day", "dia mais quente"),
                ("cell_vpd", "VPD"), ("cell_precip", "chuva")]) + ".")),
    ])
    return


@app.function
def plot_monthly_anomalies(daily, agg):
    months = daily.resample("MS").agg(agg)
    normal = months.loc[BASE[0]:BASE[1]].groupby(lambda d: d.month).mean()
    t_anom = months.t2m - normal.t2m.reindex(months.index.month).values
    r_anom = 100 * (months.precip / normal.precip.reindex(months.index.month).values - 1)

    def grid(s):
        return s.groupby([s.index.year, s.index.month]).first().unstack()

    fig, axes = plt.subplots(1, 2, figsize=(13, 9), layout="constrained")
    for ax, data, cmap, label, lim in [
            (axes[0], grid(t_anom), "RdBu_r", "Anomalia de temperatura (°C)",
             float(np.abs(t_anom).max())),
            (axes[1], grid(r_anom), "BrBG", "Anomalia de chuva (%)", 100)]:
        im = ax.imshow(data, aspect="auto", cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim))
        ax.set(xticks=range(12), xticklabels=MONTHS, yticks=range(0, len(data), 2),
               yticklabels=data.index[::2], title=label)
        ax.grid(False)
        fig.colorbar(im, ax=ax, shrink=0.6)
    return fig


@app.function
def plot_extremes(daily, annual, summary):
    t_daily, _ = anomalies(daily.tmax, BASE)
    threshold = t_daily.loc[BASE[0]:BASE[1]].quantile(0.9)
    hot_days = (t_daily > threshold).groupby(t_daily.index.year).sum()
    w = summary.weight_km2
    rain_days = (summary.rain_days * w).sum(("latitude", "longitude")).values / float(w.sum())
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), layout="constrained")
    axes[0].bar(hot_days.index, hot_days,
                color=[COLORS["tmax"] if v > 36.5 else "#e2a39a" for v in hot_days])
    axes[0].axhline(36.5, color=COLORS["ink"], ls=":", lw=1)
    axes[0].set(title='Dias "quentes para a época" por ano', ylabel="dias")
    axes[1].plot(annual.index, annual.dry_spell, "o-", color="#b0523b", ms=3.5)
    axes[1].set(title="Maior sequência sem chuva (< 1 mm/dia)", ylabel="dias · média regional")
    axes[2].plot(annual.index, rain_days, "o-", color=COLORS["precip"], ms=3.5)
    axes[2].set(title="Dias com chuva (≥ 1 mm) por ano", ylabel="dias · média regional")
    return fig


@app.cell(hide_code=True)
def _(agg, annual, daily, region, slug, summary):
    mo.vstack([
        mo.md("## 8. Anomalias mês a mês e extremos\n\nCada quadrado é um mês de um ano; "
              "vermelho é mais quente (ou mais seco, no painel da chuva) que a normal daquele "
              "mês. Procure os El Niño fortes de **1997–98, 2015–16 e 2023–24** e as secas de "
              "**2005 e 2010**."),
        book.figure(plot_monthly_anomalies(daily, agg), "anomalias_mensais",
                    f"{region}: anomalias mensais de temperatura (°C) e de chuva (%) em relação "
                    "à normal 1991–2020 de cada mês.", region=slug),
        book.figure(plot_extremes(daily, annual, summary), "extremos",
                    f"{region}: dias com máxima regional acima do 90º percentil das anomalias "
                    "de 1991–2020 (cerca de 36,5 por ano por construção), maior sequência seca "
                    "(calculada por célula e promediada) e dias com chuva.", region=slug),
        nb.caveat("A sequência seca é calculada em cada célula e depois promediada; sequências "
                  "que atravessam o réveillon são cortadas na virada do ano.", "neutral"),
    ])
    return


@app.function
def archive_difference(daily, agg):
    early = daily.loc["1990":"2000"].resample("MS").agg(agg)
    late = daily.loc[SCIENCE[0]:SCIENCE[1]].resample("MS").agg(agg)
    return late.groupby(late.index.month).mean() - early.groupby(early.index.month).mean()


@app.function
def plot_archive(diff):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), layout="constrained")
    for ax, (var, unit) in zip(axes, [("t2m", "°C"), ("vpd", "kPa"), ("precip", "mm/mês")],
                               strict=True):
        values = diff[var].values
        ax.bar(MONTHS, values, color=np.where(values > 0, COLORS[var], "#9aa3a9"))
        ax.axhline(0, color=COLORS["ink"], lw=0.8)
        ax.set(title=f'{LABELS[var].split(" (")[0]}: 2001–2024 menos 1990–2000', ylabel=unit)
        ax.grid(axis="x", visible=False)
    return fig


@app.cell(hide_code=True)
def _(agg, daily, region, slug):
    _diff = archive_difference(daily, agg)
    mo.vstack([
        mo.md("## 9. Arquivo 1990–2000 × janela científica 2001–2024\n\nA análise principal "
              "usa 2001–2024; os onze anos anteriores são um arquivo para testar a sensibilidade "
              "à climatologia e às condições antecedentes (D-006). Diferenças entre décadas não "
              "são, por si só, efeito de perturbação: há El Niños, secas e aquecimento global "
              "diferentes em cada uma."),
        book.figure(plot_archive(_diff), "arquivo_vs_janela",
                    f"{region}: ciclo anual de 2001–2024 menos o de 1990–2000 (temperatura, VPD "
                    "e chuva).", region=slug),
        mo.md(nb.pt(f"Em média, 2001–2024 foi **{_diff.t2m.mean():+.2f} °C** e teve "
                    f"**{_diff.precip.sum():+.0f} mm/ano** em relação a 1990–2000; VPD "
                    f"**{_diff.vpd.mean():+.3f} kPa**.")),
    ])
    return


@app.function
def compare_regions(daily, region, other_cfg):
    other = regional_frame(summarize(other_cfg, 1990, 2024))
    agg = {c: MONTHLY.get(c, "mean") for c in daily.columns}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), layout="constrained")
    for frame, name, kw in [(daily, region, {"color": COLORS["t2m"]}),
                            (other, other_cfg["name"], {"color": COLORS["ink"], "ls": "--"})]:
        monthly = frame.loc[BASE[0]:BASE[1]].resample("MS").agg(agg)
        normal = monthly.groupby(monthly.index.month).mean()
        for ax, var in zip(axes, ["t2m", "precip", "vpd"], strict=True):
            ax.plot(MONTHS, normal[var], marker="o", label=name, **kw)
    for ax, title in zip(axes, ["Temperatura média (°C)", "Chuva (mm/mês)", "VPD (kPa)"],
                         strict=True):
        ax.set_title(title)
    axes[0].legend()
    fig.suptitle("Normal 1991–2020 · médias regionais das duas bacias", fontsize=13, x=0.02,
                 ha="left")
    return fig


@app.cell(hide_code=True)
def _(daily, region, slug):
    _other = load_region("tapajos" if slug == "xingu" else "xingu")
    try:
        _shown = book.figure(compare_regions(daily, region, _other), "duas_bacias",
                             f"Normais 1991–2020 de {region} e {_other['name']}: temperatura, "
                             "chuva e VPD regionais.", region=slug)
    except FileNotFoundError:
        _shown = nb.missing([regions.processed_dir(_other)],
                            f"make pull REGION={_other['slug']}")
    mo.vstack([mo.md(f"## 10. {region} ao lado de {_other['name']}\n\nAs duas bacias são "
                     "vizinhas e atravessam a mesma faixa de latitude; a comparação regional "
                     "mostra quanto o clima de fundo difere antes de qualquer análise de "
                     "perturbação."), _shown])
    return


@app.cell(hide_code=True)
def _(annual_rain, anomaly, daily, dry, inside, normals, region, summary, trends):
    _t = trends.set_index("Variável").loc["Temperatura média (°C)"]
    _v = trends.set_index("Variável").loc["VPD médio (kPa)"]
    mo.vstack([
        mo.md("## 11. Em resumo"),
        mo.md(nb.pt("\n".join([
            f"- **{region}** · {int(inside.sum())} células ERA5 · "
            f"{float(summary.weight_km2.sum()):,.0f} km² · {len(daily):,} dias completos.",
            f"- **Ano típico (1991–2020):** {normals.t2m.mean():.1f} °C, "
            f"{annual_rain.mean():,.0f} mm de chuva; meses secos: "
            f"{', '.join(dry) if dry else 'nenhum'}.",
            f"- **Temperatura:** {_t.iloc[0]:+.2f} °C/década em 1990–2024 (p = {_t.iloc[1]:.3f}) "
            f"e {_t.iloc[2]:+.2f} °C/década em 2001–2024; ano mais quente: {anomaly.idxmax()}.",
            f"- **VPD:** {_v.iloc[0]:+.3f} kPa/década em 1990–2024 (p = {_v.iloc[1]:.3f}).",
            f"- **Dia mais quente da série:** {daily.tmax.max():.1f} °C (média regional das "
            f"máximas) em {daily.tmax.idxmax():%d/%m/%Y}.",
        ]))),
        nb.caveat(
            "**Cuidados de leitura.** (1) Reanálise não é estação: com poucas observações, o "
            "ERA5 depende mais do modelo, e sua vegetação **não acompanha** o desmatamento ano a "
            "ano (D-011). (2) A precisão do EDH é irrelevante para médias, mas é testada nos "
            "descritores por célula (D-007). (3) Tendência não é causa: nada aqui separa "
            "perturbação local, variabilidade natural e aquecimento global. (4) O espaço de "
            "fases, com τ por informação mútua e m por falsos vizinhos, está no caderno 07."),
    ])
    return


@app.cell(hide_code=True)
def _(cfg):
    nb.provenance(cfg, [regions.processed_dir(cfg) / "summary_1990_2024.nc",
                        regions.processed_dir(cfg) / "basin_grid.geojson"])
    return


if __name__ == "__main__":
    app.run()
