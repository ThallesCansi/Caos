"""Comparações exploratórias do caderno 13. Somente arquivos locais; nenhum download.

As novas curvas são calculadas explicitamente das séries e do pareamento recebido.
Não interpretamos as métricas A/R de `memoria`, cujo código não acompanha esta cópia.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely

EXPERIMENTS = {"xingu": "xingu-era5-1990-2024", "tapajos": "tapajos-bacia-era5-1990-2024"}
NAMES = {"xingu": "Xingu", "tapajos": "Tapajós"}
TERRITORIES = ["TI", "UC federal", "TI e UC", "Demais áreas"]
EVENTS = {
    "xingu": {
        "match": "TERRA DO MEIO", "name": "Estação Ecológica da Terra do Meio",
        "date": "2005-02-17",
        "source": "https://www.gov.br/icmbio/pt-br/assuntos/unidade-de-conservacao/"
                  "unidades-de-biomas/amazonia/lista-de-ucs/esec-da-terra-do-meio/"
                  "esec-da-terra-do-meio",
    },
    "tapajos": {
        "match": "FLORESTA NACIONAL DO JAMANXIM", "name": "Floresta Nacional do Jamanxim",
        "date": "2006-02-13",
        "source": "https://www.gov.br/icmbio/pt-br/assuntos/unidade-de-conservacao/"
                  "unidades-de-biomas/amazonia/lista-de-ucs/flona-do-jamanxim",
    },
}


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def processed(slug: str) -> Path:
    return root() / "data/processed" / EXPERIMENTS[slug]


def layers(slug: str) -> dict:
    """Grade recortada à bacia; limites atuais de TI e UC federal."""
    folder = root() / "data/external" / slug
    boundary_file = "bacia_ibge_bhb250_2021.geojson" if slug == "xingu" else "limite.geojson"
    boundary = gpd.read_file(folder / boundary_file).to_crs(4326).geometry.union_all()
    grid = gpd.read_file(processed(slug) / "basin_grid.geojson").to_crs(4326)
    shapely.prepare(boundary)
    edge = ~shapely.contains(boundary, grid.geometry.to_numpy())
    grid.loc[edge, "geometry"] = grid.loc[edge].geometry.intersection(boundary)
    grid = grid[~grid.geometry.is_empty].set_index("cell_id")
    out = {"grid": grid, "boundary": boundary}
    for key in ("tis", "ucs"):
        frame = gpd.read_file(folder / "contexto" / f"{key}.geojson").to_crs(4326)
        out[key] = frame
    return out


def covered_area(grid: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame) -> np.ndarray:
    """Área de união por célula, consultando apenas polígonos vizinhos; sem dupla contagem."""
    shapes = polygons.geometry.to_numpy()
    tree = shapely.STRtree(shapes)
    result = []
    for cell in grid.geometry:
        candidates = tree.query(cell, predicate="intersects")
        clipped = shapely.intersection(shapes[candidates], cell)
        result.append(shapely.area(shapely.union_all(clipped)))
    return np.asarray(result)


def cells(slug: str, geo: dict) -> gpd.GeoDataFrame:
    table = pd.read_parquet(processed(slug) / "perturbacao/celulas.parquet")
    if "cell_id" in table.columns:
        table = table.set_index("cell_id")
    out = geo["grid"][["geometry"]].join(table, validate="one_to_one")
    metric = out.to_crs(6933)
    for key in ("tis", "ucs"):
        out[f"frac_{key}"] = covered_area(metric, geo[key].to_crs(6933)) / metric.area
    out["territorio"] = "Mista"
    protected = pd.concat([geo["tis"][["geometry"]], geo["ucs"][["geometry"]]])
    out.loc[covered_area(metric, protected.to_crs(6933)) / metric.area < 0.1,
            "territorio"] = "Demais áreas"
    out.loc[(out.frac_tis >= 0.5) & (out.frac_tis >= out.frac_ucs), "territorio"] = "TI"
    out.loc[(out.frac_ucs >= 0.5) & (out.frac_ucs > out.frac_tis), "territorio"] = "UC federal"
    return out


def maps(slug: str, table: gpd.GeoDataFrame, geo: dict):
    fig, axes = plt.subplots(1, 3, figsize=(15, 7), layout="constrained")
    fields = [("mb_queimada_alguma_vez_frac_2024", "Área queimada ≥ 1 vez, 1985–2024", "OrRd"),
              ("mb_frequencia_fogo_media_2024", "Frequência média de queima, 1985–2024", "YlOrRd"),
              ("agro_frac_2024", "Agropecuária, 2024", "YlOrBr")]
    for ax, (column, title, cmap) in zip(axes, fields, strict=True):
        table.plot(column=column, ax=ax, cmap=cmap, legend=True,
                   missing_kwds={"color": "lightgrey"})
        for key, color in (("tis", "#17683d"), ("ucs", "#36309b")):
            frame = geo[key].copy()
            frame.geometry = frame.geometry.intersection(geo["boundary"])
            frame[~frame.geometry.is_empty].boundary.plot(ax=ax, color=color, linewidth=0.6)
        ax.set_title(title, fontsize=10)
        ax.set_axis_off()
    fig.suptitle(f"{NAMES[slug]} · TI: verde; UC federal: roxo · limites atuais")
    return fig


def territorial_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Médias ponderadas por área terrestre; não são estatísticas exatas dos polígonos."""
    rows = []
    for name, g in table.groupby("territorio"):
        row = {"Classe da célula": name, "Células": len(g)}
        for col, label in [("mb_queimada_alguma_vez_frac_2024", "Área queimada (%)"),
                           ("agro_frac_2024", "Agropecuária (%)"),
                           ("mb_frequencia_fogo_media_2024", "Frequência média")]:
            good = g[[col, "terra_km2_2024"]].dropna()
            value = np.average(good[col], weights=good.terra_km2_2024)
            row[label] = value * (100 if "(%)" in label else 1)
        rows.append(row)
    return pd.DataFrame(rows).round(2)


