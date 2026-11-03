"""Timelapses de mapa: as duas bacias, vizinhas, mudando no tempo.

`mapa_animado` desenha uma vez o contorno, os rios e os polígonos das células e, a cada
quadro, só troca as cores das células, a data e o painel lateral. Os quadros intermediários
entre duas datas (`subpassos`) misturam linearmente os dois campos: é uma transição visual, e
a data mostrada é sempre a de um dado real.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import imageio_ffmpeg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.animation import FFMpegWriter
from matplotlib.collections import PolyCollection
from matplotlib.colors import (
    LinearSegmentedColormap,
    LogNorm,
    Normalize,
    TwoSlopeNorm,
    to_rgba,
)
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
from shapely.geometry import MultiPolygon, Polygon

from amazon_chaos.animacoes import dados
from amazon_chaos.animacoes.tema import AR, DPI, FOGO, POLEGADAS, aplicar, halo

plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
ESPERA = (1.0, 3.0)  # segundos parados no primeiro e no último quadro


@dataclass
class Anotacao:
    inicio: str
    fim: str
    texto: str


@dataclass
class Timelapse:
    """O que muda de um timelapse para outro; o resto é `mapa_animado`."""
    titulo: str
    subtitulo: str
    fonte: str
    rotulo: str  # da barra de cores
    cmap: str
    norm: Normalize
    campos: dict[str, xr.DataArray]  # slug → (time, latitude, longitude)
    data: Callable[[pd.Timestamp], tuple[str, str]]  # (linha pequena, linha grande)
    fps: int = 24
    subpassos: int = 2
    anotacoes: list[Anotacao] = field(default_factory=list)
    # monta o painel em `ax` e devolve a função que o atualiza para a posição p (fracionária)
    painel: Callable[[plt.Axes, dict], Callable[[float], None]] | None = None
    espera: tuple[float, float] = ESPERA  # (0, 0) num clipe feito para rodar em loop
    # brilho por cima das cores (0 a 1, tempo × latitude × longitude), para destacar o novo
    brilho: dict[str, xr.DataArray] | None = None
    # células cobertas por uma hachura fixa (latitude × longitude, booleano) e a legenda dela
    mascara: dict[str, xr.DataArray] | None = None
    mascara_rotulo: str = ""
    # campo fixo desenhado por baixo (latitude × longitude), com escala e barra de cores próprias
    fundo: dict[str, xr.DataArray] | None = None
    fundo_cmap: str | None = None
    fundo_norm: Normalize | None = None
    fundo_rotulo: str = ""


def _poligonos(celulas, campo: xr.DataArray):
    """Vértices de cada parte de cada célula e a posição (i, j) dela no campo."""
    lat = {round(v, 4): i for i, v in enumerate(campo.latitude.values)}
    lon = {round(v, 4): j for j, v in enumerate(campo.longitude.values)}
    verts, ii, jj = [], [], []
    for row in celulas.itertuples():
        geom = row.geometry
        partes = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        for parte in partes:
            if isinstance(parte, Polygon) and not parte.is_empty:
                verts.append(np.asarray(parte.exterior.coords))
                ii.append(lat[round(row.latitude, 4)])
                jj.append(lon[round(row.longitude, 4)])
    return verts, np.array(ii), np.array(jj)


def mapa_animado(t: Timelapse, saida: Path, qualidade: str = "previa", claro: bool = False,
                 quadros: int | None = None) -> Path:
    """Grava o timelapse em `saida` (MP4) e o último quadro como pôster (PNG ao lado)."""
    tema = aplicar(claro)
    bacias = {slug: dados.bacia(slug) for slug in t.campos}
    fig = plt.figure(figsize=POLEGADAS)

    # mapa à esquerda, as duas bacias no mesmo eixo
    ax = fig.add_axes([0.02, 0.03, 0.47, 0.94])
    ax.set_axis_off()
    colecoes, brilhos = [], []
    for slug, b in bacias.items():
        campo = t.campos[slug]
        verts, ii, jj = _poligonos(b.celulas, campo)
        if t.fundo:
            base = t.fundo[slug].reindex_like(campo.isel(time=0)).values[ii, jj]
            ax.add_collection(PolyCollection(
                verts, array=np.ma.masked_invalid(base), cmap=t.fundo_cmap, norm=t.fundo_norm,
                edgecolor="face", linewidth=0.6))
        col = PolyCollection(verts, cmap=t.cmap, norm=t.norm, edgecolor="face", linewidth=0.6)
        ax.add_collection(col)
        colecoes.append((col, campo.values, ii, jj))
        if t.brilho:
            luz = PolyCollection(verts, edgecolor="none", facecolor="none")
            ax.add_collection(luz)
            brilhos.append((luz, t.brilho[slug].values, ii, jj))
        if t.mascara:
            coberta = t.mascara[slug].reindex_like(campo.isel(time=0)).fillna(False).values[ii, jj]
            ax.add_collection(PolyCollection(
                [v for v, c in zip(verts, coberta, strict=True) if c], facecolor=tema["grade"],
                edgecolor=tema["suave"], linewidth=0, hatch="///", alpha=0.95))
        b.rios.plot(ax=ax, color=tema["rio"], linewidth=1.0, alpha=0.55)
        b.limite.boundary.plot(ax=ax, color=tema["contorno"], linewidth=1.3)
        c = b.limite.union_all().representative_point()
        ax.text(c.x, c.y, b.nome, ha="center", va="center", fontsize=22, fontweight="bold",
                color=tema["texto"], path_effects=halo(tema, 6))
    if t.mascara:
        ax.legend(handles=[Patch(facecolor=tema["grade"], edgecolor=tema["suave"], hatch="///",
                                 label=t.mascara_rotulo)],
                  loc="upper left", fontsize=13, frameon=False, labelcolor=tema["texto"])
    w, s, e, n = np.array([b.limite.total_bounds for b in bacias.values()]).T
    ax.set(xlim=(w.min() - 0.2, e.max() + 0.2), ylim=(s.min() - 0.2, n.max() + 0.2),
           aspect="equal")

    # coluna da direita: título, data, barra de cores, anotação, painel, fonte
    x0 = 0.52
    fig.text(x0, 0.93, t.titulo, fontsize=34, fontweight="bold", va="top")
    fig.text(x0, 0.865, textwrap.fill(t.subtitulo, 70), fontsize=15, va="top",
             color=tema["suave"], linespacing=1.4)
    data_peq = fig.text(x0, 0.70, "", fontsize=26, color=tema["suave"], va="bottom")
    data_grd = fig.text(x0, 0.585, "", fontsize=78, fontweight="bold", va="bottom")
    barra = fig.add_axes([x0, 0.525, 0.40, 0.022])
    cb = fig.colorbar(plt.cm.ScalarMappable(t.norm, t.cmap), cax=barra, orientation="horizontal")
    cb.set_label(t.rotulo, fontsize=14, color=tema["texto"])
    cb.outline.set_visible(False)
    cb.formatter = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
    barra.tick_params(labelsize=12, colors=tema["suave"])
    y_nota = 0.445
    if t.fundo:  # uma segunda barra, mais fina, para o campo fixo
        barra2 = fig.add_axes([x0, 0.445, 0.40, 0.012])
        cb2 = fig.colorbar(plt.cm.ScalarMappable(t.fundo_norm, t.fundo_cmap), cax=barra2,
                           orientation="horizontal")
        cb2.set_label(t.fundo_rotulo, fontsize=13, color=tema["suave"])
        cb2.outline.set_visible(False)
        cb2.formatter = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
        barra2.tick_params(labelsize=11, colors=tema["suave"])
        y_nota = 0.375
    nota = fig.text(x0, y_nota, "", fontsize=19, va="top", linespacing=1.3)
    fig.text(x0, 0.025, t.fonte, fontsize=11, color=tema["suave"], va="bottom")
    atualizar_painel = (t.painel(fig.add_axes([x0 + 0.03, 0.09, 0.42, 0.20]), tema)
                        if t.painel else None)

    tempos = pd.DatetimeIndex(next(iter(t.campos.values())).time.values)
    ultimo = len(tempos) - 1
    posicoes = np.concatenate([
        np.zeros(round(t.espera[0] * t.fps)),
        np.arange(ultimo * t.subpassos + 1) / t.subpassos,
        np.full(round(t.espera[1] * t.fps), float(ultimo)),
    ])
    if quadros:  # renderização relâmpago (testes): poucos quadros espalhados
        posicoes = np.linspace(0, ultimo, quadros)
    notas = [(pd.Timestamp(a.inicio), pd.Timestamp(a.fim), a.texto) for a in t.anotacoes]

    def desenhar(p: float):
        k, f = int(p), p - int(p)
        k1 = min(k + 1, ultimo)
        for col, valores, ii, jj in colecoes:
            v = (1 - f) * valores[k, ii, jj] + f * valores[k1, ii, jj]
            col.set_array(np.ma.masked_invalid(v))
        for luz, valores, ii, jj in brilhos:
            alfa = np.nan_to_num((1 - f) * valores[k, ii, jj] + f * valores[k1, ii, jj])
            cores = np.tile(to_rgba(tema["texto"]), (len(alfa), 1))
            cores[:, 3] = 0.85 * np.clip(alfa, 0, 1)
            luz.set_facecolor(cores)
        hoje = tempos[round(p)]
        pequeno, grande = t.data(hoje)
        data_peq.set_text(pequeno)
        data_grd.set_text(grande)
        ativa = [texto for ini, fim, texto in notas if ini <= hoje <= fim]
        nota.set_text(textwrap.fill(ativa[0], 64) if ativa else "")
        if atualizar_painel:
            atualizar_painel(p)

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    writer = FFMpegWriter(fps=t.fps, codec="libx264", bitrate=-1,
                          extra_args=["-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow"])
    with writer.saving(fig, str(saida), dpi=DPI[qualidade]):
        for p in posicoes:
            desenhar(p)
            writer.grab_frame()
    fig.savefig(saida.with_suffix(".png"), dpi=DPI[qualidade])
    plt.close(fig)
    return saida


# ── os timelapses ──────────────────────────────────────────────────────────


def _listras(campos: dict[str, xr.DataArray], cmap, norm) -> Callable:
    """Painel de listras mensais, uma faixa por bacia, que se acumulam até o mês atual."""
    medias = {slug: dados.media(c, dados.bacia(slug).pesos) for slug, c in campos.items()}
    tempos = pd.DatetimeIndex(next(iter(campos.values())).time.values)

    def montar(ax, tema):
        grade = np.vstack([medias[s] for s in campos])
        imagem = ax.imshow(np.full_like(grade, np.nan), cmap=cmap, norm=norm, aspect="auto",
                           interpolation="nearest", extent=(0, len(tempos), len(campos), 0))
        cursor = ax.axvline(0, color=tema["texto"], linewidth=1.5)
        ax.set_yticks(np.arange(len(campos)) + 0.5, [dados.BACIAS[s] for s in campos],
                      fontsize=15)
        anos = [i for i, d in enumerate(tempos) if d.month == 1 and d.year % 5 == 0]
        ax.set_xticks(anos, [str(tempos[i].year) for i in anos], fontsize=12)
        ax.tick_params(length=0)
        for lado in ax.spines.values():
            lado.set_visible(False)
        ax.set_title("Média da bacia, mês a mês", fontsize=14, loc="left",
                     color=tema["suave"], pad=10)

        def atualizar(p):
            k = round(p)
            visivel = grade.copy()
            visivel[:, k + 1:] = np.nan
            imagem.set_data(np.ma.masked_invalid(visivel))
            cursor.set_xdata([k + 1, k + 1])

        return atualizar

    return montar


def anomalia(variavel: str = "t2m") -> Timelapse:
    """A2: a anomalia mensal de cada célula, de 1990 a 2024."""
    campos = {slug: dados.anomalia(slug, variavel) for slug in dados.BACIAS}
    textos = {
        "t2m": ("Anomalia da temperatura, mês a mês",
                "Temperatura média do ar a 2 m em cada célula de 0,25° do ERA5, menos a "
                "média do mesmo mês em 1991–2020.", "Anomalia (°C)", "RdBu_r", 2.0),
        "vpd": ("Anomalia da secura do ar, mês a mês",
                "Déficit de pressão de vapor em cada célula de 0,25° do ERA5, menos a média "
                "do mesmo mês em 1991–2020.", "Anomalia (kPa)", "BrBG_r", 0.6),
        "precip": ("Anomalia da chuva, mês a mês",
                   "Chuva acumulada no mês em cada célula de 0,25° do ERA5, menos a média do "
                   "mesmo mês em 1991–2020.", "Anomalia (mm)", "BrBG", 150),
    }
    titulo, subtitulo, rotulo, cmap, limite = textos[variavel]
    norm = TwoSlopeNorm(0, -limite, limite)
    return Timelapse(
        titulo=titulo, subtitulo=subtitulo, rotulo=rotulo, cmap=cmap, norm=norm,
        fonte="ERA5 (ECMWF/Copernicus), médias mensais por célula · normal de 1991–2020",
        campos=campos, data=lambda d: (MESES[d.month - 1], str(d.year)),
        fps=24, subpassos=2, painel=_listras(campos, cmap, norm),
        anotacoes=[
            Anotacao("1997-10", "1998-12", "1997–98: um El Niño forte já aquece as duas "
                     "bacias no começo do registro."),
            Anotacao("2015-08", "2016-08", "2015–16: o El Niño mais forte do período."),
            Anotacao("2023-07", "2024-12", "2023–24: os meses mais quentes de 35 anos, "
                     "nas duas bacias."),
        ] if variavel == "t2m" else [],
    )


def _eixo_painel(ax, tema, titulo):
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(tema["suave"])
    ax.tick_params(labelsize=12, length=0)
    ax.set_title(titulo, fontsize=14, loc="left", color=tema["suave"], pad=10)


def _barras(series: dict[str, np.ndarray], tempos, titulo: str, cores: dict[str, str],
            largura: float = 1.0, marcas: list[int] | None = None) -> Callable:
    """Barras empilhadas por bacia (uma por data) que aparecem até a data atual."""
    nomes = list(series)
    x = np.arange(len(tempos))

    def montar(ax, tema):
        base = np.zeros(len(tempos))
        grupos = []
        for slug in nomes:
            valores = np.nan_to_num(series[slug])
            barras = ax.bar(x, valores, largura, bottom=base, color=cores[slug],
                            label=dados.BACIAS[slug], linewidth=0)
            grupos.append((barras, valores, base.copy()))
            base = base + valores
        ax.set_ylim(0, base.max() * 1.05)
        ax.set_xlim(-0.5, len(tempos) - 0.5)
        ticks = marcas if marcas is not None else list(range(0, len(tempos), 5))
        ax.set_xticks(ticks, [str(tempos[i].year) for i in ticks])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
        _eixo_painel(ax, tema, titulo)
        ax.legend(loc="upper right", fontsize=12, frameon=False, labelcolor=tema["texto"])

        def atualizar(p):
            k = round(p)
            for barras, valores, _ in grupos:
                for i, retangulo in enumerate(barras):
                    retangulo.set_height(valores[i] if i <= k else 0)

        return atualizar

    return montar


def _ciclo(series: dict[str, np.ndarray], tempos, titulo: str, cores: dict[str, str],
           unidade: str) -> Callable:
    """O ano médio de cada bacia, inteiro e apagado, com um ponto que anda pelo dia atual."""
    def montar(ax, tema):
        x = np.arange(len(tempos))
        pontos = []
        for slug, valores in series.items():
            ax.plot(x, valores, color=cores[slug], linewidth=2.5, alpha=0.9,
                    label=dados.BACIAS[slug])
            pontos.append((ax.plot([], [], "o", color=cores[slug], markersize=11,
                                   markeredgecolor=tema["fundo"])[0], valores))
        cursor = ax.axvline(0, color=tema["suave"], linewidth=1)
        inicio = [i for i, d in enumerate(tempos) if d.day == 1]
        ax.set_xticks(inicio, [MESES[tempos[i].month - 1][:3] for i in inicio])
        ax.set_xlim(0, len(tempos) - 1)
        ax.set_ylabel(unidade, fontsize=12, color=tema["suave"])
        _eixo_painel(ax, tema, titulo)
        ax.legend(loc="upper center", fontsize=12, frameon=False, labelcolor=tema["texto"],
                  ncols=2)

        def atualizar(p):
            k = round(p)
            for ponto, valores in pontos:
                ponto.set_data([k], [valores[k]])
            cursor.set_xdata([k, k])

        return atualizar

    return montar


CORES_BACIAS = {"tapajos": "#f6d27a", "xingu": FOGO}
FOGO_CMAP = LinearSegmentedColormap.from_list(
    "fogo", ["#22332a", "#5c2a14", "#b5461c", FOGO, "#f6d27a", "#fff6dc"])
ABERTO_CMAP = LinearSegmentedColormap.from_list(
    "aberto", ["#2e6b45", "#56705a", "#7d8471", "#a39f8c"])
NOVO_CMAP = LinearSegmentedColormap.from_list(
    "novo", [(0.878, 0.482, 0.224, 0.0), (0.878, 0.482, 0.224, 0.75), (0.71, 0.27, 0.11, 1.0),
             (0.97, 0.82, 0.48, 1.0)])
CHUVA_CMAP = LinearSegmentedColormap.from_list(
    "chuva", ["#7a4a1f", "#c89a55", "#e9dcb8", "#8cc0e6", AR, "#1f4e8c"])
SECURA_CMAP = LinearSegmentedColormap.from_list(
    "secura", ["#e9f1ea", "#e9dcb8", "#e0b45a", FOGO, "#a8361d", "#5c1a0e"])


def fogo() -> Timelapse:
    """A3: os focos de fogo de cada mês, de 2003 a 2024, com um rastro que esmaece."""
    campos, totais = {}, {}
    for slug in dados.BACIAS:
        densidade = dados.focos(slug)
        totais[slug] = (densidade * dados.terra(slug) / 100).sum(("latitude", "longitude")).values
        # o rastro: cada célula apaga até 45% do brilho por mês, a não ser que queime de novo
        brilho = densidade.values.copy()
        for k in range(1, len(brilho)):
            brilho[k] = np.fmax(brilho[k], 0.45 * brilho[k - 1])
        campos[slug] = densidade.copy(data=np.clip(brilho, 0.1, None))
    tempos = pd.DatetimeIndex(campos["xingu"].time.values)
    return Timelapse(
        titulo="O fogo, mês a mês",
        subtitulo="Focos de fogo ativo detectados pelo satélite de referência em cada célula, "
                  "por 100 km² de terra. Cada estação seca acende o mapa.",
        fonte="BDQueimadas/INPE, satélite de referência · 2003–2024 · o brilho esmaece em "
              "dois ou três meses (rastro visual)",
        rotulo="Focos por 100 km² no mês", cmap=FOGO_CMAP, norm=LogNorm(0.1, 30, clip=True),
        campos=campos, data=lambda d: (MESES[d.month - 1], str(d.year)), fps=24, subpassos=2,
        painel=_barras(totais, tempos, "Focos por mês, total da bacia", CORES_BACIAS, 1.0,
                       [i for i, d in enumerate(tempos) if d.month == 1 and d.year % 5 == 0]),
        anotacoes=[
            Anotacao("2003-01", "2007-12", "2003–2007: os anos de mais fogo, junto com o "
                     "auge do desmatamento."),
            Anotacao("2010-07", "2010-12", "2010: uma seca forte, e o fogo volta a crescer."),
            Anotacao("2024-06", "2024-12", "2024: a seca extrema; no Tapajós, o maior número "
                     "de focos desde 2007."),
        ],
    )


def desmatamento() -> Timelapse:
    """A4: o desmatamento novo de cada célula, de 2008 a 2024, sobre o que já estava aberto.

    O bloco até 2007 domina a fração acumulada; numa escala de 0 a 1 o que vem depois mal muda
    a cor. Por isso ele fica fixo, por baixo, em tons apagados, e só o novo é animado.
    """
    acumulado = {slug: dados.desmatamento(slug) for slug in dados.BACIAS}
    campos = {slug: (c - c.isel(time=0)).clip(min=0) for slug, c in acumulado.items()}
    tempos = pd.DatetimeIndex(campos["xingu"].time.values)
    anuais = {}
    for slug, campo in acumulado.items():
        area = (campo * dados.terra(slug)).sum(("latitude", "longitude")).values
        anuais[slug] = np.concatenate([[0], np.diff(area)])  # km² desmatados no ano
    # o desmatamento do ano acende a célula: 3% da terra ou mais no ano é brilho pleno
    brilho = {slug: (c.diff("time").reindex_like(c).fillna(0) / 0.03).clip(0, 1)
              for slug, c in acumulado.items()}
    mascara = {slug: dados.nao_floresta(slug) > 0.5 for slug in dados.BACIAS}
    return Timelapse(
        titulo="Desmatamento, ano a ano",
        subtitulo="Em tons apagados, o que estava aberto até 2007; em laranja, a fração da "
                  "terra desmatada de 2008 até o ano indicado.",
        fonte="PRODES/INPE · bloco de 1988–2007, depois anual (ano de agosto a julho) · "
              "terra: MapBiomas 2000",
        rotulo="Desmatado desde 2008 (fração da terra)", cmap=NOVO_CMAP,
        norm=Normalize(0, 0.3, clip=True), campos=campos,
        fundo={slug: c.isel(time=0) for slug, c in acumulado.items()}, fundo_cmap=ABERTO_CMAP,
        fundo_norm=Normalize(0, 1), fundo_rotulo="Desmatado até 2007",
        data=lambda d: ("o ponto de partida" if d.year == 2007 else "de 2008 até", str(d.year)),
        fps=24, subpassos=24, espera=(2.5, 3.0), brilho=brilho, mascara=mascara,
        mascara_rotulo="Mais da metade não era floresta (Cerrado; fora do PRODES)",
        painel=_barras(anuais, tempos, "Desmatado no ano (km²)", CORES_BACIAS, 0.8,
                       [i for i, d in enumerate(tempos) if d.year % 4 == 0]),
        anotacoes=[
            Anotacao("2007-01", "2007-12", "Aberto até 2007: o sul do Tapajós e o leste do "
                     "Xingu."),
            Anotacao("2008-01", "2008-12", "Em laranja, o desmatamento novo; em claro, o do "
                     "ano."),
            Anotacao("2009-01", "2012-12", "2008–2012: o desmatamento anual cai a cerca de "
                     "um terço."),
            Anotacao("2019-01", "2022-12", "2019–2022: volta a subir, na frente que avança "
                     "para o norte."),
            Anotacao("2023-01", "2024-12", "2023–2024: um novo recuo."),
        ],
    )


def ano_medio(variavel: str = "precip") -> Timelapse:
    """A1: o ano médio de 1991–2020, dia a dia, em loop."""
    campos = {slug: dados.climatologia(slug, variavel) for slug in dados.BACIAS}
    tempos = pd.DatetimeIndex(campos["xingu"].time.values)
    medias = {slug: dados.media(c, dados.bacia(slug).pesos) for slug, c in campos.items()}
    textos = {
        "precip": ("O ano médio da chuva",
                   "Chuva de cada dia do calendário em cada célula do ERA5, na média de "
                   "1991–2020 e suavizada em 31 dias.", "Chuva (mm/dia)", CHUVA_CMAP,
                   Normalize(0, 12), {"tapajos": "#e9dcb8", "xingu": AR}),
        "vpd": ("O ano médio da secura do ar",
                "Déficit de pressão de vapor de cada dia do calendário em cada célula do ERA5, "
                "na média de 1991–2020 e suavizado em 31 dias.", "VPD (kPa)", SECURA_CMAP,
                Normalize(0.3, 2.4), CORES_BACIAS),
    }
    titulo, subtitulo, rotulo, cmap, norm, cores = textos[variavel]
    return Timelapse(
        titulo=titulo, subtitulo=subtitulo, rotulo=rotulo, cmap=cmap, norm=norm,
        fonte="ERA5 (ECMWF/Copernicus), valores diários por célula · normal de 1991–2020",
        campos=campos, data=lambda d: ("o ano médio, 1991–2020",
                                       f"{d.day} {MESES[d.month - 1][:3]}"),
        fps=24, subpassos=1, espera=(0.0, 0.0),
        painel=_ciclo(medias, tempos, "Média da bacia", cores, rotulo),
        anotacoes=[
            Anotacao("2001-01-01", "2001-03-20", "Janeiro a março: o auge da estação chuvosa, "
                     "em toda a parte."),
            Anotacao("2001-04-01", "2001-05-31", "Abril e maio: a seca começa pelo sul e sobe "
                     "para o norte."),
            Anotacao("2001-06-01", "2001-08-31", "Junho a agosto: a estação seca, com poucos "
                     "milímetros por dia, ou nada."),
            Anotacao("2001-09-15", "2001-11-30", "Outubro e novembro: a chuva volta pelo oeste e "
                     "pelo centro; o baixo Xingu, ao norte, é o último a molhar."),
        ] if variavel == "precip" else [],
    )
