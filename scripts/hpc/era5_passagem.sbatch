#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH -p cpu
#SBATCH -J era5_passagem
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# skt, t2m e tcc do ERA5 às 13–15 UTC, junho a setembro de 2001–2024, para comparar com o
# MODIS LST no horário da passagem do Terra (F2e, D-027). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/era5_passagem.sbatch
#
# Poucos fragmentos do Zarr por ano. Retomável por ano.
source scripts/hpc/_common.sh

notify "🌡️ $EXP: baixando o skt do ERA5 na passagem do MODIS Terra (F2e)…"
STEP="skt na passagem do Terra"
run $PY -m amazon_chaos.cli era5 passage "$REGION"
notify "✅ $EXP: skt, t2m e tcc da passagem do Terra prontos.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