def episode_context(slug: str, table: pd.DataFrame, geo: dict) -> pd.DataFrame:
    base = processed(slug) / "vegetacao/fogo_subamostra"
    episodes = pd.read_parquet(base / "episodios.parquet")
    dates = pd.read_parquet(base / "memoria/datas_queima.parquet")
    drought = pd.read_parquet(base / "memoria/seca.parquet")
    out = episodes.merge(dates, on="episodio", validate="one_to_one").merge(
        drought, on="episodio", validate="one_to_one")
    out["data_queima"] = pd.to_datetime(out.data_queima)
    atmosphere = pd.read_parquet(base / "memoria/atmosfera.parquet")
    atmosphere["data"] = pd.to_datetime(atmosphere.data)
    pre_drought = []
    for ep in out.itertuples():
        before = atmosphere[(atmosphere.cell_id == ep.cell_id)
                            & (atmosphere.data < ep.data_queima)
                            & (atmosphere.data >= ep.data_queima - pd.Timedelta(days=60))]
        values = before.vpd_z.dropna()
        pre_drought.append(values.mean() if len(values) >= 4 else np.nan)
    out["vpd_pre_60d"] = pre_drought
    # Última fotografia ESTRITAMENTE anterior ao ano do evento. Não usamos 2024.
    out["ano_cobertura"] = np.where(out.ano > 2012, 2012, 2000)
    for year in (2000, 2012):
        hit = out.ano_cobertura == year
        out.loc[hit, "agro_pre"] = out.loc[hit, "cell_id"].map(table[f"agro_frac_{year}"])
    out["contexto_agro"] = pd.cut(out.agro_pre, [-np.inf, 0.1, 0.3, np.inf],
                                 labels=["Até 10%", "10–30%", "Mais de 30%"])
    points = gpd.GeoSeries(gpd.points_from_xy(out.lon, out.lat), crs=4326)
    ti = points.intersects(geo["tis"].geometry.union_all()).to_numpy()
    uc = points.intersects(geo["ucs"].geometry.union_all()).to_numpy()
    out["territorio_ponto"] = np.select([ti & uc, ti, uc],
                                       ["TI e UC", "TI", "UC federal"], "Demais áreas")
    out["contexto_seca"] = np.where(out.vpd_pre_60d >= 1, "VPD ≥ +1 desvio", "VPD < +1 desvio")
    out.loc[out.vpd_pre_60d.isna(), "contexto_seca"] = None
    return out


