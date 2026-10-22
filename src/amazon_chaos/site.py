"""Página pública dos cadernos (ramo `gh-pages`): galeria, leitura e execução no molab.

`make site` monta `site/` com uma galeria de cartões (as capas de `make capas`), a versão
de leitura de cada capítulo (os HTML de `make notebooks`, com todas as figuras) e o pacote
de visualização (`amazon_chaos.bundle`). `make publicar` envia `site/` para o ramo
`gh-pages`, servido pelo GitHub Pages.
"""

from __future__ import annotations

# ruff: noqa: E501  (modelo HTML)
import html
import shutil
from pathlib import Path

from amazon_chaos.covers import COVERS
from amazon_chaos.paths import project_root

REPO = "https://github.com/ThallesCansi/Caos"
MOLAB = "https://molab.marimo.io/github/ThallesCansi/Caos/blob/main/notebooks/{name}.py"

PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caos na floresta–atmosfera amazônica</title>
<meta name="description" content="Cadernos do TCC: dinâmica não linear do clima diário nas bacias do Xingu e do Tapajós.">
<meta property="og:image" content="capas/00_inicio.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{ --verde: #1f3b2d; --folha: #8fbf9f; --creme: #f4f1e8; --tinta: #263238;
         --fundo: #fbfaf6; --cartao: #ffffff; --borda: #e4e2da; --suave: #5b6770; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --fundo: #141a17; --cartao: #1c2420; --borda: #2c3631; --tinta: #e8e6df;
           --suave: #a9b3ad; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--fundo); color: var(--tinta);
        font: 16px/1.6 Inter, system-ui, sans-serif; }}
header {{ background: var(--verde); color: var(--creme); padding: 56px 16px 48px; }}
.largura {{ max-width: 1120px; margin: 0 auto; }}
header p.sobre {{ color: var(--folha); font-weight: 600; letter-spacing: .02em; margin: 0 0 12px; }}
h1 {{ font: 600 clamp(28px, 4.4vw, 44px)/1.15 "Source Serif 4", Georgia, serif; margin: 0 0 16px; }}
header p.texto {{ max-width: 760px; margin: 0 0 24px; color: #dcd9cf; }}
header nav a {{ color: var(--creme); margin-right: 20px; font-weight: 600; }}
main {{ padding: 40px 16px 64px; }}
.grade {{ display: grid; gap: 24px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }}
.cartao {{ background: var(--cartao); border: 1px solid var(--borda); border-radius: 14px;
          overflow: hidden; display: flex; flex-direction: column; }}
.cartao img {{ width: 100%; aspect-ratio: 1200 / 630; object-fit: cover; display: block; }}
.corpo {{ padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 8px; flex: 1; }}
.corpo h2 {{ font: 600 19px/1.3 "Source Serif 4", Georgia, serif; margin: 0; }}
.corpo p {{ margin: 0; color: var(--suave); font-size: 15px; }}
.acoes {{ margin-top: auto; padding-top: 10px; display: flex; gap: 10px; flex-wrap: wrap; }}
.acoes a {{ text-decoration: none; font-weight: 600; font-size: 14px; padding: 8px 14px;
           border-radius: 8px; }}
.ler {{ background: var(--verde); color: var(--creme); }}
.rodar {{ border: 1px solid var(--verde); color: var(--tinta); }}
@media (prefers-color-scheme: dark) {{ .rodar {{ border-color: var(--folha); }} }}
footer {{ border-top: 1px solid var(--borda); padding: 28px 16px; color: var(--suave);
         font-size: 14px; }}
footer a {{ color: inherit; }}
</style>
</head>
<body>
<header><div class="largura">
<p class="sobre">TCC · Ilum Escola de Ciência (CNPEM) · 2026</p>
<h1>Caos na floresta–atmosfera amazônica</h1>
<p class="texto">Os cadernos do trabalho de Caio Ruas e Thalles Cansi, com orientação de
Vinicius Wasques: a dinâmica não linear do clima diário em 1.541 células das bacias do
Xingu e do Tapajós, comparada com o desmatamento e o fogo. Cada capítulo pode ser lido
aqui, com todas as figuras, ou aberto no molab para mexer nos controles e no código.</p>
<nav><a href="{repo}">Código no GitHub</a><a href="dados/caos-dados.zip">Pacote de dados (59 MB)</a></nav>
</div></header>
<main><div class="largura grade">
{cards}
</div></main>
<footer><div class="largura">
Dados: ERA5 (Copernicus Climate Change Service, ECMWF), PRODES, DETER e BDQueimadas (INPE),
MapBiomas (coleções 11 e Fogo 5), MOD11A2 (NASA LP DAAC), BHB250 (IBGE/ANA), FUNAI e ICMBio.
Na versão de leitura, os controles mostram a escolha inicial; no molab, eles funcionam.
</div></footer>
</body>
</html>
"""

CARD = """<article class="cartao">
<a href="capitulos/{name}.html"><img src="capas/{name}.png" alt="Capa do capítulo {number}" loading="lazy"></a>
<div class="corpo">
<h2>{number} · {title}</h2>
<p>{subtitle}</p>
<div class="acoes"><a class="ler" href="capitulos/{name}.html">Ler o capítulo</a>
<a class="rodar" href="{molab}">Abrir no molab</a></div>
</div>
</article>"""


def build(root: Path | None = None) -> Path:
    root = Path(root or project_root())
    site = root / "site"
    for folder in ("capitulos", "capas"):
        shutil.rmtree(site / folder, ignore_errors=True)
        (site / folder).mkdir(parents=True)
    cards = []
    for name, (title, subtitle, _) in COVERS.items():
        page = root / "reports/html" / f"{name}.html"
        cover = root / "notebooks/__marimo__/assets" / name / "opengraph.png"
        for path, hint in ((page, "make notebooks"), (cover, "make capas")):
            if not path.exists():
                raise FileNotFoundError(f"{path.relative_to(root)} ausente: rode `{hint}`")
        shutil.copy(page, site / "capitulos" / page.name)
        shutil.copy(cover, site / "capas" / f"{name}.png")
        cards.append(CARD.format(name=name, number=name[:2], title=html.escape(title),
                                 subtitle=html.escape(subtitle),
                                 molab=MOLAB.format(name=name)))
    (site / "index.html").write_text(PAGE.format(cards="\n".join(cards), repo=REPO),
                                     encoding="utf-8")
    (site / ".nojekyll").write_text("")
    return site


if __name__ == "__main__":
    print(build())
