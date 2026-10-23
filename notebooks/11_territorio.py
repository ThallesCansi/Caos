# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "11 · O território"
# description = "Terras Indígenas e Unidades de Conservação diante do clima e do fogo"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="11 · O território")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from amazon_chaos import gradient as G
    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.features import fire_weather as F
    from amazon_chaos.features.territory import protection
    from amazon_chaos.nonlinear import precip as P
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.viz import COLORS, map_basins

    book = nb.notebook("11_territorio")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    SHORT = {"xingu": "Xingu", "tapajos": "Tapajós"}
    CLASS_NAMES = {"ti": "Terra Indígena", "uc": "Unidade de Conservação",
                   "mista": "mista", "fora": "fora de áreas protegidas"}
    CLASS_COLORS = {"ti": "#8c4a2f", "uc": "#2e7d4f", "mista": "#c9a227",
                    "fora": COLORS["t2m"]}
    DRY_SEASON = (6, 7, 8, 9, 10)


@app.function(hide_code=True)
@mo.cache
def cells(slug):
    cfg = load_region(slug)
    table = P.cell_table(cfg, SPEC).join(G.surface_table(cfg)).join(protection(cfg))
    return table


@app.function(hide_code=True)
@mo.cache
def basin(slug):
    cfg = load_region(slug)
    context = regions.load_context(cfg)
    return {"cells": regions.cells(cfg), "limit": regions.boundary(cfg),
            "tis": context["tis"], "ucs": context["ucs"]}


