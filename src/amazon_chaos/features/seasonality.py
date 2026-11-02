"""Memória e variância sazonais por célula (G2a): a explicação alternativa da associação.

O gate realista mostrou que um AR(1) cuja memória muda com o dia do ano já faz os padrões
ordinais e a D2 do VPD rejeitarem as substitutas (D-029). Se a força dessa sazonalidade
varia entre células junto com a perda antecedente, ela pode explicar a associação do z
desses descritores com a perturbação. Por célula e variável (t2m e VPD), com o procedimento
fixo de `synthetic.fit_realistic` na normal 1991–2020:

- `phi_media` e `phi_amplitude`: média e amplitude (máximo − mínimo) de φ(dia do ano);
- `sd_razao`: razão entre o maior e o menor desvio sazonal da anomalia;
- `ciclo_frac`: fração da variância da série bruta explicada pelo ciclo sazonal médio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.nonlinear.batch import NORMAL, load_cubes
from amazon_chaos.nonlinear.synthetic import fit_realistic

VARIABLES = {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"}


def series_seasonality(raw: pd.Series) -> dict[str, float]:
    params = fit_realistic(raw, NORMAL)
    phi, sd = np.asarray(params["phi_doy"]), np.asarray(params["sd_doy"])
    normal = raw.loc[NORMAL[0]:NORMAL[1]]
    cycle = normal.groupby(normal.index.day_of_year).transform("mean")
    return {"phi_media": float(phi.mean()), "phi_amplitude": float(phi.max() - phi.min()),
            "sd_razao": float(sd.max() / sd.min()),
            "ciclo_frac": float(cycle.var() / normal.var())}


def cell_seasonality(cfg) -> pd.DataFrame:
    """Uma linha por célula, com as quatro medidas de cada variável (`<medida>_<var>`)."""
    cubes = load_cubes(cfg, VARIABLES)
    rows = []
    for cell in regions.cells(cfg).itertuples():
        row = {"cell_id": cell.cell_id}
        for var, cube in cubes.items():
            raw = cube.sel(latitude=cell.latitude, longitude=cell.longitude).to_series()
            row |= {f"{k}_{var}": v for k, v in series_seasonality(raw).items()}
        rows.append(row)
    return pd.DataFrame(rows).set_index("cell_id")
