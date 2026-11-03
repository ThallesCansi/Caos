"""Apresentação dos resultados: uma página HTML de slides feita das figuras dos cadernos.

`make apresentacao` lê o roteiro (`docs/apresentacao/roteiro.yaml`) e os índices das
figuras (`reports/figures/*/index.json`, refeitos por `make notebooks`) e monta
`reports/apresentacao/`: a página, com CSS e JS embutidos, e as figuras reduzidas. Cada
slide de figura tem um painel "Como ler" com a explicação, a legenda e destaques numerados
sobre a figura; o apêndice é uma galeria de todas as figuras dos índices.
"""

from __future__ import annotations

# ruff: noqa: E501  (modelo HTML)
import csv
import html
import json
import re
import shutil
from pathlib import Path

import yaml
from PIL import Image

from amazon_chaos.covers import COVERS
from amazon_chaos.paths import project_root

ROTEIRO = Path("docs/apresentacao/roteiro.yaml")
SAIDA = Path("reports/apresentacao")
CAPITULOS = "https://thallescansi.github.io/Caos/capitulos/{name}.html"
LARGURA, MINIATURA = 2800, 720  # px das figuras dos slides e das miniaturas

# Geometria do slide de figura, no canvas de 1920 × 1080: a área livre abaixo do título
# e da mensagem, onde as figuras são encaixadas sem distorcer (e os destaques, por cima).
AREA_W, AREA_H, VAO, BORDA = 1696, 640, 28, 18
LIVRE = 1920 - 720 - 112 - 64  # largura à esquerda do painel "Como ler" aberto


# ── figuras ────────────────────────────────────────────────────────────────


def _indices(root: Path) -> dict[str, dict]:
    """Todas as figuras dos índices, pela chave `capitulo/[regiao/]nome`."""
    figures = {}
    for index in sorted((root / "reports/figures").glob("*/index.json")):
        chapter = index.parent.name
        for item in json.loads(index.read_text(encoding="utf-8")):
            key = "/".join(p for p in (chapter, item.get("region"), item["name"]) if p)
            figures[key] = {**item, "key": key, "chapter": chapter}
    if not figures:
        raise FileNotFoundError("reports/figures/*/index.json ausentes: rode `make notebooks`")
    return figures


