"""B4: a máquina de substitutas, em matplotlib.

Dois anos da temperatura do Xingu (anomalia padronizada da média da bacia) passam pela
máquina: o espectro fica, as fases giram ao acaso e a série se transforma; o passo do IAAFT
devolve os valores originais na nova ordem. Depois, os 199 valores de cada descritor nas
substitutas da série inteira (2001–2024, o lote do resultado principal) caem nos histogramas,
e a linha do valor observado desce: o DET fica fora da nuvem, o Lyapunov fica dentro.

Nada é recalculado para os histogramas: valores observados, nulas, z e p vêm de
`basin_test.load`. As séries mostradas na primeira parte são ilustrativas (uma janela de dois
anos e substitutas dela).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np

from amazon_chaos.animacoes import dados
from amazon_chaos.animacoes.tema import AR, CREME, FOGO, POLEGADAS, aplicar

JANELA = ("2019-01-01", "2020-12-31")
N_FASES = 24  # mostradores visíveis (as 24 frequências mais baixas)
N_FANTASMAS = 30
DESCRITORES = {"rqa_det": "Determinismo (RQA)", "lyapunov": "Expoente de Lyapunov"}


def pacote(slug: str = "xingu", variavel: str = "t2m", metodo: str = "IAAFT") -> dict:
    """A janela, as fases sorteadas, os fantasmas e os resultados do teste (cache em .npz)."""
    path = dados.DADOS / slug / f"substitutas_{variavel}_{metodo}.npz"
    if not path.exists():
        from amazon_chaos.config import load_region
        from amazon_chaos.nonlinear import basin_test
        from amazon_chaos.nonlinear.suite import load_spec
        from amazon_chaos.nonlinear.surrogates import iaaft_surrogate

        spec, cfg = load_spec(), load_region(slug)
        serie = basin_test.basin_series(cfg, variavel, spec).loc[JANELA[0]:JANELA[1]]
        x = serie.to_numpy()
        rng = np.random.default_rng(0)
        tabela, nulas = basin_test.load(cfg, spec)
        sel = (tabela.region == slug) & (tabela.variable == variavel) & (tabela.method == metodo)
        linhas = tabela[sel].set_index("descriptor")
        saida = {"serie": x, "inicio": np.array(JANELA[0]), "fim": np.array(JANELA[1]),
                 "fases_novas": rng.uniform(-np.pi, np.pi, len(np.fft.rfft(x))),
                 "fantasmas": np.array([iaaft_surrogate(x, rng, max_iter=200).values
                                        for _ in range(N_FANTASMAS)])}
        for d in DESCRITORES:
            nula = nulas[(nulas.region == slug) & (nulas.variable == variavel)
                         & (nulas.method == metodo) & (nulas.descriptor == d)]
            saida[f"{d}_nula"] = nula.sort_values("surrogate").value.to_numpy()
            for campo in ("observed", "z", "pvalue"):
                saida[f"{d}_{campo}"] = np.array(linhas.loc[d, campo])
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, **saida)
    with np.load(path) as arquivo:
        return {k: arquivo[k] for k in arquivo.files}


def _suave(t, a, b):
    """0 antes de a, 1 depois de b, e uma rampa suave no meio."""
    u = np.clip((t - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


def _pontos(valores, bins=28, limites=None):
    """Posições de um gráfico de pontos empilhados (um ponto por substituta)."""
    lo, hi = limites if limites else (valores.min(), valores.max())
    bordas = np.linspace(lo, hi, bins + 1)
    idx = np.clip(np.digitize(valores, bordas) - 1, 0, bins - 1)
    centros = (bordas[:-1] + bordas[1:]) / 2
    alturas = np.zeros(bins, int)
    xy = np.zeros((len(valores), 2))
    for i, b in enumerate(idx):
        alturas[b] += 1
        xy[i] = centros[b], alturas[b]
    return xy, alturas.max()


def _fmt(v, casas=1, sinal=False):
    return (f"{v:+.{casas}f}" if sinal else f"{v:.{casas}f}").replace(".", ",")


def maquina(saida: Path, qualidade: str = "previa", quadros: int | None = None,
            claro: bool = False) -> Path:
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    from amazon_chaos.animacoes.video import gravar

    tema = aplicar(claro)
    p = pacote()
    x = p["serie"]
    espectro = np.fft.rfft(x)
    amp, fase0 = np.abs(espectro), np.angle(espectro)
    fase1 = p["fases_novas"].copy()
    fase1[0] = fase0[0]  # a média não muda
    if len(x) % 2 == 0:
        fase1[-1] = fase0[-1]  # nem o termo de Nyquist, que é real
    delta = np.angle(np.exp(1j * (fase1 - fase0)))  # o caminho mais curto de cada mostrador
    ordem = np.argsort(np.argsort(np.fft.irfft(amp * np.exp(1j * fase1), len(x))))
    reordenada = np.sort(x)[ordem]  # o passo do IAAFT: os valores originais, na nova ordem
    dias = np.arange(len(x))

    fig = plt.figure(figsize=POLEGADAS)
    fig.text(0.04, 0.94, "A máquina de substitutas", fontsize=34, fontweight="bold", va="top")
    fig.text(0.04, 0.875, "Temperatura do Xingu, anomalia padronizada da média da bacia "
             "(ERA5), de janeiro de 2019 a dezembro de 2020", fontsize=15,
             color=tema["suave"], va="top")
    rodape = fig.text(0.04, 0.02, "", fontsize=12, color=tema["suave"])

    ax_s = fig.add_axes([0.05, 0.60, 0.90, 0.22])
    ax_s.set_xlim(0, len(x) - 1)
    lim = np.abs(np.concatenate([x, p["fantasmas"].ravel()])).max() * 1.05
    ax_s.set_ylim(-lim, lim)
    ax_s.set_yticks([])
    ax_s.set_xticks([0, 365, len(x) - 1], ["jan 2019", "jan 2020", "dez 2020"], fontsize=12)
    ax_s.spines["left"].set_visible(False)
    fantasmas = LineCollection([], colors=AR, linewidths=1.0, alpha=0.18)
    ax_s.add_collection(fantasmas)
    ax_s.plot(dias, x, color=CREME, linewidth=1.6)
    (linha_nova,) = ax_s.plot(dias, x, color=AR, linewidth=1.6, alpha=0)
    ax_s.text(0.0, 1.04, "a série real", transform=ax_s.transAxes, fontsize=16,
                          color=CREME)
    legenda_n = ax_s.text(0.2, 1.04, "", transform=ax_s.transAxes, fontsize=16, color=AR)

    # espectro e mostradores das fases (primeira parte)
    ax_e = fig.add_axes([0.05, 0.13, 0.40, 0.33])
    k = np.arange(1, 61)
    ax_e.bar(k, amp[k], color=FOGO, width=0.8)
    ax_e.set_yticks([])
    ax_e.set_xticks([])
    ax_e.spines["left"].set_visible(False)
    ax_e.set_title("as amplitudes de cada frequência: ficam", fontsize=16, loc="left",
                   color=tema["texto"])
    ax_f = fig.add_axes([0.55, 0.13, 0.40, 0.33])
    ax_f.set_axis_off()
    ax_f.set_xlim(-0.6, 11.6)
    ax_f.set_ylim(-1.6, 3.6)
    ax_f.set_aspect("equal")
    ax_f.set_title("as fases: são sorteadas", fontsize=16, loc="left", color=tema["texto"])
    centros = [(2 * (i % 6), 2 * (1 - i // 6) + 0.6) for i in range(N_FASES // 2)]
    centros = [(c[0], c[1]) for c in centros] + [(c[0] + 1, c[1] - 1) for c in centros]
    ponteiros = []
    for cx, cy in centros[:N_FASES]:
        ax_f.add_patch(plt.Circle((cx, cy), 0.42, fill=False, color=tema["suave"], lw=1.2))
        ponteiros.append(ax_f.plot([], [], color=AR, lw=2.2)[0])

    # histogramas (segunda parte)
    paineis = {}
    for i, (d, nome) in enumerate(DESCRITORES.items()):
        ax = fig.add_axes([0.05 + 0.48 * i, 0.10, 0.42, 0.33])
        nula, obs = p[f"{d}_nula"], float(p[f"{d}_observed"])
        lo, hi = min(nula.min(), obs), max(nula.max(), obs)
        margem = 0.08 * (hi - lo)
        xy, topo = _pontos(nula, limites=(nula.min(), nula.max()))
        ax.set_xlim(lo - margem, hi + margem)
        ax.set_ylim(0, topo * 1.9)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.tick_params(labelsize=12)
        ax.xaxis.set_major_locator(plt.MaxNLocator(5))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt(v, 3)))
        ax.set_title(nome, fontsize=18, loc="left", color=tema["texto"])
        pontos = ax.scatter([], [], s=30, color=AR, edgecolor="none")
        (obs_linha,) = ax.plot([], [], color=FOGO, lw=3.5)
        rotulo = ax.text(0, 0, "", fontsize=16, color=FOGO, va="bottom")
        ax.set_visible(False)
        paineis[d] = (ax, xy, topo, pontos, obs_linha, rotulo, obs)

    legenda = fig.text(0.05, 0.535, "", fontsize=20, va="center")
    mensagem = fig.text(0.5, 0.505, "", fontsize=24, fontweight="bold", ha="center",
                        va="center")

    n_nula = len(p["rqa_det_nula"])
    duracao = 38.0
    # quando cada nula cai: devagar no começo, depressa depois (13 s a 23 s)
    queda = 13 + 10 * (np.arange(n_nula) / n_nula) ** 0.55

    def desenhar(t):
        # parte 1: as fases giram, a série se transforma
        g = _suave(t, 4.5, 9.5)
        fases = fase0 + g * delta
        nova = np.fft.irfft(amp * np.exp(1j * fases), len(x))
        r = _suave(t, 10.5, 11.5)
        nova = (1 - r) * nova + r * reordenada
        for (cx, cy), ponteiro, f in zip(centros, ponteiros, fases[1:N_FASES + 1], strict=True):
            ponteiro.set_data([cx, cx + 0.38 * np.cos(f)], [cy, cy + 0.38 * np.sin(f)])
        aparece = _suave(t, 3.5, 4.5)
        linha_nova.set_ydata(nova)
        linha_nova.set_alpha(aparece * (1 - _suave(t, 12, 13)))
        legenda_n.set_text("a substituta" if 3.5 <= t < 13 else
                           "199 substitutas" if t >= 13 else "")
        primeira = t < 12.5
        rodape.set_text("" if primeira else
                        "Nos histogramas, os valores do teste do resultado principal: a série "
                        "inteira (2001–2024) e as suas 199 substitutas IAAFT.")
        ax_e.set_visible(primeira)
        ax_f.set_visible(primeira)
        if t < 3.5:
            legenda.set_text("Uma série real: o que nela é não linear?")
        elif t < 10.5:
            legenda.set_text("Mesmo espectro, fases ao acaso: a mesma autocorrelação, sem a "
                             "estrutura não linear.")
        elif t < 12.5:
            legenda.set_text("IAAFT: os valores originais voltam, na nova ordem; o histograma "
                             "também é o mesmo.")
        elif t < 24:
            legenda.set_text("Para cada substituta, cada descritor dá um valor: um ponto.")
        else:
            legenda.set_text("")

        # parte 2: os fantasmas e os pontos
        caidas = int(np.searchsorted(queda, t, side="right"))
        fantasmas.set_segments([np.column_stack([dias, f])
                                for f in p["fantasmas"][:min(caidas, N_FANTASMAS)]])
        for i, (d, (ax, xy, topo, pontos, obs_linha, rotulo, obs)) in enumerate(paineis.items()):
            ax.set_visible(t >= 12.5)
            pos = xy[:caidas].copy()
            if caidas:  # o último ponto ainda caindo
                u = np.clip((t - queda[caidas - 1]) / 0.35, 0, 1)
                pos[-1, 1] = topo * 1.8 * (1 - u) + pos[-1, 1] * u
            pontos.set_offsets(pos if len(pos) else np.empty((0, 2)))
            inicio = 24 + 5.5 * i  # DET primeiro, depois o Lyapunov
            desce = _suave(t, inicio, inicio + 1.2)
            if desce > 0:
                obs_linha.set_data([obs, obs], [topo * 1.85, topo * 1.85 * (1 - desce)])
                z = float(p[f"{d}_z"])
                fora = d == "rqa_det"
                texto = (f"a série real: z = {_fmt(z, 1, True)}\nfora de tudo o que o acaso deu"
                         if fora else f"a série real: z = {_fmt(z, 1, True)}\n"
                         "dentro da nuvem: o acaso também dá isso")
                rotulo.set_text(texto if desce >= 1 else "")
                xmin, xmax = ax.get_xlim()
                direita = obs < xmin + 0.6 * (xmax - xmin)
                rotulo.set_position((obs + (0.02 if direita else -0.02) * (xmax - xmin),
                                     topo * 1.25))
                rotulo.set_ha("left" if direita else "right")
        mensagem.set_text(textwrap.fill(
            "Só conta como estrutura o que as substitutas não reproduzem.", 80)
            if t >= 34 else "")

    gravar(fig, saida, desenhar, duracao, fps=30, qualidade=qualidade, quadros=quadros)
    plt.close(fig)
    return saida