def ordinal(dates) -> np.ndarray:
    dates = pd.DatetimeIndex(pd.to_datetime(dates))
    return dates.year.to_numpy() * 46 + (dates.dayofyear.to_numpy() - 1) // 8


def recovery(slug: str, episodes: pd.DataFrame) -> pd.DataFrame:
    """Diferença queimado − média de ≥2 controles; remove diferença média prévia.

    k=0 é a composição que contém a data MCD64A1 recebida. Nenhuma interpolação nova.
    Referência: 2 anos anteriores, mínimo de 24 pares válidos. Sensibilidade sazonal:
    subtrai a diferença do mesmo slot do ano nos dois anos anteriores.
    """
    base = processed(slug) / "vegetacao/fogo_subamostra"
    pairs = pd.read_parquet(base / "pareamento.parquet")
    controls = pairs[["episodio", "controle"]].rename(columns={"controle": "id"})
    controls["queimado"] = False
    burned = episodes[["episodio"]].assign(id=episodes.episodio, queimado=True)
    lookup = pd.concat([burned, controls], ignore_index=True)
    series = pd.read_parquet(base / "pontos.parquet", columns=["id", "data", "variavel", "valor"])
    # O pacote repete pontos em tarefas diferentes; valores são os mesmos nas repetições.
    series = series.drop_duplicates(["id", "data", "variavel"])
    series = series.merge(lookup, on="id", validate="many_to_one")
    series["data"] = pd.to_datetime(series.data)
    good = series[~series.queimado].groupby(["episodio", "data", "variavel"]).valor.agg(
        controle="mean", n_controles="count").reset_index()
    good.loc[good.n_controles < 2, "controle"] = np.nan
    obs = series[series.queimado][["episodio", "data", "variavel", "valor"]]
    out = obs.merge(good, on=["episodio", "data", "variavel"], validate="one_to_one")
    out = out.merge(episodes, on="episodio", validate="many_to_one")
    out["k"] = ordinal(out.data) - ordinal(out.data_queima)
    out = out[out.k.between(-92, 138) & out.k.ne(0)].copy()
    out["slot"] = (out.data.dt.dayofyear - 1) // 8
    out["diferenca"] = out.valor - out.controle
    pre = out[out.k < 0]
    baseline = pre.groupby(["episodio", "variavel"]).diferenca.agg(
        referencia="mean", n_pre="count").reset_index()
    out = out.merge(baseline, on=["episodio", "variavel"], validate="many_to_one")
    out["delta"] = (out.diferenca - out.referencia).where(out.n_pre >= 24)
    seasonal = pre.groupby(["episodio", "variavel", "slot"]).diferenca.mean().rename(
        "referencia_sazonal").reset_index()
    out = out.merge(seasonal, on=["episodio", "variavel", "slot"], how="left",
                    validate="many_to_one")
    out["delta_sazonal"] = (out.diferenca - out.referencia_sazonal).where(out.n_pre >= 24)
    return out.drop(columns=["i", "j"], errors="ignore")


