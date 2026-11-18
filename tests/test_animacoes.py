import numpy as np
import pandas as pd
import pytest
import xarray as xr

pytest.importorskip("imageio_ffmpeg")  # grupo opcional `animacao`

from amazon_chaos.animacoes import dados, mapas  # noqa: E402


def _cubo(anos=4):
    tempo = pd.date_range("1991-01-01", periods=12 * anos, freq="MS")
    ciclo = 5 * np.sin(2 * np.pi * tempo.month.values / 12)
    valores = ciclo[:, None, None] + np.arange(6).reshape(1, 2, 3)
    return xr.DataArray(valores, coords={"time": tempo, "latitude": [-1.0, -1.25],
                                         "longitude": [-55.0, -54.75, -54.5]},
                        dims=("time", "latitude", "longitude"))


def test_anomalia_mensal_tira_o_ciclo_e_a_media_de_cada_celula():
    anomalia = dados.anomalia_mensal(_cubo(), base=("1991-01-01", "1994-12-31"))
    np.testing.assert_allclose(anomalia.values, 0, atol=1e-12)


def test_media_pondera_pela_area_dentro_da_bacia():
    cubo = _cubo(1)
    pesos = xr.zeros_like(cubo.isel(time=0))
    pesos[0, 0] = 3.0
    pesos[1, 2] = 1.0
    esperado = (3 * cubo[:, 0, 0] + cubo[:, 1, 2]) / 4
    np.testing.assert_allclose(dados.media(cubo, pesos), esperado.values)


def test_poligonos_apontam_para_a_celula_certa():
    import geopandas as gpd
    from shapely.geometry import MultiPolygon, box

    celulas = gpd.GeoDataFrame({
        "latitude": [-1.25, -1.0], "longitude": [-54.5, -55.0],
        "geometry": [box(-54.625, -1.375, -54.375, -1.125),
                     MultiPolygon([box(-55.1, -1.1, -55.0, -1.0),
                                   box(-54.95, -0.95, -54.9, -0.9)])],
    })
    verts, ii, jj = mapas._poligonos(celulas, _cubo(1))
    assert len(verts) == 3
    assert list(zip(ii, jj, strict=True)) == [(1, 2), (0, 0), (0, 0)]


def test_renderizacao_relampago(tmp_path, monkeypatch):
    import geopandas as gpd
    from shapely.geometry import box

    cubo = _cubo(1)
    celulas = gpd.GeoDataFrame({
        "cell_id": ["a", "b"], "latitude": [-1.0, -1.25], "longitude": [-55.0, -54.75],
        "weight_km2": [1.0, 1.0],
        "geometry": [box(-55.125, -1.125, -54.875, -0.875),
                     box(-54.875, -1.375, -54.625, -1.125)],
    })
    limite = gpd.GeoDataFrame(geometry=[celulas.union_all()])
    falsa = dados.Bacia("xingu", "Xingu", celulas, limite, limite.boundary.to_frame("geometry"),
                        celulas.set_index(["latitude", "longitude"]).weight_km2.to_xarray())
    monkeypatch.setattr(dados, "bacia", lambda slug: falsa)
    t = mapas.Timelapse(
        titulo="Teste", subtitulo="Um cubo sintético.", fonte="—", rotulo="x",
        cmap="RdBu_r", norm=mapas.TwoSlopeNorm(0, -6, 11), campos={"xingu": cubo},
        data=lambda d: (mapas.MESES[d.month - 1], str(d.year)),
        painel=mapas._listras({"xingu": cubo}, "RdBu_r", mapas.TwoSlopeNorm(0, -6, 11)),
        anotacoes=[mapas.Anotacao("1991-03", "1991-05", "Uma nota.")],
        brilho={"xingu": (cubo > 0).astype(float)},
        mascara={"xingu": cubo.isel(time=0) > 3}, mascara_rotulo="Coberta",
    )
    saida = mapas.mapa_animado(t, tmp_path / "teste.mp4", quadros=3)
    assert saida.stat().st_size > 0
    assert saida.with_suffix(".png").exists()


def test_maquina_de_substitutas_relampago(tmp_path, monkeypatch):
    from amazon_chaos.animacoes import substitutas

    rng = np.random.default_rng(1)
    x = rng.standard_normal(730)
    falso = {"serie": x, "inicio": np.array("2019-01-01"), "fim": np.array("2020-12-31"),
             "fases_novas": rng.uniform(-np.pi, np.pi, len(np.fft.rfft(x))),
             "fantasmas": rng.standard_normal((substitutas.N_FANTASMAS, 730))}
    for d in substitutas.DESCRITORES:
        falso[f"{d}_nula"] = rng.normal(0.5, 0.01, 199)
        falso[f"{d}_observed"] = np.array(0.6)
        falso[f"{d}_z"] = np.array(10.0)
        falso[f"{d}_pvalue"] = np.array(0.005)
    monkeypatch.setattr(substitutas, "pacote", lambda: falso)
    saida = substitutas.maquina(tmp_path / "s.mp4", quadros=4)
    assert saida.stat().st_size > 0
    assert saida.with_suffix(".png").exists()


def test_pontos_empilham_um_por_valor():
    from amazon_chaos.animacoes import substitutas

    xy, topo = substitutas._pontos(np.array([0.0, 0.0, 1.0, 0.5]), bins=2)
    assert topo == 2
    assert sorted(xy[:, 1].tolist()) == [1, 1, 2, 2]
