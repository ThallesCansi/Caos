# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "12 · A floresta como sistema dinâmico"
# description = "A vegetação sozinha, com a atmosfera e depois do fogo"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="12 · A floresta como sistema dinâmico")

with app.setup(hide_code=True):
    import json

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from amazon_chaos import gradient as G
    from amazon_chaos import nb
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear import fire_response as FR
    from amazon_chaos.nonlinear import gate as GT
    from amazon_chaos.nonlinear import vegetation_dynamics as VD
    from amazon_chaos.nonlinear import vegetation_scales as VS
    from amazon_chaos.nonlinear.results import NAMES
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.nonlinear.vegetation_gate import load_vegetation_spec
    from amazon_chaos.nonlinear.vegetation_gate import output_dir as gate_dir
    from amazon_chaos.viz import COLORS

    book = nb.notebook("12_floresta_atmosfera")
    VSPEC = load_vegetation_spec()
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    SHORT = {"xingu": "Xingu", "tapajos": "Tapajós"}
    VARS = {"lai": "LAI", "ndmi": "NDMI"}
    VAR_COLORS = {"lai": "#2e7d4f", "ndmi": COLORS["precip"]}
    BASIN_COLORS = {"xingu": "#2e7d4f", "tapajos": COLORS["vpd"]}
    PRIMARY = VSPEC["families"]["primary"]
    DESCRIPTORS = NAMES | {"cao_de2": "Cao (E2)", "smap": "S-map (ganho não linear)",
                           "kantz": "Lyapunov (Kantz)", "wolf": "Lyapunov (Wolf)"}
    FORCINGS = {"vpd": "VPD", "chuva_32d": "chuva de 32 dias", "chuva_96d": "chuva de 96 dias"}
    PREDICTORS = {"vegetacao": "só a vegetação", "atmosfera": "só a atmosfera",
                  "conjunto": "vegetação e atmosfera"}
    ALPHA = VSPEC["surrogates"]["alpha"]
    MAIN = VD.RULES["primary_max_missing"]


@app.function(hide_code=True)
@mo.cache
def results(slug):
    out = pd.read_parquet(VD.output_dir(load_region(slug), VSPEC) / "resultados.parquet")
    out = out[out.descriptor != "excluida"].copy()
    out["grupo"] = np.where(out.lacunas <= MAIN, "principal", "sensibilidade")
    return out


@app.function(hide_code=True)
@mo.cache
def gate_table():
    folder = gate_dir(VSPEC)
    rates = GT.rejection_rates(pd.read_csv(folder / "descritores.csv"), ALPHA)
    out = GT.verdict(rates, VSPEC).set_index("descriptor")
    sm = pd.read_csv(folder / "smap.csv")
    sm = sm[(sm.horizon == 1) & (sm.noise == max(VSPEC["gate"]["noise"]))]
    smap_rate = (sm.pvalue <= ALPHA).groupby(sm.control).mean()
    out.loc["smap"] = {**{f"poder {c}": smap_rate[c] for c in ("henon", "logistic", "lorenz")},
                       "rejeição ar1": smap_rate["ar1"], "rejeição white": smap_rate["white"],
                       "rejeição seasonal_trend": smap_rate["seasonal_trend"]}
    return out


@app.function(hide_code=True)
def stage1_rates():
    rows = []
    for slug in SLUGS:
        r = results(slug)
        e = r[(r.etapa == 1) & r.descriptor.isin(PRIMARY)]
        # o LAI se lê nas células principais; o NDMI quase só tem células de sensibilidade
        for (v, d), g in e.groupby(["variable", "descriptor"]):
            g = g[g.grupo == "principal"] if v == "lai" else g
            rows.append({"bacia": slug, "variavel": v, "descritor": d,
                         "celulas": g.cell_id.nunique(),
                         "rejeicao": (g.pvalue <= ALPHA).mean(), "z": g.z.median()})
    return pd.DataFrame(rows)


@app.function(hide_code=True)
@mo.cache
def association():
    """Medidas por célula contra a perda antecedente, com os controles geográficos."""
    rows = []
    for slug in SLUGS:
        cfg = load_region(slug)
        cells = G.cell_table(cfg, SPEC)
        r = results(slug)
        for v in VARS:
            x = r[r.variable == v]
            m = pd.DataFrame({
                "ccm_vpd": x[(x.analise == "ccm") & (x.forcante == "vpd")
                             & (x.sentido == "atmosfera→vegetação")]
                .set_index("cell_id").eval("rho - rho_nulo"),
                "ganho_conjunto": x[(x.analise == "previsao") & (x.preditores == "conjunto")
                                    & (x.modelo == "smap")].set_index("cell_id").ganho,
                **{f"z_{d}": x[(x.etapa == 1) & (x.descriptor == d)].set_index("cell_id").z
                   for d in ("pe_entropy", "pe_complexity", "prediction", "cao_de2")}})
            frame = cells.join(m, how="inner")
            for measure in m.columns:
                a = G.associate(frame, "perda_antecedente", measure)
                rows.append({"bacia": slug, "variavel": v, "medida": measure, **a})
    return pd.DataFrame(rows)


@app.function(hide_code=True)
@mo.cache
def fire(slug):
    folder = FR.folder(load_region(slug), local=True)
    meta = json.loads((folder / "fogo_execucao.json").read_text())
    return (pd.read_parquet(folder / "delta.parquet"), pd.read_parquet(folder / "resposta.parquet"),
            meta, pd.read_parquet(folder / "episodios.parquet"))


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🌳 A floresta como sistema dinâmico

    Os capítulos anteriores olharam para a atmosfera: o clima diário do ERA5 em cada célula,
    comparado com a perturbação da floresta embaixo dele. Este capítulo inverte o ponto de
    vista e trata a própria floresta como a variável dinâmica. Em vez de perguntar se o ar
    sobre as áreas desmatadas evolui de outro jeito, perguntamos como evolui a vegetação
    vista por satélite, se essa evolução depende da atmosfera e o que acontece com ela
    depois de um fogo. A mudança de foco tem uma razão prática, que o capítulo da
    perturbação e dinâmica deixou clara: o ERA5 usa um mapa de vegetação fixo e não
    acompanha o desmatamento no tempo, enquanto o satélite vê a floresta como ela é em cada
    semana.

    A análise segue três etapas, fixadas antes de olharmos os dados (D-031). A primeira
    trata a vegetação sozinha, com os mesmos métodos e o mesmo cuidado com as substitutas do
    clima diário. A segunda junta a vegetação e a atmosfera e pergunta se uma ajuda a prever
    a outra e se a relação entre elas muda com o estado do sistema. A terceira acompanha
    pixels de floresta que queimaram, ao lado de pixels parecidos que não queimaram, e mede
    quanto a vegetação cai, quanto se recupera e se passa a responder de outro modo à chuva
    e à secura do ar.
    """)
    return


@app.cell(hide_code=True)
def _():
    _n = {s: results(s).groupby("variable").cell_id.nunique() for s in SLUGS}
    _main = {s: results(s)[results(s).grupo == "principal"].groupby("variable")
             .cell_id.nunique().reindex(list(VARS), fill_value=0) for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🛰️ Os dados

        Usamos dois produtos do sensor MODIS em composições de 8 dias, de 2001 a 2024, o que
        dá 1.104 pontos por série. O índice de área foliar (LAI, do MOD15A2H) mede quantos
        metros quadrados de folha há sobre cada metro quadrado de chão. O índice de umidade
        da vegetação (NDMI, calculado com as refletâncias do MOD09A1 no infravermelho próximo
        e no de ondas curtas) responde à água guardada nas folhas. Em cada célula da
        subamostra do capítulo dos descritores, sorteada ao acaso entre as células elegíveis,
        tiramos a média dos pixels de floresta persistente que nunca queimaram, depois de
        descartar os pixels com nuvem, sombra, aerossol ou ângulo de visada acima de 35°. A
        série de cada célula é a anomalia padronizada em relação à mesma composição dos outros
        anos, para que o ciclo do ano não se passe por dinâmica. A floresta persistente é a
        classe de floresta perene do mapa de cobertura do próprio MODIS (MCD12Q1) em 2001 e
        em 2024, porque o acesso aos mapas do MapBiomas falhou durante o cálculo.

        As nuvens são o grande limite desses dados. Na estação chuvosa, só cerca de um
        sexto das observações de refletância passa nos filtros, contra três quartos na seca.
        Por isso, antes de calcular qualquer resultado, a regra de cobertura foi revista só
        pela disponibilidade dos dados: uma composição vale quando pelo menos 5% dos pixels
        da célula são válidos, entram as células com até 35% de composições vazias, e a
        leitura principal fica nas que têm até 20%. O LAI, que tem o seu próprio algoritmo de
        recuperação, sustenta a leitura principal; o NDMI fica quase todo no grupo de
        sensibilidade.
        """),
        mo.callout(mo.md(nb.pt("Células analisadas (leitura principal entre parênteses): " +
                               "; ".join(f"{SHORT[s]}, LAI {_n[s]['lai']} ({_main[s]['lai']}) "
                                         f"e NDMI {_n[s]['ndmi']} ({_main[s]['ndmi']})"
                                         for s in SLUGS) + ".")), kind="info"),
    ])
    return