def _reduce(src: Path, dst: Path, width: int, box: list[float] | None = None) -> tuple[int, int]:
    """Copia `src` reduzida a `width` px (e recortada em `box`, frações), em WebP."""
    with Image.open(src) as image:
        image = image.convert("RGB")
        if box:
            w, h = image.size
            image = image.crop((round(box[0] * w), round(box[1] * h),
                                round(box[2] * w), round(box[3] * h)))
        if image.width > width:
            image = image.resize((width, round(image.height * width / image.width)),
                                 Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        image.save(dst, "WEBP", quality=90, method=4)
        return image.size


def _fit(ratio: float, w: float, h: float) -> tuple[int, int]:
    """Maior caixa de proporção `ratio` (largura/altura) dentro de w × h."""
    return (round(w), round(w / ratio)) if w / ratio <= h else (round(h * ratio), round(h))


def _boxes(ratios: list[float], arrangement: str | None) -> tuple[str, list[tuple[int, int]]]:
    """Arranjo (lado a lado ou em pilha) e tamanho da imagem de cada figura na área livre."""
    n = len(ratios)
    pad = 2 * BORDA
    if n == 1:
        return "lado", [_fit(ratios[0], AREA_W - pad, AREA_H - pad)]
    if arrangement is None:
        arrangement = "pilha" if min(ratios) > 2.2 else "lado"
    if arrangement == "pilha":
        h = (AREA_H - VAO * (n - 1)) / n - pad
        return "pilha", [_fit(r, AREA_W - pad, h) for r in ratios]
    # lado a lado: a largura é repartida na proporção das razões, para alturas iguais
    free = AREA_W - VAO * (n - 1) - pad * n
    h = min(AREA_H - pad, free / sum(ratios))
    return "lado", [(round(h * r), round(h)) for r in ratios]


# ── texto ──────────────────────────────────────────────────────────────────


def _inline(text: str) -> str:
    """Escapa e aplica a única marcação do roteiro: *itálico*."""
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", html.escape(text.strip(), quote=False))


def _paragraphs(text: str | None, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    blocks = [b for b in re.split(r"\n\s*\n", text or "") if b.strip()]
    return "".join(f"<p{attr}>{_inline(' '.join(b.split()))}</p>" for b in blocks)


# ── slides ─────────────────────────────────────────────────────────────────


def _figure_html(figs: list[dict], sizes: list[tuple[int, int]], arrangement: str,
                 spots: list[dict]) -> str:
    cards = []
    for i, (fig, (w, h)) in enumerate(zip(figs, sizes, strict=True)):
        marks = "".join(
            f'<button class="ponto" data-n="{j}" style="left:{s["x"] * 100:.2f}%;top:{s["y"] * 100:.2f}%">{j}</button>'
            for j, s in enumerate(spots, 1) if s.get("figura", 0) == i)
        cards.append(
            f'<figure class="quadro" style="width:{w + 2 * BORDA}px;height:{h + 2 * BORDA}px">'
            f'<div class="imagem" style="width:{w}px;height:{h}px">'
            f'<img src="figuras/{fig["file"]}" alt="{html.escape(fig["caption"])}" '
            f'data-zoom="{fig["key"]}" draggable="false">{marks}</div></figure>')
    # com o painel aberto, o conjunto encolhe para caber à esquerda dele, alinhado à margem
    if arrangement == "pilha":
        width = max(w for w, _ in sizes) + 2 * BORDA
    else:
        width = sum(w + 2 * BORDA for w, _ in sizes) + VAO * (len(sizes) - 1)
    k, ox = min(1, LIVRE / width), (AREA_W - width) / 2
    return (f'<div class="area {arrangement}" style="--k:{k:.3f};--ox:{ox:.0f}px;--tx:{-ox:.0f}px">'
            f'{"".join(cards)}</div>')


def _panel(slide: dict, figs: list[dict]) -> str:
    spots = slide.get("destaques") or []
    items = "".join(f'<li data-n="{j}"><span class="num">{j}</span><span>{_inline(s["texto"])}</span></li>'
                    for j, s in enumerate(spots, 1))
    captions = "".join(f'<p class="legenda">{html.escape(c)}</p>' for c in dict.fromkeys(f["caption"] for f in figs))
    chapters = sorted({f["chapter"] for f in figs})
    links = " · ".join(f'<a href="{CAPITULOS.format(name=c)}" target="_blank" rel="noopener">caderno {c[:2]}</a>'
                       for c in chapters)
    return (f'<aside class="painel"><div class="painel-corpo">'
            f'<p class="rotulo">Como ler</p>{_paragraphs(slide.get("explicacao"))}'
            f'{f"<ol class=destaques>{items}</ol>" if items else ""}'
            f'<p class="rotulo">Legenda</p>{captions}'
            f'<p class="fonte">{links}</p></div></aside>')


def _table_html(root: Path, slide: dict) -> str:
    with open(root / slide["tabela"], encoding="utf-8") as f:
        rows = list(csv.reader(f))
    keep = slide.get("colunas") or list(range(len(rows[0])))
    first, last = slide.get("linhas") or (0, len(rows) - 1)
    rows = [rows[0], *rows[1 + first:1 + last]]
    head = "".join(f"<th>{html.escape(rows[0][c])}</th>" for c in keep)
    body = []
    for row in rows[1:]:
        body.append("<tr>" + "".join(f"<td>{html.escape(row[c])}</td>" for c in keep) + "</tr>")
    return f'<div class="tabela"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _slide(root: Path, slide: dict, figures: dict, used: dict, number: int, section: str) -> str:
    kind = slide["tipo"]
    notes = html.escape(" ".join((slide.get("notas") or "").split()))
    title = _inline(slide.get("titulo", ""))
    attrs = f'data-secao="{html.escape(section)}" data-notas="{notes}"'
    if kind == "capa":
        band = ""
        if "faixa" in slide:
            band = '<img class="faixa" src="figuras/capa_faixa.webp" alt="">'
        return (f'<section class="slide capa" {attrs}>{band}<div class="capa-texto">'
                f'<p class="sobre">{_inline(slide.get("sobre", ""))}</p><h1>{title}</h1>'
                f'{_paragraphs(slide.get("subtitulo"), "sub")}'
                f'<p class="autores">{_inline(slide.get("autores", ""))}</p>'
                f'<p class="orientacao">{_inline(slide.get("orientacao", ""))}</p></div></section>')
    if kind == "secao":
        backdrop = ""
        if slide.get("fundo"):
            backdrop = f'<img class="fundo" src="figuras/mini/{figures[slide["fundo"]]["file"]}" alt="">'
        return (f'<section class="slide secao" {attrs}>{backdrop}<p class="numero">{_inline(slide.get("numero", ""))}</p>'
                f'<h1>{title}</h1>{_paragraphs(slide.get("texto"), "sub")}</section>')
    if kind == "frase":
        cards = "".join(
            f'<div class="item"><p class="item-titulo">{_inline(c["titulo"])}</p>{_paragraphs(c.get("texto"))}</div>'
            for c in slide.get("itens") or [])
        return (f'<section class="slide frase" {attrs}><p class="rotulo-topo">{_inline(slide.get("rotulo", ""))}</p>'
                f'<h2>{title}</h2>{_paragraphs(slide.get("texto"), "texto")}'
                f'{f"<div class=itens>{cards}</div>" if cards else ""}{_footer(number)}</section>')
    if kind == "tabela":
        return (f'<section class="slide tabela-slide" {attrs}><header><h2>{title}</h2>'
                f'{_paragraphs(slide.get("mensagem"), "mensagem")}</header>{_table_html(root, slide)}'
                f'{_footer(number)}</section>')
    if kind == "figura":
        keys = slide["figuras"]
        missing = [k for k in keys if k not in figures]
        if missing:
            raise KeyError(f"figura(s) do roteiro sem índice: {', '.join(missing)}")
        figs = [figures[k] for k in keys]
        for f in figs:
            used.setdefault(f["key"], number)
        arrangement, sizes = _boxes([f["ratio"] for f in figs], slide.get("arranjo"))
        spots = slide.get("destaques") or []
        return (f'<section class="slide figura" {attrs}><header><h2>{title}</h2>'
                f'{_paragraphs(slide.get("mensagem"), "mensagem")}</header>'
                f'{_figure_html(figs, sizes, arrangement, spots)}{_panel(slide, figs)}'
                f'{_footer(number, explain=True, spots=bool(spots))}</section>')
    raise ValueError(f"tipo de slide desconhecido: {kind}")


def _footer(number: int, explain: bool = False, spots: bool = False) -> str:
    buttons = ""
    if explain:
        buttons = ('<button class="botao explicar" title="Como ler (E)">Como ler <kbd>E</kbd></button>')
    return (f'<footer class="rodape"><span class="rodape-secao"></span>'
            f'<span class="rodape-acoes">{buttons}<span class="pagina">{number}</span></span></footer>')


def _gallery(figures: dict, used: dict) -> str:
    by_chapter: dict[str, list[dict]] = {}
    for fig in figures.values():
        by_chapter.setdefault(fig["chapter"], []).append(fig)
    parts = []
    for chapter, figs in sorted(by_chapter.items()):
        cards = []
        for f in figs:
            where = f'<span class="no-slide">slide {used[f["key"]]}</span>' if f["key"] in used else ""
            region = f' · {f["region"].capitalize()}' if f.get("region") else ""
            cards.append(
                f'<button class="cartao" data-zoom="{f["key"]}"><img src="figuras/mini/{f["file"]}" alt="" loading="lazy">'
                f'<span class="cartao-nome">{html.escape(f["name"].replace("_", " "))}{html.escape(region)}{where}</span></button>')
        title = COVERS[chapter][0] if chapter in COVERS else chapter[3:].replace("_", " ")
        parts.append(f'<h3>{chapter[:2]} · {html.escape(title)}</h3>'
                     f'<div class="cartoes">{"".join(cards)}</div>')
    return "".join(parts)


# ── página ─────────────────────────────────────────────────────────────────


def build(root: Path | None = None) -> Path:
    root = Path(root or project_root())
    script = yaml.safe_load((root / ROTEIRO).read_text(encoding="utf-8"))
    figures = _indices(root)
    out = root / SAIDA
    shutil.rmtree(out, ignore_errors=True)
    (out / "figuras/mini").mkdir(parents=True)
    for fig in figures.values():
        fig["file"] = fig["key"].replace("/", "__") + ".webp"
        w, h = _reduce(root / fig["png"], out / "figuras" / fig["file"], LARGURA)
        _reduce(root / fig["png"], out / "figuras/mini" / fig["file"], MINIATURA)
        fig["ratio"] = w / h
    for slide in script["slides"]:
        if slide["tipo"] == "capa" and "faixa" in slide:
            band = slide["faixa"]
            _reduce(root / figures[band["figura"]]["png"], out / "figuras/capa_faixa.webp",
                    LARGURA, band.get("recorte"))

    used: dict[str, int] = {}
    sections, section = [], ""
    for number, slide in enumerate(script["slides"], 1):
        if slide["tipo"] == "secao":
            section = slide.get("rodape") or slide.get("titulo", "")
        sections.append(_slide(root, slide, figures, used, number, section))
    zoom = {k: {"src": f"figuras/{f['file']}", "caption": f["caption"], "slide": used.get(k)}
            for k, f in figures.items()}
    page = (PAGE.replace("{{titulo}}", html.escape(script["titulo"]))
            .replace("{{autores}}", html.escape(script.get("autores", "")))
            .replace("{{slides}}", "\n".join(sections))
            .replace("{{galeria}}", _gallery(figures, used))
            .replace("{{zoom}}", json.dumps(zoom, ensure_ascii=False).replace("</", "<\\/")))
    (out / "index.html").write_text(page, encoding="utf-8")
    return out / "index.html"


PAGE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{titulo}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root { --mata: #13201a; --mata2: #1a2b22; --linha: #2d4237; --creme: #f1ede2;
        --suave: #a7b5ab; --fogo: #e07b39; --ar: #6aa7dc; --folha: #8fbf9f; --papel: #fbfaf6;
        --serif: "Source Serif 4", Georgia, serif; --sans: Inter, system-ui, sans-serif; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: #0b120e; color: var(--creme);
             font-family: var(--sans); overflow: hidden; }
button { font: inherit; color: inherit; }
#palco { position: fixed; inset: 0; display: grid; place-items: center; }
#deck { position: relative; width: 1920px; height: 1080px; transform-origin: center; flex: none; }
.slide { position: absolute; inset: 0; background: var(--mata); overflow: hidden;
         opacity: 0; visibility: hidden; transition: opacity .35s ease, visibility 0s .35s; }
.slide.atual { opacity: 1; visibility: visible; transition: opacity .35s ease; }
.slide p { margin: 0; }
h1, h2 { font-family: var(--serif); font-weight: 600; margin: 0; letter-spacing: -.01em; }

/* capa */
.capa { background: radial-gradient(120% 90% at 85% 0%, #21372b 0%, var(--mata) 55%, #0e1712 100%); }
.capa .faixa { position: absolute; left: 0; right: 0; bottom: 0; width: 100%; height: 150px;
               object-fit: cover; opacity: .9; }
.capa-texto { position: absolute; left: 128px; top: 150px; width: 1500px; display: flex;
              flex-direction: column; gap: 28px; }
.capa .sobre { color: var(--folha); font-size: 26px; font-weight: 600; letter-spacing: .08em;
               text-transform: uppercase; }
.capa h1 { font-size: 96px; line-height: 1.04; }
.capa .sub { font-family: var(--serif); font-size: 36px; line-height: 1.35; color: #d8d4c8;
             font-style: italic; max-width: 1350px; }
.capa .autores { font-size: 32px; font-weight: 500; margin-top: 36px; }
.capa .orientacao { font-size: 26px; color: var(--suave); }

/* seção */
.secao { display: flex; flex-direction: column; justify-content: center; padding: 0 160px;
         background: linear-gradient(100deg, #0e1712 0%, var(--mata) 60%, #1c3326 100%); }
.secao .fundo { position: absolute; right: -40px; top: 50%; width: 1100px; transform: translateY(-50%);
               opacity: .16; filter: grayscale(.3); border-radius: 18px;
               mask-image: linear-gradient(90deg, transparent 0%, #000 45%);
               -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 45%); }
.secao > :not(.fundo) { position: relative; }
.secao .numero { font-family: var(--serif); font-size: 200px; line-height: 1; color: var(--fogo);
                 font-weight: 400; margin-bottom: 24px; }
.secao h1 { font-size: 104px; line-height: 1.05; max-width: 1500px; }
.secao .sub { font-size: 34px; line-height: 1.45; color: var(--suave); max-width: 1300px;
              margin-top: 36px; font-family: var(--serif); }

/* frase */
.frase { padding: 120px 128px 160px; display: flex; flex-direction: column; gap: 40px; }
.rotulo-topo { color: var(--fogo); font-size: 24px; font-weight: 600; letter-spacing: .1em;
               text-transform: uppercase; }
.frase h2 { font-size: 72px; line-height: 1.12; max-width: 1600px; }
.frase .texto { font-size: 34px; line-height: 1.5; color: #d8d4c8; max-width: 1500px;
                font-family: var(--serif); }
.itens { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 32px; margin-top: auto; }
.item { background: var(--mata2); border: 1px solid var(--linha); border-top: 4px solid var(--fogo);
        border-radius: 14px; padding: 32px 36px; display: flex; flex-direction: column; gap: 14px; }
.item:nth-child(2) { border-top-color: var(--ar); }
.item:nth-child(3) { border-top-color: var(--folha); }
.item-titulo { font-family: var(--serif); font-size: 36px; font-weight: 600; }
.item p:not(.item-titulo) { font-size: 26px; line-height: 1.45; color: var(--suave); }

/* figura e tabela */
.slide header { position: absolute; left: 112px; right: 112px; top: 84px; display: flex;
                flex-direction: column; gap: 18px; }
.slide header h2 { font-size: 60px; line-height: 1.1; }
.mensagem { font-size: 30px; line-height: 1.38; color: #cfd6cf; max-width: 1580px; }
.area { position: absolute; left: 112px; top: 300px; width: 1696px; height: 640px; display: flex;
        gap: 28px; align-items: center; justify-content: center; }
.area.pilha { flex-direction: column; }
.quadro { margin: 0; background: var(--papel); border-radius: 16px; padding: 18px; flex: none;
          box-shadow: 0 24px 60px rgba(0, 0, 0, .35); transition: transform .45s ease; }
.imagem { position: relative; }
.imagem img { width: 100%; height: 100%; display: block; cursor: zoom-in; user-select: none; }
.ponto { position: absolute; width: 46px; height: 46px; margin: -23px 0 0 -23px; border-radius: 50%;
         border: 3px solid var(--papel); background: var(--fogo); color: #fff; font-weight: 700;
         font-size: 22px; cursor: pointer; opacity: 0; transform: scale(.4); pointer-events: none;
         transition: opacity .25s, transform .25s; box-shadow: 0 4px 14px rgba(0,0,0,.4); }
.mostra-pontos .ponto { opacity: 1; transform: scale(1); pointer-events: auto; }
.ponto.ativo { background: var(--ar); transform: scale(1.25); }
.tabela { position: absolute; left: 112px; right: 112px; top: 250px; bottom: 112px; overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: 22px; line-height: 1.34; }
th { text-align: left; color: var(--folha); font-weight: 600; font-size: 20px; letter-spacing: .06em;
     text-transform: uppercase; padding: 0 18px 12px 0; border-bottom: 2px solid var(--linha); }
td { padding: 12px 22px 12px 0; border-bottom: 1px solid var(--linha); vertical-align: top; color: #dcdcd2; }
td:first-child { color: var(--fogo); white-space: nowrap; font-weight: 600; }
td:nth-child(2) { font-family: var(--serif); font-size: 25px; color: var(--creme); width: 46%; }

/* painel "Como ler" */
.painel { position: absolute; top: 0; right: 0; bottom: 0; width: 720px; background: rgba(15, 25, 20, .97);
          border-left: 4px solid var(--fogo); transform: translateX(100%); transition: transform .4s ease;
          box-shadow: -30px 0 60px rgba(0, 0, 0, .4); z-index: 3; }
.explica .painel { transform: none; }
.area { transition: transform .4s ease; transform-origin: var(--ox) 50%; }
.explica .area { transform: translateX(var(--tx)) scale(var(--k)); }
.explica header { right: 800px; }
.painel-corpo { position: absolute; inset: 0 0 112px 0; padding: 72px 64px 24px; overflow-y: auto;
                display: flex; flex-direction: column; gap: 20px; }
.painel-corpo p { font-size: 25px; line-height: 1.55; color: #e2e0d7; font-family: var(--serif); }
.painel .rotulo { font-family: var(--sans); color: var(--fogo); font-size: 22px; font-weight: 600;
                  letter-spacing: .1em; text-transform: uppercase; margin-top: 12px; }
.painel .legenda { font-size: 21px; color: var(--suave); font-family: var(--sans); line-height: 1.5; }
.painel .fonte a { color: var(--folha); font-size: 22px; font-family: var(--sans); }
.destaques { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.destaques li { display: flex; gap: 18px; font-size: 24px; line-height: 1.45; font-family: var(--serif);
                color: #e2e0d7; padding: 10px 12px; border-radius: 10px; cursor: default; }
.destaques li.ativo { background: #22382c; }
.num { flex: none; width: 38px; height: 38px; border-radius: 50%; background: var(--fogo); color: #fff;
       font: 700 19px/38px var(--sans); text-align: center; }

/* rodapé */
.rodape { position: absolute; left: 112px; right: 112px; bottom: 44px; height: 48px; display: flex;
          align-items: center; justify-content: space-between; font-size: 22px; color: var(--suave); z-index: 4; }
.rodape-secao { letter-spacing: .04em; }
.rodape-acoes { display: flex; gap: 28px; align-items: center; }
.botao { background: transparent; border: 1.5px solid var(--linha); border-radius: 999px; padding: 8px 20px;
         font-size: 22px; color: var(--creme); cursor: pointer; display: flex; gap: 10px; align-items: center; }
.botao:hover, .explica .explicar { border-color: var(--fogo); color: var(--fogo); }
kbd { font: 600 16px var(--sans); border: 1px solid currentColor; border-radius: 5px; padding: 1px 7px; opacity: .7; }
.pagina { font-variant-numeric: tabular-nums; min-width: 40px; text-align: right; }
#progresso { position: absolute; left: 0; bottom: 0; height: 6px; background: var(--fogo); transition: width .35s; z-index: 10; }

/* camadas: visão geral, galeria, zoom, ajuda */
.camada { position: fixed; inset: 0; background: #0b120e; z-index: 20; display: none;
          overflow-y: auto; padding: 48px 5vw 80px; }
.camada.aberta { display: block; }
.camada h2 { font-family: var(--serif); font-size: 34px; margin: 0 0 28px; }
.camada h3 { font-family: var(--serif); font-weight: 600; font-size: 22px; margin: 36px 0 14px; color: var(--folha); }
.fechar { position: fixed; top: 20px; right: 28px; z-index: 30; background: none; border: none;
          font-size: 38px; color: var(--creme); cursor: pointer; }
#miniaturas { display: grid; grid-template-columns: repeat(auto-fill, minmax(288px, 1fr)); gap: 22px; }
.mini { position: relative; aspect-ratio: 16 / 9; border-radius: 8px; overflow: hidden; cursor: pointer;
        outline: 2px solid transparent; background: var(--mata); }
.mini:hover, .mini.atual { outline-color: var(--fogo); }
.mini > .slide, .ap-tela > .slide { inset: auto; left: 0; top: 0; width: 1920px; height: 1080px; opacity: 1;
  visibility: visible; transform-origin: 0 0; pointer-events: none; transition: none; }
.mini span { position: absolute; left: 8px; bottom: 6px; font-size: 13px; background: rgba(0,0,0,.6);
             padding: 2px 7px; border-radius: 4px; }
.cartoes { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.cartao { background: var(--papel); border: none; border-radius: 10px; padding: 10px; cursor: zoom-in;
          display: flex; flex-direction: column; gap: 8px; text-align: left; }
.cartao img { width: 100%; aspect-ratio: 16 / 10; object-fit: contain; }
.cartao-nome { color: #263238; font-size: 14px; display: flex; justify-content: space-between; gap: 8px; }
.no-slide { color: var(--fogo); font-weight: 600; white-space: nowrap; }
#zoom { padding: 0; overflow: hidden; cursor: grab; }
#zoom.arrastando { cursor: grabbing; }
#zoom img { position: absolute; left: 0; top: 0; transform-origin: 0 0; background: var(--papel);
            border-radius: 6px; user-select: none; }
#zoom-legenda { position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); width: min(1100px, 92vw);
                background: rgba(15, 25, 20, .94); border: 1px solid var(--linha); border-radius: 12px;
                padding: 14px 20px; font-size: 15px; line-height: 1.5; color: #d8d4c8; }
#zoom-legenda a { color: var(--fogo); cursor: pointer; }
#ajuda { max-width: 640px; margin: 10vh auto 0; display: none; }
#ajuda.aberta { display: block; }
#ajuda-camada dl { display: grid; grid-template-columns: 120px 1fr; gap: 12px 20px; font-size: 18px; }
#ajuda-camada dt { text-align: right; }
#ajuda-camada dd { margin: 0; color: var(--suave); }

/* apresentador */
body.apresentador { overflow: auto; background: #0b120e; }
body.apresentador #palco, body.apresentador #progresso { display: none; }
#ap { display: none; padding: 24px; gap: 24px; grid-template-columns: 1.6fr 1fr; height: 100vh; }
body.apresentador #ap { display: grid; }
.ap-tela { position: relative; aspect-ratio: 16 / 9; overflow: hidden; border-radius: 8px; background: var(--mata); }
#ap-dir { display: flex; flex-direction: column; gap: 18px; min-height: 0; }
#ap-notas { flex: 1; overflow-y: auto; font: 22px/1.55 var(--serif); color: #e2e0d7; background: var(--mata2);
            border-radius: 8px; padding: 20px 24px; }
#ap-topo { display: flex; justify-content: space-between; font-size: 22px; color: var(--suave); }
#ap-relogio { font-variant-numeric: tabular-nums; color: var(--creme); font-size: 32px; }

@media print {
  @page { size: 1920px 1080px; margin: 0; }
  html, body { overflow: visible; height: auto; background: none; }
  #palco { position: static; display: block; }
  #deck { transform: none !important; width: auto; height: auto; }
  .slide { position: relative; width: 1920px; height: 1080px; opacity: 1; visibility: visible;
           break-after: page; transition: none; }
  .painel, .botao, #progresso, .camada, .fechar, #ap { display: none !important; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>
</head>
<body>
<div id="palco"><div id="deck">
{{slides}}
<div id="progresso"></div>
</div></div>

<div class="camada" id="geral"><h2>Visão geral</h2><div id="miniaturas"></div></div>
<div class="camada" id="galeria"><h2>Galeria de todas as figuras</h2>{{galeria}}</div>
<div class="camada" id="zoom"><img alt=""><div id="zoom-legenda"></div></div>
<div class="camada" id="ajuda-camada"><div id="ajuda" class="aberta"><h2>Atalhos</h2><dl>
<dt><kbd>→</kbd> <kbd>espaço</kbd></dt><dd>próximo slide</dd>
<dt><kbd>←</kbd></dt><dd>slide anterior</dd>
<dt><kbd>E</kbd></dt><dd>abre o painel "Como ler" da figura, com os destaques</dd>
<dt><kbd>D</kbd></dt><dd>mostra ou esconde só os destaques numerados</dd>
<dt>clique</dt><dd>na figura: zoom com roda do mouse e arraste</dd>
<dt><kbd>O</kbd></dt><dd>visão geral de todos os slides</dd>
<dt><kbd>G</kbd></dt><dd>galeria com todas as figuras do trabalho</dd>
<dt><kbd>P</kbd></dt><dd>janela do apresentador (notas, próximo slide, relógio)</dd>
<dt><kbd>F</kbd></dt><dd>tela cheia</dd>
<dt><kbd>Esc</kbd></dt><dd>fecha o que estiver aberto</dd>
</dl></div></div>
<button class="fechar" hidden aria-label="Fechar">×</button>

<div id="ap"><div style="display:flex;flex-direction:column;gap:12px;min-height:0">
<div id="ap-topo"><span id="ap-pos"></span><span id="ap-relogio">00:00</span></div>
<div class="ap-tela" id="ap-atual"></div></div>
<div id="ap-dir"><div id="ap-topo2" style="color:var(--suave);font-size:18px">A seguir</div>
<div class="ap-tela" id="ap-proximo"></div><div id="ap-notas"></div></div></div>

<script>
const ZOOM = {{zoom}};
const slides = [...document.querySelectorAll('#deck > .slide')];
const deck = document.getElementById('deck');
const presenter = location.hash === '#apresentador';
const canal = 'BroadcastChannel' in window ? new BroadcastChannel('caos-apresentacao') : null;
let atual = 0;

slides.forEach(s => { const r = s.querySelector('.rodape-secao'); if (r) r.textContent = s.dataset.secao; });

function escala() {
  const k = Math.min(innerWidth / 1920, innerHeight / 1080);
  deck.style.transform = `scale(${k})`;
}
addEventListener('resize', escala); escala();

function ir(n, avisar = true) {
  n = Math.max(0, Math.min(slides.length - 1, n));
  slides[atual].classList.remove('atual', 'explica', 'mostra-pontos');
  atual = n;
  slides[atual].classList.add('atual');
  document.getElementById('progresso').style.width = `${100 * (atual + 1) / slides.length}%`;
  if (!presenter) history.replaceState(null, '', `#${atual + 1}`);
  if (avisar && canal) canal.postMessage({ slide: atual });
  if (presenter) desenhaApresentador();
}

function camadaAberta() { return document.querySelector('.camada.aberta'); }
function fecharCamadas() {
  document.querySelectorAll('.camada.aberta').forEach(c => c.classList.remove('aberta'));
  document.querySelector('.fechar').hidden = true;
}
function abrir(id) {
  fecharCamadas();
  document.getElementById(id).classList.add('aberta');
  document.querySelector('.fechar').hidden = false;
}
document.querySelector('.fechar').onclick = fecharCamadas;

function explicar(s = slides[atual]) {
  if (!s.classList.contains('figura')) return;
  const on = !s.classList.contains('explica');
  s.classList.toggle('explica', on);
  s.classList.toggle('mostra-pontos', on);
}
function pontos(s = slides[atual]) {
  if (s.querySelector('.ponto')) s.classList.toggle('mostra-pontos');
}
slides.forEach(s => {
  s.querySelector('.explicar')?.addEventListener('click', () => explicar(s));
  const marca = n => s.querySelectorAll('[data-n]').forEach(e => e.classList.toggle('ativo', e.dataset.n === n));
  s.querySelectorAll('[data-n]').forEach(e => {
    e.addEventListener('mouseenter', () => marca(e.dataset.n));
    e.addEventListener('mouseleave', () => marca(null));
    if (e.classList.contains('ponto')) e.addEventListener('click', ev => {
      ev.stopPropagation(); if (!s.classList.contains('explica')) explicar(s); marca(e.dataset.n);
    });
  });
});

// visão geral
function miniatura(s, alvo, largura) {
  const c = s.cloneNode(true);
  c.classList.remove('explica', 'mostra-pontos'); c.classList.add('atual');
  c.style.transform = `scale(${largura / 1920})`;
  alvo.replaceChildren(c);
}
function visaoGeral() {
  const grade = document.getElementById('miniaturas');
  if (!grade.children.length) slides.forEach((s, i) => {
    const m = document.createElement('div'); m.className = 'mini';
    m.onclick = () => { fecharCamadas(); ir(i); };
    grade.append(m);
  });
  abrir('geral');
  [...grade.children].forEach((m, i) => {
    if (!m.firstChild) { miniatura(slides[i], m, m.clientWidth); const t = document.createElement('span'); t.textContent = i + 1; m.append(t); }
    m.classList.toggle('atual', i === atual);
  });
  grade.children[atual].scrollIntoView({ block: 'center' });
}

// zoom
const zoom = document.getElementById('zoom'), zimg = zoom.querySelector('img');
let zk = 1, zx = 0, zy = 0, arraste = null;
function zaplica() { zimg.style.transform = `translate(${zx}px, ${zy}px) scale(${zk})`; }
function zoomAbre(key) {
  const f = ZOOM[key]; if (!f) return;
  abrir('zoom');
  const leg = document.getElementById('zoom-legenda');
  leg.textContent = f.caption;
  if (f.slide && f.slide !== atual + 1) {
    const a = document.createElement('a'); a.textContent = `  Ir ao slide ${f.slide}`;
    a.onclick = () => { fecharCamadas(); ir(f.slide - 1); }; leg.append(a);
  }
  zimg.onload = () => {
    const w = innerWidth * .94, h = innerHeight * .8;
    zk = Math.min(w / zimg.naturalWidth, h / zimg.naturalHeight);
    zx = (innerWidth - zimg.naturalWidth * zk) / 2; zy = (innerHeight * .86 - zimg.naturalHeight * zk) / 2;
    zaplica();
  };
  zimg.src = f.src;
}
zoom.addEventListener('wheel', e => {
  e.preventDefault();
  const f = Math.exp(-e.deltaY * .0015);
  zx = e.clientX - (e.clientX - zx) * f; zy = e.clientY - (e.clientY - zy) * f; zk *= f; zaplica();
}, { passive: false });
zoom.addEventListener('pointerdown', e => {
  if (e.target.closest('#zoom-legenda')) return;
  arraste = { x: e.clientX - zx, y: e.clientY - zy, mx: e.clientX, my: e.clientY }; zoom.classList.add('arrastando');
});
addEventListener('pointermove', e => { if (arraste) { zx = e.clientX - arraste.x; zy = e.clientY - arraste.y; zaplica(); } });
addEventListener('pointerup', e => {
  if (arraste && Math.hypot(e.clientX - arraste.mx, e.clientY - arraste.my) < 4 && e.target === zoom) fecharCamadas();
  arraste = null; zoom.classList.remove('arrastando');
});
document.addEventListener('click', e => {
  const z = e.target.closest('[data-zoom]');
  if (z && !e.target.closest('#ap')) zoomAbre(z.dataset.zoom);
});

// apresentador
let inicio = null;
function desenhaApresentador() {
  miniatura(slides[atual], document.getElementById('ap-atual'), document.getElementById('ap-atual').clientWidth);
  const prox = document.getElementById('ap-proximo');
  if (atual + 1 < slides.length) miniatura(slides[atual + 1], prox, prox.clientWidth); else prox.replaceChildren();
  document.getElementById('ap-notas').textContent = slides[atual].dataset.notas || '—';
  const secao = slides[atual].dataset.secao;
  document.getElementById('ap-pos').textContent = `${atual + 1} / ${slides.length}${secao ? ' · ' + secao : ''}`;
}
if (presenter) {
  document.body.classList.add('apresentador');
  inicio = Date.now();
  setInterval(() => {
    const s = Math.floor((Date.now() - inicio) / 1000);
    document.getElementById('ap-relogio').textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  }, 1000);
  addEventListener('resize', desenhaApresentador);
}
if (canal) {
  canal.onmessage = e => {
    if (e.data.pergunta && !presenter) canal.postMessage({ slide: atual });
    else if (typeof e.data.slide === 'number' && e.data.slide !== atual) ir(e.data.slide, false);
  };
  if (presenter) canal.postMessage({ pergunta: true });
}

addEventListener('keydown', e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  if (k === 'Escape') {
    if (camadaAberta()) fecharCamadas();
    else slides[atual].classList.remove('explica', 'mostra-pontos');
    return;
  }
  const aberta = camadaAberta();
  if (aberta && aberta.id !== 'geral') return;
  if (['ArrowRight', 'PageDown', ' ', 'Enter'].includes(k)) { e.preventDefault(); fecharCamadas(); ir(atual + 1); }
  else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(k)) { e.preventDefault(); fecharCamadas(); ir(atual - 1); }
  else if (k === 'Home') ir(0);
  else if (k === 'End') ir(slides.length - 1);
  else if (k === 'e' || k === 'E') explicar();
  else if (k === 'd' || k === 'D') pontos();
  else if (k === 'o' || k === 'O') aberta ? fecharCamadas() : visaoGeral();
  else if (k === 'g' || k === 'G') abrir('galeria');
  else if (k === 'p' || k === 'P') window.open(location.pathname + '#apresentador', 'caos-apresentador', 'width=1280,height=800');
  else if (k === 'f' || k === 'F') document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
  else if (k === '?' || k === 'h' || k === 'H') abrir('ajuda-camada');
});
let toque = null;
addEventListener('touchstart', e => { toque = e.touches[0].clientX; }, { passive: true });
addEventListener('touchend', e => {
  if (toque === null || camadaAberta()) return;
  const dx = e.changedTouches[0].clientX - toque;
  if (Math.abs(dx) > 60) ir(atual + (dx < 0 ? 1 : -1));
  toque = null;
});

const comPainel = /^#\d+e$/.test(location.hash);  // #12e abre o slide 12 com o painel
const comGaleria = location.hash === '#galeria';
ir(presenter ? 0 : (parseInt(location.hash.slice(1), 10) || 1) - 1, false);
if (comPainel) explicar();
if (comGaleria) abrir('galeria');
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(build())
