import json
import subprocess

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from amazon_chaos import nb  # noqa: E402


def test_figure_and_table_are_saved_indexed_and_exported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book = nb.Notebook("99_teste")
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    book.figure(fig, "linha", "Uma reta de 1.5 unidade.", region="xingu")
    book.table(pd.DataFrame({"a": [1.25]}), "tabela", "Uma tabela.", overleaf=False)
    folder = tmp_path / "reports/figures/99_teste"
    assert (folder / "xingu/linha.png").exists() and (folder / "xingu/linha.pdf").exists()
    index = json.loads((folder / "index.json").read_text())
    assert index[0]["caption"].startswith("Uma reta") and index[0]["region"] == "xingu"
    assert "1,25" in (tmp_path / "reports/tables/99_teste/tabela.tex").read_text()

    first = (folder / "xingu/linha.pdf").read_bytes()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    book.figure(fig, "linha", "Uma reta de 1.5 unidade.", region="xingu")
    assert (folder / "xingu/linha.pdf").read_bytes() == first  # PDF determinístico
    assert len(json.loads((folder / "index.json").read_text())) == 1  # sem duplicar

    copied = nb.export_overleaf(tmp_path)
    assert [p.name for p in copied] == ["fig_99_teste_xingu_linha.pdf"]  # tabela fora
    assert "Uma reta" in (tmp_path / "reports/overleaf/INDICE.md").read_text()

def _git(path, *args):
    subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)


def test_stamp_ignores_notebook_outputs(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "index.json").write_text("{}")
    (tmp_path / "codigo.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reports" / "index.json").unlink()   # como faz `make notebooks`
    assert not nb._git_commit().endswith("+modificado")
    (tmp_path / "codigo.py").write_text("x = 2\n")
    assert nb._git_commit().endswith("+modificado")