def cluster_mean(frame: pd.DataFrame, value: str, draws: int = 499) -> dict:
    """Média por episódio com bootstrap de células inteiras, preservando seus episódios."""
    f = frame[["episodio", "cell_id", value]].dropna()
    per = f.groupby(["cell_id", "episodio"])[value].mean().reset_index()
    grouped = per.groupby("cell_id")[value].agg(["sum", "count"])
    n = len(grouped)
    result = {"media": per[value].mean(), "episodios": len(per), "celulas": n,
              "ic_inf": np.nan, "ic_sup": np.nan}
    if n >= 5:
        rng = np.random.default_rng(20261117)
        pick = rng.integers(0, n, size=(draws, n))
        boot = grouped["sum"].to_numpy()[pick].sum(axis=1) / grouped["count"].to_numpy()[
            pick].sum(axis=1)
        result["ic_inf"], result["ic_sup"] = np.quantile(boot, [0.025, 0.975])
    return result


RECOVERY_WINDOWS = {"Antes: −2 a −1 ano": (-92, -47), "Antes: último ano": (-46, -1),
                    "Até 1,5 mês": (1, 6), "2–6 meses": (7, 23), "6–12 meses": (24, 46),
                    "1–2 anos": (47, 92), "2–3 anos": (93, 138)}


def window_means(curves: pd.DataFrame, value: str = "delta",
                 cohort: str = "available") -> pd.DataFrame:
    """Uma média por episódio/janela. Coorte fixa exige cobertura em TODAS as 7 janelas.

    Não afrouxa a cobertura quando a interseção é pequena. A elegibilidade é separada
    por bacia (se presente), variável e episódio, nunca pelo valor da resposta.
    """
    if cohort not in {"available", "fixed"}:
        raise ValueError("cohort deve ser available ou fixed")
    keys = [k for k in ("bacia", "variavel", "episodio") if k in curves]
    parts = []
    for label, (lo, hi) in RECOVERY_WINDOWS.items():
        part = curves[curves.k.between(lo, hi)].copy()
        count = part.groupby(keys)[value].transform("count")
        part = part[count >= (hi - lo + 1) / 2]
        if not part.empty:
            mean = part.groupby(keys, observed=True)[value].mean().rename(value).reset_index()
            metadata = part.drop_duplicates(keys).drop(columns=[value, "k", "janela"],
                                                       errors="ignore")
            mean = mean.merge(metadata, on=keys, validate="one_to_one")
            parts.append(mean.assign(janela=label))
    if not parts:
        return curves.iloc[:0].assign(janela=pd.Series(dtype=str))
    out = pd.concat(parts, ignore_index=True)
    if cohort == "fixed":
        full = out.groupby(keys).janela.transform("nunique") == len(RECOVERY_WINDOWS)
        out = out[full]
    return out


def recovery_summary(curves: pd.DataFrame, grouping: str, value: str = "delta",
                     cohort: str = "available") -> pd.DataFrame:
    means = window_means(curves, value, cohort)
    rows = []
    for (variable, group), _ in curves.groupby(["variavel", grouping], observed=True):
        frame = means[(means.variavel == variable) & (means[grouping] == group)]
        for label in RECOVERY_WINDOWS:
            part = frame[frame.janela == label]
            rows.append({"variavel": variable, "grupo": str(group), "janela": label,
                         **cluster_mean(part, value)})
    return pd.DataFrame(rows)


def recovery_plot(summary: pd.DataFrame, variable: str, title: str):
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    windows = summary.janela.unique().tolist()
    for group, frame in summary[summary.variavel == variable].groupby("grupo", sort=False):
        frame = frame.set_index("janela").reindex(windows)
        valid = frame.celulas >= 5
        y = frame.media.where(valid).to_numpy()
        ax.plot(range(len(windows)), y, marker="o", label=group)
        ax.fill_between(range(len(windows)), frame.ic_inf.where(valid).to_numpy(),
                        frame.ic_sup.where(valid).to_numpy(), alpha=0.13)
    ax.axhline(0, color="grey", lw=1)
    ax.axvline(1.5, color="grey", ls="--", lw=1)
    ax.set_xticks(range(len(windows)), windows, rotation=25, ha="right")
    ax.set_ylabel(f"Diferença ajustada de {variable.upper()} (unidade do índice)")
    ax.set_title(title)
    ax.legend(fontsize=8)
    if not ((summary.variavel == variable) & (summary.celulas >= 5)).any():
        ax.text(0.5, 0.5, "Nenhum grupo com pelo menos 5 células nesta seleção.\n"
                "Consulte as contagens; ausência de curva não é ausência de efeito.",
                transform=ax.transAxes, ha="center", va="center", fontsize=10)
    return fig


