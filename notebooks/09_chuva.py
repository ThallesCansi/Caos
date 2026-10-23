# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "09 · A chuva vista de duas formas"
# description = "O ERA5 e o CHIRPS diante da perturbação da floresta"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="09 · A chuva vista de duas formas")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from amazon_chaos import gradient as G
    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear import precip as P
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.viz import COLORS, map_basins

    book = nb.notebook("09_chuva")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    SHORT = {"xingu": "Xingu", "tapajos": "Tapajós"}
    SOURCES = {"precip_era5": "ERA5", "precip_chirps": "CHIRPS"}
    SOURCE_COLORS = {"precip_era5": COLORS["muted"], "precip_chirps": COLORS["precip"]}
    NAMES = {"pe_entropy": "Entropia de permutação", "pe_complexity": "Complexidade estatística"}
    DRY = ("chuva_anual_chirps", "dias_secos_chirps", "meses_secos_chirps")
    YEAR = "2018"


@app.function(hide_code=True)
@mo.cache
def cells(slug):
    return P.cell_table(load_region(slug), SPEC)


@app.function(hide_code=True)
@mo.cache
def basin(slug):
    cfg = load_region(slug)
    return {"cells": regions.cells(cfg), "limit": regions.boundary(cfg)}


@app.function(hide_code=True)
@mo.cache
def daily(slug):
    cfg = load_region(slug)
    return {s: P.load_series(cfg, s).loc[YEAR] for s in SOURCES}


@app.function(hide_code=True)
def example_cell(slug):
    """A célula elegível mais próxima do centro das células elegíveis da bacia."""
    e = cells(slug)[cells(slug).elegivel]
    d = np.hypot(e.latitude - e.latitude.mean(), e.longitude - e.longitude.mean())
    return d.idxmin()


@app.function(hide_code=True)
@mo.cache
def associations():
    rows = []
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel].copy()
        for source in SOURCES:
            for d in NAMES:
                e[f"exc_{source}_{d}"] = e[f"obs_{source}_{d}"] - e[f"nulo_{source}_{d}"]
                for measure, column in [("z", f"z_{source}_{d}"),
                                        ("observado", f"obs_{source}_{d}"),
                                        ("excesso", f"exc_{source}_{d}")]:
                    rows.append({"bacia": slug, "fonte": source, "descritor": d,
                                 "medida": measure,
                                 **G.associate(e, "perda_antecedente", column)})
                rows.append({"bacia": slug, "fonte": source, "descritor": d,
                             "medida": "longitudinal",
                             **G.associate(e, "mb_perda_floresta_2001_2012",
                                           f"delta_{source}_{d}")})
    return pd.DataFrame(rows)


@app.function(hide_code=True)
@mo.cache
def dryness():
    rows = []
    variants = {"controles do pré-registro": G.CONTROLS,
                "+ chuva anual": G.CONTROLS + DRY[:1],
                "+ dias secos": G.CONTROLS + DRY[1:2],
                "+ meses secos": G.CONTROLS + DRY[2:],
                "+ os três": G.CONTROLS + DRY}
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel]
        column = "obs_precip_chirps_pe_entropy"
        for name, controls in variants.items():
            rows.append({"bacia": slug, "modelo": name,
                         **G.associate(e, "perda_antecedente", column, controls)})
        rows.append({"bacia": slug, "modelo": "conversão, + os três",
                     **G.associate(e, "agro_frac_2000", column,
                                   G.CONTROLS + DRY + ("natural_nao_florestal_2000",))})
        forest = e[e.natural_nao_florestal_2000 < 0.05]
        rows.append({"bacia": slug, "modelo": "só células de floresta, + os três",
                     **G.associate(forest, "perda_antecedente", column, G.CONTROLS + DRY)})
    return pd.DataFrame(rows)


