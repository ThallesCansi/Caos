# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "10 · O tempo antes do fogo"
# description = "Quando o fogo segue o tempo seco e quando segue o calendário"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="10 · O tempo antes do fogo")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from amazon_chaos import gradient as G
    from amazon_chaos import nb
    from amazon_chaos.config import load_region
    from amazon_chaos.features import fire_weather as F
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.viz import COLORS

    book = nb.notebook("10_fogo")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    SHORT = {"xingu": "Xingu", "tapajos": "Tapajós"}
    THIRDS = list(F.THIRDS)
    THIRD_COLORS = {"preservada": "#2e7d4f", "intermediária": "#c9a227",
                    "perturbada": COLORS["t2m"]}
    DRY_SEASON = (6, 7, 8, 9, 10)
    SHOWN = ["vpd_7d", "vpd_30d", "t2m_7d", "t2m_30d", "chuva_30d_chirps",
             "dias_secos_chirps"]
    LABELS = {"vpd_7d": "VPD, 7 dias", "vpd_30d": "VPD, 30 dias",
              "t2m_7d": "temperatura, 7 dias", "t2m_30d": "temperatura, 30 dias",
              "chuva_30d_chirps": "chuva, 30 dias (CHIRPS)",
              "chuva_30d_era5": "chuva, 30 dias (ERA5)",
              "dias_secos_chirps": "dias seguidos sem chuva"}


@app.function(hide_code=True)
@mo.cache
def events(slug):
    cfg = load_region(slug)
    ev = F.composite(cfg)
    cells = G.cell_table(cfg, SPEC)
    ev = ev.join(cells[["perda_antecedente", "elegivel"]], on="cell_id")
    ev = ev[ev.elegivel].copy()
    ev["estacao"] = np.where(ev.dia.dt.month.isin(DRY_SEASON), "seca", "chuvosa")
    # os cortes dos terços são feitos nas células, e cada evento herda o da sua célula
    ev["terco"] = ev.cell_id.map(F.cell_thirds(cells)).astype(
        pd.CategoricalDtype(THIRDS, ordered=True))
    return ev


@app.function(hide_code=True)
@mo.cache
def contrasts():
    return pd.concat([F.contrast(events(slug), ["estacao"]).assign(bacia=slug)
                      for slug in SLUGS], ignore_index=True)


@app.function(hide_code=True)
@mo.cache
def summaries():
    rows = []
    for slug in SLUGS:
        rows.append(F.summary(events(slug), ["estacao", "terco"]).assign(bacia=slug))
        rows.append(F.summary(events(slug), ["estacao"]).assign(bacia=slug, terco="todas"))
    return pd.concat(rows, ignore_index=True)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🔥 O tempo antes do fogo

    Na Amazônia, quase todo fogo é aceso por pessoas. Ele limpa o pasto, queima o que foi
    derrubado e prepara a roça; às vezes escapa e entra na floresta. O tempo não acende o
    fogo, mas decide se ele pega, quanto se espalha e se a floresta úmida, que normalmente
    não queima, deixa de ser uma barreira [1, 2]. Este capítulo responde à pergunta secundária
    do trabalho: quais condições do tempo antecedem as detecções de fogo nas células das
    duas bacias?

    A pergunta parece simples, mas tem uma armadilha. O fogo se concentra na estação seca, e
    na estação seca faz calor e chove pouco por definição. Comparar o tempo antes do fogo com
    a média do ano mostraria só o calendário. Por isso comparamos cada início de fogo com os
    mesmos dias do calendário, na mesma célula, nos anos em que ela não queimou: a pergunta
    passa a ser se o fogo começa em dias mais secos que o normal para aquela época e aquele
    lugar.
    """)
    return


@app.cell(hide_code=True)
def _():
    _n = {s: len(events(s)) for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🧮 Como medimos

        Um foco de fogo ativo é um pixel quente visto pelo satélite de referência do
        BDQueimadas; um incêndio pode gerar dezenas deles, em vários dias. Para não contar o
        mesmo incêndio muitas vezes, o evento é o início de um episódio: um dia com foco numa
        célula que passou pelo menos 30 dias sem nenhum. Para cada evento, medimos o tempo até
        a véspera: a anomalia do déficit de pressão de vapor e da temperatura no ERA5, em
        relação à normal de 1991 a 2020, na semana e no mês anteriores; a chuva do mês
        anterior; e o número de dias seguidos sem chuva até a véspera, estes dois pelo CHIRPS,
        a chuva observada do capítulo anterior.

        Cada medida do evento é comparada com a dos seus controles: em cada um dos outros
        anos, a mesma data do calendário e os 15 dias corridos de cada lado, na mesma célula,
        desde que ela não tenha tido foco nesse intervalo, cerca de 300 dias por evento. Um
        evento de 5 de janeiro tem, assim, controles no fim de dezembro do ano anterior. O resultado é o percentil do evento entre os
        controles. Um percentil de 0,5 quer dizer que o fogo começou com o tempo de um dia
        típico; 0,6 quer dizer que, naquele lugar e naquela época, só 40% dos dias sem fogo
        tinham um VPD tão alto. Como uma mesma seca atinge muitas células de uma vez, os
        intervalos de confiança reamostram anos inteiros, e não eventos (D-025).

        Aqui a estação seca vai de junho a outubro, e não de junho a setembro como nos
        capítulos 3, 4 e 8. A escolha foi fixada antes do cálculo (D-025) porque outubro,
        ainda seco no sul das duas bacias, é um dos meses com mais fogo; com junho a
        setembro, as diferenças entre as paisagens ficam iguais ou um pouco maiores.

        Para comparar paisagens, dividimos as células elegíveis em três terços de igual
        número de células pela perda antecedente, das mais preservadas às mais perturbadas,
        e cada evento herda o terço da sua célula. Os cortes são feitos nas células, e não
        nos eventos: as células perturbadas queimam muito mais vezes, e cortar sobre os
        eventos empurraria boa parte das células preservadas para o terço do meio. Por isso
        o terço preservado tem bem menos eventos que os outros dois.
        """),
        mo.callout(mo.md(nb.pt("Inícios de episódio de fogo de 2003 a 2024 nas células "
                               "elegíveis: " + "; ".join(f"{SHORT[s]}, {_n[s]:,}"
                                                         for s in SLUGS) + ".")),
                   kind="info"),
    ])
    return


