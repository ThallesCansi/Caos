#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J estimadores
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Wolf, Kantz e Cao na série média da bacia (199 IAAFT) e na subamostra de D-024 (39 IAAFT)
# (F2d, F2h; D-027). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/estimadores.sbatch
#
# Retomável por parte (bacia, subamostra).
source scripts/hpc/_common.sh

notify "🧭 $EXP: começando Wolf, Kantz e Cao (F2d, F2h)…"
STEP="Wolf, Kantz e Cao"
run $PY -m amazon_chaos.cli descriptors estimators "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: Wolf, Kantz e Cao (F2d, F2h) prontos.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
