"""Estilo e mapas por célula comuns aos cadernos regionais."""

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize

COLORS = {
    "t2m": "#c0504d", "tmin": "#e28b6d", "tmax": "#8f2d2a", "dtr": "#d9822b",
    "rh": "#2a9d8f", "vpd": "#b5832a", "q": "#6f9659", "wind": "#6b7bb0",
    "precip": "#2f7fb5", "sp": "#7a6f9b", "ink": "#263238", "muted": "#8a949c",
}
LABELS = {
    "t2m": "Temperatura média (°C)", "tmin": "Temperatura mínima (°C)",
    "tmax": "Temperatura máxima (°C)", "dtr": "Amplitude térmica diária (°C)",
    "rh": "Umidade relativa (%)", "vpd": "Déficit de pressão de vapor (kPa)",
    "q": "Umidade específica (g/kg)", "wind": "Vento a 10 m (m/s)",
    "precip": "Chuva (mm)", "sp": "Pressão à superfície (hPa)",
}
MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def style():
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 170, "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titlelocation": "left", "axes.titlesize": 11.5, "axes.titleweight": "bold",
        "axes.labelcolor": COLORS["ink"], "axes.edgecolor": "#9aa3a9",
        "xtick.color": "#56626a", "ytick.color": "#56626a",
        "axes.grid": True, "grid.color": "#e4e7ea", "grid.linewidth": 0.7,
        "legend.frameon": False, "figure.facecolor": "white",
    })


def save(fig, folder, name):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / f"{name}.png", bbox_inches="tight")


def map_cells(ax, cells, field, cmap, label, outline=None, norm=None, stipple=None, lines=None,
              legend=True, **kw):
    """Colore cada polígono de célula pelo valor de `field` (DataArray latitude × longitude)."""
    table = field.rename("value").to_dataframe().reset_index()[["latitude", "longitude", "value"]]
    mapped = cells.merge(table, on=["latitude", "longitude"])
    mapped = mapped[np.isfinite(mapped.value)]
    if norm is None:  # o geopandas aplica vmin/vmax só à barra de cor; a norma vale para ambos
        norm = Normalize(kw.pop("vmin", mapped.value.min()), kw.pop("vmax", mapped.value.max()))
    mapped.plot(column="value", ax=ax, cmap=cmap, norm=norm, legend=legend, edgecolor="none",
                **({"legend_kwds": {"shrink": 0.7, "label": label}} if legend else {}), **kw)
    if stipple is not None:
        flags = stipple.rename("flag").to_dataframe().reset_index()
        flagged = cells.merge(flags[flags.flag.astype(bool)], on=["latitude", "longitude"])
        ax.scatter(flagged.longitude, flagged.latitude, s=1.2, color="#222222", alpha=0.55)
    if outline is not None:
        outline.boundary.plot(ax=ax, color=COLORS["ink"], linewidth=0.9)
    if lines is not None:  # rios de contexto, limitados à extensão das células
        w, s, e, n = cells.total_bounds
        lines.plot(ax=ax, color="#1d5d7a", linewidth=1.1, alpha=0.75)
        ax.set(xlim=(w, e), ylim=(s, n))
    ax.set(aspect="equal", xlabel="", ylabel="")
    ax.grid(False)
    ax.tick_params(labelsize=8)
    return mapped


def map_basins(ax, parts, cmap, label, norm=None, vmin=None, vmax=None, lines=None):
    """As duas bacias (vizinhas) no mesmo mapa, com uma só escala de cor.

    `parts` é uma lista de (células, campo, limite) ou (células, campo, limite, pontilhado);
    cada bacia usa as suas células recortadas, então a faixa do divisor não se sobrepõe.
    """
    if norm is None:
        values = np.concatenate([np.ravel(p[1].values) for p in parts])
        values = values[np.isfinite(values)]
        norm = Normalize(values.min() if vmin is None else vmin,
                         values.max() if vmax is None else vmax)
    for k, part in enumerate(parts):
        cells, field, limit = part[:3]
        map_cells(ax, cells, field, cmap, label, outline=limit, norm=norm,
                  stipple=part[3] if len(part) > 3 else None, legend=k == 0)
    w = min(p[0].total_bounds[0] for p in parts)
    s_ = min(p[0].total_bounds[1] for p in parts)
    e = max(p[0].total_bounds[2] for p in parts)
    n = max(p[0].total_bounds[3] for p in parts)
    if lines is not None:
        lines.plot(ax=ax, color="#1d5d7a", linewidth=1.0, alpha=0.7)
    ax.set(xlim=(w - 0.1, e + 0.1), ylim=(s_ - 0.1, n + 0.1))
    return norm


NUMBER = re.compile(
    r"(?<![\w/.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w/])"  # 1,234 e 1,234.5
    r"|(?<![\w/.,])\d+\.\d+(?![\w/])"  # 3.14
)


def pt(text):
    """Números no padrão brasileiro: 508,627.5 → 508.627,5 (datas e intervalos intactos)."""
    return NUMBER.sub(lambda m: m.group().translate(str.maketrans(",.", ".,")), text)

