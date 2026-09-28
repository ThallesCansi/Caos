import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full", app_title="TCC — piloto ERA5/DETER")


@app.cell
def _():
    from pathlib import Path
    import geopandas as gpd
    import marimo as mo
    import matplotlib.pyplot as plt
    from amazon_chaos.config import load_config
    from amazon_chaos.io.era5 import merge_step_types
    from amazon_chaos.preprocess.climate import (
        aggregate_daily,
        derive_climate_variables,
        extract_nearest_point,
        infer_coord_names,
    )
    from amazon_chaos.preprocess.quality import qc_table, time_regularity
    from amazon_chaos.preprocess.spatial import clip_bbox
    from amazon_chaos.features.disturbance import summarize_deter

    return (
        Path,
        clip_bbox,
        derive_climate_variables,
        extract_nearest_point,
        gpd,
        infer_coord_names,
        load_config,
        merge_step_types,
        mo,
        qc_table,
        summarize_deter,
        time_regularity,
    )


@app.cell
def _(Path, load_config):
    cfg = load_config("configs/pilot.yaml")
    base = Path("data/raw") / cfg["experiment_id"]
    era_dir = base / "era5"
    deter_path = base / "terrabrasilis" / "deter.geojson"
    instant_files = sorted(era_dir.glob("era5_instant*.nc")) + sorted((era_dir / "era5_instant_extracted").glob("**/*.nc"))
    accum_files = sorted(era_dir.glob("era5_accum*.nc")) + sorted((era_dir / "era5_accum_extracted").glob("**/*.nc"))
    return accum_files, cfg, deter_path, instant_files


@app.cell
def _(accum_files, instant_files, mo):
    status = mo.md(
        f"""
        ## Arquivos locais
        - ERA5 instant: **{len(instant_files)}** arquivo(s)
        - ERA5 accum: **{len(accum_files)}** arquivo(s)

        Se ambos forem zero, rode antes: `uv run amazon-chaos pilot --config configs/pilot.yaml`.
        """
    )
    status
    return


@app.cell
def _(accum_files, derive_climate_variables, instant_files, merge_step_types):
    if not instant_files or not accum_files:
        ds = None
        derived = None
    else:
        ds = merge_step_types(instant_files, accum_files)
        derived = derive_climate_variables(ds)
    return (derived,)


@app.cell
def _(
    cfg,
    derived,
    extract_nearest_point,
    infer_coord_names,
    qc_table,
    time_regularity,
):
    if derived is None:
        point = None
        qc = None
        regularity = None
    else:
        lat, lon = cfg["spatial"]["pilot_point"]
        point = extract_nearest_point(derived, lat, lon)
        time_name, _, _ = infer_coord_names(point)
        qc = qc_table(point, time_name)
        regularity = time_regularity(point, time_name)
    return qc, regularity


@app.cell
def _(mo, qc, regularity):
    mo.vstack([mo.md("## QC do ponto piloto"), mo.ui.table(qc), mo.md(f"Regularidade: `{regularity}`")])
    return


@app.cell
def _(cfg, clip_bbox, deter_path, gpd, summarize_deter):
    deter = gpd.read_file(deter_path)
    clipped = clip_bbox(deter, cfg["spatial"]["area"])
    deter_summary = summarize_deter(clipped, equal_area_crs=cfg["spatial"]["equal_area_crs"])
    return (deter_summary,)


@app.cell
def _(deter_summary, mo):
    mo.vstack([mo.md("## DETER na caixa piloto — área após clipping"), mo.ui.table(deter_summary)])
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
