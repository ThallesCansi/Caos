"""Diagnostica a chave do Earth Data Hub sem imprimi-la.

    set -a; source ~/.edh_env; set +a; .venv/bin/python scripts/hpc/check_edh.py
"""

import os
import string

import requests

from amazon_chaos.io.era5_edh import EDH_URL

token = os.environ.get("EDH_TOKEN", "")
print(f"EDH_TOKEN: {len(token)} caracteres")
if not token or "cole-a-chave" in token:
    raise SystemExit("❌ EDH_TOKEN vazio ou ainda com o texto de exemplo em ~/.edh_env")
odd = sorted({c for c in token if c not in string.ascii_letters + string.digits + "-_."})
if odd:
    print(f"⚠️ Caracteres inesperados na chave: {[repr(c) for c in odd]} (aspas, espaço, \\r?)")
if token != token.strip():
    print("⚠️ A chave tem espaço ou quebra de linha nas pontas")

url = f"{EDH_URL}/zarr.json"
for label, kwargs in [
    ("sem chave", {}),
    ("chave (Basic edh:<chave>)", {"auth": ("edh", token.strip())}),
]:
    response = requests.get(url, timeout=30, allow_redirects=False, **kwargs)
    print(f"\n{label}: HTTP {response.status_code}")
    for header in ["Location", "WWW-Authenticate"]:
        if header in response.headers:
            print(f"  {header}: {response.headers[header]}")
    if not response.ok:
        print(f"  resposta: {response.text[:300]!r}")

print("\nHTTP 200 com chave = chave válida. 401 com chave = gerar nova chave em Quota & API Keys.")
