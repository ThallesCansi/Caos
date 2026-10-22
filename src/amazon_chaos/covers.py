"""Capas dos cadernos para a galeria do Marimo (`marimo run notebooks/`).

O Marimo mostra, em cada cartão da galeria, o título e a descrição declarados no cabeçalho
PEP 723 do caderno (`[tool.marimo.opengraph]`) e a imagem em
`notebooks/__marimo__/assets/<caderno>/opengraph.png`. Esta capa é desenhada a partir da
figura mais representativa de cada capítulo, já gravada em `reports/figures/`; por isso
ela não é versionada e se refaz com `make capas` depois de `make notebooks`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

from amazon_chaos.paths import project_root

GREEN, LEAF, CREAM = "#1f3b2d", "#8fbf9f", "#f4f1e8"
COVERS = {
    "00_inicio": ("Apresentação", "A pergunta, o percurso e o que encontramos",
                  "04_perturbacao/temperatura_superficie.png"),
    "01_laboratorio": ("Laboratório de sistemas dinâmicos",
                       "Equilíbrios, bifurcações e caos em modelos conhecidos",
                       "01_laboratorio/bifurcacao_lyapunov.png"),
    "02_regioes": ("As bacias do Xingu e do Tapajós", "O recorte, a grade e as células",
                   "02_regioes/xingu/mapa.png"),
    "03_clima": ("O clima de 1990 a 2024", "Ritmo do ano, geografia e tendências",
                 "03_clima/mapas_tendencia.png"),
    "04_perturbacao": ("Desmatamento e fogo, célula por célula",
                       "Quatro fontes e o que elas medem", "04_perturbacao/cobertura.png"),
    "05_validacao_metodos": ("Os métodos diante de casos conhecidos",
                             "O portão dos descritores", "05_validacao_metodos/controles.png"),
    "06_surrogates": ("Séries substitutas", "O clima sem não linearidade",
                      "06_surrogates/anatomia.png"),
    "07_descritores": ("Descritores não lineares", "1.541 células, oito descritores",
                       "07_descritores/xingu/mapa_z_pe_complexity_t2m.png"),
    "08_gradiente": ("Perturbação e dinâmica", "O que o ERA5 vê e o que o satélite vê",
                     "08_gradiente/modis.png"),
}


def _crop(image: np.ndarray, aspect: float) -> np.ndarray:
    """Recorte central com a proporção largura/altura pedida."""
    h, w = image.shape[:2]
    if w / h > aspect:
        new_w = int(h * aspect)
        x0 = (w - new_w) // 2
        return image[:, x0:x0 + new_w]
    new_h = int(w / aspect)
    y0 = (h - new_h) // 2
    return image[y0:y0 + new_h]


def draw(name: str, root: Path | None = None) -> Path:
    root = Path(root or project_root())
    title, subtitle, figure = COVERS[name]
    number = name[:2]
    fig = plt.figure(figsize=(12, 6.3), dpi=200)
    fig.patch.set_facecolor(GREEN)
    split = 0.46
    art = fig.add_axes([split, 0, 1 - split, 1])
    image = mpimg.imread(root / "reports/figures" / figure)
    art.imshow(_crop(image, (1 - split) * 12 / 6.3), aspect="auto")
    art.set_axis_off()
    # esmaece a borda esquerda da figura no verde do painel
    fade = np.zeros((2, 256, 4))
    fade[..., :3] = np.array([0x1f, 0x3b, 0x2d]) / 255
    fade[..., 3] = np.linspace(1, 0, 256) ** 1.4
    veil = fig.add_axes([split, 0, (1 - split) * 0.3, 1])
    veil.imshow(fade, aspect="auto")
    veil.set_axis_off()
    panel = fig.add_axes([0, 0, split, 1])
    panel.set_axis_off()
    panel.set(xlim=(0, 1), ylim=(0, 1))
    panel.text(0.09, 0.84, "Capítulo" if number != "00" else "Caos na floresta",
               color=LEAF, fontsize=17, fontweight="bold")
    panel.text(0.09, 0.62, number, color=CREAM, fontsize=78, fontweight="bold",
               va="center")
    panel.text(0.09, 0.42, textwrap.fill(title, 24), color=CREAM, fontsize=23,
               fontweight="bold", va="top", linespacing=1.15)
    panel.text(0.09, 0.20, textwrap.fill(subtitle, 40), color=LEAF, fontsize=14, va="top")
    panel.plot([0.09, 0.3], [0.08, 0.08], color=LEAF, lw=2)
    panel.text(0.09, 0.04, "Floresta–atmosfera amazônica · TCC Ilum 2026", color=LEAF,
               fontsize=10.5, va="center")
    target = root / "notebooks/__marimo__/assets" / name / "opengraph.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, facecolor=GREEN)
    plt.close(fig)
    return target


if __name__ == "__main__":
    for key in COVERS:
        print(draw(key))
