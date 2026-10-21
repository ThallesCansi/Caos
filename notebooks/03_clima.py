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
        daily_files,
        regional_frame,
        standardized_anomalies,
        summarize,
        theil_sen,
    )
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
    mo.md(r"""
    # 🌡️ O clima de 1990 a 2024

    Antes de perguntar que tipo de dinâmica o clima amazônico tem, precisamos conhecê-lo
    pelo que ele tem de mais simples: quanto faz de calor, quanto chove, como o ano se
    divide entre estação chuvosa e seca, como tudo isso muda de um lugar para outro dentro
    de cada bacia e o que mudou em 35 anos. Este capítulo é esse retrato. Ele não depende
    de nenhum método não linear e serve a três propósitos: mostrar ao leitor o sistema que
    estamos estudando, conferir que os dados se comportam como esperado e preparar, passo a
    passo, a série que todos os capítulos seguintes analisam.

    Começamos pela origem dos números, a reanálise ERA5. Depois olhamos para 35 anos de
    temperatura e chuva e, de perto, para um ano escolhido pelo leitor. Seguem o ritmo do
    ano, a geografia do clima dentro da bacia, as tendências, as anomalias e os extremos.
    Comparamos então as duas bacias e terminamos mostrando como a série diária vira a
    anomalia padronizada que entra nos descritores. O menu abaixo escolhe a bacia; todo o
    capítulo, figuras e números, acompanha a escolha.
    """)
    return


@app.cell(hide_code=True)
def _():
    picker = nb.region_picker()
    picker
    return (picker,)