def selection_table(slug: str) -> pd.DataFrame:
    """Contagens recebidas: episódios-pixel não são células ERA5; critérios se sobrepõem."""
    base = processed(slug) / "vegetacao/fogo_subamostra"
    meta = json.loads((base / "episodios.json").read_text(encoding="utf-8"))
    episodes = pd.read_parquet(base / "episodios.parquet")
    matches = pd.read_parquet(base / "pareamento.parquet")
    paired = episodes[episodes.episodio.isin(matches.episodio)]
    records = [
        ("Candidatos encontrados", meta["encontrados"], None),
        ("Com requeima em 3 anos (critério sobreposto)", meta["requeima"], None),
        ("Perdem classe florestal em 2 anos (critério sobreposto)",
         meta["perdem_floresta"], None),
        ("Elegíveis após ambos os filtros", meta["validos"], None),
        ("Sorteados", len(episodes), episodes.cell_id.nunique()),
        ("Com controle pareado", len(paired), paired.cell_id.nunique()),
    ]
    out = pd.DataFrame(records, columns=["Etapa", "Episódios-pixel", "Células ERA5"])
    out["Células ERA5"] = out["Células ERA5"].astype("Int64")
    return out


def basin_contrast(curves: pd.DataFrame, value: str = "delta",
                   cohort: str = "available", draws: int = 999) -> pd.DataFrame:
    """Diferença descritiva Xingu − Tapajós, bootstrap de células dentro de cada bacia.

    Sem ajuste por clima, ano ou dano inicial; IC pontual sem correção múltipla.
    Não substitui a análise pré-registrada nem identifica efeito da bacia.
    """
    means = window_means(curves, value, cohort)
    rows = []
    for variable in curves.variavel.unique():
        for window in RECOVERY_WINDOWS:
            f = means[(means.variavel == variable) & (means.janela == window)]
            row = {"Indicador": variable.upper(), "Período": window,
                   "Xingu − Tapajós": np.nan, "IC inferior": np.nan, "IC superior": np.nan}
            aggregates = []
            for basin in ("xingu", "tapajos"):
                per = f[f.bacia == basin].dropna(subset=[value])
                cells = per.groupby("cell_id")[value].agg(["sum", "count"])
                row[f"Episódios {NAMES[basin]}"] = len(per)
                row[f"Células {NAMES[basin]}"] = len(cells)
                aggregates.append(cells)
            if all(len(a) >= 5 for a in aggregates):
                rng = np.random.default_rng(20261117)
                estimates, boot = [], []
                for a in aggregates:
                    estimates.append(a["sum"].sum() / a["count"].sum())
                    pick = rng.integers(0, len(a), size=(draws, len(a)))
                    boot.append(a["sum"].to_numpy()[pick].sum(1)
                                / a["count"].to_numpy()[pick].sum(1))
                row["Xingu − Tapajós"] = estimates[0] - estimates[1]
                row["IC inferior"], row["IC superior"] = np.quantile(
                    boot[0] - boot[1], [0.025, 0.975])
            rows.append(row)
    return pd.DataFrame(rows)