@app.function(hide_code=True)
def plot_months():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.4), sharey=True, layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        ev = events(slug)
        for third in THIRDS:
            part = ev[ev.terco == third]
            share = part.dia.dt.month.value_counts(normalize=True).reindex(range(1, 13),
                                                                           fill_value=0)
            ax.plot(share.index, 100 * share.values, "-o", color=THIRD_COLORS[third], ms=4,
                    label=f"células {third}s" if third != "intermediária"
                    else "células intermediárias")
        ax.axvspan(DRY_SEASON[0] - 0.5, DRY_SEASON[-1] + 0.5, color=COLORS["muted"],
                   alpha=0.12)
        ax.set_xticks(range(1, 13), ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago",
                                     "set", "out", "nov", "dez"])
        ax.set(title=load_region(slug)["name"], ylabel="% dos inícios de episódio")
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=3, frameon=False)
    return fig


@app.cell(hide_code=True)
def _():
    _share = {s: (events(s).estacao == "seca").groupby(events(s).terco, observed=True).mean()
              for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 📅 Quando o fogo começa

        A Figura 1 mostra em que meses começam os episódios de fogo nas células de cada terço
        de perda antecedente, das mais preservadas às mais perturbadas.
        """),
        book.figure(plot_months(), "meses",
                    "Figura 1. Distribuição, por mês, dos inícios de episódio de fogo (um dia "
                    "com foco depois de 30 dias sem foco na célula) de 2003 a 2024, nas células "
                    "de cada terço de perda antecedente. Faixa cinza: estação seca (junho a "
                    "outubro)."),
        mo.callout(mo.md(nb.pt("Fração dos inícios de episódio na estação seca, das células "
                               "preservadas às perturbadas: " + "; ".join(
            f"{SHORT[s]}, " + ", ".join(f"{100 * v:.0f}%" for v in _share[s].values)
            for s in SLUGS) + ".")), kind="info"),
        mo.md(r"""
        Nas células preservadas, o fogo começa sobretudo no auge da seca, de julho a
        setembro, com o pico em agosto. Nas perturbadas, a distribuição é mais espalhada
        pelo ano, com mais
        episódios começando também na estação chuvosa: onde há pasto e lavoura, há queima
        em quase todos os meses. Esse contraste já sugere que o fogo das duas paisagens
        obedece a ritmos diferentes, e a seção seguinte mostra o papel do tempo em cada uma.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_percentiles():
    res = summaries()
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.2), sharex=True, layout="constrained")
    for row, slug in enumerate(SLUGS):
        for col, season in enumerate(["seca", "chuvosa"]):
            ax = axes[row, col]
            part = res[(res.bacia == slug) & (res.estacao == season)]
            for k, third in enumerate(THIRDS):
                sel = part[part.terco == third].set_index("medida").loc[SHOWN]
                y = np.arange(len(SHOWN)) + (k - 1) * 0.22
                ax.errorbar(sel.percentil, y, xerr=[sel.percentil - sel.ic_inf,
                                                    sel.ic_sup - sel.percentil],
                            fmt="o", color=THIRD_COLORS[third], ms=5, capsize=2, lw=1.2,
                            label=f"células {third}s" if third != "intermediária"
                            else "células intermediárias")
            ax.axvline(0.5, color=COLORS["muted"], lw=1)
            ax.set_yticks(range(len(SHOWN)), [LABELS[m] for m in SHOWN], fontsize=9)
            ax.invert_yaxis()
            ax.set_title(f"{load_region(slug)['name']} · estação {season}", fontsize=11)
            if row == 1:
                ax.set_xlabel("percentil do evento entre os seus controles (IC 95% por anos)")
    handles, names = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=3, frameon=False)
    return fig


