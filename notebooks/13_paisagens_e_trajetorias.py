# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo>=0.23.16", "geopandas>=1.0", "pandas>=2.2", "pyarrow>=17",
#                 "matplotlib>=3.9", "numpy>=2.0", "shapely>=2.0",
#                 "xarray>=2024.7", "netcdf4>=1.7"]
# [tool.marimo.opengraph]
# title = "13 · Paisagens e trajetórias"
# description = "Fogo, recuperação e história territorial com os dados locais"
# ///
import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="13 · Paisagens e trajetórias")

with app.setup(hide_code=True):
    import sys
    from pathlib import Path

    import marimo as mo

    # Usa esta cópia do projeto. Não instala código remoto nem busca dados.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from amazon_chaos import context_followup as F
    from amazon_chaos import territorial_comparison as T


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 13 · Paisagens e trajetórias

    **A floresta se recupera do mesmo modo em contextos territoriais diferentes?**
    Este caderno é um começo de conversa. Reúne mapas, episódios de queima e duas
    trajetórias históricas nas bacias do Xingu e do Tapajós. Tudo vem do pacote local
    `data-all`: nenhuma base é baixada e nenhum resultado dos capítulos anteriores é alterado.

    Vamos olhar onde o fogo aparece, como a vegetação muda depois dele e como esses
    registros atravessam a criação de uma unidade de conservação. As comparações são
    exploratórias: ajudam a formular perguntas e não identificam, sozinhas, causas.

    **Presença humana não é sinônimo de degradação.** Terras Indígenas são habitadas.
    Aqui a agropecuária mede uma forma de uso da terra; TI e UC são categorias territoriais
    distintas, com histórias que as medidas numéricas não resumem.
    """)
    return


@app.cell(hide_code=True)
def _():
    basin_choice = mo.ui.dropdown(options={"Xingu": "xingu", "Tapajós": "tapajos"},
                                  value="Xingu", label="Bacia")
    variable_choice = mo.ui.radio(options={"Área foliar (LAI)": "lai", "Índice de umidade (NDMI)": "ndmi"},
                                  value="Área foliar (LAI)", label="Indicador", inline=True)
    baseline_choice = mo.ui.radio(options={"Média anterior": "delta", "Mesma época do ano": "delta_sazonal"},
                                  value="Média anterior", label="Referência da recuperação", inline=True)
    cohort_choice = mo.ui.radio(options={"Disponíveis em cada janela": "available",
                                         "Mesmos episódios em todas as janelas": "fixed"},
                                value="Disponíveis em cada janela", label="Amostra", inline=True)
    mo.vstack([basin_choice, variable_choice, baseline_choice, cohort_choice])
    return baseline_choice, basin_choice, cohort_choice, variable_choice


@app.function(hide_code=True)
@mo.cache
def landscape(slug):
    geo = T.layers(slug)
    table = T.cells(slug, geo)
    episodes = T.episode_context(slug, table, geo)
    return geo, table, episodes


@app.function(hide_code=True)
@mo.cache
def recovery_data(slug):
    return T.recovery(slug, landscape(slug)[2])


@app.function(hide_code=True)
@mo.cache
def all_recovery_data():
    import pandas as pd

    return pd.concat([recovery_data(s).assign(bacia=s) for s in T.EXPERIMENTS],
                     ignore_index=True)


@app.function(hide_code=True)
@mo.cache
def historical_data(slug):
    return T.historical(slug, landscape(slug)[0])


@app.function(hide_code=True)
@mo.cache
def paired_context_data(slug, baseline):
    pairs = F.paired_episodes(recovery_data(slug), baseline)
    summary, contrasts = F.context_comparison(pairs)
    return pairs, summary, contrasts


@app.function(hide_code=True)
@mo.cache
def historical_climate_data(slug):
    return F.history_climate(slug, landscape(slug)[0], historical_data(slug)[1])


@app.cell(hide_code=True)
def _(basin_choice):
    slug = basin_choice.value
    geo, cell_table, episodes = landscape(slug)
    mo.vstack([
        mo.md("### De onde vêm estes resultados?"),
        mo.ui.table([T.provenance(slug)], selection=None),
        mo.md("""A pasta `memoria` contém checagens posteriores ao capítulo 12.
        Usamos as **datas de queima** e a atmosfera nela armazenadas, mas não atribuímos
        significado às métricas A/R sem o código que as produziu. Recalculamos abaixo as
        diferenças de vegetação a partir das séries e dos controles pareados recebidos.
        O commit da tabela identifica os dados recebidos, não este novo cálculo."""),
    ])
    return cell_table, episodes, geo, slug


@app.cell(hide_code=True)
def _(cell_table, geo, slug):
    mo.vstack([
        mo.md("""## Onde o fogo e a conversão da terra se encontram?

        Os três mapas usam o mesmo recorte. Área queimada e frequência de queima vêm do
        MapBiomas Fogo; agropecuária é a cobertura de 2024. As janelas são diferentes e
        estão nos títulos: sobreposição espacial não estabelece ordem temporal.
        As linhas verdes são TIs; as roxas são UCs federais, com seus limites atuais.
        **Uma célula tem cerca de 25–30 km de lado:** o mapa não resolve suas bordas internas.
        """),
        T.maps(slug, cell_table, geo),
        mo.ui.table(T.territorial_summary(cell_table), selection=None),
        mo.md("""A tabela resume **células classificadas por predominância territorial**,
        com médias ponderadas pela área terrestre. TI/UC exigem ≥50% da célula;
        “Demais áreas” têm <10% de TI ou UC federal, e as restantes são mistas.
        Ela não calcula a queima exata dentro dos polígonos nem a fração de floresta que
        queimou. Também não cobre UCs estaduais ou municipais. Cerrado natural e áreas
        convertidas não devem ser confundidos: pouca floresta não implica desmatamento.

        **Para conversar:** em quais lugares os limites jurídicos coincidem com mudanças
        da paisagem? Quais práticas e histórias poderiam explicar esses encontros?"""),
    ])
    return


@app.cell(hide_code=True)
def _(episodes, slug):
    _rows = []
    for _dimension, _column in [("Agropecuária anterior", "contexto_agro"),
                                ("Território do ponto", "territorio_ponto"),
                                ("Secura anterior", "contexto_seca")]:
        for _name, _g in episodes.groupby(_column, observed=True):
            _rows.append({"Comparação": _dimension, "Grupo": str(_name),
                          "Episódios sorteados": len(_g), "Células": _g.cell_id.nunique()})
    mo.vstack([
        mo.md(f"""## Quem entra na comparação de recuperação? · {T.NAMES[slug]}

        Os episódios são pixels florestais queimados, com controles locais pareados antes
        do fogo. A amostra exclui novas queimas nos três anos seguintes e perda da
        classificação florestal nos dois anos seguintes. Portanto, não representa todas
        as trajetórias de degradação.

        A tabela mostra a amostra sorteada. Os números efetivamente disponíveis variam
        por indicador e janela e aparecem nos resultados abaixo. O grupo territorial é
        definido pela localização do **ponto**, não pela predominância da célula."""),
        mo.ui.table(T.selection_table(slug), selection=None),
        mo.md("""As exclusões de requeima e de perda florestal se sobrepõem: não somar.
        Células ausentes nas primeiras etapas não significam zero; esses IDs não foram
        guardados nos resumos recebidos. O filtro atua em episódios-pixel, não descarta
        automaticamente uma célula inteira. As contagens finais são calculadas dos
        episódios efetivamente pareados, não de todas as células do sorteio."""),
        mo.ui.table(_rows, selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(baseline_choice, cohort_choice, slug):
    curves = recovery_data(slug)
    summaries = {key: T.recovery_summary(curves, key, baseline_choice.value, cohort_choice.value)
                 for key in ["contexto_agro", "territorio_ponto", "contexto_seca"]}
    return curves, summaries


@app.cell(hide_code=True)
def _(baseline_choice, cohort_choice, curves, variable_choice):
    _all = curves.assign(grupo="Todos os episódios")
    _availability = T.recovery_summary(_all, "grupo", baseline_choice.value, cohort_choice.value)
    mo.vstack([
        mo.md("""## A cobertura sustenta uma trajetória contínua?

        Na opção **disponíveis**, cada janela pode conter episódios diferentes. A linha
        liga médias desses conjuntos; não estima a velocidade de recuperação de uma
        população fixa. Na opção **mesmos episódios**, exigimos dados suficientes em
        todas as sete janelas, incluindo os dois períodos anteriores. Não afrouxamos
        o critério se a interseção ficar pequena. Essa sensibilidade seleciona os casos
        mais bem observados e pode não representar a amostra inteira.
        """),
        T.availability_plot(_availability, variable_choice.value, "Cobertura da amostra selecionada"),
        mo.ui.table(T.readable_summary(_availability, variable_choice.value), selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(summaries, variable_choice):
    mo.vstack([
        mo.md("""## A recuperação muda com o contexto agropecuário?

        Cada ponto do gráfico é a diferença entre a vegetação queimada e seus controles,
        descontando a diferença anterior à queima. Zero significa ausência de diferença
        adicional no índice; não significa que a floresta inteira se recuperou.

        Exigimos dois controles válidos por composição e pelo menos 24 composições
        pareadas nos dois anos anteriores. A composição que contém a queima é excluída.
        São regras explícitas desta exploração, não uma reprodução exata do capítulo 12.
        LAI aproxima a área de folhas; NDMI é um índice espectral ligado à umidade da
        vegetação. Ambos dependem da qualidade das observações por satélite.

        Usamos a última fotografia de agropecuária anterior ao ano da queima: 2000 ou
        2012. A proporção é da célula inteira, não a distância da queima a uma borda.
        As faixas (até 10%, 10–30%, mais de 30%) foram escolhidas para organizar a
        exploração; não são limiares ecológicos demonstrados.
        """),
        T.recovery_plot(summaries["contexto_agro"], variable_choice.value,
                        "Recuperação e agropecuária anterior na célula"),
        mo.ui.table(T.readable_summary(summaries["contexto_agro"], variable_choice.value), selection=None),
        mo.md("""**Como ler a incerteza:** faixas de 95% reamostrando células inteiras,
        mantendo seus episódios juntos (499 reamostragens). Grupos com menos de cinco
        células ficam apenas na tabela, sem curva ou intervalo. As janelas são médias
        por episódio, com pelo menos metade das composições válidas.
        **Trechos sem curva indicam dados ou células insuficientes, não ausência de efeito.**
        As tabelas junto de cada curva mostram sua amostra efetiva em cada janela.

        Uma queda inicial maior pode produzir um déficit posterior maior mesmo com
        recuperação semelhante. Compare ambas as partes da trajetória. Os dois anos
        anteriores também ajudam a perceber diferenças que já existiam entre os grupos.
        As faixas não são um teste de diferença entre grupos; não há controle simultâneo
        de clima, ano e vegetação inicial nesta primeira versão."""),
    ])
    return


@app.cell(hide_code=True)
def _(summaries, variable_choice):
    mo.vstack([
        mo.md("""## E conforme o território e a secura anterior?

        A classificação territorial usa limites atuais e não reconstrói a situação
        jurídica em cada ano. A segunda comparação separa episódios com média do VPD
        padronizado ≥+1 ou <+1 nos registros de oito dias dos 60 dias anteriores à queima
        (mínimo de quatro registros). Ela é recalculada da coluna `vpd_z` recebida.
        VPD é o déficit de pressão de vapor, ligado à demanda atmosférica por água.
        Mede uma condição atmosférica, não a intensidade da queima.
        """),
        T.recovery_plot(summaries["territorio_ponto"], variable_choice.value,
                        "Recuperação e território do ponto queimado"),
        mo.ui.table(T.readable_summary(summaries["territorio_ponto"], variable_choice.value), selection=None),
        T.recovery_plot(summaries["contexto_seca"], variable_choice.value,
                        "Recuperação e secura nos 60 dias anteriores"),
        mo.ui.table(T.readable_summary(summaries["contexto_seca"], variable_choice.value), selection=None),
        mo.md("""**Pergunta para a reunião:** as diferenças parecem acompanhar a conversão
        do entorno, as condições climáticas ou o dano inicial? TI e UC não são tratamentos
        intercambiáveis. Suas histórias, formas de habitar e condições de gestão precisam
        entrar na interpretação. “Resiliência” aqui só pode se referir à recuperação
        destes indicadores, não de toda a diversidade e das relações ecológicas."""),
    ])
    return


@app.cell(hide_code=True)
def _(baseline_choice, cohort_choice, variable_choice):
    _contrast = T.basin_contrast(all_recovery_data(), baseline_choice.value, cohort_choice.value)
    mo.vstack([
        mo.md("""## As respostas diferem entre Xingu e Tapajós?

        Este é um contraste exploratório novo: **Xingu menos Tapajós**, calculado
        dos episódios do caderno 13. Negativo significa déficit relativo mais intenso
        no Xingu. Reamostramos células dentro de cada bacia, separadamente (999 vezes).
        Só calculamos o intervalo com ao menos cinco células em cada bacia.

        O contraste não ajusta ano, clima ou dano inicial; seus ICs são pontuais, sem
        correção múltipla. Não é um teste causal nem substitui o capítulo 12. Confira
        a opção de amostra fixa e as contagens antes de comparar janelas.
        """),
        T.contrast_plot(_contrast, variable_choice.value),
        mo.ui.table(_contrast[_contrast.Indicador == variable_choice.value.upper()].round(3),
                    selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(baseline_choice, slug, variable_choice):
    _pairs, _summary, _contrasts = paired_context_data(slug, baseline_choice.value)
    _indicator = variable_choice.value.upper()
    mo.vstack([
        mo.md("""## Os mesmos episódios: do déficit inicial a 6–12 meses

        Este aprofundamento mantém os episódios com cobertura suficiente **nas duas
        janelas escolhidas previamente**: até 1,5 mês e 6–12 meses. Não exige observação
        nas outras cinco janelas e independe do seletor de coorte acima.

        A mudança é o déficit posterior menos o inicial. Positivo significa estreitamento
        da diferença em relação aos controles, não recuperação ecológica completa nem
        velocidade instantânea. Compare a queda inicial e o déficit que ainda resta.
        LAI é a leitura principal; NDMI e a referência sazonal são sensibilidades.
        """),
        F.paired_plot(_summary, variable_choice.value, T.NAMES[slug] + " · mesmos episódios"),
        mo.ui.table(_summary[(_summary.Indicador == _indicator)
                              & (_summary.Modelo == "Bruto")].round(3), selection=None),
        mo.md("""### O contraste muda ao considerar as condições anteriores?

        O gráfico contrasta **mais de 30% menos até 10% de agropecuária**, na mudança
        entre as duas janelas. Negativo significa menor estreitamento do déficit no
        primeiro grupo; pode acompanhar uma queda inicial menor.

        Comparamos o bruto, o bruto nos casos completos e um ajuste linear nos mesmos
        casos completos, por ano (tendência linear), VPD nos 60 dias anteriores e média
        da vegetação antes da queima. O ano linear não representa cada seca anual.
        Não condicionamos ao dano inicial, que já é uma resposta após o fogo.
        """),
        F.comparison_plot(_contrasts, variable_choice.value, "Contraste exploratório entre contextos"),
        mo.ui.table(_contrasts[_contrasts.Indicador == _indicator].round(3), selection=None),
        mo.accordion({
            "Covariáveis e disponibilidade": mo.ui.table(F.balance_table(_pairs).round(3),
                                                           selection=None),
            "Sobreposição dos contextos": mo.ui.table(F.overlap_table(_pairs).round(3),
                                                       selection=None)}),
        mo.md("""**Limites:** 999 reamostragens de células inteiras, sorteadas conjuntamente
        para todos os contextos. Uma célula que muda de grupo ao longo dos anos mantém
        todos os seus episódios juntos. ICs pontuais, sem correção múltipla; não são
        testes confirmatórios. Só estimamos com pelo menos cinco células por grupo.
        O ajuste exige também dez células no total, 30 casos para seis parâmetros e
        posto completo; são guardas de disponibilidade, não cálculo de poder.

        Exigimos ao menos 95% de réplicas válidas para mostrar IC. Réplicas sem grupo
        ou sem posto completo ficam registradas. As tabelas de sobreposição mostram
        distribuições marginais, não garantem sobreposição conjunta. Um ajuste linear
        pode extrapolar e não identifica o efeito causal da agropecuária."""),
    ])
    return


@app.cell(hide_code=True)
def _(cell_table, slug):
    monthly_result = T.monthly_fire(slug, cell_table)
    mo.vstack([
        mo.md("""## Quando o período anterior é mais seco, o fogo aparece mais?

        Aqui entram meses com e sem detecção de focos, de junho a outubro de 2003–2024.
        Comparamos a chuva **do mês anterior**, em três faixas relativas à mesma célula e
        mês do calendário. As paisagens são classificadas pela agropecuária em 2000.
        Incluímos apenas meses anteriores com todos os dias de chuva disponíveis.

        É uma análise mensal simples: a resposta é presença de pelo menos um foco, não
        início de incêndio, ignição ou área queimada. Ela não testa previsão fora da amostra.
        """),
        T.fire_plot(monthly_result),
        mo.ui.table(monthly_result.round(2), selection=None),
        mo.md("""Intervalos por reamostragem de anos inteiros (999 vezes). O ranqueamento
        por célula e mês reduz diferenças de sazonalidade na exposição, mas não controla
        simultaneamente geografia, práticas de queima e mudanças de cobertura ao longo dos
        anos. Uma curva mais inclinada sugere uma associação maior com a secura anterior;
        não identifica quem acendeu o fogo nem sua causa."""),
    ])
    return (monthly_result,)


@app.cell(hide_code=True)
def _(slug):
    historical_table, historical_zones = historical_data(slug)
    _event = T.EVENTS[slug]
    mo.vstack([
        mo.md(f"""## O que acontece quando colocamos uma data histórica na trajetória?

        **{_event['name']} · decreto de {_event['date']}.**
        [Fonte: ICMBio]({_event['source']}). A data e o ato também constam da camada local.
        A consulta documental verificou a data; nenhuma nova base de dados foi baixada.

        Acompanhamos os focos do satélite de referência dentro do **polígono atual** da UC
        e em seu entorno de 25 km, ambos recortados à bacia. As contagens vêm dos pontos
        originais, não de atribuição proporcional de células. Cada série é dividida pela
        sua área. O entorno é contexto de comparação; pode conter outras áreas protegidas
        e não é um controle causal. O ano do decreto está sombreado, pois mistura períodos
        anteriores e posteriores ao acontecimento.
        """),
        T.history_plot(slug, historical_table, historical_zones),
        mo.ui.table(T.history_windows(slug, historical_table).round(2), selection=None),
        mo.ui.table(historical_table.round(2), selection=None),
        mo.md("""**Não há um experimento nesta linha vertical.** Temos apenas dois ou três
        anos completos de focos antes desses decretos. Fiscalização, conflitos, secas,
        mudanças econômicas e decisões posteriores também podem alterar as curvas.
        Os limites atuais podem diferir dos originais; a série acompanha uma área fixa,
        não o estatuto histórico exato de cada pedaço de terra.

        A tabela compara janelas simétricas de anos completos, excluindo o ano do decreto:
        dois anos de cada lado no Xingu, três no Tapajós. A diferença é descritiva, sem
        teste de efeito. Veja se UC e entorno mudam juntos, se a trajetória já se alterava
        antes e se os anos escolhidos concentram picos nas duas séries.

        Esta figura abre uma investigação situada: por que aquela unidade foi criada?
        Quem defendia sua criação? Que disputas continuaram depois? Houve implantação,
        gestão e fiscalização no mesmo momento do decreto? A data organiza uma pergunta,
        mas a história não cabe em um marcador de antes/depois."""),
    ])
    return historical_table, historical_zones


@app.cell(hide_code=True)
def _(historical_table, slug):
    _sensitivity = F.history_sensitivity(slug, historical_table)
    mo.vstack([
        mo.md("""## A leitura histórica depende da janela ou de um ano de pico?

        Comparamos um, dois ou três anos completos de cada lado, conforme a disponibilidade,
        sempre excluindo o ano do decreto. Em cada janela com pelo menos dois anos de
        cada lado, retiramos um ano por vez, na UC e no entorno ao mesmo tempo.

        Os pontos mostram a mudança com todos os anos; as hastes mostram o mínimo e
        máximo entre as retiradas e o cálculo original. **Não são intervalos de confiança.**
        A diferença entre a mudança da UC e do entorno também está na tabela: é apenas
        uma diferença descritiva de mudanças, sem identificação causal.
        """),
        F.history_sensitivity_plot(_sensitivity, T.NAMES[slug] + " · sensibilidade histórica"),
        mo.ui.table(_sensitivity.round(3), selection=None),
        mo.md("""## Que meteorologia acompanha esses mesmos recortes?

        Chuva anual do CHIRPS e VPD médio anual do ERA5, ponderados pela área de
        interseção de cada célula com os polígonos atuais. Exigimos 90% dos dias por
        célula e 90% da área por ano. São aproximações na grade, diferentes da contagem
        exata dos pontos de focos nos polígonos; o clima não tem essa precisão territorial.
        As curvas situam anos secos e úmidos. Não ajustam o contraste histórico nem
        distinguem quem acendeu o fogo, práticas de uso, fiscalização ou conflitos.
        """),
        F.history_climate_plot(slug, historical_climate_data(slug)),
        mo.ui.table(historical_climate_data(slug).round(3), selection=None),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ## O que levar para a conversa

    - Uma diferença entre grupos só merece interpretação depois de conferir amostra,
      comportamento anterior, dano inicial e sensibilidade à referência escolhida.
    - Os mapas jurídicos atuais não são uma história pronta dos territórios.
    - Recuperar LAI ou NDMI não equivale a recuperar composição, biomassa ou modos de vida.
    - As duas trajetórias históricas permitem formular perguntas regionais concretas;
      não medem o efeito causal dos decretos.

    **Aprofundamentos executados, sem novos dados:** coorte fixa de duas janelas,
    contrastes entre contextos com sensibilidade por covariáveis anteriores, janelas
    históricas e retirada de um ano por vez, e meteorologia dos mesmos recortes.
    O dano inicial é mostrado separadamente; não foi usado como covariável anterior.
    """)
    return


if __name__ == "__main__":
    app.run()
