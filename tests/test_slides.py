"""Apresentação (amazon_chaos.slides): o roteiro aponta para figuras existentes e o build roda."""

import json

import pytest
import yaml
from PIL import Image

from amazon_chaos import slides
from amazon_chaos.paths import project_root


def test_roteiro_usa_figuras_dos_indices():
    root = project_root()
    if not list((root / "reports/figures").glob("*/index.json")):
        pytest.skip("índices das figuras ausentes")
    figures = slides._indices(root)
    script = yaml.safe_load((root / slides.ROTEIRO).read_text(encoding="utf-8"))
    keys = [k for s in script["slides"] for k in s.get("figuras", [])]
    keys += [s["fundo"] for s in script["slides"] if s.get("fundo")]
    keys += [s["faixa"]["figura"] for s in script["slides"] if s.get("faixa")]
    assert keys and not [k for k in keys if k not in figures]
    for s in script["slides"]:
        for spot in s.get("destaques") or []:
            assert 0 <= spot["x"] <= 1 and 0 <= spot["y"] <= 1


def test_encaixe_cabe_na_area():
    for ratios in ([3.3], [0.9], [1.2, 1.2], [3.0, 2.5]):
        arrangement, sizes = slides._boxes(ratios, None)
        pad = 2 * slides.BORDA
        if arrangement == "pilha":
            assert sum(h + pad for _, h in sizes) <= slides.AREA_H + 1
        else:
            gaps = slides.VAO * (len(sizes) - 1)
            assert sum(w + pad for w, _ in sizes) + gaps <= slides.AREA_W + 1
        assert all(h + pad <= slides.AREA_H + 1 for _, h in sizes)


def test_build(tmp_path):
    folder = tmp_path / "reports/figures/01_teste"
    folder.mkdir(parents=True)
    Image.new("RGB", (900, 300), "white").save(folder / "a.png")
    (folder / "index.json").write_text(json.dumps([{
        "name": "a", "region": None, "caption": "Figura 1. Teste.", "overleaf": True,
        "png": "reports/figures/01_teste/a.png", "commit": "x"}]), encoding="utf-8")
    (tmp_path / "docs/apresentacao").mkdir(parents=True)
    (tmp_path / slides.ROTEIRO).write_text(yaml.safe_dump({"titulo": "T", "slides": [
        {"tipo": "capa", "titulo": "Capa"},
        {"tipo": "secao", "numero": "I", "titulo": "Parte"},
        {"tipo": "figura", "titulo": "Fig", "mensagem": "m *i*", "figuras": ["01_teste/a"],
         "explicacao": "um\n\ndois", "destaques": [{"x": 0.5, "y": 0.5, "texto": "aqui"}]},
    ]}, allow_unicode=True), encoding="utf-8")
    page = slides.build(tmp_path).read_text(encoding="utf-8")
    assert page.count('<section class="slide') == 3
    assert "<i>i</i>" in page and 'class="ponto"' in page and "Figura 1. Teste." in page
    assert (tmp_path / "reports/apresentacao/figuras/01_teste__a.webp").exists()
