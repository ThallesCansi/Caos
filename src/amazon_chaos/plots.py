"""Tema e atalhos dos gráficos interativos (Plotly) dos cadernos.

Um único tema ("tcc") garante a mesma tipografia, cores e grade em todos os cadernos. A
figura exibida no caderno é a mesma que `nb.Notebook.figure` grava em PNG e PDF.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from amazon_chaos.viz import COLORS

FONT = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"
INK = COLORS["ink"]
GRID = "#e7eaee"

_axis = dict(showgrid=True, gridcolor=GRID, zeroline=False, linecolor="#9aa3a9",
             ticks="outside", tickcolor="#9aa3a9", title_standoff=8)
pio.templates["tcc"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=13, color=INK),
    title=dict(font=dict(size=15), x=0.01, xanchor="left"),
    paper_bgcolor="white", plot_bgcolor="white",
    colorway=[COLORS["ink"], COLORS["t2m"], COLORS["precip"], COLORS["q"], COLORS["vpd"],
              COLORS["wind"], "#8f2d2a", "#7a6f9b"],
    xaxis=_axis, yaxis=_axis,
    legend=dict(bgcolor="rgba(255,255,255,0.85)", borderwidth=0, font=dict(size=12)),
    margin=dict(l=60, r=25, t=70, b=55),
    hoverlabel=dict(font=dict(family=FONT, size=12)),
    hovermode="closest",
))
pio.templates.default = "tcc"


def grid(rows: int, cols: int, titles: list[str] | None = None, *, height: int = 420,
         width: int | None = None, **kw) -> go.Figure:
    """Painéis lado a lado com o tema do projeto."""
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles,
                        horizontal_spacing=kw.pop("horizontal_spacing", 0.08),
                        vertical_spacing=kw.pop("vertical_spacing", 0.14), **kw)
    fig.update_layout(height=height, width=width)
    fig.update_annotations(font=dict(size=13, color=INK))
    return fig


def vline(fig: go.Figure, x: float, *, row=None, col=None, color=None, dash="dash",
          text: str | None = None) -> None:
    fig.add_vline(x=x, line=dict(color=color or COLORS["t2m"], dash=dash, width=1.6),
                  row=row, col=col, annotation_text=text, annotation_position="top right",
                  annotation_font=dict(size=11, color=color or COLORS["t2m"]))
