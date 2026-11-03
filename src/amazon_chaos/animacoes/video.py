"""Gravação dos clipes em matplotlib: uma função do tempo vira MP4 (H.264) e pôster PNG."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import imageio_ffmpeg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter

from amazon_chaos.animacoes.tema import DPI

plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()


def gravar(fig, saida: Path, desenhar: Callable[[float], None], duracao: float, *,
           fps: int = 30, qualidade: str = "previa", quadros: int | None = None) -> Path:
    """Chama `desenhar(t)` para cada quadro (t em segundos) e grava; `quadros` faz uma
    renderização relâmpago com poucos quadros espalhados (testes)."""
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    tempos = (np.linspace(0, duracao, quadros) if quadros
              else np.arange(round(duracao * fps)) / fps)
    writer = FFMpegWriter(fps=fps, codec="libx264", bitrate=-1,
                          extra_args=["-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow"])
    with writer.saving(fig, str(saida), dpi=DPI[qualidade]):
        for t in tempos:
            desenhar(float(t))
            writer.grab_frame()
    fig.savefig(saida.with_suffix(".png"), dpi=DPI[qualidade])
    return saida