@app.cell(hide_code=True)
def _():
    _res = summaries()
    _tab = _res[_res.terco == "todas"].copy()
    _tab["Bacia"] = _tab.bacia.map(SHORT)
    _tab["Estação"] = _tab.estacao
    _tab["Medida"] = _tab.medida.map(LABELS)
    _tab["Percentil [IC 95%]"] = [f"{p:.3f} [{a:.3f}; {b:.3f}]" for p, a, b in zip(
        _tab.percentil, _tab.ic_inf, _tab.ic_sup, strict=True)]
    _tab = _tab[["Bacia", "Estação", "Medida", "eventos", "Percentil [IC 95%]"]].rename(
        columns={"eventos": "Eventos"})
    _con = contrasts()
    _con = pd.DataFrame({
        "Bacia": _con.bacia.map(SHORT), "Estação": _con.estacao,
        "Medida": _con.medida.map(LABELS), "Preservadas": _con.preservada.round(3),
        "Perturbadas": _con.perturbada.round(3),
        "Diferença [IC 95%]": [f"{d:+.3f} [{a:+.3f}; {b:+.3f}]" for d, a, b in zip(
            _con.diferenca, _con.ic_inf, _con.ic_sup, strict=True)]})
    mo.vstack([
        mo.md(r"""
        ## 🌡️ O tempo antes do fogo

        A Figura 2 mostra o percentil médio dos eventos em cada medida, por estação e por
        terço de perda antecedente. A linha vertical marca 0,5, o tempo de um dia típico;
        pontos à direita indicam mais VPD, mais calor ou mais dias secos que o normal, e, na
        chuva, pontos à esquerda indicam menos chuva que o normal.
        """),
        book.figure(plot_percentiles(), "percentis",
                    "Figura 2. Percentil médio dos inícios de episódio de fogo entre os seus "
                    "controles (mesma célula, ±15 dias do calendário, anos sem foco), para a "
                    "anomalia do VPD e da temperatura (ERA5) e a chuva e os dias secos "
                    "(CHIRPS) antes do evento, por bacia, estação e terço de perda antecedente, "
                    "com IC 95% por bootstrap de anos. Linha vertical: 0,5, um dia típico."),
        mo.md(r"""
        Na estação chuvosa, o padrão é o mesmo nas três paisagens e nas duas bacias: o fogo só
        começa depois de uma janela de tempo seco. O VPD da semana anterior fica entre os
        percentis 0,59 e 0,64, os dias secos seguidos entre 0,57 e 0,67, e os intervalos dos
        dois ficam longe de 0,5; a chuva do mês anterior fica um pouco abaixo do normal, com
        intervalos que quase sempre tocam o meio. Fora da época do fogo, é preciso uma janela
        de alguns dias sem chuva para queimar.

        Na estação seca, as paisagens se separam. Nas células preservadas, o fogo continua
        exigindo tempo anormalmente seco: VPD perto do percentil 0,59, dias secos perto de
        0,61, menos chuva no mês anterior, nas duas bacias e com intervalos que excluem 0,5.
        Nas células perturbadas, o percentil fica perto de 0,5 em todas as medidas, e os
        intervalos incluem o meio da distribuição: o fogo começa com o tempo de um dia
        qualquer da estação seca. As células intermediárias ficam entre as duas no Xingu,
        onde os dias secos e a chuva do mês anterior ainda se afastam do normal, e perto
        das perturbadas no Tapajós. Na estação seca, portanto, o papel do tempo diminui
        aos poucos à medida que a paisagem é convertida. A temperatura do mês anterior
        acompanha o VPD com menos força, perto do normal na estação chuvosa e um pouco acima
        dele nas células preservadas na estação seca. A Tabela 1 traz os valores de todas as
        células juntas.
        """),
        book.table(_tab, "resumo",
                   "Tabela 1. Percentil médio dos inícios de episódio de fogo entre os seus "
                   "controles, por bacia, estação e medida, em todas as células elegíveis, com "
                   "IC 95% por bootstrap de anos.", selection=None),
        mo.md(r"""
        Intervalos que não se sobrepõem sugerem uma diferença entre as paisagens, mas não a
        testam. A Tabela 2 faz o teste direto: a diferença entre o percentil médio dos
        eventos das células preservadas e o das perturbadas, com o intervalo obtido
        reamostrando os mesmos anos para os dois grupos, já que eles dividem as mesmas
        secas. Na estação seca, a diferença fica perto de 0,1 e exclui zero nas duas bacias
        no VPD da semana e do mês, nos dias secos e na chuva do mês anterior, pelas duas
        fontes; na temperatura, ela exclui zero nas duas escalas no Tapajós e só na semana
        anterior no Xingu. Na estação chuvosa, as diferenças são menores, e só a dos dias
        secos seguidos exclui zero nas duas bacias: mesmo fora da época do fogo, ele começa
        nas preservadas depois de uma janela seca um pouco mais longa.
        """),
        book.table(_con, "contraste",
                   "Tabela 2. Diferença do percentil médio dos inícios de episódio de fogo "
                   "entre as células preservadas e as perturbadas (terços de perda "
                   "antecedente), por bacia, estação e medida, com IC 95% por bootstrap dos "
                   "mesmos anos nos dois grupos.", selection=None),
        mo.callout(mo.md(
            "Na estação seca, o fogo da paisagem convertida começa com o tempo de um dia "
            "qualquer, como se esperaria de queimas agendadas pelo uso da terra; o fogo das "
            "áreas preservadas começa quando o tempo está mais seco que o normal, quando a "
            "floresta deixa de ser úmida o bastante para barrar o fogo que chega até ela."),
            kind="success"),
        mo.md(r"""
        Essa leitura é coerente com o que se sabe do fogo amazônico [1, 2], mas os dados não a
        demonstram sozinhos. O foco marca onde o satélite viu calor, não onde o fogo foi
        aceso: um episódio numa célula preservada pode ser um fogo que veio do pasto vizinho.
        E o terço de perda antecedente mistura a paisagem e a geografia, como nos capítulos
        anteriores. O que os dados mostram com segurança é a diferença de ritmo: o fogo da
        floresta depende do tempo; o da paisagem convertida, muito menos.
        """),
        mo.callout(mo.md(
            "A análise é descritiva (D-025). Ela não separa a ignição, que é humana, da "
            "propagação, que depende do tempo e da vegetação, e por isso não deve ser lida "
            "como efeito do tempo sobre o número de incêndios."), kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O que este capítulo acrescenta

    A pergunta secundária tem uma resposta em duas partes. Em toda parte, começar um fogo
    fora da estação seca exige uma janela de tempo seco. Dentro da estação seca, o tempo
    importa onde a floresta está de pé e quase não importa onde ela já foi convertida. Isso
    liga a dinâmica do clima, assunto dos capítulos anteriores, ao território: o calendário
    do fogo numa paisagem de pasto e lavoura é um calendário humano, e a vulnerabilidade da
    floresta ao fogo aparece justamente nos dias em que o tempo foge do normal, como os
    das secas de 2015–2016 e 2023–2024. É nessa fronteira, entre o fogo
    que se acende por decisão e o que se espalha por condição, que a leitura socioespacial
    deste trabalho se apoia.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Aragão, L. E. O. C. et al. 21st Century drought-related fires counteract the decline
    of Amazon deforestation carbon emissions. *Nature Communications*, v. 9, 536, 2018.

    [2] Brando, P. M. et al. The gathering firestorm in southern Amazonia. *Science
    Advances*, v. 6, eaay1632, 2020.
    """)
    return


if __name__ == "__main__":
    app.run()