@app.cell(hide_code=True)
def _():
    _g = gate_table()
    _tab = pd.DataFrame({
        "Descritor": [DESCRIPTORS.get(d, d) for d in _g.index],
        "Família": ["primária" if d in PRIMARY else "exploratória" for d in _g.index],
        "Poder (logística, Hénon, Lorenz)": [
            f"{a:.2f}, {b:.2f}, {c:.2f}" for a, b, c in
            zip(_g["poder logistic"], _g["poder henon"], _g["poder lorenz"], strict=True)],
        "Rejeição (branco, AR(1))": [f"{a:.2f}, {b:.2f}" for a, b in
                                     zip(_g["rejeição white"], _g["rejeição ar1"], strict=True)],
        "Rejeição (sazonal com tendência)": _g["rejeição seasonal_trend"].round(2).to_numpy(),
    })
    mo.vstack([
        mo.md(r"""
        ## 🧪 O portão das séries de 8 dias

        Uma série de 1.104 pontos a cada 8 dias não é uma série diária de 12.784 pontos, e os
        descritores validados no capítulo dos métodos precisavam ser validados de novo no
        novo tamanho. Repetimos o portão com os mesmos sistemas de resposta conhecida: três
        caóticos (o mapa logístico, o de Hénon e o sistema de Lorenz) e quatro aleatórios
        (ruído branco, um processo autorregressivo, uma senoide com ruído e um processo
        sazonal com tendência), cada um com 1.104 pontos, 20 repetições e 20% de ruído de
        observação. O poder é a fração das séries caóticas em que o descritor rejeita as
        substitutas; o tamanho, a fração das aleatórias em que ele rejeita sem motivo. A
        Tabela 1 mostra o resultado.
        """),
        book.table(_tab, "portao",
                   "Tabela 1. Portão dos descritores nas séries de 8 dias (1.104 pontos, 20% de "
                   "ruído de observação, 20 repetições): fração de rejeição das substitutas "
                   "IAAFT nos controles caóticos (poder) e nos aleatórios (tamanho). Família "
                   "primária: os descritores que entram na leitura, fixados no pré-registro "
                   "das séries de vegetação.", selection=None),
        mo.md(r"""
        Os padrões ordinais, o erro de previsão e o teste de Cao reconhecem os três sistemas
        caóticos e quase nunca rejeitam nos aleatórios, e o S-map reconhece o Hénon e o
        Lorenz. A assimetria temporal não vê o Lorenz, que é simétrico no tempo, e a dimensão
        de correlação perde o poder com só 1.104 pontos. O resultado que mais importa está na
        última coluna. O expoente de Lyapunov pelo método de Kantz rejeita em todas as séries
        do processo sazonal com tendência, e o de Rosenstein em 70% delas: numa série curta e
        sazonal, eles confundem a memória do ano com dinâmica. Por isso a leitura da
        vegetação fica nos descritores primários, e os outros aparecem só como contexto.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_stage1():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), sharey=True, layout="constrained")
    shown = [d for d in PRIMARY if d != "smap"]
    for ax, v in zip(axes, VARS, strict=True):
        for k, slug in enumerate(SLUGS):
            r = results(slug)
            e = r[(r.etapa == 1) & (r.variable == v) & r.descriptor.isin(shown)]
            e = e[e.grupo == "principal"] if v == "lai" else e
            data = [e[e.descriptor == d].z.dropna().to_numpy() for d in shown]
            pos = np.arange(len(shown)) + (k - 0.5) * 0.36
            parts = ax.boxplot(data, positions=pos, widths=0.3, patch_artist=True,
                               showfliers=False, medianprops={"color": COLORS["ink"]})
            for box in parts["boxes"]:
                box.set(facecolor=BASIN_COLORS[slug], alpha=0.55, edgecolor=COLORS["ink"])
            ax.plot([], [], "s", color=BASIN_COLORS[slug], alpha=0.55, label=SHORT[slug])
        ax.axhspan(-1.96, 1.96, color=COLORS["muted"], alpha=0.12)
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.set_xticks(range(len(shown)), [DESCRIPTORS[d] for d in shown], rotation=20,
                      ha="right", fontsize=9)
        group = "células principais" if v == "lai" else "todas as células (sensibilidade)"
        ax.set_title(f"{VARS[v]} · {group}", fontsize=11)
    axes[0].set_ylabel("z (dados − substitutas, em desvios)")
    axes[0].legend(loc="upper left")
    return fig


@app.cell(hide_code=True)
def _():
    _r = stage1_rates()
    _tab = _r.assign(Bacia=_r.bacia.map(SHORT), Variável=_r.variavel.map(VARS),
                     Descritor=_r.descritor.map(DESCRIPTORS))
    _tab = _tab.pivot_table(index=["Variável", "Descritor"], columns="Bacia",
                            values="rejeicao").reset_index()
    _tab = _tab.rename(columns={s: f"Rejeição, {s}" for s in SHORT.values()})
    _cells = _r.groupby(["bacia", "variavel"]).celulas.max()
    _ndmi = {s: results(s)[(results(s).etapa == 1) & (results(s).variable == "ndmi")]
             for s in SLUGS}
    _asym = {s: _ndmi[s][_ndmi[s].descriptor == "asymmetry"] for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 1️⃣ A vegetação sozinha

        Em cada célula, cada série foi comparada com 99 substitutas IAAFT, que preservam o
        espectro e a distribuição de valores da série e apagam qualquer outra estrutura. As
        substitutas recebem as mesmas lacunas da série observada, preenchidas do mesmo jeito,
        para que o tratamento das composições vazias não crie diferenças por si mesmo. A
        Figura 1 mostra, para cada descritor primário, a distribuição entre as células do z,
        a distância entre o valor dos dados e o das substitutas, medida em desvios das
        substitutas.
        """),
        book.figure(plot_stage1(), "descritores",
                    "Figura 1. z dos descritores primários (valor observado menos a média das 99 "
                    "substitutas IAAFT, em desvios-padrão das substitutas) nas células da "
                    "subamostra, por bacia: LAI nas células com até 20% de composições vazias e "
                    "NDMI em todas as analisadas (até 35%). Caixas: quartis; faixa cinza: "
                    "±1,96."),
        mo.md(nb.pt(r"""
        Quase todas as caixas ficam dentro da faixa de ±1,96, onde os dados não se
        distinguem das substitutas. A exceção chama atenção pelo sentido. A entropia de
        permutação dos dados é maior que a das substitutas, e a complexidade estatística
        menor, nas duas variáveis e nas duas bacias: a anomalia da vegetação de uma
        composição para a outra é mais irregular do que um processo linear com o mesmo
        espectro. Estrutura determinística faria o contrário, deixaria a série mais
        organizada que as substitutas. O que torna a série mais irregular é o ruído de
        recuperação do satélite, as pequenas falhas de nuvem e de geometria de visada que
        sobrevivem aos filtros e mudam de uma composição para a outra. No LAI esse sinal
        aparece também nas células com menos de 12% de lacunas, e por isso não é um efeito
        do preenchimento. A Tabela 2 traz a fração de células em que cada descritor rejeita
        as substitutas no sentido pré-registrado, que no caso dos padrões ordinais é o da
        série mais organizada.
        """)),
        book.table(_tab, "rejeicao",
                   "Tabela 2. Fração das células em que cada descritor primário rejeita as 99 "
                   "substitutas IAAFT (α = 0,05, no sentido pré-registrado): LAI nas células com "
                   "até 20% de lacunas e NDMI em todas as analisadas. Células: " +
                   "; ".join(f"{SHORT[s]}, LAI {_cells[(s, 'lai')]} e NDMI "
                             f"{_cells[(s, 'ndmi')]}" for s in SLUGS) + ".",
                   selection=None, float_format="%.2f"),
        mo.md(nb.pt(f"""
        No LAI, a rejeição fica entre 0% e 9%, no nível do acaso, para todos os descritores
        primários. No NDMI, a assimetria temporal rejeita em
        {(_asym['tapajos'].pvalue <= ALPHA).sum()} das {len(_asym['tapajos'])} células do
        Tapajós e em {(_asym['xingu'].pvalue <= ALPHA).sum()} das {len(_asym['xingu'])} do
        Xingu, e o teste de Cao e o S-map ficam perto de 13% no Tapajós, pouco acima dos 5%
        esperados ao acaso. Essas rejeições não acompanham a fração de lacunas das células,
        mas uma assimetria no NDMI tem uma explicação simples, que não é dinâmica: as falhas
        de nuvem e de aerossol que escapam dos filtros só podem baixar o índice, nunca
        subir, e isso cria quedas rápidas e voltas lentas. Com padrões ordinais mais
        irregulares que as substitutas e sem ganho de previsão, a leitura é a mesma do LAI.
        """)),
        mo.callout(mo.md(
            "A vegetação vista pelo MODIS, em composições de 8 dias, não mostra estrutura não "
            "linear além do que um processo linear com o mesmo espectro explica. A anomalia "
            "de uma composição para a outra é dominada por ruído de recuperação. As nulas "
            "realistas, que no clima diário separaram a memória sazonal da não linearidade, "
            "ficam dispensadas aqui: os dados não rejeitam nem as substitutas lineares."),
            kind="success"),
        mo.callout(mo.md(
            "O expoente de Lyapunov pelos métodos de Kantz e de Rosenstein rejeita as "
            "substitutas em 79% a 97% das células de NDMI. Não é sinal de caos: são os "
            "descritores que o portão desqualificou por rejeitarem o processo sazonal com "
            "tendência, e as suas rejeições acompanham a fração de lacunas das células."),
            kind="danger"),
    ])
    return


