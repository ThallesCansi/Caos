"""MODIS LST (MOD11A2.061, 8 dias, 1 km) pelo NASA AppEEARS, para a checagem D-011.

O AppEEARS recorta o produto pelo polígono da bacia no servidor; aqui só se envia o
pedido, acompanha o processamento e baixa os arquivos com manifesto. O login usa usuário
e senha do NASA Earthdata em `~/.netrc` (linha `machine urs.earthdata.nasa.gov login …
password …`); o token devolvido pelo AppEEARS vale só para a sessão.
"""

from __future__ import annotations

import json
import netrc
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from amazon_chaos import regions
from amazon_chaos.provenance import sha256_file

API = "https://appeears.earthdatacloud.nasa.gov/api"
PRODUCT = "MOD11A2.061"
LAYERS = ["LST_Day_1km", "LST_Night_1km", "QC_Day", "QC_Night"]
HOST = "urs.earthdata.nasa.gov"


def credentials(path: str | Path | None = None) -> tuple[str, str]:
    """Usuário e senha do Earthdata; nunca inclui o conteúdo do arquivo nas mensagens."""
    path = Path(path or Path.home() / ".netrc")
    try:
        entry = netrc.netrc(str(path)).authenticators(HOST)
    except (FileNotFoundError, netrc.NetrcParseError):
        entry = None  # a mensagem de NetrcParseError repete a linha inválida: não propagar
    if not entry or not entry[0] or not entry[2]:
        raise RuntimeError(
            f"{path}: falta uma linha 'machine {HOST} login <usuário> password <senha>' "
            "(formato do .netrc; o AppEEARS não aceita só o token)")
    return entry[0], entry[2]


def login(attempts: int = 12, wait: int = 120, report=print) -> str:
    """Token de sessão do AppEEARS. O `/login` às vezes devolve 502/504 por horas, mesmo
    com credenciais válidas; nesse caso tenta de novo com espera crescente."""
    user, password = credentials()
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(f"{API}/login", auth=(user, password), timeout=180)
            if response.status_code == 401:
                raise RuntimeError("AppEEARS recusou usuário ou senha do Earthdata (HTTP 401)")
            if response.status_code < 500:
                response.raise_for_status()
                return response.json()["token"]
            reason = f"HTTP {response.status_code}"
        except requests.RequestException as error:
            reason = type(error).__name__
        if attempt < attempts:
            minutes = wait * attempt // 60
            report(f"AppEEARS indisponível ({reason}); nova tentativa em {minutes} min")
            time.sleep(wait * attempt)
    raise RuntimeError(f"AppEEARS indisponível após {attempts} tentativas ({reason})")


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def task_payload(cfg, start="01-01-2001", end="12-31-2024", tolerance=0.01) -> dict:
    """Pedido de área: o limite da bacia simplificado (~1 km) como FeatureCollection."""
    limit = regions.boundary(cfg).to_crs("EPSG:4326")
    limit = limit.assign(geometry=limit.geometry.simplify(tolerance))
    return {
        "task_type": "area",
        "task_name": f"tcc-caos-{cfg['slug']}-mod11a2",
        "params": {
            "dates": [{"startDate": start, "endDate": end}],
            "layers": [{"product": PRODUCT, "layer": layer} for layer in LAYERS],
            "output": {"format": {"type": "netcdf4"}, "projection": "geographic"},
            "geo": json.loads(limit[["geometry"]].to_json()),
        },
    }


def task_dir(cfg) -> Path:
    path = Path("data/raw") / cfg["experiment_id"] / "modis"
    path.mkdir(parents=True, exist_ok=True)
    return path


def submit(cfg, token) -> str:
    """Envia o pedido (ou reaproveita o já enviado) e devolve o id da tarefa."""
    record = task_dir(cfg) / "tarefa.json"
    if record.exists():
        return json.loads(record.read_text())["task_id"]
    response = requests.post(f"{API}/task", json=task_payload(cfg), headers=_headers(token),
                             timeout=300)
    response.raise_for_status()
    task_id = response.json()["task_id"]
    record.write_text(json.dumps({"task_id": task_id, "product": PRODUCT, "layers": LAYERS,
                                  "submitted_utc": datetime.now(UTC).isoformat()}, indent=2))
    return task_id


def wait(task_id, token, report=print, every=600, timeout_hours=48) -> None:
    started = time.time()
    last = None
    while True:
        response = requests.get(f"{API}/task/{task_id}", headers=_headers(token), timeout=120)
        response.raise_for_status()
        status = response.json().get("status")
        if status != last:
            report(f"AppEEARS {task_id[:8]}: {status}")
            last = status
        if status == "done":
            return
        if status in {"error", "deleted"}:
            raise RuntimeError(f"Tarefa AppEEARS {task_id}: {status}")
        if time.time() - started > timeout_hours * 3600:
            raise TimeoutError("AppEEARS não terminou no prazo; reenvie para continuar")
        time.sleep(every)


def download(cfg, task_id, token, report=print) -> list[Path]:
    """Baixa os arquivos do pacote (só NetCDF e metadados), conferindo o tamanho."""
    response = requests.get(f"{API}/bundle/{task_id}", headers=_headers(token), timeout=120)
    response.raise_for_status()
    files = [f for f in response.json()["files"]
             if f["file_name"].endswith((".nc", ".json", ".csv", ".txt", ".xml"))]
    out, records = task_dir(cfg), []
    for item in files:
        target = out / Path(item["file_name"]).name
        if not (target.exists() and target.stat().st_size == item["file_size"]):
            report(f"MODIS: {target.name} ({item['file_size'] / 2**20:.0f} MiB)")
            with requests.get(f"{API}/bundle/{task_id}/{item['file_id']}",
                              headers=_headers(token), stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(target, "wb") as fh:
                    for chunk in r.iter_content(2**20):
                        fh.write(chunk)
        if target.stat().st_size != item["file_size"]:
            raise RuntimeError(f"{target}: tamanho difere do anunciado pelo AppEEARS")
        records.append({"file": target.name, "bytes": item["file_size"],
                        "sha256": sha256_file(target)})
    (out / "manifest.json").write_text(json.dumps({
        "task_id": task_id, "files": records,
        "retrieved_utc": datetime.now(UTC).isoformat()}, indent=2))
    return [out / r["file"] for r in records]
