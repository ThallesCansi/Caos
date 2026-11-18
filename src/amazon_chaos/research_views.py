"""Leituras guiadas dos resultados existentes. Nenhum teste ou download novo.

Figuras reutilizadas pelos notebooks e pela síntese em PDF. Comparações estatísticas
continuam nos módulos originais; aqui apenas selecionamos e explicamos seus resultados.
"""

from __future__ import annotations

import re
from functools import lru_cache

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from amazon_chaos import territorial_comparison as T

DESCRIPTORS = {
    "asymmetry": ("Assimetria temporal", "A sequência tem a mesma organização ao inverter o tempo?",
                  "Detecta irreversibilidade frente à nula; não identifica caos."),
    "d2": ("Dimensão de correlação", "Como a ocupação do espaço reconstruído muda com a escala?",
           "Ruído e tamanho da série limitam a interpretação dimensional."),
    "prediction": ("Erro de previsão não linear", "Os estados passados antecipam o seguinte?",
                   "Avaliar fora da amostra e contra alternativas; previsão não prova caos."),
    "rqa_det": ("Recorrência · DET", "Por quanto tempo os padrões recorrentes mantêm continuidade?",
                "Também responde a memória estocástica; não é prova de determinismo físico."),
    "rqa_lam": ("Recorrência · laminaridade", "Os estados recorrentes permanecem parecidos?",
                "Persistência também pode ocorrer sem caos."),
    "pe_entropy": ("Entropia de permutação", "Como se distribuem os padrões de ordenação?",
                   "Sazonalidade, ruído e dependência temporal alteram o valor."),
    "pe_complexity": ("Complexidade estatística", "Quão estruturada é a distribuição dos padrões?",
                      "Não equivale a uma escala de saúde da floresta ou de caos."),
    "lyapunov": ("Lyapunov · Rosenstein", "Trajetórias próximas divergem no espaço reconstruído?",
                 "Estimativa positiva também ocorre em processos estocásticos; requer controles."),
}
FAMILIES = {
    "Estrutura além da nula": ["asymmetry", "d2", "prediction"],
    "Recorrência e ordenação": ["rqa_det", "rqa_lam", "pe_entropy", "pe_complexity"],
    "Diagnóstico de divergência": ["lyapunov"],
}
VARIABLES = {"t2m": "Temperatura", "vpd": "VPD"}


def method_guide() -> pd.DataFrame:
    return pd.DataFrame([{"Ferramenta": name, "Pergunta": question, "Limite": limit}
                         for name, question, limit in DESCRIPTORS.values()])


def vegetation_diagnostics() -> pd.DataFrame:
    """Resumo de testes já calculados, mantendo os filtros do caderno 12.

    LAI: até 20% de lacunas; NDMI: até 35%, leitura de sensibilidade. Não recalcula
    descritores, substitutas ou significância. Contagens usam apenas p finito.
    """
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear import vegetation_dynamics as VD
    from amazon_chaos.nonlinear.vegetation_gate import load_vegetation_spec

    rows = []
    descriptors = {"asymmetry": "Assimetria temporal", "cao_de2": "Cao (E2)",
                   "lyapunov": "Lyapunov (Rosenstein)", "kantz": "Lyapunov (Kantz)"}
    for slug in T.EXPERIMENTS:
        data = pd.read_parquet(VD.output_dir(load_region(slug), load_vegetation_spec())
                               / "resultados.parquet")
        frame = data[data.etapa.eq(1) & data.descriptor.isin(descriptors)].copy()
        frame = frame[np.isfinite(frame.pvalue)]
        frame = frame[(frame.variable.ne("lai")) | (frame.lacunas <= VD.RULES[
            "primary_max_missing"])]
        for (variable, descriptor), group in frame.groupby(["variable", "descriptor"]):
            rows.append({"Bacia": T.NAMES[slug], "Variável": variable.upper(),
                         "Descritor": descriptors[descriptor],
                         "Células": group.cell_id.nunique(),
                         "Rejeitam": int(group.pvalue.le(0.05).sum()),
                         "Rejeição (%)": 100 * group.pvalue.le(0.05).mean()})
    return pd.DataFrame(rows)


