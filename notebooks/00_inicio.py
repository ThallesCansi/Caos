# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "00 · Apresentação"
# description = "A pergunta, o percurso e o que encontramos"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="00 · Apresentação")

with app.setup(hide_code=True):
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    from amazon_chaos import nb
    from amazon_chaos.config import list_regions, load_region

    book = nb.notebook("00_inicio")
    CHAPTERS = [
        ("01_laboratorio", "🌀 Laboratório de sistemas dinâmicos"),
        ("02_regioes", "🗺️ As bacias do Xingu e do Tapajós"),
        ("03_clima", "🌡️ O clima de 1990 a 2024"),
        ("04_perturbacao", "🔥 Desmatamento e fogo, célula por célula"),
        ("05_validacao_metodos", "🧪 Os métodos diante de casos conhecidos"),
        ("06_surrogates", "🎭 Séries substitutas"),
        ("07_descritores", "🧩 Descritores não lineares, célula por célula"),
        ("08_gradiente", "🌳 Perturbação da floresta e dinâmica do clima"),
        ("09_chuva", "🌧️ A chuva vista de duas formas"),
        ("10_fogo", "🔥 O tempo antes do fogo"),
        ("11_territorio", "🗺️ O território"),
    ]


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🌎 Caos na floresta e na atmosfera da Amazônia

    A floresta amazônica não é apenas um cenário por onde o clima passa. Ela devolve à
    atmosfera, pela transpiração, boa parte da água que recebe da chuva; o ar que atravessa
    a floresta chega mais úmido do que o que atravessa áreas desmatadas, e chove mais a
    jusante dele [1]. A atmosfera, por sua vez, define quanta água e quanta energia a
    floresta recebe. É um sistema acoplado, em que cada parte responde à outra, e sistemas
    acoplados com respostas não lineares podem ter comportamentos que nenhuma das partes tem
    sozinha: equilíbrios múltiplos, oscilações, mudanças abruptas e caos.

    Esse acoplamento está sob pressão. Desde a década de 1970, perto de um quinto da floresta
    brasileira foi convertido em pasto e lavoura, e o fogo se tornou frequente onde antes era raro.
    Há um debate científico sério sobre a possibilidade de a floresta, em parte do seu
    território, cruzar um limiar a partir do qual não se recompõe [2, 3]. Esse debate se
    apoia em modelos e em sinais indiretos, e uma das perguntas abertas é se a perturbação
    da floresta já deixa marca na dinâmica do clima local, isto é, não só na média da
    temperatura ou da chuva, mas na forma como o tempo evolui de um dia para o outro.

    Este trabalho examina essa pergunta com as ferramentas da teoria do caos e da análise
    não linear de séries temporais [4, 5]. Elas foram criadas para responder se uma série
    que parece aleatória esconde uma regra determinística, quão sensível ela é às condições
    iniciais e quanta estrutura ela tem além do que um processo linear explicaria. A
    pergunta central, fixada antes de olharmos os dados, é a seguinte: as regiões da
    Amazônia com mais desmatamento e fogo têm uma dinâmica climática diária diferente da
    de regiões comparáveis preservadas, depois de controlar a sazonalidade, o ruído, a
    autocorrelação e a geografia?

    Estudamos duas bacias hidrográficas vizinhas, a do Xingu e a do Tapajós, que vão da
    floresta contínua do norte à fronteira agrícola do sul. Elas foram divididas em 1.541
    células de cerca de 28 km de lado, e cada célula tem 35 anos de clima diário da
    reanálise ERA5 [6] e uma medida independente de quanto foi desmatada e queimada,
    construída com os dados do INPE e do MapBiomas.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.mermaid("""
    flowchart LR
      L[🌀 Laboratório<br/>o que é caos e<br/>como medi-lo] --> V[🧪 Validação<br/>os métodos em<br/>casos conhecidos]
      V --> S[🎭 Substitutas<br/>como testar<br/>não linearidade]
      R[🗺️ Regiões] --> C[🌡️ Clima<br/>35 anos diários]
      R --> P[🔥 Perturbação<br/>desmatamento e fogo]
      S --> D[🧩 Descritores<br/>célula por célula]
      C --> D
      D --> G[🌳 Perturbação<br/>e dinâmica]
      P --> G
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O percurso

    Os cadernos são capítulos, e a figura acima mostra como eles se encadeiam. Há dois
    caminhos que se encontram no fim. O primeiro é o do método. O laboratório apresenta os
    conceitos com modelos cujas equações conhecemos: estabilidade, bifurcações, expoente de
    Lyapunov, reconstrução do espaço de fases e recorrência, e mostra por que um número
    positivo não basta para falar em caos. A validação submete cada descritor a séries
    sintéticas com resposta conhecida, caóticas e aleatórias, com o tamanho e o ruído das
    nossas, e só os que passam entram na interpretação. O capítulo das substitutas explica o
    teste de hipótese que acompanha todos os resultados: comparar cada série com versões
    dela mesma das quais a não linearidade foi apagada.

    O segundo caminho é o dos dados. O capítulo das regiões apresenta as bacias e a grade
    de células; o do clima descreve 35 anos de temperatura, umidade, vento e chuva e as
    tendências do período; o da perturbação mede, célula por célula, o desmatamento e o fogo
    com quatro fontes independentes e compara as fontes entre si.

    Os dois caminhos se encontram nos dois últimos capítulos. No dos descritores, os métodos
    validados são aplicados às 1.541 células, e vemos que tipo de estrutura as séries têm e
    como ela se distribui no espaço. No último, comparamos essa estrutura com a perturbação
    da floresta e respondemos à pergunta central, na medida em que os dados permitem.
    """)
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _name, _title in CHAPTERS:
        _figs = list(Path("reports/figures", _name).rglob("*.png"))
        _tabs = list(Path("reports/tables", _name).rglob("*.csv"))
        _rows.append({"Capítulo": _title, "Figuras": len(_figs), "Tabelas": len(_tabs)})
    mo.vstack([
        mo.md("A tabela abaixo lista os capítulos e quantas figuras e tabelas cada um "
              "fornece à monografia; todas são geradas pelos próprios cadernos."),
        mo.ui.table(pd.DataFrame(_rows), selection=None, show_download=False,
                    page_size=10),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🎨 Como ler os cadernos

        Cada capítulo começa com uma introdução que diz aonde queremos chegar e por quê, e
        cada seção abre com uma explicação curta do que vem nela. As figuras são numeradas,
        apresentadas antes de aparecerem e comentadas depois; quando faz sentido, elas têm
        controles, como menus e barras deslizantes, que permitem trocar a bacia, a variável
        ou um parâmetro, e o texto ao redor acompanha a escolha. A versão impressa de cada
        figura, que vai para a monografia, é a da escolha inicial dos controles. O código
        fica escondido; quem quiser vê-lo pode abrir cada célula. A matemática aparece
        completa, mas sempre depois da intuição, e as referências são numeradas entre
        colchetes, com a lista completa no fim de cada capítulo.

        Ao longo do texto, caixas coloridas destacam quatro tipos de informação, sempre com
        o mesmo significado.
        """),
        mo.callout(mo.md(
            "Azul: números que vêm dos dados e mudam com os controles da figura mais "
            "próxima. Servem para ler a figura com precisão."), kind="info"),
        mo.callout(mo.md(
            "Verde: uma ideia central ou um resultado que vale a pena guardar."),
            kind="success"),
        mo.callout(mo.md(
            "Amarelo: uma cautela de método, um limite de um resultado ou uma análise que "
            "não estava prevista no plano e foi acrescentada depois de olharmos os dados."),
            kind="warn"),
        mo.callout(mo.md(
            "Vermelho: uma armadilha que levaria a uma conclusão errada, ou uma limitação "
            "fundamental dos dados que condiciona tudo o que vem depois."), kind="danger"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🔑 O que encontramos, em uma página

        As séries diárias de temperatura e de déficit de pressão de vapor das duas bacias
        têm estrutura que um processo linear não explica: recorrências mais organizadas,
        padrões ordinais menos uniformes e uma assimetria entre subida e descida que as
        substitutas não reproduzem. Essa estrutura, porém, não é a de um caos de baixa
        dimensão: um previsor não linear não acerta o dia seguinte melhor nas séries reais
        do que nas substitutas, e o expoente de Lyapunov não passou na validação como
        evidência confiável. O clima diário amazônico, visto por esses métodos, é um
        processo não linear e ruidoso, e não um sistema caótico simples escondido no
        ruído.

        A estrutura varia no espaço, e boa parte dessa variação acompanha a latitude: o sul,
        mais seco e mais sazonal, é diferente do norte. Entre células comparáveis em
        latitude, água e relevo, as que tinham mais floresta convertida até 2000 têm uma
        dinâmica diária menos estruturada, nas duas bacias. Mas essa diferença passa, em boa
        parte, pelo mapa de vegetação que o próprio ERA5 usa, que é fixo e data do início da
        década de 1990; e as células que mais perderam floresta depois de 2000 não mudaram
        de dinâmica mais que as outras.

        A temperatura da superfície medida por satélite explica por quê. Ela mostra as células
        com mais floresta convertida de 6 a 7 °C mais quentes que as preservadas, de dia, na
        estação seca, e as
        células que mais perderam floresta entre 2001 e 2012 esquentando quatro a cinco vezes
        mais que as outras. O ERA5 não registra nenhuma das duas coisas. O desmatamento muda,
        e muito, a superfície; a reanálise é que não acompanha essa mudança.
        """),
        mo.callout(mo.md(
            "Os dados mostram que a dinâmica climática diária da Amazônia é não linear e que "
            "essa não linearidade acompanha a geografia e a história de uso da terra "
            "registrada no modelo, e que o desmatamento aquece fortemente a superfície. Eles "
            "não permitem dizer, com uma reanálise de vegetação fixa, se o desmatamento "
            "recente alterou a dinâmica diária do clima, nem falar em caos induzido pelo "
            "desmatamento."),
            kind="success"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## ⚠️ Duas regras de leitura

        Duas confusões são comuns quando se fala de caos e de pontos de não retorno, e
        convém afastá-las desde já. A primeira é tomar um expoente de Lyapunov positivo como
        prova de caos: ele também aparece em séries puramente aleatórias, e só tem valor
        quando comparado com substitutas e validado em casos conhecidos, como fazemos nos
        capítulos de método. A segunda é tomar caos por instabilidade ou colapso. Um sistema
        caótico pode ser perfeitamente estável no longo prazo, e um sistema que se aproxima
        de um ponto de não retorno pode não ter nada de caótico. Os sinais de alerta de
        transição, que também calculamos, respondem a outra pergunta e são tratados à parte.
        """),
        mo.callout(mo.md(
            "O ERA5 é uma reanálise: um modelo de previsão do tempo corrigido por "
            "observações. Ele usa um mapa de vegetação fixo e não incorpora o desmatamento "
            "ano a ano. Por isso, a pergunta que conseguimos responder é se a perturbação "
            "se associa à dinâmica do clima tal como o ERA5 a reconstrói, e não se o "
            "desmatamento causou uma mudança no clima real."), kind="danger"),
    ])
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _slug in list_regions():
        _cfg = load_region(_slug)
        _exp = Path("data/processed", _cfg["experiment_id"])
        _rows.append({
            "Região": _cfg["name"],
            "Clima diário (anos)": len(list(_exp.glob("daily_*-01-01_*-12-31.nc"))),
            "Perturbação": "✅" if (_exp / "perturbacao/celulas.parquet").exists() else "—",
            "Descritores": "✅" if any(_exp.glob("descritores/*/descritores.parquet"))
            else "—",
        })
    mo.accordion({
        "🛠️ Para reproduzir": mo.vstack([
            mo.md(r"""
            Todo o trabalho é reprodutível a partir do repositório. Os downloads e os
            cálculos pesados rodam por uma linha de comando própria, no computador local ou
            no cluster, e gravam arquivos com manifesto e somas de verificação; os cadernos
            apenas leem esses arquivos, contam a história e gravam as figuras e tabelas. As
            regras de análise foram congeladas num pré-registro antes de os descritores
            serem calculados nos dados reais, e cada desvio delas está registrado e
            justificado no diário de decisões do projeto. O passo a passo está no README e
            no guia do cluster; abaixo, o que existe nesta cópia local.
            """),
            mo.ui.table(pd.DataFrame(_rows), selection=None, show_download=False),
        ]),
        "👥 Autoria": mo.md(r"""
            Trabalho de Conclusão de Curso de Caio Ruas e Thalles Cansi, Ilum Escola de
            Ciência (CNPEM), 2026, com orientação de Vinicius Wasques. Thalles responde pela
            parte computacional, que estes cadernos documentam; Caio, pela análise
            socioespacial; a interpretação é da dupla.
            """),
    })
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Spracklen, D. V.; Arnold, S. R.; Taylor, C. M. Observations of increased tropical
    rainfall preceded by air passage over forests. *Nature*, v. 489, p. 282–285, 2012.

    [2] Lovejoy, T. E.; Nobre, C. Amazon tipping point. *Science Advances*, v. 4,
    eaat2340, 2018.

    [3] Flores, B. M. et al. Critical transitions in the Amazon forest system. *Nature*,
    v. 626, p. 555–564, 2024.

    [4] Strogatz, S. H. *Nonlinear Dynamics and Chaos: With Applications to Physics,
    Biology, Chemistry, and Engineering*. 2. ed. Boulder: Westview Press, 2015.

    [5] Kantz, H.; Schreiber, T. *Nonlinear Time Series Analysis*. 2. ed. Cambridge:
    Cambridge University Press, 2004.

    [6] Hersbach, H. et al. The ERA5 global reanalysis. *Quarterly Journal of the Royal
    Meteorological Society*, v. 146, p. 1999–2049, 2020.
    """)
    return


if __name__ == "__main__":
    app.run()
