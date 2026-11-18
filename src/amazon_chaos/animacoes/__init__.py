"""Clipes animados do TCC: peças avulsas, mudas, para a defesa e as palestras.

`python -m amazon_chaos.animacoes [nome …] [--qualidade previa|final|4k] [--claro]` grava cada
clipe (timelapse de mapa ou cena do Manim) em `reports/animacoes/<nome>.mp4`, com o último
quadro como pôster ao lado. Sem nomes, lista os clipes. Depende do grupo opcional `animacao`
(`uv sync --group animacao`); o `--claro` vale só para os timelapses.
"""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path

SAIDA = Path("reports/animacoes")


def _clipes() -> dict:
    from amazon_chaos.animacoes import mapas

    return {
        "anomalia-t2m": partial(mapas.anomalia, "t2m"),
        "anomalia-vpd": partial(mapas.anomalia, "vpd"),
        "anomalia-precip": partial(mapas.anomalia, "precip"),
        "fogo": mapas.fogo,
        "desmatamento": mapas.desmatamento,
        "ano-chuva": partial(mapas.ano_medio, "precip"),
        "ano-vpd": partial(mapas.ano_medio, "vpd"),
    }


PECAS = ["substitutas"]  # peças conceituais em matplotlib, com cronograma próprio
# peças em Manim (amazon_chaos.animacoes.cenas_manim)
CENAS = ["trajetorias", "bifurcacao", "lorenz"]
MANIM_PYTHON = Path.home() / "miniconda3/envs/manim/bin/python"


def _manim(nome: str, qualidade: str) -> None:
    """Renderiza a cena aqui, se o Manim estiver instalado, ou no Python do ambiente conda."""
    try:
        from amazon_chaos.animacoes import cenas_manim
    except ImportError:
        import os
        import subprocess

        if nome == "lorenz":  # a cena lê a série da bacia, preparada aqui, no ambiente do uv
            from amazon_chaos.animacoes import dados

            dados.takens()
        python = os.environ.get("MANIM_PYTHON", str(MANIM_PYTHON))
        env = {**os.environ, "PYTHONPATH": "src"}
        subprocess.run([python, "-m", "amazon_chaos.animacoes", nome, "--qualidade", qualidade],
                       env=env, check=True)
        return
    sufixo = "" if qualidade == "final" else f"-{qualidade}"
    saida = cenas_manim.renderizar(cenas_manim.CENAS[nome], SAIDA / f"{nome}{sufixo}.mp4",
                                   qualidade)
    print(f"→ {saida}")


def main(argv: list[str] | None = None) -> None:
    from amazon_chaos.paths import project_root

    parser = argparse.ArgumentParser(prog="python -m amazon_chaos.animacoes")
    parser.add_argument("nomes", nargs="*")
    parser.add_argument("--qualidade", choices=["previa", "final", "4k"], default="previa")
    parser.add_argument("--claro", action="store_true", help="fundo de papel, para slides claros")
    args = parser.parse_args(argv)
    if args.nomes and all(nome in CENAS for nome in args.nomes):
        clipes = {}  # no ambiente do Manim não há matplotlib para os timelapses
    else:
        clipes = _clipes()
    if not args.nomes:
        print("Timelapses:", ", ".join(clipes))
        print("Peças em matplotlib:", ", ".join(PECAS))
        print("Manim:", ", ".join(CENAS))
        return
    import os

    os.chdir(project_root())
    for nome in args.nomes:
        sufixo = ("-claro" if args.claro else "") + ("" if args.qualidade == "final"
                                                     else f"-{args.qualidade}")
        if nome in CENAS:
            _manim(nome, args.qualidade)
            continue
        if nome in PECAS:
            from amazon_chaos.animacoes import substitutas

            saida = substitutas.maquina(SAIDA / f"{nome}{sufixo}.mp4", args.qualidade,
                                        claro=args.claro)
            print(f"→ {saida}")
            continue
        from amazon_chaos.animacoes.mapas import mapa_animado

        saida = mapa_animado(clipes[nome](), SAIDA / f"{nome}{sufixo}.mp4",
                             args.qualidade, args.claro)
        print(f"→ {saida}")