@app.function(hide_code=True)
def plot_forecast():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.4), sharey=True, layout="constrained")
    for ax, v in zip(axes, VARS, strict=True):
        for k, slug in enumerate(SLUGS):
            r = results(slug)
            f = r[(r.analise == "previsao") & (r.variable == v) & (r.modelo == "smap")]
            f = f[f.grupo == "principal"] if v == "lai" else f
            data = [f[f.preditores == p].rmse.dropna().to_numpy() for p in PREDICTORS]
            pos = np.arange(len(PREDICTORS)) + (k - 0.5) * 0.36
            parts = ax.boxplot(data, positions=pos, widths=0.3, patch_artist=True,
                               showfliers=False, medianprops={"color": COLORS["ink"]})
            for box in parts["boxes"]:
                box.set(facecolor=BASIN_COLORS[slug], alpha=0.55, edgecolor=COLORS["ink"])
            ax.plot([], [], "s", color=BASIN_COLORS[slug], alpha=0.55, label=SHORT[slug])
        ax.axhline(1, color=COLORS["muted"], lw=1)
        ax.set_xticks(range(len(PREDICTORS)), list(PREDICTORS.values()))
        ax.set_title(VARS[v], fontsize=11)
    axes[0].set_ylabel("RMSE da previsão (desvios da anomalia)")
    axes[0].legend(loc="upper left")
    return fig


@app.function(hide_code=True)
def ccm_table():
    rows = []
    for slug in SLUGS:
        r = results(slug)
        c = r[r.analise == "ccm"]
        for (v, f, s), g in c.groupby(["variable", "forcante", "sentido"]):
            g = g[g.grupo == "principal"] if v == "lai" else g
            rows.append({"Bacia": SHORT[slug], "Variável": VARS[v], "Forçante": FORCINGS[f],
                         "Sentido": s, "Células": len(g),
                         "Significativas": (g.pvalue <= ALPHA).mean(),
                         "ρ mediano": g.rho.median(), "ρ nulo mediano": g.rho_nulo.median()})
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _c = ccm_table()
    _vpd = _c[(_c["Forçante"] == "VPD") & (_c.Sentido == "atmosfera→vegetação")]
    _state = pd.concat([results(s)[results(s).analise == "estado"].assign(bacia=s)
                        for s in SLUGS])
    _state = _state[(_state.grupo == "principal") & (_state.variable == "lai")]
    _state_max = _state.groupby(["bacia", "forcante"]).rho_estado.median().abs().max()
    mo.vstack([
        mo.md(r"""
        ## 2️⃣ A vegetação e a atmosfera

        Se a floresta e a atmosfera formam um sistema acoplado, o estado de uma deveria
        ajudar a prever a outra. Para cada célula, alinhamos à data de observação de cada
        composição o VPD médio dos 8 dias anteriores, do ERA5, e a chuva acumulada em 32 e em
        96 dias, do CHIRPS, a chuva baseada em observações do capítulo da chuva. Depois
        previmos a anomalia da vegetação na composição seguinte com três conjuntos de
        preditores: só o passado da própria vegetação, só o da atmosfera e os dois juntos,
        tanto com um modelo linear quanto com o S-map, que permite que a resposta dependa do
        estado. O modelo aprende nos primeiros 60% da série e é avaliado no resto. A Figura 2
        mostra o erro da previsão com o S-map. Um erro de 1 é o de quem chutasse a média: a
        previsão não sabe nada.
        """),
        book.figure(plot_forecast(), "previsao",
                    "Figura 2. Erro quadrático médio (RMSE, em desvios da anomalia) da previsão "
                    "da anomalia da vegetação uma composição à frente pelo S-map, fora da "
                    "amostra (últimos 40% da série), com três conjuntos de preditores, nas "
                    "células da subamostra (LAI nas principais, NDMI em todas). Linha: erro de "
                    "quem prevê a média."),
        mo.md(r"""
        O LAI é praticamente imprevisível uma composição à frente: o erro mediano fica entre
        0,96 e 1,0 com o seu próprio passado, perto do erro de quem chuta a média. O NDMI tem
        um pouco de memória, com erro mediano entre 0,86 e 0,88. O resultado mais importante
        é a comparação entre as caixas. Juntar a atmosfera ao passado da vegetação não reduz
        o erro, pelo contrário, aumenta-o um pouco fora da amostra, e a atmosfera sozinha
        prevê pior que a média. O mesmo vale para o modelo linear e para o de vizinhos. Se
        a atmosfera dos 8 dias anteriores empurrasse a vegetação de modo reconhecível, essa
        comparação mostraria o ganho.

        A previsão responde se a atmosfera ajuda a prever a vegetação; o mapeamento cruzado
        convergente (CCM) pergunta outra coisa, se a vegetação guarda informação sobre a
        atmosfera. A ideia vem da reconstrução do espaço de fases. Se o VPD influencia a
        vegetação, a série da vegetação carrega um rastro do VPD, e a vizinhança de cada
        ponto no espaço reconstruído da vegetação aponta para valores parecidos do VPD. A
        habilidade ρ é a correlação entre o VPD estimado desse jeito e o observado. Como o
        ciclo do ano sozinho já produz uma correlação, cada ρ é comparado com o de 99
        substitutas que embaralham anos inteiros da atmosfera e mantêm o seu ciclo sazonal.
        A Tabela 3 traz os resultados nos dois sentidos.
        """),
        book.table(_c, "ccm",
                   "Tabela 3. Mapeamento cruzado convergente (CCM) entre a anomalia da vegetação "
                   "e a atmosfera, nos dois sentidos: fração das células em que a habilidade ρ "
                   "supera a de 99 substitutas sazonais (α = 0,05), ρ mediano e ρ mediano das "
                   "substitutas. O sentido atmosfera→vegetação é estimado pelo espaço de fases "
                   "da vegetação.", selection=None, float_format="%.2f"),
        mo.md(nb.pt(f"""
        O VPD passa as substitutas sazonais em boa parte das células, de
        {_vpd.Significativas.min():.0%} a {_vpd.Significativas.max():.0%}, mas com uma
        habilidade minúscula, um ρ mediano de {_vpd['ρ mediano'].min():.2f} a
        {_vpd['ρ mediano'].max():.2f} contra cerca de 0,02 nas substitutas. A chuva aparece
        em menos células. E o sentido inverso também passa, em 18% a 47% das células para o
        VPD, o que é difícil de ler como influência da vegetação sobre o ar
        em 8 dias. O conjunto aponta para um sinal comum fraco, e não para um acoplamento
        dinâmico. Uma fonte provável desse sinal é a própria medida: nuvem fina e fumaça da
        estação seca que escapam dos filtros baixam o LAI e o NDMI recuperados nos mesmos
        dias em que o VPD está alto, e a correlação passa pelas substitutas porque não é
        sazonal, é de cada ano.

        Por fim, perguntamos se a resposta da vegetação à atmosfera muda com o estado do
        sistema, isto é, se a floresta reage mais à secura quando já está seca. Para isso,
        medimos, no S-map com a vegetação e a atmosfera juntas, a correlação entre a
        sensibilidade local à atmosfera e o estado da vegetação. Nas células principais de
        LAI, a mediana fica em {_state.rho_estado.median():+.3f}, e em nenhuma combinação de
        bacia e forçante ela passa de {_state_max:.2f} em módulo: a resposta não depende do
        estado. O NDMI, com uma só célula principal, não sustenta essa leitura.
        """)),
        mo.callout(mo.md(
            "A atmosfera dos 8 dias anteriores não melhora a previsão da vegetação, e o sinal "
            "comum que o CCM detecta é fraco e aparece nos dois sentidos. Com composições de "
            "8 dias, o acoplamento entre a floresta e o ar não se mostra como dinâmica."),
            kind="success"),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def scales(slug):
    """Resultados da D-032 (horizontes, estado compacto e direção inversa)."""
    return pd.read_parquet(VS.output_dir(load_region(slug)) / "resultados.parquet")


@app.function(hide_code=True)
def scale_medians(slug, vegetation="lai", direction=None, variant="estrita", model="linear",
                  analysis="ganho", max_missing=VS.PRIMARY_MAX_MISSING):
    """Mediana entre as células do ganho, nos dados (substituta 0) e em cada permutação."""
    t = scales(slug)
    t = t[(t.analise == analysis) & (t.vegetacao == vegetation) & (t.variante == variant)
          & (t.modelo == model) & (t.sentido == (direction or VS.DIRECTIONS[0]))
          & (t.lacunas <= max_missing)]
    if analysis == "nao_linear":
        t = t[t.preditores == "conjunto"]
    return t.groupby(["horizonte", "substituta"]).ganho.median().unstack()


@app.function(hide_code=True)
def plot_scales():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.4), sharey=True, layout="constrained")
    days = {h: 8 * h for h in VS.HORIZONS}
    styles = {"linear": ("o-", COLORS["ink"], "linear"), "smap": ("s--", COLORS["vpd"], "S-map"),
              "vizinhos": ("^:", COLORS["precip"], "vizinhos")}
    for ax, slug in zip(axes, SLUGS, strict=True):
        null = scale_medians(slug).drop(columns=0)
        x = [days[h] for h in null.index]
        ax.fill_between(x, null.quantile(0.05, axis=1), null.quantile(0.95, axis=1),
                        color=COLORS["muted"], alpha=0.3, lw=0,
                        label="anos permutados (5% a 95%, linear)")
        for model, (fmt, color, name) in styles.items():
            m = scale_medians(slug, model=model)[0]
            ax.plot([days[h] for h in m.index], m, fmt, color=color, label=name)
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.set_xscale("log", base=2)
        ax.set_xticks(list(days.values()), [f"{d} dias" for d in days.values()])
        ax.set_title(SHORT[slug], fontsize=11)
    axes[0].set_ylabel("ganho G(h) mediano entre as células")
    axes[0].legend(loc="lower left", fontsize=9)
    return fig


