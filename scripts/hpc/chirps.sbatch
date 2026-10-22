#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH -p cpu
#SBATCH -J chirps
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# CHIRPS v3 sat 2001–2024 recortado na caixa das regiões e chuva por célula (D-021).
# Guia: docs/hpc.md
#
#   sbatch scripts/hpc/chirps.sbatch
#
# Um NetCDF global de ~3,3 GB por vez, apagado depois do recorte: o servidor do CHC bane o
# IP diante de leituras parciais em paralelo. Retomável: reenviar continua do ano que falta.
NEEDS_REGION=0
source scripts/hpc/_common.sh

STEP="download e recorte do CHIRPS"
run $PY -m amazon_chaos.cli chirps fetch
for region in $($PY -c "from amazon_chaos.config import list_regions; print(*list_regions())"); do
  STEP="chuva por célula ($region)"
  run $PY -m amazon_chaos.cli chirps build "$region"
done
notify "✅ CHIRPS 2001–2024 baixado e agregado por célula.
Próximo: sbatch --export=ALL,REGION=<região>,SOURCES=precip_chirps scripts/hpc/precip.sbatch
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