@app.function(hide_code=True)
@mo.cache
def fire_events(slug):
    ev = F.composite(load_region(slug))
    c = cells(slug)
    ev = ev.join(c[["classe", "elegivel"]], on="cell_id")
    ev = ev[ev.elegivel & ev.dia.dt.month.isin(DRY_SEASON)]
    return ev


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🗺️ O território

    Os capítulos anteriores trataram a perturbação da floresta como um número por célula, a
    fração desmatada ou queimada. Mas a perturbação não se distribui ao acaso. Ela segue as
    estradas, o preço da soja e do gado, a posse da terra e, sobretudo, os limites que a
    sociedade traçou no mapa. Nas duas bacias, quase metade da área do Xingu e um terço da do
    Tapajós estão em Terras Indígenas ou em Unidades de Conservação federais, e esses limites
    aparecem nitidamente em qualquer mapa de desmatamento.

    Este capítulo é uma ponte entre a parte quantitativa do trabalho e a leitura
    socioespacial. Ele não pergunta se proteger uma área reduz o desmatamento, uma pergunta
    com literatura própria e métodos próprios [1, 2], e sim como as áreas protegidas
    aparecem em cada resultado dos capítulos anteriores: na perturbação, na temperatura da
    superfície, na chuva e no fogo. É material para a interpretação, e não uma conclusão
    causal.
    """)
    return


@app.function(hide_code=True)
def plot_maps():
    fig, axes = plt.subplots(1, 2, figsize=(14, 8.2), layout="constrained")
    fields = {}
    for slug in SLUGS:
        c = cells(slug).reset_index().set_index(["latitude", "longitude"])
        lst = c.lst_dia_seca_c - c.loc[c.elegivel, "lst_dia_seca_c"].mean()
        fields[slug] = (c.perda_2000_2024.to_xarray(), lst.to_xarray())
    specs = [("Perda de floresta 2000–2024 (fração)", "OrRd", 0, 0.6),
             ("LST diurno na estação seca, anomalia na bacia (°C)", "RdBu_r", -5, 5)]
    for k, (ax, (title, cmap, vmin, vmax)) in enumerate(zip(axes, specs, strict=True)):
        map_basins(ax, [(basin(s)["cells"], fields[s][k], basin(s)["limit"]) for s in SLUGS],
                   cmap, title, vmin=vmin, vmax=vmax)
        for s in SLUGS:
            basin(s)["tis"].boundary.plot(ax=ax, color="#3b1f12", lw=0.8)
            basin(s)["ucs"].boundary.plot(ax=ax, color="#0f4d2a", lw=0.8, ls="--")
        ax.set_title(title)
    return fig


@app.cell(hide_code=True)
def _():
    _rows = []
    for _s in SLUGS:
        _e = cells(_s)[cells(_s).elegivel]
        for _k, _g in _e.groupby("classe"):
            _rows.append({"Bacia": SHORT[_s], "Classe": CLASS_NAMES[_k], "Células": len(_g),
                          "Latitude": round(_g.latitude.median(), 1),
                          "Perda até 2000": round(_g.perda_antecedente.median(), 3),
                          "Perda 2000–2024": round(_g.perda_2000_2024.median(), 3),
                          "Focos por 100 km² por ano": round(
                              _g.focos_100km2_ano_2003_2024.median(), 2),
                          "LST seco (°C)": round(_g.lst_dia_seca_c.median(), 1),
                          "Máxima ERA5 seca (°C)": round(_g.era5_tmax_seca.median(), 1)})
    _order = {"Terra Indígena": 0, "Unidade de Conservação": 1, "mista": 2,
              "fora de áreas protegidas": 3}
    _tab = pd.DataFrame(_rows).sort_values(["Bacia", "Classe"],
                                           key=lambda s: s.map(_order).fillna(s))
    mo.vstack([
        mo.md(r"""
        ## 🧭 O que os limites separam

        A Figura 1 mostra a perda de floresta de 2000 a 2024 e a temperatura da superfície na
        estação seca, com os limites das Terras Indígenas (linhas contínuas) e das Unidades de
        Conservação federais (tracejadas). Cada célula recebe uma classe: Terra Indígena ou
        Unidade de Conservação quando a categoria cobre pelo menos metade dela, fora quando
        menos de 10% é protegido, e mista nos demais casos.
        """),
        book.figure(plot_maps(), "mapas",
                    "Figura 1. Perda de floresta de 2000 a 2024 (MapBiomas) e temperatura "
                    "diurna da superfície na estação seca (MODIS, 2001–2024, anomalia em relação "
                    "à média das células elegíveis de cada bacia), com os limites atuais das "
                    "Terras Indígenas (FUNAI, linhas contínuas) e das Unidades de Conservação "
                    "federais (ICMBio, tracejadas)."),
        book.table(_tab, "classes",
                   "Tabela 1. Mediana, nas células elegíveis de cada classe, da latitude, da "
                   "perda de floresta até 2000 e de 2000 a 2024, da densidade de focos de "
                   "fogo de 2003 a 2024, da temperatura diurna da superfície (MODIS) e da "
                   "máxima do ar (ERA5) na estação seca.", selection=None),
        mo.md(r"""
        Os limites são visíveis a olho nu. Dentro das Terras Indígenas e das Unidades de
        Conservação, a perda de floresta de 2000 a 2024 é praticamente nula, e a densidade de
        focos de fogo é de 30 a 55 vezes menor que fora no Xingu e cerca de 6 vezes menor no
        Tapajós. A superfície, na estação seca, fica de 3 a 4,4 °C mais fresca. A máxima do ar no ERA5, por outro lado, é a mesma nas
        quatro classes, cerca de 33 °C: o modelo não vê o território. A Tabela 1 tem uma
        exceção que vale notar. No Tapajós, as Terras Indígenas têm uma perda antecedente
        mediana de 10%, que não é desmatamento: são as terras do sul da bacia, como as dos
        povos Paresí, Nambikwara e Bakairí, onde boa parte da vegetação original é Cerrado.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_latitude():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), sharey=True, layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        e = cells(slug)[cells(slug).elegivel & cells(slug).classe.isin(["ti", "uc", "fora"])]
        e = e.assign(protegida=e.classe != "fora", faixa=np.floor(e.latitude) + 0.5)
        for column, style, source in [("lst_dia_seca_c", "-o", "MODIS, superfície"),
                                      ("era5_tmax_seca", "--s", "ERA5, ar a 2 m")]:
            for protected, color in [(True, CLASS_COLORS["uc"]), (False, CLASS_COLORS["fora"])]:
                g = e[e.protegida == protected].groupby("faixa")[column].median()
                ax.plot(g.index, g.values, style, color=color, ms=4,
                        mfc=color if "MODIS" in source else "white",
                        label=f"{'TI ou UC' if protected else 'fora'} · {source}")
        ax.set(xlabel="latitude (°)", ylabel="°C, estação seca",
               title=load_region(slug)["name"])
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=4, frameon=False)
    return fig


