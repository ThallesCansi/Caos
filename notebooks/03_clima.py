# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "03 · O clima de 1990 a 2024"
# description = "Ritmo do ano, geografia e tendências"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="03 · O clima de 1990 a 2024")

with app.setup(hide_code=True):
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
    from amazon_chaos.regional import (
        anomalies,
        regional_frame,
        standardized_anomalies,
        summarize,
        theil_sen,
    )
    from amazon_chaos.viz import COLORS, LABELS, MONTHS, map_basins

    book = nb.notebook("03_clima")
    SLUGS = ["xingu", "tapajos"]
    SHORT = {"xingu": "Xingu", "tapajos": "Tapajós"}
    BASIN_COLORS = {"xingu": COLORS["ink"], "tapajos": COLORS["t2m"]}
    BASE = ("1991-01-01", "2020-12-31")  # normal climatológica da OMM
    SCIENCE = ("2001-01-01", "2024-12-31")
    TREND_SERIES = [("t2m", "Temperatura média (°C)"), ("tmax", "Máxima média (°C)"),
                    ("vpd", "VPD médio (kPa)"), ("rh", "Umidade relativa (%)"),
                    ("precip", "Chuva anual (mm)"),
                    ("dry_spell", "Maior sequência seca (dias)")]


@app.function(hide_code=True)
def agg_of(frame):
    return {c: "sum" if c == "precip" else "mean" for c in frame.columns}


@app.function(hide_code=True)
@mo.cache
def basin(slug):
    """Tudo o que o capítulo usa de uma bacia, calculado uma vez."""
    cfg = load_region(slug)
    summary = summarize(cfg, 1990, 2024)
    daily = regional_frame(summary)
    agg = agg_of(daily)
    monthly = daily.loc[BASE[0]:BASE[1]].resample("MS").agg(agg)
    annual = daily.resample("YS").agg(agg)
    annual.index = annual.index.year
    w = summary.weight_km2
    annual["dry_spell"] = ((summary.longest_dry_spell * w).sum(("latitude", "longitude"))
                           .values / float(w.sum()))
    return {
        "cfg": cfg, "name": cfg["name"], "summary": summary, "daily": daily,
        "inside": w > 0, "cells": regions.cells(cfg), "limit": regions.boundary(cfg),
        "rivers": regions.load_context(cfg).get("rios"),
        "normals": monthly.groupby(monthly.index.month).mean(),
        "p10": monthly.groupby(monthly.index.month).quantile(0.1),
        "p90": monthly.groupby(monthly.index.month).quantile(0.9),
        "annual_rain": monthly.precip.groupby(monthly.index.year).sum(),
        "annual": annual,
        "anomaly": annual.t2m - annual.loc[1991:2020].t2m.mean(),
    }


