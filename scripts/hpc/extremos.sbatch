#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J extremos
#SBATCH --time=16:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Mínima, máxima e amplitude térmica: entropia e complexidade ordinais com 39 IAAFT em
# todas as células e janelas; RQA·DET e erro de previsão na subamostra (F2b, D-027).
# Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/extremos.sbatch
#
# Retomável por bloco.
source scripts/hpc/_common.sh

notify "🌡️ $EXP: começando o lote da mínima, máxima e amplitude (F2b)…"
STEP="lote da mínima, máxima e amplitude"
run $PY -m amazon_chaos.cli descriptors extremes "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: lote da mínima, máxima e amplitude (F2b) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