@app.function(hide_code=True)
def scales_table():
    from statsmodels.stats.multitest import multipletests

    rows = []
    for slug in SLUGS:
        s = VS.basin_summary(scales(slug)[lambda t: t.lacunas <= VS.PRIMARY_MAX_MISSING])
        s = s[(s.vegetacao == "lai") & (s.sentido == VS.DIRECTIONS[0])
              & (s.variante == "estrita") & (s.modelo == "linear")]
        for r in s.itertuples():
            rows.append({"Bacia": SHORT[slug], "Horizonte (dias)": 8 * r.horizonte,
                         "Células": r.celulas, "G mediano": r.ganho_mediano,
                         "G das permutações": r.nulo_mediano, "p da bacia": r.p_bacia,
                         "Células acima das permutações": r.frac_celulas})
    out = pd.DataFrame(rows)
    out.insert(6, "p (Holm)", multipletests(out["p da bacia"], method="holm")[1])
    return out


@app.function(hide_code=True)
def scales_other():
    readings = {
        "LAI, média das composições seguintes": dict(variant="media"),
        "LAI, S-map contra linear (G_NL)": dict(analysis="nao_linear", model="smap"),
        "VPD previsto com o LAI (direção inversa)": dict(direction=VS.DIRECTIONS[1]),
        "NDMI, consistência (até 35% de lacunas)": dict(vegetation="ndmi",
                                                         max_missing=VS.MAX_MISSING),
    }
    rows = []
    for slug in SLUGS:
        for name, kw in readings.items():
            m = scale_medians(slug, **kw)
            row = {"Bacia": SHORT[slug], "Leitura": name}
            for h in VS.HORIZONS:
                row[f"{8 * h} dias"] = m[0].get(h, np.nan)
            rows.append(row)
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _t = scales_table()
    _o = scales_other()
    _lai = pd.concat([scales(s)[(scales(s).analise == "ganho") & (scales(s).substituta == 0)
                                & (scales(s).vegetacao == "lai") & (scales(s).modelo == "linear")
                                & (scales(s).variante == "estrita")
                                & (scales(s).sentido == VS.DIRECTIONS[0])
                                & (scales(s).lacunas <= VS.PRIMARY_MAX_MISSING)]
                      for s in SLUGS])
    _skill = (_lai.rmse_vegetacao / _lai.rmse_clima).groupby(_lai.horizonte).median()
    _nl = _o[_o.Leitura.str.contains("G_NL")].iloc[:, 2:].to_numpy()
    _inv = _o[_o.Leitura.str.contains("inversa")].iloc[:, 2:].to_numpy()
    mo.vstack([
        mo.md(nb.pt("""
        ## 🔭 Outras escalas de tempo e um estado mais enxuto

        A comparação anterior tem duas limitações que poderiam esconder um acoplamento real.
        Ela olha só uma composição à frente, oito dias, e a resposta de uma floresta à seca
        passa pela água guardada no solo e nas árvores, por ajustes fisiológicos e pela troca
        de folhas, coisas que podem levar semanas para aparecer. E ela usa o mesmo número de
        atrasos para todas as variáveis, o que monta um espaço de estados grande, em que a
        previsão por vizinhança se perde, ainda mais com duas chuvas acumuladas que contam
        quase a mesma história. Por isso refizemos a pergunta de outro jeito (D-032).

        Para cada horizonte h de 1, 2, 4 e 8 composições, isto é, de 8 a 64 dias, comparamos
        a previsão de V(t+h) feita só com V(t) e V(t−1) com a feita por um estado compacto de
        quatro coordenadas, V(t), V(t−1), uma das duas chuvas, H(t−k), e o VPD, D(t−k), cada
        uma com o seu atraso k de 0, 2, 4 ou 8 composições. O ganho G(h) = 1 −
        RMSE do conjunto / RMSE da vegetação é positivo quando a atmosfera ajuda. Tudo o que
        se escolhe, a chuva, os atrasos e o parâmetro θ do S-map, é escolhido só com os dados
        de treino. A validação imita o uso real de um modelo: aprende com os anos anteriores e
        prevê blocos de quatro anos que ele nunca viu (2013–16, 2017–20 e 2021–24), e até a
        climatologia que define a anomalia é calculada só com os anos de treino. Os buracos
        da série são preenchidos apenas com o passado, porque a interpolação usada antes
        empresta um pedaço do valor seguinte, justamente o que se quer prever, e o erro é
        medido só nas composições realmente observadas.

        Falta o termo de comparação. Um modelo com mais preditores pode errar um pouco menos
        ou um pouco mais por acaso, e a vegetação e a atmosfera dividem o mesmo ciclo do ano.
        Então repetimos todo o procedimento 39 vezes com os anos da atmosfera embaralhados
        inteiros: cada ano mantém a sua estação seca, a sua memória e a relação entre chuva e
        VPD, mas deixa de estar alinhado com a vegetação daquele ano. A mesma permutação vale
        para todas as células da bacia, de modo que a mediana das permutações carrega a mesma
        dependência espacial dos dados. Antes de olhar os dados reais, o procedimento foi
        testado em séries sintéticas montadas sobre a atmosfera e as lacunas reais: um ganho
        de 2% no erro, plantado de propósito, aparece com folga, e sem acoplamento nada
        aparece. A Figura 3 mostra o resultado no LAI.
        """)),
        book.figure(plot_scales(), "escalas",
                    "Figura 3. Ganho G(h) da previsão da anomalia do LAI quando a chuva e o VPD "
                    "entram no estado compacto, mediana entre as células principais (até 20% de "
                    "lacunas), para os três modelos, em função do horizonte. Validação "
                    "cronológica em três blocos de quatro anos. Faixa: 5% a 95% das medianas "
                    "das 39 permutações de anos inteiros da atmosfera, modelo linear."),
        mo.md(nb.pt("""
        As três curvas ficam abaixo de zero em todos os horizontes e nas duas bacias. A do
        modelo linear fica na faixa das permutações ou um pouco abaixo dela, sobretudo no
        Xingu: incluir a atmosfera do próprio ano piora a previsão tanto quanto, ou até um
        pouco mais que, incluir a atmosfera de outro ano. Uma explicação possível é que, no
        treino, a vegetação e a atmosfera compartilham tendências lentas que não se mantêm
        nos anos seguintes, e a permutação desfaz esse alinhamento. A Tabela 4 traz os oito
        testes principais, com a correção de Holm.
        """)),
        book.table(_t, "escalas",
                   "Tabela 4. Ganho da previsão do LAI com a atmosfera no estado compacto, por "
                   "bacia e horizonte (modelo linear, células com até 20% de lacunas): mediana "
                   "entre as células, mediana das 39 permutações de anos, p da bacia contra "
                   "as permutações, p corrigido por Holm nos oito testes e fração das células "
                   "acima do 95º percentil das suas próprias permutações.", float_format="%.3f"),
        mo.md(nb.pt(f"""
        Nenhum teste chega perto da significância, e a fração de células que superam as suas
        próprias permutações fica entre {_t['Células acima das permutações'].min():.0%} e
        {_t['Células acima das permutações'].max():.0%}, o que o acaso sozinho produz. Os
        atrasos escolhidos também não contam história nenhuma: espalham-se pelas 32
        combinações de chuva e VPD sem que nenhuma defasagem se destaque. O motivo aparece
        quando se olha a vegetação sozinha. O erro do LAI previsto pelo próprio passado é de
        {_skill.min():.2f} a {_skill.max():.2f} vezes o erro de quem chuta a climatologia,
        do horizonte de 8 ao de 64 dias: a anomalia do LAI não guarda memória mensurável nem
        de si mesma. A Tabela 5 reúne as outras leituras.
        """)),
        book.table(_o, "escalas_outras",
                   "Tabela 5. Outras leituras da D-032, mediana entre as células por horizonte: "
                   "ganho da atmosfera quando o alvo é a média do LAI nas h composições "
                   "seguintes; ganho do S-map sobre o linear com os mesmos preditores; ganho "
                   "do LAI na previsão do VPD; e ganho da atmosfera no NDMI.",
                   float_format="%.3f"),
        mo.md(nb.pt(f"""
        Prever a média das próximas composições, em vez de uma só, tira parte do ruído do
        satélite, mas o ganho da atmosfera continua negativo. O S-map, que deixa a resposta
        depender do estado do sistema, perde para o modelo linear com os mesmos preditores,
        de {np.nanmin(_nl):+.3f} a {np.nanmax(_nl):+.3f}: ele escolhe no treino uma
        vizinhança mais local e erra mais nos anos seguintes, o contrário do que faria uma
        resposta que mudasse com o estado. No sentido inverso, o passado do LAI não ajuda a
        prever o VPD (de {np.nanmin(_inv):+.3f} a {np.nanmax(_inv):+.3f}), o que também se
        esperava, porque o ERA5 usa uma vegetação climatológica e não o LAI de cada ano. O
        NDMI tem alguns ganhos acima das permutações, nos dois sentidos, mas sempre abaixo de
        meio por cento do erro, e um sinal que aparece igual nos dois sentidos combina melhor
        com a contaminação atmosférica da reflectância do que com uma resposta da floresta.
        """)),
        mo.callout(mo.md(
            "Nem horizontes de até 64 dias, nem atrasos de até dois meses, nem um estado "
            "compacto, nem modelos não lineares, nem a direção inversa revelam informação da "
            "atmosfera sobre a anomalia de 8 dias da vegetação, num desenho capaz de ver um "
            "ganho de 2%. A conclusão negativa deixa de depender da escolha de um passo e de "
            "um espaço de estados grande. O limite é o instrumento: com nuvem, a anomalia do "
            "LAI do MODIS fica abaixo do ruído de recuperação, e é no fogo que a resposta da "
            "floresta aparece."), kind="success"),
    ])
    return