@app.cell(hide_code=True)
def _(picker):
    cfg = load_region(picker.value)
    slug = cfg["slug"]
    try:
        daily_files(cfg, 1990, 2024)
    except FileNotFoundError:
        mo.stop(True, nb.missing([regions.processed_dir(cfg) / "daily_<ano>.nc"],
                                 f"make pull REGION={slug}"))
    with mo.status.spinner(f"Resumindo {cfg['name']} (na primeira vez lê os 35 anos)…"):
        summary = summarize(cfg, 1990, 2024)
    daily = regional_frame(summary)
    inside = summary.weight_km2 > 0
    cells = regions.cells(cfg)
    limit = regions.boundary(cfg)
    rivers = regions.load_context(cfg).get("rios")
    region = cfg["name"]
    return cells, cfg, daily, inside, limit, region, rivers, slug, summary


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
        completas. A Tabela 1 mostra que nenhum dia ficou de fora.
        """),
        book.table(_quality, "completude",
                   "Tabela 1. Células-dia com as 24 horas válidas, de 1990 a 2024, por "
                   "variável.", region=slug, selection=None),
        mo.callout(mo.md(
            "Os dados vêm de um espelho do ERA5 que guarda os números com precisão reduzida, "
            "um erro relativo de até 0,05%, sem viés, cerca de um décimo de grau numa hora. "
            "Nas médias o efeito desaparece; nos descritores por célula, a validação dos "
            "métodos mostra que ele fica muito abaixo do ruído das próprias séries."),
            kind="warn"),
    ])
    return


@app.function(hide_code=True)
def plot_series(daily, region):
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
def _(daily, region, slug):
    _first = daily.t2m.loc["1991":"1995"].mean()
    _last = daily.t2m.loc["2020":"2024"].mean()
    mo.vstack([
        mo.md(r"""
        ## 📈 Trinta e cinco anos de uma bacia

        A série de cada bacia é a média diária das suas células, ponderada pela área que
        cada uma tem dentro do limite; para a chuva, é a média dos totais diários, a altura
        de água que caiu em média sobre a bacia. A Figura 1 mostra a temperatura e a chuva
        de 1990 a 2024.
        """),
        book.figure(plot_series(daily, region), "serie_35_anos",
                    "Figura 1. Temperatura média diária da bacia (faixa: entre a mínima e a "
                    "máxima do dia; linha grossa: média móvel de 365 dias) e chuva mensal, de "
                    "1990 a 2024.", region=slug),
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


@app.cell(hide_code=True)
def _():
    year_slider = mo.ui.slider(1990, 2024, value=2024, step=1, label="Ano", show_value=True)
    return (year_slider,)


@app.function(hide_code=True)
def plot_year(daily, region, year):
    sel = daily.loc[str(year)]
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
def _(daily, region, slug, year_slider):
    _hot = anomalies(daily.t2m, BASE)[0].loc[str(year_slider.value)]
    _rain = anomalies(daily.precip, BASE)[0].loc[str(year_slider.value)].sum()
    mo.vstack([
        mo.md(r"""
        A Figura 2 aproxima a lente: um ano inteiro, dia a dia, em cinco variáveis, contra o
        ano normal. A linha tracejada é a normal climatológica de 1991–2020 [5], a média de
        cada dia do calendário nesses trinta anos, suavizada numa janela de 31 dias. O
        controle escolhe o ano; a versão impressa é a de 2024.
        """),
        year_slider,
        book.figure(plot_year(daily, region, year_slider.value), "ano",
                    "Figura 2. Um ano dia a dia (temperatura, umidade relativa, VPD, vento e "
                    "chuva) contra o ciclo anual normal de 1991–2020. Na versão impressa, 2024.",
                    region=slug, save=year_slider.value == 2024),
        mo.callout(mo.md(nb.pt(
            f"Em {year_slider.value}, {int((_hot > 0).sum())} de {len(_hot)} dias ficaram "
            f"acima da normal de temperatura, com anomalia média de {_hot.mean():+.2f} °C; a "
            f"chuva do ano ficou {_rain:+.0f} mm em relação à normal.")), kind="info"),
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


@app.cell(hide_code=True)
def _(daily):
    agg = {c: MONTHLY.get(c, "mean") for c in daily.columns}
    monthly = daily.loc[BASE[0]:BASE[1]].resample("MS").agg(agg)
    normals = monthly.groupby(monthly.index.month).mean()
    p10 = monthly.groupby(monthly.index.month).quantile(0.1)
    p90 = monthly.groupby(monthly.index.month).quantile(0.9)
    dry = [MONTHS[m - 1] for m in normals.index[normals.precip < 100]]
    annual_rain = monthly.precip.groupby(monthly.index.year).sum()
    return agg, annual_rain, dry, normals, p10, p90


@app.function(hide_code=True)
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


@app.function(hide_code=True)
def plot_cycles(normals, p10, p90):
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained", sharex=True)
    for ax, var in zip(axes.flat, ["rh", "vpd", "dtr", "wind"], strict=True):
        ax.fill_between(MONTHS, p10[var], p90[var], color=COLORS[var], alpha=0.18,
                        label="10º–90º percentil entre anos")
        ax.plot(MONTHS, normals[var], color=COLORS[var], marker="o", lw=2)
        ax.set(title=LABELS[var])
    axes[0, 0].legend(fontsize=8)
    return fig


@app.cell(hide_code=True)
def _(annual_rain, dry, normals, p10, p90, region, slug):
    _table = normals[["t2m", "tmin", "tmax", "precip", "rh", "vpd", "wind"]].copy()
    _table.index = MONTHS
    _table = _table.round(2).rename(columns={k: LABELS[k] for k in _table.columns}).T
    _peak = MONTHS[int(normals.vpd.idxmax()) - 1]
    mo.vstack([
        mo.md(r"""
        ## 🌦️ O ritmo do ano

        A Figura 3 é o climograma da bacia: a chuva de cada mês na normal de 1991–2020, com
        a faixa entre o décimo e o nonagésimo percentil dos anos, e as temperaturas média,
        mínima e máxima. Marcamos como secos os meses com menos de 100 mm, um limiar
        operacional comum em estudos amazônicos: abaixo dele, a floresta tende a transpirar
        mais água do que recebe e passa a depender da reserva do solo [6].
        """),
        book.figure(plot_climogram(normals, p10, p90, region), "climograma",
                    "Figura 3. Climograma da normal 1991–2020: chuva mensal (barras claras: "
                    "meses com menos de 100 mm; hastes: 10º e 90º percentis entre os anos) e "
                    "temperaturas média, mínima e máxima.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Chuva anual normal: {annual_rain.mean():,.0f} mm, de {annual_rain.min():,.0f} "
            f"a {annual_rain.max():,.0f} mm entre os anos. Meses secos: "
            f"{', '.join(dry) if dry else 'nenhum'}. Pico do VPD: {_peak}.")), kind="info"),
        mo.md(r"""
        As duas bacias têm o regime típico do sul da Amazônia: uma estação chuvosa longa, de
        outubro a maio, com o pico de janeiro a março, e uma estação seca bem marcada, de
        junho a setembro, em que a chuva cai a poucas dezenas de milímetros por mês. A
        temperatura média varia pouco ao longo do ano, de dois a três graus, e chega ao máximo
        no fim da estação seca, em agosto e setembro, quando o céu limpo e o solo mais seco
        deixam a superfície esquentar. A Figura 4 completa o quadro com as outras variáveis.
        """),
        book.figure(plot_cycles(normals, p10, p90), "ciclo_anual",
                    "Figura 4. Ciclo anual da umidade relativa, do VPD, da amplitude térmica "
                    "diária e do vento na normal 1991–2020 (faixa: 10º e 90º percentis entre os "
                    "anos).", region=slug),
        mo.md(r"""
        Na estação seca, a umidade relativa cai de quase 90% para perto de 60%, o VPD
        quadruplica, a amplitude térmica diária passa de 7 para 12 graus e o vento ganha
        força. As faixas mostram outra coisa importante: a variação entre anos da umidade e do VPD é maior
        na estação seca. Um agosto pode ser muito mais seco que outro, enquanto os meses
        chuvosos se parecem mais entre si. Diferenças de variabilidade ao longo do ano como essa são
        a razão de padronizarmos as séries antes de analisar a sua dinâmica, como veremos no
        fim do capítulo. A Tabela 2 reúne as normais mensais.
        """),
        book.table(_table.reset_index(names="Variável"), "normais_mensais",
                   "Tabela 2. Normais mensais de 1991–2020, médias da bacia (chuva em "
                   "mm/mês).", region=slug, selection=None),
    ])
    return


@app.cell(hide_code=True)
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


@app.function(hide_code=True)
def plot_normal_maps(cells, fields, limit, rivers, region):
    fig, axes = plt.subplots(2, 3, figsize=(14, 14), layout="constrained")
    for ax, (field, cmap, label) in zip(axes.flat, fields.values(), strict=True):
        map_cells(ax, cells, field, cmap, label, outline=limit, lines=rivers)
        ax.set_title(label)
    fig.suptitle(f"Normal 1991–2020 · {region}", fontsize=14, x=0.02, ha="left")
    return fig


@app.function(hide_code=True)
def latitude_profile(summary, fields):
    w = summary.weight_km2
    keep = w.sum("longitude").values > 0
    return pd.DataFrame({
        key: ((field.fillna(0) * w).sum("longitude") / w.sum("longitude")).values[keep]
        for key, (field, _, _) in fields.items()
    }, index=summary.latitude.values[keep])


@app.function(hide_code=True)
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


@app.function(hide_code=True)
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
    return fig


@app.cell(hide_code=True)
def _(by_month, cells, fields, limit, normals, region, rivers, slug, summary):
    _profile = latitude_profile(summary, fields)
    _north, _south = _profile.iloc[:8].mean(), _profile.iloc[-8:].mean()
    mo.vstack([
        mo.md(r"""
        ## 🧭 A geografia do clima

        A média da bacia esconde diferenças grandes. A Figura 5 mostra a mesma normal de
        1991–2020, agora célula por célula, para seis grandezas; cada painel tem a sua escala
        de cor, e os rios principais aparecem como referência.
        """),
        book.figure(plot_normal_maps(cells, fields, limit, rivers, region), "mapas_normal",
                    "Figura 5. Normal 1991–2020 por célula ERA5: temperatura média, chuva "
                    "anual, número de meses com menos de 100 mm, VPD médio, amplitude térmica "
                    "diária e vento.", region=slug),
        mo.md(r"""
        O padrão dominante é um gradiente de norte a sul. O norte das bacias, perto do
        Amazonas, é mais chuvoso, tem uma estação seca curta e um ar mais úmido. O sul, nas
        cabeceiras em Mato Grosso, é mais alto, mais seco e mais sazonal, com mais meses
        secos, VPD maior e uma amplitude térmica maior; é ali que a floresta encontra o
        Cerrado. A temperatura média segue o relevo mais que a latitude: as terras altas do
        sul são um pouco mais frescas na média, embora tenham máximas altas na estação seca.
        A Figura 6 resume o gradiente com a média de cada faixa de latitude, ponderada pela
        área.
        """),
        book.figure(plot_profile(_profile, region), "perfil_norte_sul",
                    "Figura 6. Médias por faixa de latitude, ponderadas pela área das células, "
                    "na normal 1991–2020.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Dois graus mais ao norte contra dois graus mais ao sul: chuva de "
            f"{_north.precip:,.0f} contra {_south.precip:,.0f} mm por ano, "
            f"{_north.dry:.1f} contra {_south.dry:.1f} meses secos e VPD de "
            f"{_north.vpd:.2f} contra {_south.vpd:.2f} kPa.")), kind="info"),
        mo.callout(mo.md(
            "O sul de cada bacia é ao mesmo tempo o mais seco, o mais sazonal e o mais "
            "desmatado. Qualquer comparação entre células perturbadas e preservadas que não "
            "leve isso em conta confundiria clima de fundo com efeito da perturbação; por "
            "isso o último capítulo compara células controlando a latitude e o relevo."),
            kind="danger"),
        mo.md(r"""
        A Figura 7 mostra o mesmo gradiente nas duas estações: o trimestre mais chuvoso e o
        mais seco da normal, com a mesma escala de cor para cada variável nos dois.
        """),
        book.figure(plot_seasons(cells, by_month, normals, limit, rivers), "estacoes",
                    "Figura 7. Chuva média mensal e VPD no trimestre mais chuvoso (acima) e no "
                    "mais seco (abaixo) da normal 1991–2020; mesma escala de cor por variável.",
                    region=slug),
        mo.md(r"""
        No trimestre chuvoso a bacia inteira recebe chuva abundante e o VPD é baixo em toda
        parte. No seco, a chuva quase desaparece no sul enquanto o norte ainda recebe alguma,
        e o VPD do sul chega a quase o dobro do que se vê no norte. O contraste entre norte e sul,
        portanto, é sobretudo um contraste de estação seca.
        """),
    ])
    return


@app.cell(hide_code=True)
def _(agg, daily, summary):
    annual = daily.resample("YS").agg(agg)
    annual.index = annual.index.year
    _w = summary.weight_km2
    annual["dry_spell"] = ((summary.longest_dry_spell * _w).sum(("latitude", "longitude"))
                           .values / float(_w.sum()))
    annual["hottest"] = daily.tmax.resample("YS").max().values
    anomaly = annual.t2m - annual.loc[1991:2020].t2m.mean()
    return annual, anomaly


@app.function(hide_code=True)
def plot_stripes(anomaly, region):
    fig, ax = plt.subplots(figsize=(13, 2.6), layout="constrained")
    lim = float(np.abs(anomaly).max())
    ax.bar(anomaly.index, 1, width=1, color=plt.cm.RdBu_r((anomaly + lim) / (2 * lim)))
    ax.set(xlim=(anomaly.index[0] - 0.5, anomaly.index[-1] + 0.5), yticks=[],
           title=f"{region} · anomalia anual da temperatura em relação a 1991–2020")
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
    return fig


@app.cell(hide_code=True)
def _(annual, anomaly, region, slug):
    trends = trend_table(annual)
    _t = trends.set_index("Variável")
    mo.vstack([
        mo.md(r"""
        ## 🔥 O que mudou em 35 anos

        A Figura 8 resume a história da temperatura numa faixa de cores, à maneira das
        listras de Ed Hawkins: cada ano é uma barra, azul se foi mais frio que a normal de
        1991–2020 e vermelha se foi mais quente.
        """),
        book.figure(plot_stripes(anomaly, region), "listras",
                    "Figura 8. Anomalia anual da temperatura média da bacia em relação à normal "
                    "1991–2020.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Ano mais quente: {anomaly.idxmax()} ({anomaly.max():+.2f} °C); mais frio: "
            f"{anomaly.idxmin()} ({anomaly.min():+.2f} °C). Os cinco mais quentes: "
            f"{', '.join(map(str, sorted(anomaly.sort_values().index[-5:])))}.")),
            kind="info"),
        mo.md(r"""
        A passagem do azul para o vermelho é quase monótona, e os anos mais quentes estão
        todos na segunda metade do período, com 2024 no topo nas duas bacias. Para dar
        números a essa impressão, a Figura 9 mostra as médias anuais de seis grandezas com a
        tendência estimada pelo método de Theil–Sen, a mediana das inclinações entre todos
        os pares de anos, que não se deixa levar por um ano atípico [7]. A significância vem
        do teste de Mann–Kendall com a correção de Hamed e Rao [8], que leva em conta que um
        ano quente tende a ser seguido de outro, como acontece com os ciclos do El Niño;
        sem essa correção, o p seria otimista.
        """),
        book.figure(plot_trends(annual, trends), "series_anuais",
                    "Figura 9. Médias anuais (chuva: total anual) com a tendência de Theil–Sen "
                    "(tracejado) e o p de Mann–Kendall corrigido para autocorrelação; em cinza, "
                    "o período anterior à janela de análise.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Tendências de 1990 a 2024, por década: temperatura média "
            f"{_t.loc['Temperatura média (°C)'].iloc[0]:+.2f} °C, máxima "
            f"{_t.loc['Máxima média (°C)'].iloc[0]:+.2f} °C, VPD "
            f"{_t.loc['VPD médio (kPa)'].iloc[0]:+.3f} kPa, umidade relativa "
            f"{_t.loc['Umidade relativa (%)'].iloc[0]:+.1f} pontos e chuva "
            f"{_t.loc['Chuva anual (mm)'].iloc[0]:+.0f} mm "
            f"(p = {_t.loc['Chuva anual (mm)'].iloc[1]:.3f}).")), kind="info"),
        mo.md(r"""
        O quadro é de um clima que esquenta e seca. A temperatura média subiu de 0,3 a 0,4 °C
        por década, a máxima subiu mais depressa, perto de 0,4 a 0,5 °C, o ar ficou mais
        seco, com a umidade relativa caindo e o VPD subindo cerca de um décimo de
        quilopascal por década, e a chuva anual caiu algumas dezenas de milímetros por
        década, uma tendência menos nítida que as outras, porque a chuva varia muito de um
        ano para outro. Esses números estão em linha com o que se observa no sul da
        Amazônia, onde a estação seca ficou mais quente e mais longa nas últimas décadas [9].
        A Tabela 3 traz todas as tendências, também para 2001–2024, a janela de análise dos
        capítulos seguintes.
        """),
        book.table(trends.round(4), "tendencias",
                   "Tabela 3. Tendências de Theil–Sen por década e p de Mann–Kendall com a "
                   "correção de Hamed e Rao, em 1990–2024 e em 2001–2024.", region=slug,
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


@app.cell(hide_code=True)
def _(inside, summary):
    _group = summary[["cell_t2m", "cell_vpd", "cell_precip"]].groupby("month.year")
    annual_cells = xr.merge([_group.mean()[["cell_t2m", "cell_vpd"]],
                             _group.sum(min_count=12)[["cell_precip"]],
                             summary[["hottest_day"]]])
    trend_maps = {var: trend_field(annual_cells[var], inside)
                  for var in ["cell_t2m", "hottest_day", "cell_vpd", "cell_precip"]}
    return (trend_maps,)


@app.function(hide_code=True)
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
    return fig


@app.cell(hide_code=True)
def _(cells, limit, rivers, slug, trend_maps):
    _share = {v: float(s.sum() / np.isfinite(t).sum()) for v, (t, s) in trend_maps.items()}
    mo.vstack([
        mo.md(r"""
        A tendência também tem geografia. A Figura 10 repete o cálculo em cada célula, para
        quatro grandezas, e marca com pontos as células em que a tendência é significativa
        depois de corrigir para o número de células testadas, pelo método de
        Benjamini–Hochberg [10].
        """),
        book.figure(plot_trend_maps(cells, trend_maps, limit, rivers), "mapas_tendencia",
                    "Figura 10. Tendência de Theil–Sen de 1990 a 2024 por célula; pontos: "
                    "q < 0,05 (Benjamini–Hochberg sobre as células, com o p de Mann–Kendall "
                    "corrigido para autocorrelação).", region=slug),
        mo.callout(mo.md(nb.pt("Fração de células com tendência significativa: " + ", ".join(
            f"{name} {100 * _share[v]:.0f}%" for v, name in [
                ("cell_t2m", "temperatura"), ("hottest_day", "dia mais quente"),
                ("cell_vpd", "VPD"), ("cell_precip", "chuva")]) + ".")), kind="info"),
        mo.md(r"""
        O aquecimento e o aumento do VPD são gerais: aparecem em praticamente todas as
        células, com significância na grande maioria delas. A intensidade varia, com núcleos
        mais fortes em algumas faixas e um aquecimento menor perto da foz, mas o padrão é
        largo e suave, como se espera de uma mudança regional, e não tem o desenho recortado
        do desmatamento que veremos no próximo capítulo. A tendência da chuva
        é mais fraca e significativa em menos células. Células vizinhas não são
        independentes, e por isso os mapas devem ser lidos pelo padrão de conjunto, e não
        célula por célula.
        """),
    ])
    return


@app.function(hide_code=True)
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


@app.function(hide_code=True)
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
    axes[1].set(title="Maior sequência sem chuva (< 1 mm/dia)", ylabel="dias")
    axes[2].plot(annual.index, rain_days, "o-", color=COLORS["precip"], ms=3.5)
    axes[2].set(title="Dias com chuva (≥ 1 mm) por ano", ylabel="dias")
    return fig, hot_days


@app.cell(hide_code=True)
def _(agg, annual, daily, slug, summary):
    _fig, _hot = plot_extremes(daily, annual, summary)
    mo.vstack([
        mo.md(r"""
        ## ⚡ Anomalias e extremos

        Médias anuais escondem quando, dentro do ano, as coisas aconteceram. Na Figura 11,
        cada quadrado é um mês de um ano, colorido pela sua anomalia em relação à normal
        daquele mês: vermelho é mais quente e marrom é mais seco que o normal.
        """),
        book.figure(plot_monthly_anomalies(daily, agg), "anomalias_mensais",
                    "Figura 11. Anomalias mensais de temperatura (°C) e de chuva (%) em "
                    "relação à normal 1991–2020 de cada mês.", region=slug),
        mo.md(r"""
        Os episódios conhecidos aparecem com clareza. Os El Niño fortes de 1997–1998,
        2015–2016 e 2023–2024 formam blocos vermelhos de muitos meses seguidos, e o último
        é o mais quente de todos. As secas de 2005 e 2010, ligadas ao aquecimento do
        Atlântico Norte tropical [11], aparecem como estações secas mais quentes e mais
        longas. O vermelho vai ficando mais frequente de baixo para cima, a mesma tendência
        das listras, agora mês a mês. A Figura 12 olha para três tipos de extremo.
        """),
        book.figure(_fig, "extremos",
                    "Figura 12. Dias por ano com a máxima da bacia acima do 90º percentil das "
                    "anomalias de 1991–2020 (cerca de 36,5 por ano, por construção, no período "
                    "de referência; barras escuras acima disso), maior sequência de dias secos "
                    "(calculada por célula e promediada) e número de dias com chuva.",
                    region=slug),
        mo.callout(mo.md(nb.pt(
            f"Dias quentes para a época em 2024: {int(_hot.loc[2024])}, contra uma média de "
            f"{_hot.loc[1991:2020].mean():.0f} na normal.")), kind="info"),
        mo.md(r"""
        O número de dias quentes para a época, que por construção é de cerca de 36 por ano
        na normal, fica acima disso na maioria dos anos desde 2015 e chega a três ou quatro
        vezes o normal nos anos de El Niño, como 2015–2016 e 2023–2024; a seca de 2010 já
        tinha mostrado um salto parecido. As sequências secas mais longas e o número de
        dias de chuva oscilam mais e mostram tendências menos nítidas, coerentes com o que a
        Figura 9 mostrou para a chuva.
        """),
    ])
    return


@app.function(hide_code=True)
def compare_regions(slugs):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), layout="constrained")
    for slug, kw in zip(slugs, [{"color": COLORS["t2m"]},
                                {"color": COLORS["ink"], "ls": "--"}], strict=True):
        cfg = load_region(slug)
        frame = regional_frame(summarize(cfg, 1990, 2024))
        agg = {c: MONTHLY.get(c, "mean") for c in frame.columns}
        monthly = frame.loc[BASE[0]:BASE[1]].resample("MS").agg(agg)
        normal = monthly.groupby(monthly.index.month).mean()
        for ax, var in zip(axes, ["t2m", "precip", "vpd"], strict=True):
            ax.plot(MONTHS, normal[var], marker="o", label=cfg["name"], **kw)
    for ax, title in zip(axes, ["Temperatura média (°C)", "Chuva (mm/mês)", "VPD (kPa)"],
                         strict=True):
        ax.set_title(title)
    axes[0].legend(fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🤝 As duas bacias lado a lado

        A Figura 13 compara o ano normal das duas bacias em temperatura, chuva e VPD.
        """),
        book.figure(compare_regions(["xingu", "tapajos"]), "duas_bacias",
                    "Figura 13. Normais mensais de 1991–2020 da temperatura, da chuva e do VPD "
                    "médios das duas bacias."),
        mo.md(r"""
        As duas bacias têm quase o mesmo clima médio, o que é esperado para vizinhas que
        atravessam a mesma faixa de latitude. O Tapajós chove um pouco mais, cerca de 200 mm
        por ano, distribuídos ao longo de quase todos os meses, e tem uma estação seca que
        termina um pouco antes, com setembro menos seco; o Xingu tem um VPD ligeiramente maior em setembro. As diferenças
        são pequenas diante do contraste entre o norte e o sul de cada bacia, e é isso que
        torna as duas um bom par: se um resultado aparece em uma e não na outra, não é por
        terem climas de fundo diferentes.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    std_variable = mo.ui.radio(options={"temperatura": "t2m",
                                        "déficit de pressão de vapor": "vpd"},
                               value="temperatura", label="Variável", inline=True)
    return (std_variable,)


@app.function(hide_code=True)
def plot_standardization(daily, variable, region):
    raw = daily[variable]
    anomaly, normal = anomalies(raw, BASE)
    z, sd = standardized_anomalies(raw, BASE)
    years = slice("2019-01-01", "2024-12-31")
    unit = "°C" if variable == "t2m" else "kPa"
    fig = plt.figure(figsize=(14, 9), layout="constrained")
    grid = fig.add_gridspec(3, 2, width_ratios=[3, 1])
    ax1, ax2, ax3 = (fig.add_subplot(grid[i, 0]) for i in range(3))
    ax1.plot(raw.loc[years], color=COLORS[variable], lw=0.7)
    ax1.plot(raw.loc[years].index, normal.reindex(raw.loc[years].index.dayofyear).to_numpy(),
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
    ax_sd.yaxis.set_major_locator(mdates.MonthLocator())
    ax_sd.yaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax_sd.set_yticks(pd.date_range("2001-01-01", periods=12, freq="MS"), MONTHS)
    ax_sd.invert_yaxis()
    ax_sd.set(xlabel=unit, title="Desvio típico da anomalia\nao longo do ano")
    fig.suptitle(f"{region} · da série diária à anomalia padronizada", x=0.02, ha="left",
                 fontsize=13)
    blocks = [anomaly.loc[SCIENCE[0]:SCIENCE[1]], z.loc[SCIENCE[0]:SCIENCE[1]]]
    spread = [float(b.groupby(b.index.month).std().max() / b.groupby(b.index.month).std().min())
              for b in blocks]
    peak = MONTHS[int(pd.Series(sd.to_numpy(), index=sd.index).idxmax() // 30.5) % 12]
    return fig, float(sd.max() / sd.min()), spread, peak


@app.cell(hide_code=True)
def _(daily, region, slug, std_variable):
    _fig, _ratio, _spread, _peak = plot_standardization(daily, std_variable.value, region)
    mo.vstack([
        mo.md(r"""
        ## 🔧 A série que os próximos capítulos analisam

        Os métodos não lineares dos capítulos seguintes procuram estrutura na sucessão dos
        dias. O ciclo anual é a estrutura mais forte que existe nessas séries, e é
        trivialmente previsível; se ficasse na série, dominaria todos os descritores. Por
        isso trabalhamos com anomalias, em dois passos que a Figura 14 mostra, para os seis
        últimos anos. No primeiro, subtraímos de cada dia a normal daquele dia do calendário.
        No segundo, dividimos o resultado pelo desvio típico das anomalias naquele dia do
        ano, também estimado na normal de 1991–2020 e suavizado em 31 dias,

        $$
        z_t = \frac{x_t - \bar x_{d(t)}}{s_{d(t)}}, \qquad
        s_d^2 = \frac{1}{N_d} \sum_{t:\, d(t) = d} \left(x_t - \bar x_{d}\right)^2,
        $$

        em que $d(t)$ é o dia do ano de $t$ e a soma corre sobre os anos da normal.
        """),
        std_variable,
        book.figure(_fig, "padronizacao",
                    "Figura 14. Da série diária à anomalia padronizada, de 2019 a 2024: a série "
                    "e a sua normal, a anomalia e a anomalia dividida pelo desvio típico de "
                    "cada dia do ano; à direita, esse desvio ao longo do ano. Na versão "
                    "impressa, temperatura.", region=slug,
                    save=std_variable.value == "t2m"),
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