def contrast_plot(table: pd.DataFrame, variable: str):
    f = table[table.Indicador == variable.upper()]
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    y = np.arange(len(f))
    ax.errorbar(f["Xingu − Tapajós"], y,
                xerr=[f["Xingu − Tapajós"] - f["IC inferior"],
                      f["IC superior"] - f["Xingu − Tapajós"]],
                fmt="o", color="#24645b", capsize=3)
    ax.axvline(0, color="grey", lw=1)
    ax.set_yticks(y, f.Período)
    ax.invert_yaxis()
    ax.set(xlabel=f"Diferença de {variable.upper()}: Xingu − Tapajós (IC 95%)",
           title="Comparação exploratória entre bacias · sem ajuste de confundidores")
    if not f["Xingu − Tapajós"].notna().any():
        ax.text(0.5, 0.5, "Amostra insuficiente nas duas bacias para este contraste.\n"
                "Nenhuma janela tem pelo menos 5 células em cada bacia.",
                transform=ax.transAxes, ha="center", va="center", fontsize=10,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9})
    return fig


def readable_summary(summary: pd.DataFrame, variable: str) -> pd.DataFrame:
    return summary[summary.variavel == variable].drop(columns="variavel").rename(columns={
        "grupo": "Contexto", "janela": "Período", "media": "Diferença média",
        "episodios": "Episódios", "celulas": "Células",
        "ic_inf": "IC 95% inferior", "ic_sup": "IC 95% superior"}).round(3)


def availability_plot(summary: pd.DataFrame, variable: str, title: str):
    f = summary[summary.variavel == variable]
    groups = f.grupo.drop_duplicates().tolist()
    windows = list(RECOVERY_WINDOWS)
    cells = f.pivot(index="grupo", columns="janela", values="celulas").reindex(
        index=groups, columns=windows)
    episodes = f.pivot(index="grupo", columns="janela", values="episodios").reindex(
        index=groups, columns=windows)
    fig, ax = plt.subplots(figsize=(10, 1.8 + 0.45 * len(groups)), layout="constrained")
    ax.imshow(cells.to_numpy(), cmap="Greys", vmin=0, vmax=max(5, cells.max().max()),
              aspect="auto", alpha=0.3)
    for row in range(len(groups)):
        for col in range(len(windows)):
            ax.text(col, row, f"{int(episodes.iloc[row, col])} / {int(cells.iloc[row, col])}",
                    ha="center", va="center", fontsize=9)
    ax.set_xticks(range(len(windows)), ["Pré: 2–1 ano", "Pré: último ano", "Até 1,5 mês",
                  "2–6 meses", "6–12 meses", "1–2 anos", "2–3 anos"], rotation=20, ha="right")
    ax.set_yticks(range(len(groups)), [NAMES.get(g, g) for g in groups])
    ax.set_title(title + "\nCada casa: episódios / células ERA5", fontsize=11)
    return fig