@app.cell(hide_code=True)
def _():
    _a = association()
    _tab = pd.DataFrame({
        "Bacia": _a.bacia.map(SHORT), "Variável": _a.variavel.map(VARS),
        "Medida": _a.medida.map({"ccm_vpd": "CCM do VPD (ρ − ρ nulo)",
                                 "ganho_conjunto": "ganho da previsão conjunta",
                                 "z_pe_entropy": "z da entropia de permutação",
                                 "z_pe_complexity": "z da complexidade estatística",
                                 "z_prediction": "z do erro de previsão",
                                 "z_cao_de2": "z do Cao (E2)"}),
        "Células": _a.celulas,
        "ρ parcial [IC 95%]": [f"{p:+.2f} [{lo:+.2f}; {hi:+.2f}]" for p, lo, hi in
                               zip(_a.rho_parcial, _a.ic_inf, _a.ic_sup, strict=True)]})
    mo.vstack([
        mo.md(r"""
        ## 🌲 A vegetação e a perda antecedente

        A pergunta central do trabalho foi feita ao clima: as células com mais floresta
        convertida até 2000 têm outra dinâmica? Fazemos a mesma pergunta à vegetação que
        restou nelas. A Tabela 6 traz a correlação de postos parcial entre a perda
        antecedente e cada medida das duas primeiras etapas, com os mesmos controles de
        latitude, água e altitude do capítulo da perturbação e dinâmica, e o intervalo por
        bootstrap de blocos de 1°.
        """),
        book.table(_tab, "perda",
                   "Tabela 6. Correlação de postos parcial entre a perda antecedente de floresta "
                   "(até 2000) e as medidas da vegetação por célula (etapas 1 e 2), controlando "
                   "latitude, fração de água e altitude, com IC 95% por bootstrap de blocos de "
                   "1°.", selection=None),
        mo.md(nb.pt(f"""
        Dos {len(_a)} intervalos, {int((~_a.exclui_zero).sum())} incluem zero. As
        correlações maiores em módulo, perto de −0,4 no CCM do VPD e no Cao do NDMI do Xingu,
        vêm das séries com só 29 células, e as do LAI, perto de −0,2 no CCM do VPD nas duas
        bacias, também não excluem zero com as 56 a 62 células da subamostra. A floresta que
        restou nas células mais convertidas não tem, nessas medidas, uma dinâmica diferente
        da floresta das células preservadas. Isso não
        contradiz os capítulos anteriores: a média dos pixels de floresta persistente de uma
        célula mede a floresta que ficou, e não a paisagem convertida ao redor dela.
        """)),
    ])
    return


@app.function(hide_code=True)
def plot_delta():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), layout="constrained")
    months = 8 / 30.44
    for ax, v in zip(axes, VARS, strict=True):
        for slug in SLUGS:
            delta = fire(slug)[0]
            d = delta[delta.variavel == v].sort_values("k")
            x = d.k * months
            ax.fill_between(x, d.ic_inf, d.ic_sup, color=BASIN_COLORS[slug], alpha=0.2, lw=0)
            ax.plot(x, d.delta, color=BASIN_COLORS[slug], lw=1.4, label=SHORT[slug])
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.axvline(0, color=COLORS["ink"], lw=1, ls="--")
        ax.set(title=VARS[v], xlabel="meses desde o mês da queima",
               ylabel=f"Δ do {VARS[v]} (queimado − controles)")
    axes[0].legend(loc="lower right")
    return fig


