import base64
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from amazon_chaos.config import load_config
from amazon_chaos.io.era5_edh import compare_with_cds, download_edh, open_edh
from amazon_chaos.io.era5_monthly import (
    NAMES,
    download_plan,
    open_downloaded,
    plan_edh_requests,
    request_times,
)
from amazon_chaos.provenance import sha256_file

UNITS = {"t2m": "K", "d2m": "K", "sp": "Pa", "u10": "m s**-1", "v10": "m s**-1", "tp": "m"}


def small_config():
    cfg = load_config("configs/tapajos_2024.yaml")
    cfg["spatial"]["area"] = [-2.25, -56, -2.5, -55.75]
    return cfg


def mirror(path, drop_hour=None):
    """Recorte do formato EDH: latitude decrescente, longitude 0–360, float32."""
    times = pd.date_range("2023-12-31", "2024-01-05 23:00", freq="h")
    if drop_hour is not None:
        times = times.drop(pd.Timestamp(drop_hour))
    lats = np.arange(0, -5.01, -0.25)
    lons = np.arange(300, 310.01, 0.25)
    rng = np.random.default_rng(0)
    ds = xr.Dataset(
        {
            name: xr.DataArray(
                rng.random((len(times), len(lats), len(lons)), dtype="float32"),
                dims=("valid_time", "latitude", "longitude"),
                attrs={"units": unit},
            )
            for name, unit in UNITS.items()
        },
        coords={"valid_time": times, "latitude": lats, "longitude": lons,
                "number": 0, "surface": 0.0},
    )
    ds.chunk({"valid_time": 48, "latitude": 8, "longitude": 8}).to_zarr(
        path, zarr_format=3, consolidated=True
    )
    return ds


class MirrorCDS:
    """CDS falso que devolve exatamente os valores do espelho, na convenção do CDS."""

    def __init__(self, ds):
        self.ds = ds

    def retrieve(self, dataset, request):
        self.request = request
        return self

    def download(self, target):
        from amazon_chaos.preprocess.grid import grid_coordinates

        lats, lons = grid_coordinates(self.request["area"])
        names = [NAMES[v] for v in self.request["variable"]]
        out = self.ds[names].sel(
            valid_time=request_times(self.request), latitude=lats, longitude=lons % 360
        )
        out.assign_coords(longitude=lons).to_netcdf(target)


def test_download_matches_mirror_and_resumes(tmp_path):
    cfg = small_config()
    source = mirror(tmp_path / "edh.zarr")
    root = tmp_path / "raw"

    def opener():
        return open_edh(str(tmp_path / "edh.zarr"))

    download_edh(cfg, "2024-01-01", "2024-01-01", root, opener, report=lambda _: None)

    def offline():
        raise AssertionError("Cache completo não deve acessar rede")

    download_edh(cfg, "2024-01-01", "2024-01-01", root, offline)
    raw = open_downloaded(cfg, "2024-01-01", "2024-01-01", root, source="edh")
    assert dict(raw.sizes) == {"time": 48, "latitude": 2, "longitude": 2}
    assert list(raw.longitude.values) == [-56.0, -55.75]
    expected = source.t2m.sel(valid_time=raw.time.values, latitude=[-2.25, -2.5],
                              longitude=[304.0, 304.25])
    np.testing.assert_array_equal(raw.t2m.values, expected.values)


def test_compare_detects_identical_and_changed_values(tmp_path):
    cfg = small_config()
    source = mirror(tmp_path / "edh.zarr")
    root = tmp_path / "raw"
    cds = download_plan(cfg, "2024-01-01", "2024-01-01", root, MirrorCDS(source))
    download_edh(cfg, "2024-01-01", "2024-01-01", root,
                 lambda: open_edh(str(tmp_path / "edh.zarr")), report=lambda _: None)
    stats = compare_with_cds(cfg, root)
    assert set(stats) == set(UNITS)
    assert all(r["ok"] and r["identical"] == r["values"] for r in stats.values())

    with xr.open_dataset(cds[0]) as opened:
        changed = opened.load()
    changed["t2m"].values[0, 0, 0] += 0.01
    cds[0].unlink()
    changed.to_netcdf(cds[0])
    manifest_path = cds[0].parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["sha256"] = sha256_file(cds[0])
    manifest_path.write_text(json.dumps(manifest))
    stats = compare_with_cds(cfg, root)
    assert not stats["t2m"]["ok"] and stats["d2m"]["ok"]


def test_missing_hour_is_rejected(tmp_path):
    cfg = small_config()
    mirror(tmp_path / "edh.zarr", drop_hour="2024-01-01 07:00")
    with pytest.raises(ValueError, match="EDH sem 1 horas"):
        download_edh(cfg, "2024-01-01", "2024-01-01", tmp_path / "raw",
                     lambda: open_edh(str(tmp_path / "edh.zarr")))


def test_network_failure_is_retried(tmp_path):
    cfg = small_config()
    mirror(tmp_path / "edh.zarr")

    class Broken:
        def __getitem__(self, _):
            raise ConnectionResetError("queda simulada")

    opened = iter([Broken(), open_edh(str(tmp_path / "edh.zarr"))])
    messages = []
    download_edh(cfg, "2024-01-01", "2024-01-01", tmp_path / "raw", lambda: next(opened),
                 report=messages.append, wait_seconds=0)
    assert "tentativa 1/5" in messages[0] and "pronto" in messages[-1]


def test_http_mirror_with_token(tmp_path):
    mirror(tmp_path / "edh.zarr")
    expected = "Basic " + base64.b64encode(b"edh:segredo").decode()

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Authorization") != expected:
                self.send_error(401)
                return
            super().do_GET()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(tmp_path / "edh.zarr"))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        cfg = small_config()
        download_edh(cfg, "2024-01-01", "2024-01-01", tmp_path / "raw",
                     lambda: open_edh(url, token="segredo"), report=lambda _: None, url=url)
        assert len(list((tmp_path / "raw").rglob("manifest.json"))) == 1
        with pytest.raises(PermissionError, match="HTTP 401"):
            open_edh(url, token="errado")
    finally:
        server.shutdown()


def test_edh_plan_mirrors_cds_days_and_grid():
    cfg = load_config("configs/xingu_1990_2024.yaml")
    jobs = plan_edh_requests(cfg, "1990-01-01", "2024-12-31")
    assert len(jobs) == 421 and jobs[-1]["month"] == "2025-01"
    assert jobs[-1]["request"]["day"] == ["01"]
    assert all(len(j["request"]["variable"]) == 6 for j in jobs)
