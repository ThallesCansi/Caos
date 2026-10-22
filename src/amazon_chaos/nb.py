"""Kit dos cadernos Marimo: figuras e tabelas com nomes estáveis para a monografia.

Uso típico, na primeira célula de um caderno:

    from amazon_chaos import nb
    book = nb.notebook("03_clima")

`book.figure(fig, "ciclo_anual", "Legenda…", region="xingu")` grava PNG (300 dpi) e PDF
em `reports/figures/03_clima/xingu/` e registra a legenda no índice usado por
`make overleaf`. Nada aqui baixa dados.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import marimo as mo
import matplotlib.pyplot as plt
import pandas as pd

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


SCREEN_DPI = 110


@dataclass
class Notebook:
    """Saídas de um caderno, com nomes estáveis para a monografia."""

    name: str

    def _folder(self, base: Path, region: str | None) -> Path:
        folder = base / self.name / region if region else base / self.name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def figure(self, fig, name: str, caption: str, region: str | None = None,
               overleaf: bool = True, width: str = "100%", save: bool = True):
        """Exibe a figura com a legenda e, se `save`, grava PNG (300 dpi) e PDF.

        Com um controle deslizante, passe `save` verdadeiro só no valor de referência, para
        que mexer no controle não sobrescreva a figura da monografia.
        """
        if save:
            folder = self._folder(FIGURES, region)
            # metadados fixos: o mesmo conteúdo gera o mesmo arquivo (diffs só quando muda)
            fig.savefig(folder / f"{name}.png", dpi=300, bbox_inches="tight",
                        metadata={"Software": None})
            fig.savefig(folder / f"{name}.pdf", bbox_inches="tight",
                        metadata={"CreationDate": None, "Producer": None, "Creator": None})
            _register(folder.parent if region else folder, {
                "name": name, "region": region, "caption": caption, "overleaf": overleaf,
                "png": str(folder / f"{name}.png"), "pdf": str(folder / f"{name}.pdf"),
                "commit": _git_commit(),
            })
        # na tela, PNG em resolução de tela: a 300 dpi um mapa passa de 1 MB e o caderno
        # estoura o limite de saída do Marimo; os arquivos da monografia ficam em 300 dpi
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=SCREEN_DPI, bbox_inches="tight")
        plt.close(fig)
        data = base64.b64encode(buffer.getvalue()).decode()
        return mo.vstack([
            mo.Html(f'<img src="data:image/png;base64,{data}" style="width:{width}">'),
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
    """Ponto de partida de todo caderno: raiz do projeto como diretório e estilo comum.

    Fora do repositório (no molab, por exemplo), baixa antes o pacote de visualização.
    """
    from amazon_chaos.bundle import ensure

    os.chdir(ensure())
    style()
    plt.rcParams.update({"figure.dpi": 100, "savefig.dpi": 300})
    return Notebook(name)


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