@app.function(hide_code=True)
def ci(rho, lo, hi):
    return f"{rho:+.2f} [{lo:+.2f}; {hi:+.2f}]"


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🌧️ A chuva vista de duas formas

    O capítulo anterior terminou com uma suspeita confirmada. O ERA5 reconstrói o clima com
    um mapa de vegetação fixo, e por isso não registra o aquecimento que o satélite vê sobre
    as áreas desmatadas. A pergunta que fica é se essa cegueira vale também para a dinâmica:
    se houvesse uma marca da perturbação na forma como o tempo evolui de um dia para o
    outro, uma série observada a mostraria onde a reanálise não mostra?

    A temperatura da superfície medida pelo MODIS não serve para responder a isso, porque
    as nuvens abrem lacunas demais para uma série diária. A chuva serve. Ela é a variável
    em que o acoplamento entre floresta e atmosfera é mais direto: a floresta devolve à
    atmosfera, pela transpiração, boa parte da água que alimenta a chuva seguinte [1], e
    a troca de floresta por pasto muda a chuva local, em alguns lugares para menos, em
    outros para mais, conforme a escala do desmatamento [2]. E existe uma série de chuva
    diária baseada em observações para todo o período: o CHIRPS [3].

    O CHIRPS combina a temperatura do topo das nuvens, medida por satélites no
    infravermelho, com os pluviômetros em terra, e é calibrado em totais de cinco dias, as
    pêntadas. O valor de cada dia vem de repartir a pêntada pelos dias. Essa repartição é o
    que decide se o produto serve aqui. Na versão que usamos, a terceira, há duas opções: uma
    reparte a pêntada segundo a chuva diária do próprio ERA5, e a outra segundo o IMERG, a
    estimativa de chuva por radares e radiômetros em satélites [4]. Na primeira, a dinâmica dia
    a dia seria a do modelo que queremos verificar. Usamos a segunda: nela, o total vem de
    estações e satélites, e a distribuição entre os dias, de outra observação por satélite.

    O capítulo tem quatro partes. Primeiro comparamos as duas chuvas, em média e dia a dia.
    Depois aplicamos a ambas os mesmos métodos ordinais do capítulo 07 contra substitutas.
    Em seguida perguntamos qual das duas acompanha a perturbação da floresta e, por fim,
    se essa associação resiste à explicação mais simples, a de que a fronteira agrícola fica
    onde já chovia menos.
    """)
    return


@app.function(hide_code=True)
def plot_maps():
    fig, axes = plt.subplots(1, 3, figsize=(16, 7.2), layout="constrained")
    fields = {}
    for slug in SLUGS:
        c = cells(slug).reset_index().set_index(["latitude", "longitude"])
        era = c.chuva_anual_era5.to_xarray()
        chirps = c.chuva_anual_chirps.to_xarray()
        fields[slug] = (era, chirps, 100 * (era - chirps) / chirps)
    norm = None
    for k, (ax, title) in enumerate(zip(axes, ["Chuva anual no ERA5 (mm)",
                                                "Chuva anual no CHIRPS (mm)",
                                                "ERA5 em relação ao CHIRPS (%)"], strict=True)):
        parts = [(basin(s)["cells"], fields[s][k], basin(s)["limit"]) for s in SLUGS]
        if k < 2:
            norm = map_basins(ax, parts, "Blues", "mm por ano", norm=norm if k else None,
                              vmin=1000, vmax=2800)
        else:
            map_basins(ax, parts, "RdBu", "%", vmin=-40, vmax=40)
        ax.set_title(title)
    return fig


@app.cell(hide_code=True)
def _():
    _rows = []
    for _s in SLUGS:
        _e = cells(_s)[cells(_s).elegivel]
        _rows.append(f"{SHORT[_s]}: {_e.chuva_anual_era5.mean():.0f} mm por ano no ERA5 e "
                     f"{_e.chuva_anual_chirps.mean():.0f} no CHIRPS; correlação de postos "
                     f"entre as duas, célula a célula, de "
                     f"{_e[['chuva_anual_era5', 'chuva_anual_chirps']].corr('spearman').iloc[0, 1]:.2f}")
    mo.vstack([
        mo.md(r"""
        ## 🗺️ Duas chuvas para o mesmo lugar

        A Figura 1 mostra a chuva média anual de 2001 a 2024 em cada célula, segundo as duas
        fontes, e a diferença entre elas. Para o CHIRPS, a média é tomada sobre o quadrado
        inteiro de cada célula, o mesmo que a série do ERA5 representa, de modo que as duas
        falam da mesma área.
        """),
        book.figure(plot_maps(), "mapas",
                    "Figura 1. Chuva média anual de 2001 a 2024 por célula no ERA5 e no CHIRPS "
                    "(v3, repartição diária pelo IMERG) e a diferença do ERA5 em relação ao "
                    "CHIRPS, nas duas bacias."),
        mo.callout(mo.md(nb.pt("; ".join(_rows) + ".")), kind="info"),
        mo.md(r"""
        As duas fontes concordam no desenho geral, com o norte mais chuvoso que o sul, mas o
        ERA5 chove menos que o CHIRPS, em média de 5% a 8%, e a concordância célula a célula
        é bem maior no Tapajós do que no Xingu. A diferença não é uniforme: ela é quase nula
        no norte, onde no Tapajós o ERA5 chega a chover mais, até 40% a mais nas células da
        foz, cobertas em boa parte pelos rios, e cresce para o sul e
        com a altitude, até cerca de 17% a menos nas células mais ao sul, justamente onde
        está a maior parte da perturbação. Nenhuma das duas é a verdade:
        o CHIRPS depende de poucos pluviômetros nessa região e de uma relação entre nuvem fria
        e chuva que nem sempre vale, e o ERA5 é um modelo. O que importa aqui é que elas
        foram feitas de modos independentes.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    day_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                value="Bacia do Rio Xingu", label="Bacia")
    return (day_region,)


