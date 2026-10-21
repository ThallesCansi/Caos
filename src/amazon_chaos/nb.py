"""Kit dos cadernos Marimo: cabeçalho, região, figuras, tabelas, avisos e proveniência.

Uso típico, na primeira célula de um caderno:

    import marimo as mo
    from amazon_chaos import nb
    book = nb.notebook("03_clima")
    picker = nb.region_picker()

`book.figure(fig, "ciclo_anual", "Legenda…", region="xingu")` grava PNG (300 dpi) e PDF
em `reports/figures/03_clima/xingu/` e registra a legenda no índice usado por
`make overleaf`. Nada aqui baixa dados.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import marimo as mo
import matplotlib.pyplot as plt
import pandas as pd

from amazon_chaos.config import list_regions, load_region
from amazon_chaos.paths import project_root
from amazon_chaos.viz import pt, style

FIGURES = Path("reports/figures")
TABLES = Path("reports/tables")
OVERLEAF = Path("reports/overleaf")


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return out.stdout.strip() + ("+modificado" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido"


def _index_path(folder: Path) -> Path:
    return folder / "index.json"


def _register(folder: Path, entry: dict) -> None:
    path = _index_path(folder)
    items = json.loads(path.read_text()) if path.exists() else []
    items = [i for i in items if (i["name"], i.get("region")) != (entry["name"], entry["region"])]
    items.append(entry)
    items.sort(key=lambda i: (i.get("region") or "", i["name"]))
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2))


@dataclass
class Notebook:
    """Saídas de um caderno, com nomes estáveis para a monografia."""

    name: str

    def _folder(self, base: Path, region: str | None) -> Path:
        folder = base / self.name / region if region else base / self.name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def figure(self, fig, name: str, caption: str, region: str | None = None,
               overleaf: bool = True, width: str = "100%"):
        """Grava a figura, registra a legenda e devolve figura + legenda para exibir."""
        folder = self._folder(FIGURES, region)
        # Metadados fixos: o mesmo conteúdo gera o mesmo arquivo (diffs só quando muda).
        fig.savefig(folder / f"{name}.png", dpi=300, bbox_inches="tight",
                    metadata={"Software": None})
        fig.savefig(folder / f"{name}.pdf", bbox_inches="tight",
                    metadata={"CreationDate": None, "Producer": None, "Creator": None})
        _register(folder.parent if region else folder, {
            "name": name, "region": region, "caption": caption, "overleaf": overleaf,
            "png": str(folder / f"{name}.png"), "pdf": str(folder / f"{name}.pdf"),
            "commit": _git_commit(),
        })
        html = mo.as_html(fig)
        plt.close(fig)
        return mo.vstack([
            mo.Html(f'<div style="width:{width}">{html.text}</div>'),
            mo.Html(f'<p style="font-size:0.88em;color:#5b6770;margin:0 0 0.6em 0">'
                    f'{pt(caption)}</p>'),
        ], gap=0.25)

    def table(self, frame: pd.DataFrame, name: str, caption: str, region: str | None = None,
              overleaf: bool = True, index: bool = False, float_format: str = "%.3g",
              selection=None):
        """Grava CSV e .tex e devolve a tabela interativa com a legenda."""
        folder = self._folder(TABLES, region)
        frame.to_csv(folder / f"{name}.csv", index=index)
        latex = frame.to_latex(index=index, float_format=float_format.__mod__,
                               caption=caption, label=f"tab:{self.name}:{region or ''}:{name}",
                               escape=True)
        (folder / f"{name}.tex").write_text(pt(latex))
        _register(folder.parent if region else folder, {
            "name": name, "region": region, "caption": caption, "overleaf": overleaf,
            "csv": str(folder / f"{name}.csv"), "tex": str(folder / f"{name}.tex"),
            "commit": _git_commit(),
        })
        return mo.vstack([
            mo.Html(f'<p style="font-size:0.88em;color:#5b6770;margin:0">{pt(caption)}</p>'),
            mo.ui.table(frame.reset_index() if index else frame, selection=selection,
                        show_download=True),
        ], gap=0.25)


def notebook(name: str) -> Notebook:
    """Ponto de partida de todo caderno: raiz do projeto como diretório e estilo comum."""
    os.chdir(project_root())
    style()
    plt.rcParams.update({"figure.dpi": 100, "savefig.dpi": 300})
    return Notebook(name)


def region_picker(default: str = "xingu", regions: list[str] | None = None):
    """Seletor de região; `marimo export html … -- --region tapajos` fixa o valor."""
    regions = regions or [r for r in list_regions() if r != "tapajos_caixa"]
    chosen = mo.cli_args().get("region", default)
    if chosen not in list_regions():
        raise ValueError(f"--region {chosen}: use uma de {list_regions()}")
    options = {load_region(r)["name"]: r for r in dict.fromkeys([*regions, chosen])}
    label = next(k for k, v in options.items() if v == chosen)
    return mo.ui.dropdown(options=options, value=label, label="Região")


def header(title: str, question: str, *, stage: str, inputs: list[str], outputs: list[str],
           status: str | None = None):
    """Cabeçalho padrão: título, pergunta do caderno e o que ele lê e grava."""
    rows = "".join(
        f"<tr><th style='text-align:left;padding-right:1em'>{k}</th><td>{v}</td></tr>"
        for k, v in [("Etapa", stage), ("Lê", "<br>".join(inputs)),
                     ("Grava", "<br>".join(outputs))]
    )
    parts = [
        mo.md(f"# {title}"),
        mo.callout(mo.md(f"**Pergunta.** {question}"), kind="info"),
        mo.Html(f"<table style='font-size:0.9em'>{rows}</table>"),
    ]
    if status:
        parts.append(mo.callout(mo.md(status), kind="neutral"))
    return mo.vstack(parts, gap=0.6)


def caveat(text: str, kind: str = "warn"):
    """Limitação ou cuidado de leitura, destacado."""
    return mo.callout(mo.md(text), kind=kind)


def stats(items: dict[str, object], caption: str | None = None):
    """Linha de números-chave (`{"Células": 779, …}`)."""
    cards = [mo.stat(value=pt(f"{v:,}" if isinstance(v, int) else str(v)), label=k,
                     bordered=True) for k, v in items.items()]
    row = mo.hstack(cards, justify="start", gap=1, wrap=True)
    return mo.vstack([row, mo.md(f"<small>{caption}</small>")]) if caption else row


def missing(paths: list[Path | str], command: str):
    """Aviso padronizado quando faltam dados locais, com o comando que os produz."""
    names = "\n".join(f"- `{p}`" for p in paths)
    return mo.callout(mo.md(f"**Dados ausentes.**\n\n{names}\n\nPara produzi-los:\n\n"
                            f"```bash\n{command}\n```"), kind="danger")


def provenance(cfg: dict | None = None, files: list[Path | str] = ()):
    """Bloco recolhido com commit, configuração, versões e arquivos lidos."""
    import importlib.metadata as md

    lines = [f"- **Commit:** `{_git_commit()}`",
             f"- **Executado em:** {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
             f"- **Python:** {sys.version.split()[0]} · marimo {md.version('marimo')}"]
    if cfg:
        lines.append(f"- **Região:** `{cfg['slug']}` · experimento `{cfg['experiment_id']}`")
    rows = []
    for f in files:
        p = Path(f)
        if p.exists():
            stat = p.stat()
            rows.append(f"| `{p}` | {stat.st_size / 2**20:.1f} MiB | "
                        f"{datetime.fromtimestamp(stat.st_mtime, UTC):%Y-%m-%d %H:%M} |")
        else:
            rows.append(f"| `{p}` | ausente | — |")
    body = "\n".join(lines)
    if rows:
        body += "\n\n| Arquivo | Tamanho | Modificado (UTC) |\n|---|---|---|\n" + "\n".join(rows)
    return mo.accordion({"Proveniência": mo.md(body)})


# ── make overleaf ───────────────────────────────────────────────────────────


def export_overleaf(root: Path | None = None) -> list[Path]:
    """Copia figuras (PDF) e tabelas (.tex) marcadas para a monografia, com nomes estáveis."""
    root = Path(root or project_root())
    figures_out, tables_out = root / OVERLEAF / "figuras", root / OVERLEAF / "tabelas"
    for folder in (figures_out, tables_out):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
    copied, lines = [], ["# Figuras e tabelas para a Overleaf", "",
                         "Gerado por `make overleaf`; não editar à mão.", ""]
    for index in sorted((root / FIGURES).glob("*/index.json")) + sorted(
            (root / TABLES).glob("*/index.json")):
        notebook_name = index.parent.name
        for item in json.loads(index.read_text()):
            if not item.get("overleaf"):
                continue
            stem = "_".join(x for x in (notebook_name, item.get("region"), item["name"]) if x)
            source, target = ((item["pdf"], figures_out / f"fig_{stem}.pdf") if "pdf" in item
                              else (item["tex"], tables_out / f"tab_{stem}.tex"))
            shutil.copy2(root / source, target)
            copied.append(target)
            lines.append(f"- `{target.relative_to(root / OVERLEAF)}` — {item['caption']} "
                         f"(commit {item['commit']})")
    (root / OVERLEAF / "INDICE.md").write_text("\n".join(lines) + "\n")
    return copied


if __name__ == "__main__" and sys.argv[1:] == ["overleaf"]:
    print(f"{len(export_overleaf())} arquivos em {OVERLEAF}/")