@app.cell(hide_code=True)
def _():
    _meta = {s: fire(s)[2] for s in SLUGS}
    _eps = {s: fire(s)[3] for s in SLUGS}
    _windows = [(1, 6, "até 1,5 mês"), (7, 23, "2 a 6 meses"), (24, 46, "6 a 12 meses"),
                (47, 92, "1 a 2 anos"), (93, 138, "2 a 3 anos")]
    _rows = []
    for _s in SLUGS:
        _d = fire(_s)[0]
        for _v in VARS:
            _x = _d[_d.variavel == _v].set_index("k")
            for _a, _b, _name in _windows:
                _w = _x.loc[_a:_b]
                _rows.append({"Bacia": SHORT[_s], "Variável": VARS[_v], "Janela": _name,
                              "Δ médio": round(_w.delta.mean(), 3),
                              "IC exclui zero": f"{((_w.ic_inf > 0) | (_w.ic_sup < 0)).mean():.0%}"})
    _tab = pd.DataFrame(_rows)
    _dry = {s: _eps[s].mes.dt.month.isin([7, 8, 9, 10]).mean() for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 3️⃣ A floresta depois do fogo

        A terceira etapa segue pixels de floresta que queimaram. Um episódio é o primeiro mês
        de queima, no produto de área queimada MCD64A1, de um pixel de floresta que não
        queimava havia pelo menos 2 anos, que continua floresta nos 2 anos seguintes e que não
        queima de novo em 3 anos. Entre os episódios de 2003 a 2021, sorteamos 15 por ano de
        queima, 285 por bacia. Para cada um, sorteamos 10 pixels de floresta que
        nunca queimaram na mesma célula do ERA5 e escolhemos os 3 mais parecidos com o pixel
        queimado nos 2 anos antes da queima, na média e na amplitude do ano do LAI e do NDMI.
        Assim, o queimado e os seus controles partem do mesmo lugar e passam pelo mesmo
        tempo.

        A comparação é do tipo antes e depois com controles. Para cada composição k depois da
        queima, Δ(k) é a mudança do pixel queimado em relação ao seu ano anterior à queima
        menos a mesma mudança da média dos controles. Uma seca que derrube a vegetação de
        todos ao mesmo tempo some da diferença; o que resta é o efeito do fogo. O intervalo
        reamostra as células do ERA5, e não os episódios, porque episódios da mesma célula
        dividem o mesmo tempo. A Figura 4 mostra Δ(k) nos três anos depois da queima.
        """),
        mo.callout(mo.md(nb.pt(
            "Episódios pareados: " + "; ".join(
                f"{SHORT[s]}, {_meta[s]['pareados']} de {_meta[s]['episodios']}, em "
                f"{_eps[s].cell_id.nunique()} células do ERA5, {100 * _dry[s]:.0f}% deles "
                "entre julho e outubro" for s in SLUGS) + ".")), kind="info"),
        book.figure(plot_delta(), "delta",
                    "Figura 4. Δ(k): mudança do LAI e do NDMI do pixel queimado em relação ao "
                    "ano anterior à queima, menos a mesma mudança da média dos seus 3 "
                    "controles pareados, por composição de 8 dias depois do mês da queima, com "
                    "IC 95% por bootstrap de células do ERA5 (999 reamostragens)."),
        mo.md(r"""
        Antes da queima, as curvas oscilam em torno de zero, como deveriam se o pareamento
        funcionou. A exceção são os dois ou três meses que antecedem o mês da queima, em que
        o NDMI do pixel que vai queimar já cai um pouco abaixo do dos controles: a floresta
        que queima é a que está secando mais no fim da estação seca, ou parte das queimas
        começou antes do mês que o produto registra. A queda é imediata e forte nas duas
        bacias. Nas primeiras composições, o LAI do pixel
        queimado cai mais de uma unidade em relação aos controles, perto de um quinto do LAI
        de uma floresta amazônica, e o NDMI cai cerca de 0,13. Metade da queda do LAI se
        recupera nos primeiros seis meses, mais rápido no Tapajós que no Xingu, e no fim do
        primeiro ano resta perto de um quarto dela. Depois disso a curva não volta a zero. Do
        segundo ao terceiro ano, o LAI dos pixels queimados fica entre 0,15 e 0,20 abaixo do
        dos controles, e o NDMI cerca de 0,02 abaixo, com intervalos que excluem zero em boa
        parte das composições. O vaivém da curva dentro de cada ano acompanha a estação.
        Como quase todas as queimas são de agosto a outubro, cada ano depois da queima passa
        pela estação seca nos mesmos valores de k, e é nesses trechos que o déficit
        reaparece: depois do primeiro ano, o LAI dos queimados fica perto de 0,5 abaixo do dos
        controles em setembro e outubro e perto de zero de março a junho. A floresta
        danificada perde mais folhas que a intacta justamente quando falta água, embora uma
        parte pequena desse vaivém já existisse antes do fogo, como a seção seguinte mostra.
        A Tabela 7 resume as janelas.
        """),
        book.table(_tab, "janelas",
                   "Tabela 7. Δ médio do LAI e do NDMI por janela depois da queima e fração das "
                   "composições da janela em que o IC 95% exclui zero.", selection=None),
        mo.callout(mo.md(
            "O fogo derruba a vegetação da floresta de uma vez, e ela se recupera em boa "
            "parte no primeiro ano, mas não toda. Três anos depois, os pixels queimados "
            "ainda têm menos folha e menos água nas folhas que pixels parecidos que não "
            "queimaram."), kind="success"),
        mo.callout(mo.md(
            "Um critério automático de recuperação, fixado no plano, procura a primeira "
            "composição a partir da qual o intervalo inclui zero por seis composições "
            "seguidas, e ele aponta 1,2 a 1,5 ano depois da queima. A curva, porém, volta a "
            "ficar negativa depois desse ponto, e por isso ele não deve ser lido como o fim "
            "do efeito do fogo."), kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    _terms = {"qd": "nível depois da queima", "v_qd": "persistência (V)",
              "h_qd": "resposta à chuva de 96 dias (H)", "d_qd": "resposta ao VPD (D)"}
    _rows = []
    for _s in SLUGS:
        _r = fire(_s)[1]
        _r = _r[_r.termo.isin(list(_terms))]
        for _x in _r.itertuples():
            _rows.append({"Bacia": SHORT[_s], "Variável": VARS[_x.variavel],
                          "Termo": _terms[_x.termo],
                          "Coeficiente [IC 95%]": f"{_x.coeficiente:+.3f} [{_x.ic_inf:+.3f}; "
                                                  f"{_x.ic_sup:+.3f}]",
                          "p": round(_x.p, 3)})
    _tab = pd.DataFrame(_rows)
    mo.vstack([
        mo.md(r"""
        A queda e a recuperação dizem quanto a floresta muda; resta saber se ela passa a
        funcionar de outro modo. Para isso, ajustamos um painel com todos os pixels,
        queimados e controles, em que a anomalia da vegetação na composição seguinte depende
        da anomalia atual (V), da anomalia da chuva acumulada em 96 dias (H) e da do VPD (D):

        $$V(t+1) = a\,V(t) + b\,H(t) + c\,D(t) + \text{interações com queimado} \times
        \text{depois},$$

        com efeitos fixos de pixel, que retiram as diferenças permanentes entre os pixels, e
        erros agrupados por célula do ERA5. Cada termo de interação mede quanto o
        coeficiente muda no pixel queimado depois da queima, em relação ao que muda nos
        controles. A Tabela 8 traz as interações.
        """),
        book.table(_tab, "painel",
                   "Tabela 8. Mudança, depois da queima e nos pixels queimados em relação aos "
                   "controles, do nível, da persistência e da resposta da anomalia da vegetação "
                   "à chuva acumulada (96 dias, CHIRPS) e ao VPD (ERA5), no painel com efeitos "
                   "fixos de pixel e erros agrupados por célula do ERA5 (k de −46 a 138, sem a "
                   "composição da queima).", selection=None),
        mo.md(r"""
        Depois do fogo, a floresta queimada fica abaixo dos controles, como a Figura 4 já
        mostrava, e três coisas mudam no mesmo sentido nas duas bacias. A vegetação fica mais
        persistente: o peso da anomalia atual sobre a seguinte aumenta entre 0,13 e 0,23. Ela passa
        a responder mais à chuva acumulada, um efeito claro no Tapajós e marginal no Xingu.
        E passa a responder mais ao VPD, no sentido de perder folha e água quando o ar está
        mais seco, um efeito claro no Xingu e marginal no Tapajós. É o comportamento que se
        espera de uma floresta com o dossel aberto pelo fogo e árvores feridas, que depende
        mais da água que chega e sofre mais com o ar seco [5], e é coerente com o déficit
        que reaparece nas estações secas da Figura 4.
        """),
        mo.callout(mo.md(
            "Parte do aumento da persistência pode ser a própria recuperação lenta: enquanto "
            "a vegetação volta aos poucos, a anomalia de uma composição se parece com a da "
            "seguinte, e o painel não separa as duas coisas. As mudanças na resposta à chuva "
            "e ao VPD medem a reação a forçantes de fora, mas também podem herdar o ciclo "
            "sazonal da recuperação; a próxima seção as refaz com esse ciclo retirado."),
            kind="warn"),
        mo.callout(mo.md(
            "Os episódios e os controles foram sorteados só nas células da subamostra das "
            "etapas 1 e 2, e a vegetação de cada ponto foi lida nos mesmos dados de área "
            "(emenda de 02/11 da D-031, decidida antes dos resultados, porque os pedidos de "
            "pontos da bacia inteira ficaram mais de 40 horas parados na fila do serviço da "
            "NASA). A subamostra foi sorteada ao acaso, e as três etapas passam a usar as "
            "mesmas células; o custo é um intervalo mais largo, com perto de 40 células do "
            "ERA5 como grupos."), kind="warn"),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def memory(slug):
    """Resultados da D-033 (memória e sensibilidade depois do fogo)."""
    d = FR.memory_dir(load_region(slug))
    return {n: pd.read_parquet(d / f"{n}.parquet")
            for n in ("curvas", "metricas", "sensibilidade", "painel_corrigido")}


@app.function(hide_code=True)
def plot_memory():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), sharey=True, layout="constrained")
    months = 8 / 30.44
    lines = {("principal", "sazonal"): ("fogo, base sazonal", COLORS["ink"], "-"),
             ("principal", "media_pre"): ("fogo, base média", COLORS["vpd"], "--"),
             ("placebo_unidade", "sazonal"): ("placebo de unidade", COLORS["muted"], "-"),
             ("placebo_data", "sazonal"): ("placebo de data", COLORS["precip"], "-")}
    for ax, slug in zip(axes, SLUGS, strict=True):
        c = memory(slug)["curvas"]
        c = c[c.variavel == "lai"]
        for (variant, base), (name, color, ls) in lines.items():
            d = c[(c.variante == variant) & (c.linha_base == base)].sort_values("k")
            if variant != "principal" or base == "sazonal":
                ax.fill_between(d.k * months, d.ic_inf, d.ic_sup, color=color, alpha=0.18,
                                lw=0)
            ax.plot(d.k * months, d.delta, color=color, ls=ls, lw=1.3, label=name)
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.axvline(0, color=COLORS["ink"], lw=1, ls=":")
        ax.set(title=SHORT[slug], xlabel="meses desde a composição da queima")
    axes[0].set_ylabel("Δ do LAI (queimado − controles)")
    axes[0].legend(loc="lower right", fontsize=9)
    return fig


@app.function(hide_code=True)
@mo.cache
def memory_table():
    from amazon_chaos.nonlinear import coupling as C

    cases = [("principal", "media_pre", "fogo, base média"),
             ("principal", "sazonal", "fogo, base sazonal"),
             ("placebo_unidade", "sazonal", "placebo de unidade")]
    rows = []
    for slug in SLUGS:
        m = memory(slug)["metricas"]
        for v in VARS:
            for variant, base, name in cases:
                g = m[(m.variavel == v) & (m.variante == variant) & (m.linha_base == base)]
                row = {"Bacia": SHORT[slug], "Variável": VARS[v], "Caso": name}
                for col, label in (("A", "A (3 anos)"), ("A1", "A₁ (1º ano)"),
                                   ("R", "R (anos 2 e 3)")):
                    r = C.cluster_mean(g[col], g.cell_id, n=999)
                    row[label] = (f"{r['media']:+.2f} [{r['ic_inf']:+.2f}; "
                                  f"{r['ic_sup']:+.2f}]" if v == "lai" else
                                  f"{r['media']:+.3f} [{r['ic_inf']:+.3f}; "
                                  f"{r['ic_sup']:+.3f}]")
                rows.append(row)
    return pd.DataFrame(rows)


@app.function(hide_code=True)
def sensitivity_table():
    from statsmodels.stats.multitest import multipletests

    names = {"principal": "principal", "depois_1o_ano": "depois do 1º ano",
             "margem": "margem (sem k = ±1)", "regra_antiga": "regra antiga do tempo",
             "sorteados": "3 candidatos sorteados", "chuva_32d": "chuva de 32 dias",
             "placebo_data": "placebo de data", "placebo_unidade": "placebo de unidade"}
    rows = []
    for slug in SLUGS:
        s = memory(slug)["sensibilidade"]
        s = s[(s.variavel == "lai") & s.variante.isin(list(names))]
        for variant, label in names.items():
            g = s[s.variante == variant].set_index("termo")
            row = {"Bacia": SHORT[slug], "Variante": label}
            for t, col in (("P_d", "θ_D (VPD)"), ("P_h", "θ_H (chuva)"),
                           ("P_dif", "φ_P (persistência)")):
                row[col] = (f"{g.loc[t, 'coeficiente']:+.3f} [{g.loc[t, 'ic_inf']:+.3f}; "
                            f"{g.loc[t, 'ic_sup']:+.3f}]")
                row[f"p {col.split()[0]}"] = g.loc[t, "p"]
            rows.append(row)
    out = pd.DataFrame(rows)
    main = out.Variante == "principal"
    p = np.r_[out.loc[main, "p θ_D"], out.loc[main, "p θ_H"]]
    holm = multipletests(p, method="holm")[1]
    out["Holm θ_D"] = np.nan
    out["Holm θ_H"] = np.nan
    out.loc[main, "Holm θ_D"] = holm[:main.sum()]
    out.loc[main, "Holm θ_H"] = holm[main.sum():]
    return out.drop(columns=["p φ_P"])


@app.function(hide_code=True)
@mo.cache
def drought_table():
    from amazon_chaos.nonlinear import coupling as C

    m = pd.concat([memory(s)["metricas"] for s in SLUGS])
    m = m[(m.variante == "principal") & (m.linha_base == "media_pre") & (m.variavel == "lai")]
    rows = []
    for out, label in (("A", "A (3 anos)"), ("A1", "A₁ (1º ano)"), ("R", "R (anos 2 e 3)")):
        for exp, name in (("seca_vpd", "VPD dos 60 dias antes"),
                          ("seca_chuva", "chuva dos 96 dias antes")):
            r = C.drought_model(m, out, exp)
            rows.append({"Desfecho": label, "Seca antecedente": name,
                         "β por desvio [IC 95%]": f"{r['beta']:+.3f} [{r['ic_inf']:+.3f}; "
                                                  f"{r['ic_sup']:+.3f}]",
                         "p": r["p"], "Episódios": r["episodios"]})
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _s = sensitivity_table()
    _main = _s[_s.Variante == "principal"].set_index("Bacia")
    mo.vstack([
        mo.md(r"""
        ## 🔥 A memória do fogo

        A Figura 4 e o painel deixam duas perguntas em aberto. O fogo só baixa a vegetação
        por um tempo, ou deixa uma diferença que fica? E a floresta queimada passa a
        responder de outro modo às mesmas condições do tempo, ou só parte de um nível mais
        baixo? Para respondê-las (D-033), primeiro corrigimos dois detalhes da análise
        anterior. O produto de área queimada informa o dia da queima em cada pixel, e não só
        o mês; contar o tempo a partir da composição que contém esse dia, em vez da primeira
        composição do mês, desloca a queima de até três composições em mais da metade dos
        episódios. E, no painel, a transição da última composição antes do fogo para a
        seguinte carregava a própria queima como resposta. Refeito com as duas correções, o
        painel da Tabela 8 praticamente não muda.

        Depois trocamos o ponto de vista. Em vez de seguir cada pixel, seguimos a diferença
        entre o pixel queimado e a média dos seus controles, δ(t), que tira de uma vez tudo o
        que a vizinhança tem em comum, inclusive o tempo, já que todos estão na mesma célula
        do ERA5. Δ(k) é a mudança dessa diferença em relação ao período antes do fogo. Aqui
        apareceu um cuidado novo. Se movermos a data da queima dois anos para trás, para
        quando nada aconteceu, e refizermos a conta, a curva ainda cai nas primeiras
        composições, porque a data fictícia cai na mesma estação seca: os pixels que vão
        queimar já perdiam um pouco mais de folha que os controles na seca, antes do fogo.
        Por isso a linha de base passa a ser sazonal, a diferença do mesmo mês nos dois anos
        anteriores, e não a média do ano anterior. Um segundo placebo troca o pixel
        queimado por um dos seus controles e mede o que a mesma conta dá quando não houve
        fogo nenhum. A Figura 5 mostra as curvas do LAI.
        """),
        book.figure(plot_memory(), "memoria",
                    "Figura 5. Δ(k) do LAI depois do fogo com a linha de base sazonal (mesmo "
                    "mês nos dois anos anteriores) e com a média do ano anterior, e os dois "
                    "placebos com a base sazonal: a queima posta dois anos antes (de −46 a +46 "
                    "composições em torno da data fictícia) e um controle no lugar do pixel "
                    "queimado. Faixas: IC 95% por bootstrap de células do ERA5 (999)."),
        mo.md(r"""
        O placebo de unidade fica em zero ao longo de toda a janela. O de data também,
        com duas exceções pequenas diante do efeito do fogo: uma queda de cerca de 0,2 nos
        primeiros meses no Xingu, resto do ciclo sazonal que a base não tirou por inteiro, e
        um pico isolado e ruidoso no Tapajós. A curva do fogo fica longe dos dois durante
        os três anos. A
        diferença entre as duas linhas de base é pequena depois do primeiro ano: o déficit
        das estações secas seguintes é, em boa parte, do fogo, e não do ciclo anterior. Para
        resumir cada episódio em números, usamos o déficit acumulado A, a área entre a
        curva e o zero quando ela está abaixo dele nos três anos, em LAI vezes ano; o mesmo
        no primeiro ano, A₁; e a diferença residual R, a média de Δ nos anos 2 e 3. Como o
        ruído sozinho já produz algum déficit, o placebo de unidade dá o piso de cada medida.
        A Tabela 9 traz as médias.
        """),
        book.table(memory_table(), "memoria",
                   "Tabela 9. Déficit acumulado em três anos (A, em LAI·ano ou NDMI·ano), no "
                   "primeiro ano (A₁) e diferença residual nos anos 2 e 3 (R), média dos "
                   "episódios com IC 95% por bootstrap de células do ERA5, para o fogo com as "
                   "duas linhas de base e para o placebo de unidade.", selection=None),
        mo.md(r"""
        O fogo custa à floresta, em três anos, o equivalente a perder entre 1,2 e 1,5 unidade
        de LAI durante um ano inteiro, contra 0,5 a 0,7 do placebo; o excedente, perto de
        0,7 a 0,8, é o que o fogo tira. Mais da metade vem do primeiro ano. Nos anos 2 e 3, o
        LAI dos queimados ainda fica 0,12 a 0,17 abaixo do dos controles, enquanto o placebo
        fica em zero. A diferença de estado persiste, com qualquer das duas linhas de base,
        com controles sorteados em vez de pareados e com a regra antiga do tempo. Ela é um
        pouco maior nas queimas de 2003 a 2009 que nas mais recentes, mas os intervalos se
        sobrepõem.

        Resta a segunda pergunta. Com a diferença δ como resposta, ajustamos

        $$\delta(t+1) = \alpha_e + \varphi\,\delta(t) + \beta H(t) + \gamma D(t) +
        P\,[\varphi_P\,\delta(t) + \theta_H H(t) + \theta_D D(t)] + f(k) + s(\text{mês}) +
        P\,s_P(\text{mês}),$$

        em que P vale 1 depois do fogo, H e D são as anomalias da chuva de 96 dias e do VPD,
        f(k) acompanha a recuperação média e s(mês) e P·s_P(mês) retiram o ciclo do ano
        antes e depois do fogo. Assim, θ_D não mede o déficit típico da estação seca, mas
        quanto uma seca do ar maior que a normal aprofunda a diferença entre o queimado e
        os seus controles. A Tabela 10 traz os coeficientes e as variantes.
        """),
        book.table(_s, "sensibilidade",
                   "Tabela 10. Mudança, depois do fogo, da resposta da diferença de LAI "
                   "queimado − controles ao VPD (θ_D) e à chuva de 96 dias (θ_H) e da sua "
                   "persistência (φ_P), com IC 95% e p por bootstrap de células do ERA5 (499), "
                   "efeitos fixos de episódio e o ciclo do ano antes e depois do fogo; Holm "
                   "nos quatro testes principais.", selection=None, float_format="%.3f"),
        mo.md(nb.pt(f"""
        O coeficiente do VPD é negativo e quase igual nas duas bacias,
        {_main.loc['Xingu', 'θ_D (VPD)'].split()[0]} no Xingu e
        {_main.loc['Tapajós', 'θ_D (VPD)'].split()[0]} no Tapajós: depois do fogo, uma
        anomalia de VPD de um desvio aprofunda a diferença do queimado em cerca de 0,03 de LAI
        por composição. Ele resiste à margem em torno da queima, à regra antiga do tempo, aos
        controles sorteados e à chuva de 32 dias, e some nos dois placebos. Mas é pequeno,
        enfraquece depois do primeiro ano e, com a correção de Holm para os quatro testes
        principais, fica em {_main.loc['Xingu', 'Holm θ_D']:.2f} e
        {_main.loc['Tapajós', 'Holm θ_D']:.2f}, acima de 0,05. A resposta à chuva não muda
        (θ_H perto de zero no Tapajós e incerto no Xingu): a sensibilidade maior à chuva que o
        painel da Tabela 8 mostrava vem do ciclo sazonal da recuperação, que o modelo da
        diferença retira. A persistência aumenta, mas os placebos também se afastam de zero
        nesse termo, e ele não é lido como efeito do fogo.

        Por último, perguntamos se a seca antes do fogo prevê o tamanho do dano. A Tabela 11
        relaciona o déficit e a diferença residual com a anomalia do VPD nos 60 dias antes
        da queima e, como alternativa, com a da chuva nos 96 dias antes, com as bacias
        juntas, controlando o ano, a estação e o LAI antes da queima.
        """)),
        book.table(drought_table(), "seca_antes",
                   "Tabela 11. Déficit (A, A₁) e diferença residual (R) do LAI contra a seca "
                   "antes da queima, por desvio-padrão da seca, com bacia, ano da queima, "
                   "estação seca e LAI do ano anterior como controles; IC 95% e p por "
                   "bootstrap de células do ERA5 (999). O VPD é o teste principal.",
                   selection=None, float_format="%.3f"),
        mo.md(r"""
        O ar mais seco nos dois meses antes da queima não se associa a um dano maior. A
        chuva dos três meses anteriores talvez sim, no déficit total, mas não no resíduo nem
        no primeiro ano, e essa é uma das alternativas, não o teste fixado. O tamanho do dano
        parece depender mais do que o satélite não mede, como a intensidade da queima e o
        combustível acumulado, que do tempo que a antecedeu.
        """),
        mo.callout(mo.md(
            "O fogo deixa memória no estado da floresta: três anos depois, os pixels "
            "queimados ainda têm menos folha que os controles, além do que os placebos "
            "explicam. Há um indício de que eles também passam a sofrer mais com o ar seco, "
            "com o mesmo tamanho nas duas bacias e sem sinal nos placebos, mas pequeno demais "
            "para passar a correção de testes múltiplos. Nada disso é caos, histerese ou "
            "troca de atrator: é a perturbação deixando marca na trajetória do sistema."),
            kind="success"),
        mo.callout(mo.md(
            "A amostra só tem queimas em floresta que continua floresta por dois anos e não "
            "queima de novo em três; as conclusões valem para esse tipo de fogo, de sub-"
            "bosque, e não para as queimas que abrem caminho ao desmatamento. A versão "
            "estrita da qualidade do LAI (só o algoritmo principal sem saturação) deixou "
            "menos de 50 episódios por bacia, porque a saturação é a regra na floresta "
            "densa, e não serve como sensibilidade; no NDMI, ela confirma os resultados."),
            kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O que este capítulo acrescenta

    Visto pelo satélite em composições de 8 dias, o estado da floresta amazônica não se
    comporta como um sistema dinâmico de baixa dimensão. A sua anomalia é dominada por
    ruído de recuperação, não guarda estrutura além da linear e quase não se deixa prever,
    nem pelo próprio passado nem pela atmosfera. O sinal comum entre a vegetação e o VPD
    existe, mas é fraco, aparece nos dois sentidos e é compatível com a contaminação da
    própria medida. Isso é coerente com o que os capítulos do clima encontraram: um sistema
    estocástico, em que a não linearidade, se existe, fica abaixo do que esses dados
    conseguem mostrar.

    O fogo é outra história. Ele deixa uma marca grande, imediata e duradoura: três anos
    depois, a floresta queimada ainda tem menos folha que a vizinha que não queimou, além
    do que os placebos explicam, e há indício de que ela passe a sofrer mais com o ar seco.
    A perturbação que o
    clima diário do ERA5 não conseguia registrar no tempo aparece com clareza na
    vegetação, porque é na vegetação que ela acontece. Para a pergunta socioespacial do
    trabalho, esse é o elo: as queimas que o capítulo do fogo mostrou concentradas na
    estação seca e nas frentes de ocupação deixam florestas que, três anos depois, ainda
    não voltaram ao estado anterior e talvez sofram mais com o ar seco, justamente a
    condição que as secas recentes tornaram mais frequente.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Myneni, R.; Knyazikhin, Y.; Park, T. MOD15A2H MODIS/Terra Leaf Area Index/FPAR
    8-Day L4 Global 500m SIN Grid V061. NASA EOSDIS Land Processes DAAC, 2021.

    [2] Vermote, E. MOD09A1 MODIS/Terra Surface Reflectance 8-Day L3 Global 500m SIN Grid
    V061. NASA EOSDIS Land Processes DAAC, 2021.

    [3] Giglio, L. et al. The Collection 6 MODIS burned area mapping algorithm and product.
    *Remote Sensing of Environment*, v. 217, p. 72–85, 2018.

    [4] Sugihara, G. et al. Detecting causality in complex ecosystems. *Science*, v. 338,
    p. 496–500, 2012.

    [5] Brando, P. M. et al. Abrupt increases in Amazonian tree mortality due to
    drought–fire interactions. *PNAS*, v. 111, p. 6347–6352, 2014.
    """)
    return


if __name__ == "__main__":
    app.run()