@app.cell(hide_code=True)
def _():
    _rows = []
    _targets = {"perda_2000_2024": "perda de floresta 2000–2024",
                "focos_100km2_ano_2003_2024": "densidade de focos 2003–2024",
                "lst_dia_seca_c": "LST diurno, estação seca (MODIS)",
                "delta_lst_seca": "aquecimento do LST entre as décadas (MODIS)",
                "era5_tmax_seca": "máxima do ar, estação seca (ERA5)",
                "obs_precip_chirps_pe_entropy": "entropia da chuva (CHIRPS)"}
    for _s in SLUGS:
        _e = cells(_s)[cells(_s).elegivel]
        for _col, _name in _targets.items():
            _a = G.associate(_e, "frac_protegida", _col)
            _rows.append({"Bacia": SHORT[_s], "Resposta": _name, "Células": _a["celulas"],
                          "ρ parcial [IC 95%]": f"{_a['rho_parcial']:+.2f} "
                          f"[{_a['ic_inf']:+.2f}; {_a['ic_sup']:+.2f}]"})
    mo.vstack([
        mo.md(r"""
        ## 🌡️ Na mesma latitude

        As áreas protegidas ficam, em média, mais ao norte que a fronteira agrícola, e o norte
        é naturalmente mais úmido e mais fresco. Para separar as duas coisas, a Figura 2
        compara, em cada faixa de 1° de latitude, as células protegidas com as de fora, e a
        Tabela 2 dá a correlação parcial entre a fração protegida da célula e cada resposta,
        com os controles de sempre: latitude, água e altitude.
        """),
        book.figure(plot_latitude(), "latitude",
                    "Figura 2. Mediana, por faixa de 1° de latitude, da temperatura diurna da "
                    "superfície (MODIS, círculos cheios) e da máxima do ar a 2 m (ERA5, "
                    "quadrados vazios) na estação seca, nas células em Terra Indígena ou "
                    "Unidade de Conservação (verde) e nas de fora (vermelho)."),
        book.table(pd.DataFrame(_rows), "associacao",
                   "Tabela 2. Correlação parcial (controles: latitude, água e altitude) entre a "
                   "fração protegida (TI ou UC federal) da célula e cada resposta, com IC 95% "
                   "por blocos de 1°.", selection=None),
        mo.md(r"""
        Na mesma faixa de latitude, a superfície das áreas protegidas fica, na mediana das
        faixas, de 2 a 2,6 °C mais fresca que a de fora na estação seca, e as curvas do ERA5
        se sobrepõem. A exceção é o extremo sul das duas bacias, perto de 14°S, onde as áreas
        protegidas ficam no Cerrado e a superfície é tão quente dentro quanto fora: ali a
        vegetação natural já é aberta, e a proteção não muda a cobertura; é também só ali, no
        Tapajós, que o ERA5 mostra as áreas protegidas mais frescas. A
        Tabela 2 mostra o mesmo de outro modo: com os controles, a fração protegida se
        associa fortemente a menos desmatamento, menos fogo, uma superfície mais fresca e um
        aquecimento menor entre as duas décadas, nas duas bacias; com a máxima do ERA5, a
        associação é nula. Na chuva do CHIRPS, a fração protegida se associa a uma entropia
        maior, isto é, a uma sequência menos organizada, no Xingu, o espelho do resultado do
        capítulo 09; no Tapajós, não.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _s in SLUGS:
        _r = F.summary(fire_events(_s), ["classe"])
        _r = _r[_r.medida.isin(["vpd_7d", "dias_secos_chirps"])]
        for _, _x in _r.iterrows():
            _rows.append({"Bacia": SHORT[_s], "Classe": CLASS_NAMES[_x.classe],
                          "Medida": {"vpd_7d": "VPD, 7 dias",
                                     "dias_secos_chirps": "dias seguidos sem chuva"}[_x.medida],
                          "Eventos": _x.eventos,
                          "Percentil [IC 95%]": f"{_x.percentil:.3f} "
                          f"[{_x.ic_inf:.3f}; {_x.ic_sup:.3f}]"})
    mo.vstack([
        mo.md(r"""
        ## 🔥 O fogo dentro e fora

        O capítulo 10 mostrou que, na estação seca, o fogo das células preservadas começa
        com tempo mais seco que o normal, e o das perturbadas, com o tempo de um dia
        qualquer. A Tabela 3 refaz a mesma conta pelas classes do território.
        """),
        book.table(pd.DataFrame(_rows), "fogo",
                   "Tabela 3. Percentil médio dos inícios de episódio de fogo na estação seca "
                   "entre os seus controles (capítulo 10), para o VPD da semana anterior e os "
                   "dias seguidos sem chuva, por classe do território, com IC 95% por "
                   "bootstrap de anos.", selection=None),
        mo.md(r"""
        Fora das áreas protegidas, o fogo começa com o tempo de um dia típico da estação
        seca, com percentis em torno de 0,50. Dentro das Terras Indígenas e das Unidades de
        Conservação, os poucos episódios que há começam depois de dias mais secos que o
        normal: o VPD da semana anterior fica entre os percentis 0,54 e 0,59, e os dias sem
        chuva entre 0,57 e 0,62, com intervalos que excluem 0,5 em todos os casos menos dois,
        o VPD nas Unidades de Conservação do Xingu e nas Terras Indígenas do Tapajós, que
        tocam o meio. Ali, o fogo depende do tempo; fora, do calendário.
        """),
        mo.callout(mo.md(
            "Os limites das Terras Indígenas e das Unidades de Conservação aparecem em todos "
            "os resultados observados deste trabalho: menos desmatamento, menos fogo, uma "
            "superfície mais fresca que esquentou menos, uma chuva com outra organização no "
            "Xingu e um fogo que só começa quando o tempo foge do normal. Nenhum deles aparece "
            "no ERA5."), kind="success"),
        mo.callout(mo.md(
            "Estas são associações (D-026). As áreas protegidas não foram criadas ao acaso: "
            "muitas ficam em lugares mais remotos, e muitas foram criadas ou homologadas "
            "durante o período estudado, enquanto os limites usados aqui são os atuais. A "
            "comparação mostra o território como chave de leitura, e não mede o efeito da "
            "proteção."), kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 Para a leitura socioespacial

    O que os capítulos quantitativos mediram como gradiente de perturbação é, no mapa, em
    boa parte, a fronteira entre a terra protegida e a terra aberta à conversão. Essa
    fronteira organiza o desmatamento, o fogo e a temperatura da superfície, e, no Xingu,
    também a sequência da chuva. Ela é uma fronteira política, produzida por lutas pela
    demarcação, por políticas de criação de áreas protegidas e pela pressão da agropecuária
    e das estradas, e é nela que a interpretação socioespacial deste trabalho encontra os
    números. Dois cuidados acompanham essa leitura: a reanálise usada como instrumento
    principal não enxerga nada disso, e as diferenças aqui descritas são associações num
    território em que a proteção e a geografia andam juntas.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Nepstad, D. et al. Inhibition of Amazon deforestation and fire by parks and
    indigenous lands. *Conservation Biology*, v. 20, p. 65–73, 2006.

    [2] Joppa, L. N.; Pfaff, A. High and far: biases in the location of protected areas.
    *PLoS ONE*, v. 4, e8273, 2009.
    """)
    return


if __name__ == "__main__":
    app.run()