def monthly_fire(slug: str, table: pd.DataFrame) -> pd.DataFrame:
    """Meses COM foco vs chuva do mês ANTERIOR. Não mede ignição ou previsão diária."""
    rain = pd.read_parquet(processed(slug) / "chirps/diario.parquet")
    rain.index = pd.to_datetime(rain.index)
    monthly = rain.resample("MS").sum(min_count=1)
    valid = rain.resample("MS").count()
    monthly = monthly.where(valid.ge(monthly.index.days_in_month, axis=0)).shift(1)
    fires = pd.read_parquet(processed(slug) / "perturbacao/focos_mensais.parquet").T
    fires.index = pd.to_datetime(fires.index)
    monthly = monthly.reindex(index=fires.index, columns=fires.columns)
    # Percentis na mesma célula e mês do calendário; menos chuva = maior secura relativa.
    ranks = monthly.groupby(monthly.index.month).rank(pct=True, method="average")
    long = (1 - ranks).rename_axis(index="data", columns="cell_id").stack().rename(
        "secura").reset_index()
    detected = fires.rename_axis(index="data", columns="cell_id").stack().rename(
        "focos").reset_index()
    long = long.merge(detected, on=["data", "cell_id"], validate="one_to_one")
    long = long[long.data.dt.month.between(6, 10)].copy()
    long["ano"] = long.data.dt.year
    long["faixa"] = pd.cut(long.secura, [-np.inf, 1 / 3, 2 / 3, np.inf],
                           labels=["Menos seco", "Intermediário", "Mais seco"])
    agro = long.cell_id.map(table.agro_frac_2000)
    long["paisagem_2000"] = pd.cut(agro, [-np.inf, 0.1, 0.3, np.inf],
                                  labels=["Até 10% agro", "10–30% agro", ">30% agro"])
    long["com_foco"] = long.focos > 0
    rows = []
    for keys, part in long.groupby(["paisagem_2000", "faixa"], observed=True):
        annual = part.groupby("ano").com_foco.agg(["sum", "count"])
        rng = np.random.default_rng(20261117)
        pick = rng.integers(0, len(annual), (999, len(annual)))
        boot = annual["sum"].to_numpy()[pick].sum(1) / annual["count"].to_numpy()[pick].sum(1)
        lo, hi = np.quantile(boot, [0.025, 0.975])
        rows.append({"Paisagem em 2000": str(keys[0]), "Secura anterior": str(keys[1]),
                     "Meses-célula": len(part), "Células": part.cell_id.nunique(),
                     "Anos": len(annual), "Meses com foco (%)": 100 * part.com_foco.mean(),
                     "IC inferior": 100 * lo, "IC superior": 100 * hi})
    return pd.DataFrame(rows)


