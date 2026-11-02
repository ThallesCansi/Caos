#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J vegetacao
#SBATCH --time=24:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Floresta como variável dinâmica (D-031): cobertura do MODIS, séries de LAI e NDMI por
# célula da subamostra e etapas 1 e 2 (vegetação isolada e com a atmosfera). Exige os
# downloads de `vegetacao_fetch.sbatch`. Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu,MASK=mapbiomas scripts/hpc/vegetacao.sbatch
#
# Retomável por célula.
source scripts/hpc/_common.sh

notify "🌳 $EXP: começando a vegetação (D-031)…"
STEP="download da cobertura"
run $PY -m amazon_chaos.cli vegetation fetch "$REGION" --part cobertura
STEP="séries de LAI e NDMI"
run $PY -m amazon_chaos.cli vegetation build "$REGION" --mask "${MASK:-mapbiomas}"
STEP="etapas 1 e 2"
run $PY -m amazon_chaos.cli vegetation dynamics "$REGION" --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: vegetação (etapas 1 e 2) pronta.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