@app.function(hide_code=True)
def basin_picker(label="Bacia"):
    return mo.ui.dropdown(options={SHORT[s]: s for s in SLUGS}, value="Xingu", label=label)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🌡️ O clima de 1990 a 2024

    Antes de perguntar que tipo de dinâmica o clima amazônico tem, precisamos conhecê-lo
    pelo que ele tem de mais simples: quanto faz de calor, quanto chove, como o ano se
    divide entre estação chuvosa e seca, como tudo isso muda de um lugar para outro dentro
    das bacias e o que mudou em 35 anos. Este capítulo é esse retrato. Ele não depende de
    nenhum método não linear e serve a três propósitos: mostrar ao leitor o sistema que
    estamos estudando, conferir que os dados se comportam como esperado e preparar, passo a
    passo, a série que todos os capítulos seguintes analisam.

    Começamos pela origem dos números, a reanálise ERA5. Depois olhamos para 35 anos de
    temperatura e chuva e, de perto, para um ano escolhido pelo leitor. Seguem o ritmo do
    ano, a geografia do clima, as tendências, as anomalias e os extremos. Terminamos
    mostrando como a série diária vira a anomalia padronizada que entra nos descritores.
    Os mapas mostram as duas bacias juntas, lado a lado como estão no território; os
    gráficos de linhas as sobrepõem; e as figuras que acompanham uma única série têm um
    pequeno seletor de bacia.
    """)
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _var in ["t2m", "tmax", "rh", "vpd", "wind", "precip"]:
        _row = {"Variável": LABELS[_var]}
        for _slug in SLUGS:
            _s = basin(_slug)["summary"]
            _possible = int(_s.days_in_year.sum()) * int(basin(_slug)["inside"].sum())
            _row[f"Completude, {SHORT[_slug]} (%)"] = round(
                100 * int(_s[f"complete_days_{_var}"].sum()) / _possible, 4)
        _rows.append(_row)
    mo.vstack([
        mo.md(r"""
        ## 🛰️ De onde vêm os números

        O ERA5 é uma reanálise produzida pelo Centro Europeu de Previsões Meteorológicas de
        Médio Prazo [1]. Um modelo de previsão do tempo é rodado de 1940 até hoje e, a cada
        poucas horas, corrigido pelas observações disponíveis naquele momento: estações de
        superfície, radiossondas, aviões, boias e, sobretudo, satélites. O resultado é um
        retrato completo e fisicamente consistente da atmosfera, hora a hora, numa grade de
        0,25°. É preciso ter claro o que isso significa: o valor de uma célula não é a
        leitura de um termômetro, mas a melhor estimativa que o modelo e as observações
        permitem. Na Amazônia, onde as estações são poucas, o peso do modelo é maior.

        Baixamos seis variáveis horárias: a temperatura e a temperatura do ponto de orvalho a
        2 m, a pressão à superfície, as duas componentes do vento a 10 m e a chuva. Delas
        derivamos, ainda hora a hora, a umidade relativa, a umidade específica, a velocidade
        do vento e o déficit de pressão de vapor, o VPD. O VPD é a diferença entre o vapor
        que o ar comportaria se estivesse saturado e o vapor que ele de fato tem,

        $$
        \mathrm{VPD} = e_s(T) - e_s(T_d), \qquad
        e_s(T) = 0{,}6108\, \exp\!\left(\frac{17{,}27\, T}{T + 237{,}3}\right)\ \text{kPa},
        $$

        em que $T$ é a temperatura do ar, $T_d$ a do ponto de orvalho, ambas em °C, e $e_s$ a
        pressão de vapor de saturação pela fórmula de Tetens [2]. O VPD mede a sede do ar:
        quanto maior, mais água ele retira das folhas, e é uma das variáveis mais ligadas ao
        estresse da floresta e ao risco de fogo [3]. As estatísticas diárias usam o dia local,
        três horas atrás do horário universal, e só existem para os dias com as 24 horas
        completas. A Tabela 1 mostra que nenhum dia ficou de fora nas duas bacias.
        """),
        book.table(pd.DataFrame(_rows), "completude",
                   "Tabela 1. Porcentagem de células-dia com as 24 horas válidas, de 1990 a "
                   "2024, por variável e bacia.", selection=None),
        mo.callout(mo.md(
            "Os dados vêm de um espelho do ERA5 que guarda os números com precisão reduzida, "
            "um erro relativo de até 0,05%, sem viés, cerca de um décimo de grau numa hora. "
            "Nas médias o efeito desaparece; nos descritores por célula, a validação dos "
            "métodos mostra que ele fica muito abaixo do ruído das próprias séries."),
            kind="warn"),
    ])
    return


@app.function(hide_code=True)
def plot_series(slug):
    daily, region = basin(slug)["daily"], basin(slug)["name"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True, layout="constrained",
                                   height_ratios=[1.3, 1])
    ax1.fill_between(daily.index, daily.tmin, daily.tmax, color=COLORS["t2m"], alpha=0.12,
                     lw=0, label="mínima–máxima do dia")
    ax1.plot(daily.index, daily.t2m, color=COLORS["t2m"], lw=0.35, alpha=0.6,
             label="média do dia")
    ax1.plot(daily.t2m.rolling(365, center=True).mean(), color=COLORS["tmax"], lw=2.2,
             label="média móvel de 365 dias")
    ax1.set(ylabel="°C", title=f"Temperatura do ar a 2 m · {region}")
    ax1.legend(ncol=3, loc="upper left", fontsize=8.5)
    rain = daily.precip.resample("MS").sum()
    ax2.bar(rain.index, rain, width=25, color=COLORS["precip"], alpha=0.8)
    ax2.plot(rain.rolling(12, center=True).mean(), color="#123f5e", lw=1.8,
             label="média móvel de 12 meses")
    ax2.set(ylabel="mm/mês", title="Chuva mensal")
    ax2.legend(loc="upper left", fontsize=8.5)
    ax2.xaxis.set_major_locator(mdates.YearLocator(5))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return fig


@app.cell(hide_code=True)
def _():
    series_basin = basin_picker()
    return (series_basin,)


@app.cell(hide_code=True)
def _(series_basin):
    _d = basin(series_basin.value)["daily"]
    _first, _last = _d.t2m.loc["1991":"1995"].mean(), _d.t2m.loc["2020":"2024"].mean()
    mo.vstack([
        mo.md(r"""
        ## 📈 Trinta e cinco anos de clima

        A série de cada bacia é a média diária das suas células, ponderada pela área que
        cada uma tem dentro do limite; para a chuva, é a média dos totais diários, a altura
        de água que caiu em média sobre a bacia. A Figura 1 mostra a temperatura e a chuva
        de 1990 a 2024.
        """),
        series_basin,
        book.figure(plot_series(series_basin.value), "serie_35_anos",
                    "Figura 1. Temperatura média diária da bacia (faixa: entre a mínima e a "
                    "máxima do dia; linha grossa: média móvel de 365 dias) e chuva mensal, de "
                    "1990 a 2024.", save=False),
        mo.callout(mo.md(nb.pt(
            f"Média de 1991–1995: {_first:.1f} °C; média de 2020–2024: {_last:.1f} °C, uma "
            f"diferença de {_last - _first:+.1f} °C.")), kind="info"),
        mo.md(r"""
        Duas escalas de tempo dominam a figura. A mais visível é o ano: a temperatura sobe na
        estação seca e cai na chuvosa, e a chuva se concentra em metade do ano. A outra é a
        tendência, que a média móvel deixa ver: a curva grossa sobe quase continuamente, com
        saltos nos anos de El Niño forte, como 1998, 2015–2016 e 2023–2024, em que a
        circulação sobre o Pacífico tropical reduz a chuva e aquece a Amazônia [4]. Por cima
        das duas está a variação de um dia para o outro, a faixa de ruído em torno da média,
        que é o que os capítulos de dinâmica vão estudar.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_year(slug, year):
    daily, region = basin(slug)["daily"], basin(slug)["name"]
    sel = daily.loc[str(year)]
    panels = [("t2m", "°C"), ("rh", "%"), ("vpd", "kPa"), ("wind", "m/s"), ("precip", "mm/dia")]
    fig, axes = plt.subplots(len(panels), 1, figsize=(13, 12), sharex=True, layout="constrained")
    for ax, (var, unit) in zip(axes, panels, strict=True):
        normal = anomalies(daily[var], BASE)[1]
        if var == "precip":
            ax.bar(sel.index, sel.precip, color=COLORS["precip"], width=1)
        else:
            ax.plot(sel.index, sel[var], color=COLORS[var], lw=1.4)
        ax.plot(sel.index, normal.reindex(sel.index.day_of_year).to_numpy(), color=COLORS["ink"],
                ls="--", lw=1.1, label="normal 1991–2020")
        ax.set(ylabel=unit, title=LABELS[var])
    axes[0].fill_between(sel.index, sel.tmin, sel.tmax, color=COLORS["t2m"], alpha=0.15, lw=0)
    axes[0].legend(loc="upper left", fontsize=8.5)
    axes[-1].set_xticks(pd.date_range(f"{year}-01-01", periods=12, freq="MS"), MONTHS)
    fig.suptitle(f"{region} · {year}, dia a dia", fontsize=14, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _():
    year_basin = basin_picker()
    year_slider = mo.ui.slider(1990, 2024, value=2024, step=1, label="Ano", show_value=True)
    return year_basin, year_slider


@app.cell(hide_code=True)
def _(year_basin, year_slider):
    _d = basin(year_basin.value)["daily"]
    _hot = anomalies(_d.t2m, BASE)[0].loc[str(year_slider.value)]
    _rain = anomalies(_d.precip, BASE)[0].loc[str(year_slider.value)].sum()
    mo.vstack([
        mo.md(r"""
        A Figura 2 aproxima a lente: um ano inteiro, dia a dia, em cinco variáveis, contra o
        ano normal. A linha tracejada é a normal climatológica de 1991–2020 [5], a média de
        cada dia do calendário nesses trinta anos, suavizada numa janela de 31 dias. Os
        controles escolhem a bacia e o ano; a versão impressa é a de 2024, para as duas
        bacias.
        """),
        mo.hstack([year_basin, year_slider], justify="start", gap=1),
        book.figure(plot_year(year_basin.value, year_slider.value), "ano",
                    "Figura 2. Um ano dia a dia (temperatura, umidade relativa, VPD, vento e "
                    "chuva) contra o ciclo anual normal de 1991–2020. Na versão impressa, 2024.",
                    save=False),
        mo.callout(mo.md(nb.pt(
            f"{SHORT[year_basin.value]}, {year_slider.value}: {int((_hot > 0).sum())} de "
            f"{len(_hot)} dias acima da normal de temperatura, com anomalia média de "
            f"{_hot.mean():+.2f} °C; a chuva do ano ficou {_rain:+.0f} mm em relação à "
            f"normal.")), kind="info"),
        mo.md(r"""
        As cinco variáveis se movem juntas. Quando a chuva para, no meio do ano, a umidade
        relativa cai, o VPD dispara e a amplitude entre a mínima e a máxima se abre; o vento
        também fica mais forte na estação seca. Em 2024, um dos anos mais quentes e secos do
        registro, a temperatura ficou acima da normal em quase todos os dias, e o VPD da
        estação seca passou bem do normal. Movendo o controle para anos como 1996 ou 2008,
        mais frescos, a linha sólida passa a oscilar em torno da tracejada, como se espera de
        um ano típico.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_climogram(slug):
    d = basin(slug)
    normals, p10, p90 = d["normals"], d["p10"], d["p90"]
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    ax.bar(MONTHS, normals.precip, alpha=0.9,
           color=[COLORS["precip"] if v >= 100 else "#9ec3dc" for v in normals.precip])
    ax.errorbar(MONTHS, normals.precip, fmt="none", ecolor="#123f5e", elinewidth=0.8, capsize=3,
                yerr=[normals.precip - p10.precip, p90.precip - normals.precip])
    ax.axhline(100, color="#123f5e", ls=":", lw=1)
    ax.set(ylabel="Chuva (mm/mês)", title=f"Climograma · {d['name']} · 1991–2020")
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


@app.function(hide_code=True)
def plot_cycles():
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.4), layout="constrained", sharex=True)
    for ax, var in zip(axes.flat, ["t2m", "precip", "rh", "vpd", "dtr", "wind"], strict=True):
        for slug in SLUGS:
            d = basin(slug)
            ax.fill_between(MONTHS, d["p10"][var], d["p90"][var], color=BASIN_COLORS[slug],
                            alpha=0.12, lw=0)
            ax.plot(MONTHS, d["normals"][var], color=BASIN_COLORS[slug], marker="o", lw=2,
                    ms=4, label=SHORT[slug])
        ax.set(title=LABELS[var] if var != "precip" else "Chuva (mm/mês)")
    axes[0, 0].legend(fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    climo_basin = basin_picker()
    return (climo_basin,)


@app.cell(hide_code=True)
def _(climo_basin):
    _d = basin(climo_basin.value)
    _dry = [MONTHS[m - 1] for m in _d["normals"].index[_d["normals"].precip < 100]]
    _peak = MONTHS[int(_d["normals"].vpd.idxmax()) - 1]
    _rain = {s: basin(s)["annual_rain"].mean() for s in SLUGS}
    _rows = []
    for _slug in SLUGS:
        _n = basin(_slug)["normals"]
        for _var in ["t2m", "tmin", "tmax", "precip", "rh", "vpd", "wind"]:
            _rows.append({"Variável": LABELS[_var], "Bacia": SHORT[_slug],
                          **{m: round(float(_n[_var].iloc[i]), 2) for i, m in enumerate(MONTHS)}})
    mo.vstack([
        mo.md(r"""
        ## 🌦️ O ritmo do ano

        A Figura 3 é o climograma de uma bacia: a chuva de cada mês na normal de 1991–2020,
        com a faixa entre o décimo e o nonagésimo percentil dos anos, e as temperaturas
        média, mínima e máxima. Marcamos como secos os meses com menos de 100 mm, um limiar
        operacional comum em estudos amazônicos: abaixo dele, a floresta tende a transpirar
        mais água do que recebe e passa a depender da reserva do solo [6].
        """),
        climo_basin,
        book.figure(plot_climogram(climo_basin.value), "climograma",
                    "Figura 3. Climograma da normal 1991–2020: chuva mensal (barras claras: "
                    "meses com menos de 100 mm; hastes: 10º e 90º percentis entre os anos) e "
                    "temperaturas média, mínima e máxima.", save=False),
        mo.callout(mo.md(nb.pt(
            f"{SHORT[climo_basin.value]}: chuva anual normal de "
            f"{_d['annual_rain'].mean():,.0f} mm, de {_d['annual_rain'].min():,.0f} a "
            f"{_d['annual_rain'].max():,.0f} mm entre os anos. Meses secos: "
            f"{', '.join(_dry) if _dry else 'nenhum'}. Pico do VPD: {_peak}.")), kind="info"),
        mo.md(r"""
        As duas bacias têm o regime típico do sul da Amazônia: uma estação chuvosa longa, de
        outubro a maio, com o pico de janeiro a março, e uma estação seca bem marcada, de
        junho a setembro, em que a chuva cai a poucas dezenas de milímetros por mês. A
        temperatura média varia pouco ao longo do ano, de dois a três graus, e chega ao máximo
        no fim da estação seca, em agosto e setembro, quando o céu limpo e o solo mais seco
        deixam a superfície esquentar. A Figura 4 sobrepõe o ano normal das duas bacias em
        seis variáveis.
        """),
        book.figure(plot_cycles(), "ciclo_anual",
                    "Figura 4. Ciclo anual das duas bacias na normal 1991–2020: temperatura, "
                    "chuva, umidade relativa, VPD, amplitude térmica diária e vento (faixas: "
                    "10º e 90º percentis entre os anos)."),
        mo.callout(mo.md(nb.pt(
            f"Chuva anual normal: {_rain['xingu']:,.0f} mm no Xingu e "
            f"{_rain['tapajos']:,.0f} mm no Tapajós.")), kind="info"),
        mo.md(r"""
        As duas curvas quase se confundem, o que é esperado para bacias vizinhas que
        atravessam a mesma faixa de latitude. O Tapajós chove um pouco mais, cerca de 200 mm
        por ano, distribuídos por quase todos os meses, e a sua estação seca termina um pouco
        antes, com setembro menos seco; o Xingu tem um VPD ligeiramente maior em setembro.
        Na estação seca, nas duas, a umidade relativa cai de quase 90% para perto de 60%, o
        VPD quadruplica, a amplitude térmica diária passa de 7 para 12 graus e o vento ganha
        força. As faixas mostram outra coisa importante: a variação entre anos da umidade e
        do VPD é maior na estação seca; um agosto pode ser muito mais seco que outro, enquanto
        os meses chuvosos se parecem mais entre si. Diferenças de variabilidade ao longo do
        ano como essa são a razão de padronizarmos as séries antes de analisar a sua
        dinâmica, como veremos no fim do capítulo. A Tabela 2 reúne as normais mensais.
        """),
        book.table(pd.DataFrame(_rows), "normais_mensais",
                   "Tabela 2. Normais mensais de 1991–2020, médias de cada bacia (chuva em "
                   "mm/mês).", selection=None),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def normal_fields(slug):
    d = basin(slug)
    by_month = (d["summary"].sel(month=slice(*BASE))[
        [f"cell_{v}" for v in ["t2m", "precip", "vpd", "dtr", "wind", "rh"]]]
        .groupby("month.month").mean())
    return by_month, {
        "t2m": (by_month.cell_t2m.mean("month"), "YlOrRd", "Temperatura média (°C)"),
        "precip": (by_month.cell_precip.sum("month", min_count=12), "YlGnBu",
                   "Chuva anual (mm)"),
        "dry": ((by_month.cell_precip < 100).sum("month").where(d["inside"]), "OrRd",
                "Meses secos (< 100 mm)"),
        "vpd": (by_month.cell_vpd.mean("month"), "YlOrBr", "VPD médio (kPa)"),
        "dtr": (by_month.cell_dtr.mean("month"), "PuRd", "Amplitude térmica (°C)"),
        "wind": (by_month.cell_wind.mean("month"), "PuBu", "Vento médio (m/s)"),
    }


@app.function(hide_code=True)
def plot_normal_maps():
    fig, axes = plt.subplots(2, 3, figsize=(15, 13), layout="constrained")
    for ax, key in zip(axes.flat, ["t2m", "precip", "dry", "vpd", "dtr", "wind"], strict=True):
        _, cmap, label = normal_fields("xingu")[1][key]
        map_basins(ax, [(basin(s)["cells"], normal_fields(s)[1][key][0], basin(s)["limit"])
                        for s in SLUGS], cmap, label)
        ax.set_title(label)
    return fig


@app.function(hide_code=True)
def latitude_profile(slug):
    summary = basin(slug)["summary"]
    fields = normal_fields(slug)[1]
    w = summary.weight_km2
    keep = w.sum("longitude").values > 0
    return pd.DataFrame({
        key: ((field.fillna(0) * w).sum("longitude") / w.sum("longitude")).values[keep]
        for key, (field, _, _) in fields.items()
    }, index=summary.latitude.values[keep])


@app.function(hide_code=True)
def plot_profile():
    fig, axes = plt.subplots(1, 4, figsize=(13, 6), sharey=True, layout="constrained")
    for slug in SLUGS:
        profile = latitude_profile(slug)
        for ax, (key, label) in zip(axes, [
                ("t2m", "Temperatura (°C)"), ("precip", "Chuva anual (mm)"),
                ("dry", "Meses secos"), ("vpd", "VPD (kPa)")], strict=True):
            ax.plot(profile[key], profile.index, color=BASIN_COLORS[slug], lw=2.2,
                    label=SHORT[slug])
            ax.set(title=label)
    axes[0].set_ylabel("Latitude (°)")
    axes[0].legend(fontsize=9)
    return fig


@app.function(hide_code=True)
def plot_seasons():
    rain = (basin("xingu")["normals"].precip + basin("tapajos")["normals"].precip) / 2
    rolling = pd.concat([rain, rain.iloc[:2]]).rolling(3).sum().iloc[2:]
    rolling.index = [(m - 3) % 12 + 1 for m in range(3, 15)]

    def quarter(start):
        return [(start + k - 1) % 12 + 1 for k in range(3)]

    by = {s: normal_fields(s)[0] for s in SLUGS}
    top_rain = max(float(b.cell_precip.max()) for b in by.values())
    top_vpd = max(float(b.cell_vpd.max()) for b in by.values())
    fig, axes = plt.subplots(2, 2, figsize=(12, 13), layout="constrained")
    for row, start in enumerate([int(rolling.idxmax()), int(rolling.idxmin())]):
        months = quarter(start)
        name = "–".join(MONTHS[m - 1] for m in months)
        map_basins(axes[row, 0], [(basin(s)["cells"],
                                   by[s].cell_precip.sel(month=months).sum("month") / 3,
                                   basin(s)["limit"]) for s in SLUGS],
                   "YlGnBu", "mm/mês", vmin=0, vmax=top_rain)
        map_basins(axes[row, 1], [(basin(s)["cells"],
                                   by[s].cell_vpd.sel(month=months).mean("month"),
                                   basin(s)["limit"]) for s in SLUGS],
                   "YlOrBr", "kPa", vmin=0, vmax=top_vpd)
        axes[row, 0].set_title(f"Chuva · {name}")
        axes[row, 1].set_title(f"VPD · {name}")
    return fig


@app.cell(hide_code=True)
def _():
    _p = {s: latitude_profile(s) for s in SLUGS}
    _txt = "; ".join(
        f"{SHORT[s]}: chuva de {_p[s].iloc[:8].precip.mean():,.0f} contra "
        f"{_p[s].iloc[-8:].precip.mean():,.0f} mm por ano, {_p[s].iloc[:8].dry.mean():.1f} "
        f"contra {_p[s].iloc[-8:].dry.mean():.1f} meses secos e VPD de "
        f"{_p[s].iloc[:8].vpd.mean():.2f} contra {_p[s].iloc[-8:].vpd.mean():.2f} kPa"
        for s in SLUGS)
    mo.vstack([
        mo.md(r"""
        ## 🧭 A geografia do clima

        A média de cada bacia esconde diferenças grandes. A Figura 5 mostra a mesma normal
        de 1991–2020, agora célula por célula, nas duas bacias, que aparecem lado a lado como
        estão no território, o Tapajós a oeste e o Xingu a leste. Cada painel tem a sua escala
        de cor, comum às duas bacias.
        """),
        book.figure(plot_normal_maps(), "mapas_normal",
                    "Figura 5. Normal 1991–2020 por célula ERA5 nas duas bacias: temperatura "
                    "média, chuva anual, número de meses com menos de 100 mm, VPD médio, "
                    "amplitude térmica diária e vento."),
        mo.md(r"""
        O padrão dominante é um gradiente de norte a sul. O norte das bacias, perto do
        Amazonas, é mais chuvoso, tem uma estação seca curta e um ar mais úmido. O sul, nas
        cabeceiras em Mato Grosso, é mais alto, mais seco e mais sazonal, com mais meses
        secos, VPD maior e uma amplitude térmica maior; é ali que a floresta encontra o
        Cerrado. A temperatura média segue o relevo mais que a latitude: as terras altas do
        sul são um pouco mais frescas na média, embora tenham máximas altas na estação seca.
        A Figura 6 resume o gradiente com a média de cada faixa de latitude, ponderada pela
        área, para cada bacia.
        """),
        book.figure(plot_profile(), "perfil_norte_sul",
                    "Figura 6. Médias por faixa de latitude, ponderadas pela área das células, "
                    "na normal 1991–2020, nas duas bacias."),
        mo.callout(mo.md(nb.pt(
            f"Dois graus mais ao norte contra dois graus mais ao sul. {_txt}.")), kind="info"),
        mo.callout(mo.md(
            "O sul de cada bacia é ao mesmo tempo o mais seco, o mais sazonal e o mais "
            "desmatado. Qualquer comparação entre células perturbadas e preservadas que não "
            "leve isso em conta confundiria clima de fundo com efeito da perturbação; por "
            "isso o capítulo 8 compara células controlando a latitude e o relevo."),
            kind="danger"),
        mo.md(r"""
        A Figura 7 mostra o mesmo gradiente nas duas estações: o trimestre mais chuvoso e o
        mais seco da normal, com a mesma escala de cor para cada variável nos dois.
        """),
        book.figure(plot_seasons(), "estacoes",
                    "Figura 7. Chuva média mensal e VPD no trimestre mais chuvoso (acima) e no "
                    "mais seco (abaixo) da normal 1991–2020; mesma escala de cor por variável."),
        mo.md(r"""
        No trimestre chuvoso as duas bacias inteiras recebem chuva abundante e o VPD é baixo
        em toda parte. No seco, a chuva quase desaparece no sul enquanto o norte ainda
        recebe alguma, e o VPD do sul chega a quase o dobro do que se vê no norte. O
        contraste entre norte e sul, portanto, é sobretudo um contraste de estação seca.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_stripes():
    fig, axes = plt.subplots(2, 1, figsize=(13, 3.6), layout="constrained", sharex=True)
    lim = max(float(np.abs(basin(s)["anomaly"]).max()) for s in SLUGS)
    for ax, slug in zip(axes, SLUGS, strict=True):
        anomaly = basin(slug)["anomaly"]
        ax.bar(anomaly.index, 1, width=1, color=plt.cm.RdBu_r((anomaly + lim) / (2 * lim)))
        ax.set(xlim=(anomaly.index[0] - 0.5, anomaly.index[-1] + 0.5), yticks=[])
        ax.set_ylabel(SHORT[slug], rotation=0, ha="right", va="center")
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
    return fig


@app.function(hide_code=True)
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


@app.function(hide_code=True)
def plot_trends():
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True, layout="constrained")
    for slug in SLUGS:
        annual = basin(slug)["annual"]
        years = annual.index.values.astype(float)
        trends = trend_table(annual)
        for ax, (var, label), (_, row) in zip(axes.flat, TREND_SERIES, trends.iterrows(),
                                              strict=True):
            values = annual[var].values
            slope = row["Tendência 1990–2024 (/década)"] / 10
            ax.plot(years, values, "o-", color=BASIN_COLORS[slug], ms=3, lw=1, alpha=0.85,
                    label=nb.pt(f"{SHORT[slug]} · {10 * slope:+.3g}/década "
                                f"(p = {row['p 1990–2024']:.3f})"))
            middle = np.nanmedian(values) - slope * np.nanmedian(years)
            ax.plot(years, middle + slope * years, color=BASIN_COLORS[slug], ls="--", lw=1.3)
            ax.set_title(label, fontsize=10)
    for ax in axes.flat:
        ax.axvspan(1990, 2000.5, color="#eeeeee", zorder=0)
        ax.legend(fontsize=8, loc="best")
    return fig


@app.cell(hide_code=True)
def _():
    _an = {s: basin(s)["anomaly"] for s in SLUGS}
    _tr = {s: trend_table(basin(s)["annual"]).set_index("Variável") for s in SLUGS}
    _rows = []
    for _var, _label in TREND_SERIES:
        _row = {"Variável": _label}
        for _slug in SLUGS:
            _t = _tr[_slug].loc[_label]
            _row[f"{SHORT[_slug]}, 1990–2024"] = round(_t.iloc[0], 3)
            _row[f"p ({SHORT[_slug]})"] = round(_t.iloc[1], 3)
            _row[f"{SHORT[_slug]}, 2001–2024"] = round(_t.iloc[2], 3)
            _row[f"p 2001+ ({SHORT[_slug]})"] = round(_t.iloc[3], 3)
        _rows.append(_row)
    mo.vstack([
        mo.md(r"""
        ## 🔥 O que mudou em 35 anos

        A Figura 8 resume a história da temperatura numa faixa de cores, à maneira das
        listras de Ed Hawkins: cada ano é uma barra, azul se foi mais frio que a normal de
        1991–2020 e vermelha se foi mais quente, uma faixa para cada bacia.
        """),
        book.figure(plot_stripes(), "listras",
                    "Figura 8. Anomalia anual da temperatura média de cada bacia em relação à "
                    "normal 1991–2020, com a mesma escala de cor nas duas."),
        mo.callout(mo.md(nb.pt(" ".join(
            f"{SHORT[s]}: ano mais quente {_an[s].idxmax()} ({_an[s].max():+.2f} °C), mais "
            f"frio {_an[s].idxmin()} ({_an[s].min():+.2f} °C)." for s in SLUGS))),
            kind="info"),
        mo.md(r"""
        A passagem do azul para o vermelho é quase monótona e simultânea nas duas bacias, e
        os anos mais quentes estão todos na segunda metade do período, com 2024 no topo. Para
        dar números a essa impressão, a Figura 9 mostra as médias anuais de seis grandezas
        com a tendência estimada pelo método de Theil–Sen, a mediana das inclinações entre
        todos os pares de anos, que não se deixa levar por um ano atípico [7]. A
        significância vem do teste de Mann–Kendall com a correção de Hamed e Rao [8], que
        leva em conta que um ano quente tende a ser seguido de outro, como acontece com os
        ciclos do El Niño; sem essa correção, o p seria otimista.
        """),
        book.figure(plot_trends(), "series_anuais",
                    "Figura 9. Médias anuais das duas bacias (chuva: total anual) com a "
                    "tendência de Theil–Sen (tracejado) e o p de Mann–Kendall corrigido para "
                    "autocorrelação; em cinza, o período anterior à janela de análise."),
        mo.md(r"""
        O quadro é de um clima que esquenta e seca, nas duas bacias. A temperatura média
        subiu de 0,3 a 0,4 °C por década, a máxima subiu mais depressa, perto de 0,4 a
        0,5 °C, o ar ficou mais seco, com a umidade relativa caindo e o VPD subindo cerca de
        um décimo de quilopascal por década, e a chuva anual caiu algumas dezenas de
        milímetros por década, uma tendência menos nítida que as outras, porque a chuva
        varia muito de um ano para outro. A maior sequência de dias sem chuva de cada ano,
        por sua vez, ficou cerca de dez dias mais longa por década, uma das tendências mais
        claras da figura: chove um pouco menos no total, mas a estação seca ficou mais
        comprida. Esses números estão em linha com o que se observa
        no sul da Amazônia, onde a estação seca ficou mais quente e mais longa nas últimas
        décadas [9]. A Tabela 3 traz todas as tendências, também para 2001–2024, a janela de
        análise dos capítulos seguintes.
        """),
        book.table(pd.DataFrame(_rows), "tendencias",
                   "Tabela 3. Tendências de Theil–Sen por década e p de Mann–Kendall com a "
                   "correção de Hamed e Rao, em 1990–2024 e em 2001–2024, nas duas bacias.",
                   selection=None),
        mo.callout(mo.md(
            "Trinta e cinco anos é pouco para separar uma tendência de uma oscilação de "
            "várias décadas, e uma tendência não diz nada sobre a sua causa. Nada neste "
            "capítulo distingue o efeito do desmatamento local do aquecimento global ou da "
            "variabilidade natural do Pacífico e do Atlântico."), kind="warn"),
    ])
    return


@app.function(hide_code=True)
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


@app.function(hide_code=True)
@mo.cache
def trend_maps(slug):
    summary, inside = basin(slug)["summary"], basin(slug)["inside"]
    group = summary[["cell_t2m", "cell_vpd", "cell_precip"]].groupby("month.year")
    annual_cells = xr.merge([group.mean()[["cell_t2m", "cell_vpd"]],
                             group.sum(min_count=12)[["cell_precip"]],
                             summary[["hottest_day"]]])
    return {var: trend_field(annual_cells[var], inside)
            for var in ["cell_t2m", "hottest_day", "cell_vpd", "cell_precip"]}


@app.function(hide_code=True)
def plot_trend_maps():
    meta = {"cell_t2m": ("Temperatura média", "°C/década", "RdBu_r"),
            "hottest_day": ("Dia mais quente do ano", "°C/década", "RdBu_r"),
            "cell_vpd": ("VPD médio", "kPa/década", "BrBG_r"),
            "cell_precip": ("Chuva anual", "mm/década", "BrBG")}
    maps = {s: trend_maps(s) for s in SLUGS}
    fig, axes = plt.subplots(1, 4, figsize=(18, 7.6), layout="constrained")
    for ax, (var, (title, label, cmap)) in zip(axes, meta.items(), strict=True):
        lim = max(float(np.nanmax(np.abs(maps[s][var][0]))) for s in SLUGS)
        map_basins(ax, [(basin(s)["cells"], maps[s][var][0], basin(s)["limit"],
                         maps[s][var][1]) for s in SLUGS], cmap, label,
                   norm=TwoSlopeNorm(0, -lim, lim))
        ax.set_title(title, fontsize=10.5)
    return fig


@app.cell(hide_code=True)
def _():
    _share = {s: {v: float(m.sum() / np.isfinite(t).sum()) for v, (t, m) in trend_maps(s).items()}
              for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        A tendência também tem geografia. A Figura 10 repete o cálculo em cada célula, para
        quatro grandezas, e marca com pontos as células em que a tendência é significativa
        depois de corrigir para o número de células testadas em cada bacia, pelo método de
        Benjamini–Hochberg [10].
        """),
        book.figure(plot_trend_maps(), "mapas_tendencia",
                    "Figura 10. Tendência de Theil–Sen de 1990 a 2024 por célula, nas duas "
                    "bacias; pontos: q < 0,05 (Benjamini–Hochberg sobre as células de cada "
                    "bacia, com o p de Mann–Kendall corrigido para autocorrelação)."),
        mo.callout(mo.md(nb.pt("Fração de células com tendência significativa. " + " ".join(
            f"{SHORT[s]}: " + ", ".join(
                f"{name} {100 * _share[s][v]:.0f}%" for v, name in [
                    ("cell_t2m", "temperatura"), ("hottest_day", "dia mais quente"),
                    ("cell_vpd", "VPD"), ("cell_precip", "chuva")]) + "." for s in SLUGS))),
            kind="info"),
        mo.md(r"""
        O aquecimento e o aumento do VPD são gerais: aparecem em praticamente todas as
        células, com significância na grande maioria delas. A intensidade varia, com núcleos
        mais fortes em algumas faixas e um aquecimento menor perto da foz, mas o padrão é
        largo e suave, contínuo de uma bacia para a outra, como se espera de uma mudança
        regional, e não tem o desenho recortado do desmatamento que veremos no próximo
        capítulo. A tendência da chuva é mais fraca e significativa em menos células. Células
        vizinhas não são independentes, e por isso os mapas devem ser lidos pelo padrão de
        conjunto, e não célula por célula.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_monthly_anomalies(slug):
    daily = basin(slug)["daily"]
    months = daily.resample("MS").agg(agg_of(daily))
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
    fig.suptitle(basin(slug)["name"], x=0.02, ha="left", fontsize=13)
    return fig


@app.function(hide_code=True)
def hot_days(slug):
    t_daily, _ = anomalies(basin(slug)["daily"].tmax, BASE)
    threshold = t_daily.loc[BASE[0]:BASE[1]].quantile(0.9)
    return (t_daily > threshold).groupby(t_daily.index.year).sum()


@app.function(hide_code=True)
def plot_extremes():
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), layout="constrained")
    for k, slug in enumerate(SLUGS):
        d = basin(slug)
        hot = hot_days(slug)
        axes[0].bar(hot.index + (k - 0.5) * 0.4, hot, width=0.4, color=BASIN_COLORS[slug],
                    label=SHORT[slug])
        w = d["summary"].weight_km2
        rain_days = ((d["summary"].rain_days * w).sum(("latitude", "longitude")).values
                     / float(w.sum()))
        axes[1].plot(d["annual"].index, d["annual"].dry_spell, "o-", color=BASIN_COLORS[slug],
                     ms=3, label=SHORT[slug])
        axes[2].plot(d["annual"].index, rain_days, "o-", color=BASIN_COLORS[slug], ms=3,
                     label=SHORT[slug])
    axes[0].axhline(36.5, color=COLORS["muted"], ls=":", lw=1)
    axes[0].set(title='Dias "quentes para a época" por ano', ylabel="dias")
    axes[1].set(title="Maior sequência sem chuva (< 1 mm/dia)", ylabel="dias")
    axes[2].set(title="Dias com chuva (≥ 1 mm) por ano", ylabel="dias")
    axes[0].legend(fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    anomaly_basin = basin_picker()
    return (anomaly_basin,)


@app.cell(hide_code=True)
def _(anomaly_basin):
    _hot = {s: hot_days(s) for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## ⚡ Anomalias e extremos

        Médias anuais escondem quando, dentro do ano, as coisas aconteceram. Na Figura 11,
        cada quadrado é um mês de um ano, colorido pela sua anomalia em relação à normal
        daquele mês: vermelho é mais quente e marrom é mais seco que o normal. O seletor
        escolhe a bacia; a versão impressa traz as duas.
        """),
        anomaly_basin,
        book.figure(plot_monthly_anomalies(anomaly_basin.value), "anomalias_mensais",
                    "Figura 11. Anomalias mensais de temperatura (°C) e de chuva (%) em "
                    "relação à normal 1991–2020 de cada mês.", save=False),
        mo.md(r"""
        Os episódios conhecidos aparecem com clareza. Os El Niño fortes de 1997–1998,
        2015–2016 e 2023–2024 formam blocos vermelhos de muitos meses seguidos, e o último
        é o mais quente de todos. As secas de 2005 e 2010, ligadas ao aquecimento do
        Atlântico Norte tropical [11], aparecem como estações secas mais quentes e mais
        longas. O vermelho vai ficando mais frequente de baixo para cima, a mesma tendência
        das listras, agora mês a mês. A Figura 12 olha para três tipos de extremo nas duas
        bacias.
        """),
        book.figure(plot_extremes(), "extremos",
                    "Figura 12. Dias por ano com a máxima da bacia acima do 90º percentil das "
                    "anomalias de 1991–2020 (cerca de 36,5 por ano, por construção, no período "
                    "de referência, pontilhado), maior sequência de dias secos (calculada por "
                    "célula e promediada) e número de dias com chuva, nas duas bacias."),
        mo.callout(mo.md(nb.pt("Dias quentes para a época em 2024: " + "; ".join(
            f"{SHORT[s]} {int(_hot[s].loc[2024])}, contra uma média de "
            f"{_hot[s].loc[1991:2020].mean():.0f} na normal" for s in SLUGS) + ".")),
            kind="info"),
        mo.md(r"""
        O número de dias quentes para a época, que por construção é de cerca de 36 por ano
        na normal, fica acima disso na maioria dos anos desde 2015 e chega a três ou quatro
        vezes o normal nos anos de El Niño, como 2015–2016 e 2023–2024; a seca de 2010 já
        tinha mostrado um salto parecido. A maior sequência seca cresce nas duas bacias,
        como a Figura 9 já mostrou, e chega a mais de cem dias em 2024; e o número de dias
        com chuva caiu cerca de catorze por década. A chuva se concentra em menos dias e
        deixa intervalos secos mais longos.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_standardization(slug, variable):
    raw = basin(slug)["daily"][variable]
    anomaly, normal = anomalies(raw, BASE)
    z, sd = standardized_anomalies(raw, BASE)
    years = slice("2019-01-01", "2024-12-31")
    unit = "°C" if variable == "t2m" else "kPa"
    fig = plt.figure(figsize=(14, 9), layout="constrained")
    grid = fig.add_gridspec(3, 2, width_ratios=[3, 1])
    ax1, ax2, ax3 = (fig.add_subplot(grid[i, 0]) for i in range(3))
    ax1.plot(raw.loc[years], color=COLORS[variable], lw=0.7)
    ax1.plot(raw.loc[years].index, normal.reindex(raw.loc[years].index.day_of_year).to_numpy(),
             color=COLORS["ink"], ls="--", lw=1.2, label="normal do dia")
    ax1.set(ylabel=unit, title="1. Série diária e o seu ciclo anual normal")
    ax1.legend(fontsize=8.5, loc="upper left")
    ax2.plot(anomaly.loc[years], color=COLORS[variable], lw=0.7)
    ax2.axhline(0, color=COLORS["ink"], lw=0.8)
    ax2.set(ylabel=unit, title="2. Anomalia: a série menos a normal")
    ax3.plot(z.loc[years], color=COLORS[variable], lw=0.7)
    ax3.axhline(0, color=COLORS["ink"], lw=0.8)
    ax3.set(ylabel="desvios-padrão",
            title="3. Anomalia padronizada: a anomalia dividida pelo desvio típico do dia")
    for ax in (ax1, ax2):
        ax.tick_params(labelbottom=False)
    ax_sd = fig.add_subplot(grid[:, 1])
    days = pd.date_range("2001-01-01", periods=365)
    ax_sd.plot(sd.iloc[:365].to_numpy(), days, color=COLORS[variable], lw=2)
    ax_sd.set_yticks(pd.date_range("2001-01-01", periods=12, freq="MS"), MONTHS)
    ax_sd.invert_yaxis()
    ax_sd.set(xlabel=unit, title="Desvio típico da anomalia\nao longo do ano")
    fig.suptitle(f"{basin(slug)['name']} · da série diária à anomalia padronizada", x=0.02,
                 ha="left", fontsize=13)
    blocks = [anomaly.loc[SCIENCE[0]:SCIENCE[1]], z.loc[SCIENCE[0]:SCIENCE[1]]]
    spread = [float(b.groupby(b.index.month).std().max() / b.groupby(b.index.month).std().min())
              for b in blocks]
    peak = MONTHS[int(pd.Series(sd.to_numpy(), index=sd.index).idxmax() // 30.5) % 12]
    return fig, float(sd.max() / sd.min()), spread, peak


@app.cell(hide_code=True)
def _():
    std_basin = basin_picker()
    std_variable = mo.ui.radio(options={"temperatura": "t2m",
                                        "déficit de pressão de vapor": "vpd"},
                               value="temperatura", label="Variável", inline=True)
    return std_basin, std_variable


@app.cell(hide_code=True)
def _(std_basin, std_variable):
    _fig, _ratio, _spread, _peak = plot_standardization(std_basin.value, std_variable.value)
    mo.vstack([
        mo.md(r"""
        ## 🔧 A série que os próximos capítulos analisam

        Os métodos não lineares dos capítulos seguintes procuram estrutura na sucessão dos
        dias. O ciclo anual é a estrutura mais forte que existe nessas séries, e é
        trivialmente previsível; se ficasse na série, dominaria todos os descritores. Por
        isso trabalhamos com anomalias, em dois passos que a Figura 13 mostra, para os seis
        últimos anos. No primeiro, subtraímos de cada dia a normal daquele dia do calendário.
        No segundo, dividimos o resultado pelo desvio típico das anomalias naquele dia do
        ano, também estimado na normal de 1991–2020 e suavizado em 31 dias,

        $$
        z_t = \frac{x_t - \bar x_{d(t)}}{s_{d(t)}}, \qquad
        s_d^2 = \frac{1}{N_d} \sum_{t:\, d(t) = d} \left(x_t - \bar x_{d}\right)^2,
        $$

        em que $d(t)$ é o dia do ano de $t$ e a soma corre sobre os anos da normal.
        """),
        mo.hstack([std_basin, std_variable], justify="start", gap=1),
        book.figure(_fig, "padronizacao",
                    "Figura 13. Da série diária à anomalia padronizada, de 2019 a 2024: a série "
                    "e a sua normal, a anomalia e a anomalia dividida pelo desvio típico de "
                    "cada dia do ano; à direita, esse desvio ao longo do ano. Na versão "
                    "impressa, temperatura.", save=False),
        mo.callout(mo.md(nb.pt(
            f"O desvio típico do dia mais variável do ano, em {_peak}, é {_ratio:.1f} vezes o "
            f"do menos variável. De 2001 a 2024, o mês mais variável da anomalia simples "
            f"varia {_spread[0]:.2f} vezes o menos variável; na anomalia padronizada, "
            f"{_spread[1]:.2f} vezes.")), kind="info"),
        mo.md(r"""
        O segundo passo é o menos óbvio e o mais importante. A anomalia simples ainda tem
        uma estação, só que na variância, como o painel da direita mostra. Na temperatura,
        os dias mais variáveis são os da transição para a estação chuvosa, em setembro e
        outubro, quando as primeiras chuvas alternam dias muito quentes e quedas bruscas, e
        os menos variáveis são os do início da seca; no VPD, a variabilidade cresce ao longo
        da estação seca e chega ao máximo no fim dela. Isso se vê como trechos mais agitados
        na anomalia, no mesmo período de cada ano. Para um método que procura padrões que se
        repetem, uma agitação que volta todo ano no mesmo mês é um padrão, mas não é o que
        queremos medir. A divisão pelo desvio típico do dia torna a variabilidade
        aproximadamente igual ao longo do ano, e a série padronizada, no painel de baixo,
        não tem mais estação visível. A tendência, por outro lado, foi mantida de propósito:
        ela é parte do clima, e o capítulo das substitutas mostra que retirá-la não muda as
        conclusões.
        """),
        mo.callout(mo.md(
            "Tudo o que os capítulos seguintes calculam parte desta série: a anomalia "
            "padronizada, diária, de 2001 a 2024, em cada célula e na média de cada bacia."),
            kind="success"),
    ])
    return


@app.cell(hide_code=True)
def _():
    # Versões impressas das figuras de uma só bacia, para as duas (sem exibição).
    for _slug in SLUGS:
        book.figure(plot_series(_slug), "serie_35_anos",
                    "Figura 1. Temperatura média diária da bacia (faixa: entre a mínima e a "
                    "máxima do dia; linha grossa: média móvel de 365 dias) e chuva mensal, de "
                    "1990 a 2024.", region=_slug)
        book.figure(plot_year(_slug, 2024), "ano",
                    "Figura 2. O ano de 2024 dia a dia (temperatura, umidade relativa, VPD, "
                    "vento e chuva) contra o ciclo anual normal de 1991–2020.", region=_slug)
        book.figure(plot_climogram(_slug), "climograma",
                    "Figura 3. Climograma da normal 1991–2020: chuva mensal (barras claras: "
                    "meses com menos de 100 mm; hastes: 10º e 90º percentis entre os anos) e "
                    "temperaturas média, mínima e máxima.", region=_slug)
        book.figure(plot_monthly_anomalies(_slug), "anomalias_mensais",
                    "Figura 11. Anomalias mensais de temperatura (°C) e de chuva (%) em "
                    "relação à normal 1991–2020 de cada mês.", region=_slug)
        book.figure(plot_standardization(_slug, "t2m")[0], "padronizacao",
                    "Figura 13. Da série diária de temperatura à anomalia padronizada, de 2019 "
                    "a 2024: a série e a sua normal, a anomalia e a anomalia dividida pelo "
                    "desvio típico de cada dia do ano; à direita, esse desvio ao longo do "
                    "ano.", region=_slug)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 Em resumo

    As duas bacias têm o clima típico do sul da Amazônia: quente o ano todo, com uma estação
    chuvosa longa e uma estação seca bem marcada de junho a setembro, em que a chuva quase
    desaparece, a umidade cai e o VPD quadruplica. Dentro de cada bacia, o clima varia mais
    de norte a sul do que de uma bacia para a outra, e o sul, mais seco e mais sazonal, é
    também onde a floresta foi mais convertida. Em 35 anos, as duas bacias esquentaram de
    0,3 a 0,4 °C por década, com as máximas subindo mais depressa, o ar ficou mais seco e
    a chuva diminuiu, e os anos de El Niño de 2015–2016 e 2023–2024 foram os mais quentes do
    registro. Os dados são completos e se comportam como esperado. A série que os capítulos
    seguintes analisam é a anomalia padronizada, que retira o ciclo anual da média e da
    variabilidade, mas mantém a tendência.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Hersbach, H. et al. The ERA5 global reanalysis. *Quarterly Journal of the Royal
    Meteorological Society*, v. 146, p. 1999–2049, 2020.

    [2] Allen, R. G.; Pereira, L. S.; Raes, D.; Smith, M. *Crop evapotranspiration:
    guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56.
    Roma: FAO, 1998.

    [3] Grossiord, C. et al. Plant responses to rising vapor pressure deficit. *New
    Phytologist*, v. 226, p. 1550–1566, 2020.

    [4] Jiménez-Muñoz, J. C. et al. Record-breaking warming and extreme drought in the
    Amazon rainforest during the course of El Niño 2015–2016. *Scientific Reports*, v. 6,
    33130, 2016.

    [5] WMO. *WMO Guidelines on the Calculation of Climate Normals*. WMO-No. 1203. Genebra:
    World Meteorological Organization, 2017.

    [6] Malhi, Y. et al. Exploring the likelihood and mechanism of a climate-change-induced
    dieback of the Amazon rainforest. *PNAS*, v. 106, p. 20610–20615, 2009.

    [7] Sen, P. K. Estimates of the regression coefficient based on Kendall's tau.
    *Journal of the American Statistical Association*, v. 63, p. 1379–1389, 1968.

    [8] Hamed, K. H.; Rao, A. R. A modified Mann–Kendall trend test for autocorrelated
    data. *Journal of Hydrology*, v. 204, p. 182–196, 1998.

    [9] Marengo, J. A. et al. Changes in climate and land use over the Amazon region:
    current and future variability and trends. *Frontiers in Earth Science*, v. 6, 228,
    2018.

    [10] Benjamini, Y.; Hochberg, Y. Controlling the false discovery rate: a practical and
    powerful approach to multiple testing. *Journal of the Royal Statistical Society B*,
    v. 57, p. 289–300, 1995.

    [11] Marengo, J. A. et al. The drought of 2010 in the context of historical droughts
    in the Amazon region. *Geophysical Research Letters*, v. 38, L12703, 2011.
    """)
    return


if __name__ == "__main__":
    app.run()