def vegetation_structure_plot(summary: pd.DataFrame):
    """Duas perguntas primárias, com denominadores visíveis e sem teste entre bacias."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.1), layout="constrained", sharex=True)
    shown = ["Assimetria temporal", "Cao (E2)"]
    for ax, variable in zip(axes, ("LAI", "NDMI"), strict=True):
        for i, (basin, color) in enumerate(zip(T.NAMES.values(), ("#24645b", "#b97c4b"),
                                               strict=True)):
            frame = summary[(summary.Bacia == basin) & (summary.Variável == variable)]
            frame = frame.set_index("Descritor").reindex(shown)
            y = np.arange(len(shown)) + (i - 0.5) * 0.28
            ax.plot(frame["Rejeição (%)"], y, "o", color=color, label=basin)
            for value, pos, n, rejects in zip(frame["Rejeição (%)"], y, frame.Células,
                                              frame.Rejeitam, strict=True):
                ax.annotate(f"{int(rejects)}/{int(n)}", (value, pos), xytext=(5, 0),
                            textcoords="offset points", va="center", fontsize=9)
        ax.axvline(5, color="grey", ls=":", lw=1)
        ax.set_yticks(range(len(shown)), shown)
        ax.invert_yaxis()
        ax.set(xlim=(-1, 27), xlabel="Células que rejeitam IAAFT (%)", title=variable)
    axes[0].legend(fontsize=9)
    fig.suptitle("Vegetação em 8 dias · resultados existentes · números: rejeitam / analisadas")
    return fig


@lru_cache(maxsize=2)
def geography(slug: str):
    return T.layers(slug)


def coverage_comparison():
    """2000 e 2024, mesmas escalas; perda é redução líquida desde 1990."""
    fig, axes = plt.subplots(2, 3, figsize=(13, 12), layout="constrained")
    for row, year in enumerate((2000, 2024)):
        for col, (field, label, cmap, maximum) in enumerate([
            ("floresta", "Floresta", "Greens", 1),
            ("agro", "Agropecuária", "YlOrBr", 1),
            ("perda", "Redução líquida de floresta desde 1990", "RdBu_r", 0.6),
        ]):
            pieces = []
            for slug in T.EXPERIMENTS:
                grid = geography(slug)["grid"][["geometry"]].copy()
                table = pd.read_parquet(T.processed(slug) / "perturbacao/celulas.parquet")
                if "cell_id" in table:
                    table = table.set_index("cell_id")
                values = (table.floresta_frac_1990 - table[f"floresta_frac_{year}"]
                          if field == "perda" else table[f"{field}_frac_{year}"])
                grid["valor"] = values
                pieces.append(grid)
            combined = gpd.GeoDataFrame(pd.concat(pieces), crs=4326)
            combined.plot(column="valor", ax=axes[row, col], cmap=cmap, legend=True,
                          vmin=-maximum if field == "perda" else 0, vmax=maximum)
            axes[row, col].set_title(f"{label}\n{year}", fontsize=11)
            axes[row, col].set_axis_off()
    fig.suptitle("MapBiomas · Xingu e Tapajós · fração da área terrestre", fontsize=14)
    return fig


def coverage_change():
    fig, axes = plt.subplots(1, 2, figsize=(10, 7), layout="constrained")
    for ax, field, label in zip(axes, ("floresta", "agro"), ("Floresta", "Agropecuária"),
                               strict=True):
        pieces = []
        for slug in T.EXPERIMENTS:
            grid = geography(slug)["grid"][["geometry"]].copy()
            table = pd.read_parquet(T.processed(slug) / "perturbacao/celulas.parquet")
            if "cell_id" in table:
                table = table.set_index("cell_id")
            grid["valor"] = table[f"{field}_frac_2024"] - table[f"{field}_frac_2000"]
            pieces.append(grid)
        gpd.GeoDataFrame(pd.concat(pieces), crs=4326).plot(
            column="valor", ax=ax, cmap="BrBG", vmin=-0.6, vmax=0.6, legend=True)
        ax.set_title(f"{label} · 2024 menos 2000")
        ax.set_axis_off()
    fig.suptitle("Mudança líquida de cobertura · positivo = aumento da fração")
    return fig


def draw_territories(ax, geos=None):
    """Classes territoriais exclusivas; sobreposição TI/UC tem cor própria."""
    geos = geos or {s: geography(s) for s in T.EXPERIMENTS}
    for geo in geos.values():
        boundary = geo["boundary"]
        ti = geo["tis"].geometry.union_all().intersection(boundary)
        uc = geo["ucs"].geometry.union_all().intersection(boundary)
        gpd.GeoSeries([boundary], crs=4326).plot(ax=ax, color="white", edgecolor="#666666",
                                               linewidth=0.6)
        for shape, color in [(ti.difference(uc), "#2e7d4f"),
                             (uc.difference(ti), "#7462ac"),
                             (ti.intersection(uc), "#d9a441")]:
            if not shape.is_empty:
                gpd.GeoSeries([shape], crs=4326).plot(ax=ax, color=color, linewidth=0)
    ax.set_axis_off()
    ax.set_title("Identificação dos territórios\nLimites atuais", fontsize=11)
    ax.legend(handles=[Patch(color="#2e7d4f", label="Terra Indígena (TI)"),
                       Patch(color="#7462ac", label="UC federal"),
                       Patch(color="#d9a441", label="Sobreposição TI e UC")],
              loc="lower center", fontsize=8, frameon=True)


def territory_key():
    fig, ax = plt.subplots(figsize=(4.5, 7.5), layout="constrained")
    draw_territories(ax)
    return fig


def null_figure(slug="xingu", variable="t2m", descriptors=("asymmetry", "d2"),
                method="IAAFT"):
    """Mesmos resultados do caderno 06; seleção de métricas, sem cortar a figura antiga."""
    folder = T.processed(slug) / "substitutas_bacia/81333bb007"
    frame = pd.read_parquet(folder / f"{variable}_{method.replace(' ', '_')}.parquet")
    fig, axes = plt.subplots(1, len(descriptors), figsize=(5 * len(descriptors), 3.5),
                             layout="constrained", squeeze=False)
    for ax, descriptor in zip(axes.flat, descriptors, strict=True):
        subset = frame[frame.descriptor == descriptor]
        null = subset[subset.kind == "nula"].value.dropna()
        observed = subset[subset.kind == "teste"].iloc[0]
        ax.hist(null, bins=25, color="#c5ae7a", alpha=0.8, label="Substitutas")
        ax.axvline(observed.observed, color="#24645b", lw=2, label="Observado")
        ax.set_title(DESCRIPTORS[descriptor][0])
        ax.set_ylabel("Número de substitutas")
        ax.set_xlabel("Valor do descritor")
        ax.text(0.02, 0.97, f"p de Monte Carlo = {observed.pvalue:.3f}",
                transform=ax.transAxes, va="top", fontsize=9)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle(f"{T.NAMES[slug]} · {VARIABLES[variable]} · {method} · {len(null)} substitutas")
    return fig


def association_figure(variable="t2m", results=None):
    """Uma variável de cada vez. Pode usar a tabela congelada ou resultados em memória."""
    if results is None:
        table = pd.read_csv(T.root() / "reports/tables/08_gradiente/modelos.csv")
        table = table[table.Variável == ("temperatura" if variable == "t2m"
                                       else "déficit de pressão de vapor")].copy()
        values = table["ρ parcial [IC 95%]"].apply(
            lambda s: [float(n) for n in re.findall(r"[+-]?\d+\.\d+", s)])
        table[["rho_parcial", "ic_inf", "ic_sup"]] = pd.DataFrame(values.tolist(),
                                                                              index=table.index)
        table = table.rename(columns={"Bacia": "bacia", "Descritor": "descritor",
                                      "Modelo": "modelo"})
    else:
        table = results[results.variavel == variable].copy()
        table.bacia = table.bacia.map(T.NAMES)
        table.descritor = table.descritor.map(lambda d: DESCRIPTORS[d][0])
    models = ["pré-registrado", "conversão, sem o Cerrado natural", "com a vegetação do ERA5"]
    table = table[table.modelo.isin(models)]
    names = table.descritor.drop_duplicates().tolist()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), sharex=True, layout="constrained")
    for ax, basin in zip(axes, T.NAMES.values(), strict=True):
        for i, (model, color, marker) in enumerate(zip(
                models, ["#263e39", "#b96b36", "#588460"], ["o", "s", "D"], strict=True)):
            f = table[(table.bacia == basin) & (table.modelo == model)].set_index(
                "descritor").reindex(names)
            y = np.arange(len(names)) + (i - 1) * 0.2
            ax.errorbar(f.rho_parcial, y, xerr=[f.rho_parcial - f.ic_inf,
                                              f.ic_sup - f.rho_parcial],
                        fmt=marker, color=color, label=model, capsize=2)
        ax.set_yticks(range(len(names)), names, fontsize=9)
        ax.invert_yaxis()
        ax.axvline(0, color="grey", lw=1)
        ax.set(title=f"{basin} · {VARIABLES[variable]}", xlabel="Associação parcial (IC 95%)")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center",
               ncol=1, fontsize=8, frameon=False)
    return fig
