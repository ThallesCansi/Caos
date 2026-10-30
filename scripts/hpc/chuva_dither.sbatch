#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J chuva_dither
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Chuva (ERA5 e CHIRPS): dither em cada substituta, em todas as células, e erro espectral do
# IAAFT na subamostra (F2i, D-027). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/chuva_dither.sbatch
#
# Retomável por bloco.
source scripts/hpc/_common.sh

notify "🌧️ $EXP: começando o dither da chuva (F2i)…"
STEP="dither da chuva"
run $PY -m amazon_chaos.cli descriptors dither "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: dither da chuva (F2i) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