@app.function(hide_code=True)
def plot_days(slug):
    cell = example_cell(slug)
    series = daily(slug)
    fig, axes = plt.subplots(2, 1, figsize=(14, 5.6), sharex=True, sharey=True,
                             layout="constrained")
    for ax, source in zip(axes, SOURCES, strict=True):
        s = series[source][cell]
        ax.bar(s.index, s.values, width=1.0, color=SOURCE_COLORS[source])
        ax.set_ylabel("mm por dia")
        ax.set_title(f"{SOURCES[source]}: {(s < 0.1).mean():.0%} dos dias com menos de "
                     f"0,1 mm; {(s >= 20).sum()} dias com 20 mm ou mais", loc="left",
                     fontsize=10)
    lat, lon = cells(slug).loc[cell, ["latitude", "longitude"]]
    fig.suptitle(f"{load_region(slug)['name']} · célula em {lat:.2f}°, {lon:.2f}° · {YEAR}",
                 x=0.02, ha="left", fontsize=12)
    return fig


@app.cell(hide_code=True)
def _(day_region):
    mo.vstack([
        mo.md(r"""
        A diferença mais importante para este capítulo, porém, não está na média, e sim no
        dia a dia. A Figura 2 mostra um ano inteiro, 2018, na célula do centro da bacia
        escolhida, nas duas fontes.
        """),
        day_region,
        book.figure(plot_days(day_region.value), "dias",
                    "Figura 2. Chuva diária de 2018 numa célula do centro da bacia, no ERA5 "
                    "(acima) e no CHIRPS (abaixo). Na versão impressa, Xingu.",
                    region=day_region.value, save=day_region.value == "xingu"),
        mo.md(r"""
        No ERA5, a chuva se espalha por mais dias e com menos intensidade. Nas duas bacias,
        de dezembro a março, só 7% a 9% dos dias têm menos de 1 mm, contra 17% a 21% no
        CHIRPS, e os dias de 20 mm ou mais são metade dos do CHIRPS, de 4% a 5% contra 8%. É
        um defeito conhecido dos modelos, que disparam a convecção cedo demais e com
        intensidade de menos [5]. O CHIRPS, por sua vez, tem muitos dias de chuva muito fraca,
        abaixo de 1 mm, um efeito da repartição das pêntadas pelos dias. Para os métodos
        ordinais, que olham a sequência de subidas e descidas de um dia para o outro, essas
        são duas séries muito diferentes, mesmo quando a chuva do mês é parecida.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_z():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), sharey=True, layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        e = cells(slug)[cells(slug).elegivel]
        data, labels, colors = [], [], []
        for d in NAMES:
            for source in SOURCES:
                data.append(e[f"z_{source}_{d}"].dropna())
                labels.append(f"{NAMES[d].split()[0]}\n{SOURCES[source]}")
                colors.append(SOURCE_COLORS[source])
        box = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.6,
                         showfliers=False)
        for patch, color in zip(box["boxes"], colors, strict=True):
            patch.set(facecolor=color, alpha=0.6)
        ax.axhspan(-1.96, 1.96, color=COLORS["muted"], alpha=0.25)
        ax.set(title=load_region(slug)["name"], ylabel="z contra 39 substitutas IAAFT")
    return fig


@app.cell(hide_code=True)
def _():
    _rows = []
    for _s in SLUGS:
        _t = P.load(load_region(_s), SPEC)
        _t = _t[(_t.kind == "teste") & (_t.window == "2001_2024")]
        _el = cells(_s).index[cells(_s).elegivel]
        _t = _t[_t.cell_id.isin(_el)]
        for (_src, _d), _g in _t.groupby(["variable", "descriptor"]):
            _rows.append({"Bacia": SHORT[_s], "Fonte": SOURCES[_src], "Descritor": NAMES[_d],
                          "Células": len(_g), "Rejeitam (BH)": f"{100 * _g.rejects.mean():.0f}%",
                          "z mediano": round(_g.z.median(), 1),
                          "Dias com chuva exatamente nula": f"{100 * _g.zero_fraction.median():.0f}%"})
    mo.vstack([
        mo.md(r"""
        ## 🧩 Estrutura ordinal nas duas chuvas

        Aplicamos às duas séries de cada célula os dois descritores ordinais que o
        pré-registro previa para a chuva, a entropia de permutação e a complexidade
        estatística, com padrões de cinco dias, contra 39 substitutas IAAFT, como no capítulo
        07. A chuva tem uma particularidade: dias secos seguidos são valores iguais, e os
        padrões ordinais precisam decidir qual deles vem "antes". Desfazemos esses empates com
        um ruído de um milionésimo de milímetro, sorteado com semente fixa, antes de gerar as
        substitutas; sem isso, cada sequência seca viraria um padrão crescente artificial. A
        série é a chuva bruta, sem anomalia, porque os padrões ordinais não mudam com
        transformações que preservam a ordem e a anomalia ordenaria os dias secos pela
        climatologia. Tudo isso foi fixado antes do cálculo (D-021).
        """),
        book.figure(plot_z(), "z",
                    "Figura 3. Distribuição do z contra as substitutas nas células elegíveis "
                    "de cada bacia, para a entropia de permutação e a complexidade estatística "
                    "da chuva diária de 2001 a 2024, no ERA5 (cinza) e no CHIRPS (azul). Faixa "
                    "cinza: |z| < 1,96."),
        book.table(pd.DataFrame(_rows), "rejeicao",
                   "Tabela 1. Fração das células elegíveis que rejeitam a hipótese linear "
                   "depois da correção de Benjamini–Hochberg dentro da família exploratória, z "
                   "mediano e fração mediana de dias com chuva exatamente nula, por bacia, "
                   "fonte e descritor, 2001–2024.", selection=None),
        mo.md(r"""
        As duas chuvas rejeitam a hipótese linear em todas as células, e com folga: a
        entropia fica bem abaixo da das substitutas, e a complexidade, bem acima. A chuva
        diária tem uma estrutura de sequência, de pancadas seguidas de recessões e de dias
        secos agrupados, que um processo linear com o mesmo espectro não reproduz. Isso já
        era esperado de uma variável intermitente e não diz nada, por si só, sobre caos. O
        que interessa é a diferença entre as fontes: no CHIRPS, a distância às substitutas é
        de 1,6 a 1,7 vez a do ERA5. A chuva espalhada do modelo dilui exatamente a estrutura
        que os padrões ordinais medem.
        """),
        mo.callout(mo.md(
            "Os descritores ordinais passaram na validação dos métodos em séries contínuas, "
            "mas não foram validados em séries intermitentes como a chuva. Por isso este "
            "capítulo é exploratório e lê os resultados como comparação entre as duas fontes, "
            "e não como evidência isolada."), kind="warn"),
    ])
    return


@app.function(hide_code=True)
def plot_forest():
    res = associations()
    res = res[res.medida.isin(["observado", "z"])]
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.4), sharex=True, layout="constrained")
    labels = [f"{NAMES[d]} · {SOURCES[s]}" for d in NAMES for s in SOURCES]
    for ax, slug in zip(axes, SLUGS, strict=True):
        part = res[res.bacia == slug]
        for measure, offset, fill in [("observado", -0.15, True),
                                      ("z", 0.15, False)]:
            for i, (d, s) in enumerate([(d, s) for d in NAMES for s in SOURCES]):
                r = part[(part.descritor == d) & (part.fonte == s) & (part.medida == measure)]
                if not len(r):
                    continue
                r = r.iloc[0]
                color = SOURCE_COLORS[s]
                ax.errorbar(r.rho_parcial, i + offset,
                            xerr=[[r.rho_parcial - r.ic_inf], [r.ic_sup - r.rho_parcial]],
                            fmt="o", color=color, mfc=color if fill else "white", ms=6,
                            capsize=2, lw=1.2,
                            label=("valor observado" if fill else "z contra as substitutas")
                            if i == 1 else None)
        ax.axvline(0, color=COLORS["muted"], lw=1)
        ax.set_yticks(range(len(labels)), labels, fontsize=9)
        ax.invert_yaxis()
        ax.set(xlabel="ρ parcial com a perda antecedente (IC 95% por blocos de 1°)",
               title=load_region(slug)["name"])
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=2, frameon=False)
    return fig


@app.cell(hide_code=True)
def _():
    _res = associations()
    _tab = _res.assign(Bacia=_res.bacia.map(SHORT), Fonte=_res.fonte.map(SOURCES),
                       Descritor=_res.descritor.map(NAMES))
    _tab["ρ parcial [IC 95%]"] = [ci(r, a, b) for r, a, b in zip(
        _tab.rho_parcial, _tab.ic_inf, _tab.ic_sup, strict=True)]
    _tab = _tab.pivot_table(index=["Bacia", "Descritor", "Fonte"], columns="medida",
                            values="ρ parcial [IC 95%]", aggfunc="first").reset_index()
    _tab = _tab[["Bacia", "Descritor", "Fonte", "observado", "excesso", "z", "longitudinal"]]
    mo.vstack([
        mo.md(r"""
        ## 🌳 Qual das duas acompanha a perturbação?

        Repetimos para a chuva o desenho do capítulo 08: a correlação de postos entre a perda
        antecedente de floresta e o descritor, controlando a latitude, a fração de água e a
        altitude, com intervalos por blocos espaciais de 1°. O capítulo 08 mostrou que o $z$
        e o valor observado podem contar histórias diferentes, e por isso a Figura 4 mostra
        os dois.
        """),
        book.figure(plot_forest(), "associacao",
                    "Figura 4. Correlação parcial (controles: latitude, água e altitude) entre a "
                    "perda antecedente de floresta e os descritores ordinais da chuva diária de "
                    "2001 a 2024, no ERA5 (cinza) e no CHIRPS (azul): valor observado (círculos "
                    "cheios) e z contra as substitutas (vazios), com IC 95% por blocos de 1°."),
        book.table(_tab, "associacao",
                   "Tabela 2. Correlação parcial entre perturbação e descritores ordinais da "
                   "chuva: com a perda antecedente, o valor observado, o excesso sobre a média "
                   "das substitutas e o z; e, na última coluna, a perda de 2001 a 2012 contra a "
                   "mudança do valor observado entre 2001–2012 e 2013–2024. IC 95% por blocos "
                   "de 1°.", selection=None),
        mo.md(r"""
        As duas fontes se separam. Na chuva do ERA5, nenhuma associação se distingue de zero,
        em nenhuma bacia, em nenhuma das medidas. Na do CHIRPS, as células com mais perda
        antecedente têm entropia de permutação menor e complexidade maior, nas duas bacias:
        a chuva diária ali tem uma sequência mais organizada, com padrões de cinco dias mais
        repetidos. A associação é clara no valor observado e no excesso sobre as substitutas,
        com 0,38 em módulo no Xingu e 0,21 no Tapajós, e mais fraca no $z$, que fica no limite
        do zero. Ao longo do tempo, nenhuma das duas fontes mostra que as células desmatadas
        entre 2001 e 2012 tenham mudado mais que as outras.

        É o padrão que esperaríamos se a perturbação deixasse marca na chuva e só a
        observação a registrasse. Mas há uma explicação mais simples a afastar antes.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    _d = dryness()
    _tab = _d.assign(Bacia=_d.bacia.map(SHORT))
    _tab["Células"] = _tab.celulas
    _tab["ρ parcial [IC 95%]"] = [ci(r, a, b) for r, a, b in zip(
        _tab.rho_parcial, _tab.ic_inf, _tab.ic_sup, strict=True)]
    _tab = _tab[["Bacia", "modelo", "Células", "ρ parcial [IC 95%]"]].rename(
        columns={"modelo": "Modelo"})
    _corr = {s: cells(s)[cells(s).elegivel][["perda_antecedente", *DRY]].corr("spearman")
             .iloc[0, 1:] for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## ☀️ A secura como explicação alternativa

        A fronteira agrícola não avançou ao acaso. Ela ocupou primeiro as terras mais secas e
        planas do sul das bacias, e a chuva desses lugares já tinha, antes de qualquer
        desmatamento, uma estação seca mais longa e mais dias sem chuva. Uma estação seca mais
        longa, por si só, deixa a sequência da chuva mais organizada: longos trechos de dias
        secos, interrompidos por pancadas. A latitude captura parte disso, mas não tudo, e a
        própria chuva do CHIRPS mostra que a perda antecedente anda junto com a secura mesmo
        entre células da mesma faixa.
        """),
        mo.callout(mo.md(nb.pt("Correlação de postos entre a perda antecedente e a "
                               "climatologia do CHIRPS: " + "; ".join(
            f"{SHORT[s]}, {_corr[s].chuva_anual_chirps:+.2f} com a chuva anual, "
            f"{_corr[s].dias_secos_chirps:+.2f} com a fração de dias secos e "
            f"{_corr[s].meses_secos_chirps:+.2f} com os meses abaixo de 100 mm"
            for s in SLUGS) + ".")), kind="info"),
        mo.md(r"""
        A Tabela 3 repete a associação da entropia do CHIRPS acrescentando aos controles a
        climatologia do próprio CHIRPS, uma medida de cada vez e as três juntas; troca a
        exposição pela conversão agropecuária, controlando a vegetação natural aberta; e,
        por fim, fica só com as células em que quase não havia vegetação natural aberta em
        2000. Antes de calcular, fixamos que a associação só seria tratada como robusta numa
        bacia se sobrevivesse aos três controles juntos e ao recorte das células de floresta
        (D-023).
        """),
        book.table(_tab, "secura",
                   "Tabela 3. Entropia de permutação da chuva do CHIRPS (valor observado) "
                   "contra a perda antecedente, com controles crescentes da climatologia do "
                   "CHIRPS (chuva anual, fração de dias com menos de 0,1 mm, meses com menos de "
                   "100 mm), com a conversão agropecuária em 2000 como exposição e só nas "
                   "células com menos de 5% de vegetação natural não florestal. Correlação "
                   "parcial com IC 95% por blocos de 1°.", selection=None),
        mo.md(r"""
        No Xingu, a associação passa por todos os testes. Ela muda pouco com cada controle,
        fica em cerca de −0,35 com os três juntos, repete-se com a conversão agropecuária e
        tem o mesmo tamanho nas células de floresta, onde a vegetação aberta natural não pode
        explicá-la. No Tapajós, ela resiste aos controles da secura, menor, mas desaparece nas
        células de floresta. Lá, onde a perda antecedente se confunde muito mais com o
        Cerrado e com o planalto seco do sul, a correlação com a chuva anual chega a −0,72, e
        os dados não permitem separar a perturbação da paisagem em que ela aconteceu.
        """),
        mo.callout(mo.md(
            "No Xingu, as células com mais floresta convertida até 2000 têm, na chuva diária "
            "observada, uma sequência mais organizada que a de células comparáveis "
            "preservadas, mesmo descontando a secura e a vegetação natural. A chuva do ERA5 "
            "não mostra nada disso. No Tapajós, o mesmo sinal aparece, mas não se separa da "
            "geografia."), kind="success"),
        mo.callout(mo.md(
            "A Tabela 3 e o recorte das células de floresta são análises complementares, "
            "motivadas pelo resultado da Tabela 2 e registradas como tal (D-023)."),
            kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O que este capítulo acrescenta

    A pergunta deste trabalho tem três partes, e este capítulo responde à terceira: que tipo
    de registro é preciso para que uma marca da perturbação na dinâmica do clima apareça.
    Os capítulos anteriores já indicavam que o ERA5, sozinho, não basta. Aqui há uma
    resposta mais direta, na própria dinâmica diária: a mesma análise, feita na chuva da
    reanálise e numa chuva baseada em observações, dá resultados diferentes, e a diferença
    vai na direção que a limitação do ERA5 prevê.

    Três cautelas delimitam essa leitura. A primeira é que o CHIRPS também não é uma medida
    direta da chuva de cada dia. O total de cinco dias vem do infravermelho e dos
    pluviômetros, e a repartição pelos dias vem do IMERG, cujas estimativas sobre o
    continente dependem em parte das propriedades da superfície; não podemos excluir que
    uma parte da diferença entre floresta e pasto venha do próprio algoritmo de satélite. A
    segunda é que a associação é transversal: ela compara lugares, não acompanha mudanças, e
    ao longo do tempo nenhuma das fontes mostra efeito do desmatamento recente. A terceira é
    que só no Xingu o sinal se separa da secura e da vegetação natural.

    Com essas cautelas, o capítulo fecha o argumento do trabalho por outro caminho. O
    desmatamento não só aquece a superfície, como o satélite mostra no capítulo 08; ele
    também se associa, ao menos no Xingu, a uma organização diferente da chuva de um dia
    para o outro, que a reanálise não reproduz. Uma resposta firme sobre o efeito da
    perturbação na dinâmica do clima precisa de séries diárias que acompanhem a paisagem,
    e o ERA5 não é uma delas.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Spracklen, D. V.; Arnold, S. R.; Taylor, C. M. Observations of increased tropical
    rainfall preceded by air passage over forests. *Nature*, v. 489, p. 282–285, 2012.

    [2] Lawrence, D.; Vandecar, K. Effects of tropical deforestation on climate and
    agriculture. *Nature Climate Change*, v. 5, p. 27–36, 2015.

    [3] Funk, C. et al. The climate hazards infrared precipitation with stations — a new
    environmental record for monitoring extremes. *Scientific Data*, v. 2, 150066, 2015.

    [4] Funk, C. et al. CHIRPS version 3. *Scientific Data*, v. 13, 718, 2026.

    [5] Dai, A. Precipitation characteristics in eighteen coupled climate models. *Journal of
    Climate*, v. 19, p. 4605–4630, 2006.
    """)
    return


if __name__ == "__main__":
    app.run()