def fire_plot(table: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    order = ["Menos seco", "Intermediário", "Mais seco"]
    for name, frame in table.groupby("Paisagem em 2000", sort=False):
        f = frame.set_index("Secura anterior").reindex(order)
        ax.plot(order, f["Meses com foco (%)"], marker="o", label=name)
        ax.fill_between(order, f["IC inferior"], f["IC superior"], alpha=0.15)
    ax.set(ylabel="Meses com pelo menos um foco (%)",
           title="Junho–outubro · chuva do mês anterior · IC por anos inteiros")
    ax.legend()
    return fig


def historical_zones(slug: str, geo: dict) -> gpd.GeoDataFrame:
    """Mesmos polígonos atuais e entorno métrico, reutilizáveis sem reler todos os focos."""
    event = EVENTS[slug]
    unit = geo["ucs"][geo["ucs"].nomeuc.str.contains(event["match"], case=False, regex=False)]
    if len(unit) != 1:
        raise ValueError(f"Esperava uma UC para {event['name']}; encontrei {len(unit)}")
    unit_shape = unit.geometry.union_all()
    metric = gpd.GeoSeries([unit_shape], crs=4326).to_crs(6933).iloc[0]
    basin_metric = gpd.GeoSeries([geo["boundary"]], crs=4326).to_crs(6933).iloc[0]
    # Buffer em projeção métrica local (UTM), para representar distância em km.
    local_crs = unit.estimate_utm_crs()
    local = unit.to_crs(local_crs).geometry.union_all()
    buffer_shape = gpd.GeoSeries([local.buffer(25000).difference(local)], crs=local_crs)
    ring = buffer_shape.to_crs(6933).iloc[0].intersection(basin_metric)
    zones = gpd.GeoDataFrame({"zona": ["Área da UC atual", "Entorno de 25 km"]},
                            geometry=[metric.intersection(basin_metric), ring], crs=6933)
    zones["km2"] = zones.area / 1e6
    return zones.to_crs(4326)


def historical(slug: str, geo: dict) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Contagem exata de focos nos polígonos atuais e entorno de 25 km, sem download."""
    geographic = historical_zones(slug, geo)
    bounds = geographic.total_bounds
    rows = []
    for year in range(2003, 2025):
        path = root() / "data/raw/queimadas" / f"focos_br_ref_{year}.zip"
        with zipfile.ZipFile(path) as archive:
            csv = next(n for n in archive.namelist() if n.endswith(".csv"))
            frame = pd.read_csv(archive.open(csv), usecols=["lat", "lon", "data_pas"])
        frame = frame[frame.lon.between(bounds[0], bounds[2])
                      & frame.lat.between(bounds[1], bounds[3])].copy()
        dates = pd.to_datetime(frame.data_pas) - pd.Timedelta(hours=3)
        points = shapely.points(frame.lon.to_numpy(), frame.lat.to_numpy())
        for zone in geographic.itertuples():
            mask = shapely.intersects(points, zone.geometry)
            for local_year, count in dates[mask].dt.year.value_counts().items():
                rows.append({"ano": int(local_year), "zona": zone.zona, "focos": int(count),
                             "km2": zone.km2})
    counts = pd.DataFrame(rows).groupby(["ano", "zona"]).focos.sum()
    index = pd.MultiIndex.from_product([range(2003, 2025), geographic.zona], names=["ano", "zona"])
    result = counts.reindex(index, fill_value=0).rename("focos").reset_index()
    result["km2"] = result.zona.map(geographic.set_index("zona").km2)
    result["focos_100km2"] = result.focos / result.km2 * 100
    return result, geographic


def history_plot(slug: str, table: pd.DataFrame, zones: gpd.GeoDataFrame):
    event = EVENTS[slug]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), layout="constrained",
                             gridspec_kw={"width_ratios": [1, 2.5]})
    zones.plot(ax=axes[0], column="zona", alpha=0.5, legend=True)
    axes[0].set_title("Limite atual e entorno\nRecorte dentro da bacia", fontsize=11)
    axes[0].set_axis_off()
    for name, f in table.groupby("zona"):
        axes[1].plot(f.ano, f.focos_100km2, marker=".", label=name)
    year = pd.Timestamp(event["date"]).year
    axes[1].axvspan(year - 0.5, year + 0.5, color="grey", alpha=0.2, label="Ano do decreto")
    axes[1].set_ylabel("Focos por 100 km² por ano", fontsize=12)
    axes[1].set_title(event["name"], fontsize=14)
    years = sorted(table.ano.unique())
    axes[1].set_xticks(years)
    axes[1].tick_params(axis="x", labelrotation=60, labelsize=14)
    axes[1].set_xlim(min(years) - 0.5, max(years) + 0.5)
    axes[1].legend(fontsize=11)
    return fig


def history_windows(slug: str, table: pd.DataFrame) -> pd.DataFrame:
    """Janelas simétricas de anos completos, excluindo o ano do decreto; sem teste causal."""
    year = pd.Timestamp(EVENTS[slug]["date"]).year
    width = min(3, year - int(table.ano.min()), int(table.ano.max()) - year)
    rows = []
    for zone, group in table.groupby("zona"):
        before = group[group.ano.between(year - width, year - 1)].focos_100km2.mean()
        after = group[group.ano.between(year + 1, year + width)].focos_100km2.mean()
        rows.append({"Zona": zone, "Anos completos por janela": width,
                     "Antes": f"{year - width}–{year - 1}",
                     "Depois": f"{year + 1}–{year + width}",
                     "Focos/100 km²/ano antes": before,
                     "Focos/100 km²/ano depois": after,
                     "Mudança descritiva": after - before})
    return pd.DataFrame(rows)


def provenance(slug: str) -> dict:
    """Registro recebido, sem atribuir seu commit ao código novo."""
    p = processed(slug) / "vegetacao/fogo_subamostra/memoria/execucao.json"
    meta = json.loads(p.read_text(encoding="utf-8"))
    return {"Bacia": NAMES[slug], "Commit de memoria": meta["commit"],
            "Finalizado (UTC)": meta["finished_utc"],
            "Data do decreto": EVENTS[slug]["date"],
            "Fonte histórica": EVENTS[slug]["source"]}
