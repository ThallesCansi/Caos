"""Cores, fontes e tamanho dos clipes, a partir da paleta da apresentação.

O tema escuro usa o verde-mata do fundo dos slides; o claro, o papel. A fonte preferida é a
Inter, a mesma dos slides; sem ela instalada, o matplotlib cai na Noto Sans ou na DejaVu.
O matplotlib só é importado ao aplicar o tema: as cenas do Manim usam as cores sem ele.
"""

from __future__ import annotations

FOGO, AR, FOLHA, CREME, MATA, PAPEL = (
    "#e07b39", "#6aa7dc", "#8fbf9f", "#f1ede2", "#13201a", "#fbfaf6")
TEMAS = {
    "escuro": {"fundo": MATA, "texto": CREME, "suave": "#9fb3a6", "contorno": CREME,
               "rio": AR, "grade": "#2a3a31"},
    "claro": {"fundo": PAPEL, "texto": MATA, "suave": "#5f6b64", "contorno": "#263238",
              "rio": "#1d5d7a", "grade": "#e4e7ea"},
}
FONTES = ["Inter", "Noto Sans", "DejaVu Sans"]
# A figura tem sempre 19,2 × 10,8 polegadas; a qualidade só muda os pontos por polegada.
POLEGADAS = (19.2, 10.8)
DPI = {"previa": 50, "final": 100, "4k": 200}


def aplicar(claro: bool = False) -> dict:
    """Ajusta o matplotlib ao tema e devolve as cores dele."""
    import matplotlib.pyplot as plt

    tema = TEMAS["claro" if claro else "escuro"]
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": FONTES, "font.size": 14,
        "figure.facecolor": tema["fundo"], "axes.facecolor": tema["fundo"],
        "savefig.facecolor": tema["fundo"], "text.color": tema["texto"],
        "axes.labelcolor": tema["texto"], "axes.edgecolor": tema["suave"],
        "xtick.color": tema["suave"], "ytick.color": tema["suave"],
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "axes.unicode_minus": False,  # a Noto Sans não tem o sinal de menos tipográfico
    })
    return tema


def halo(tema: dict, largura: float = 4) -> list:
    """Contorno na cor do fundo, para texto sobre o mapa."""
    import matplotlib.patheffects as pe

    return [pe.withStroke(linewidth=largura, foreground=tema["fundo"])]
