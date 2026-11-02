#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J estimadores_checagem
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Kantz nos raios de 1%, 2%, 5% e 10% e diagnósticos do Wolf, na série da bacia
# (199 IAAFT) e na subamostra (39 IAAFT) (G5; complementa F2d). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/estimadores_checagem.sbatch
#
# Retomável por célula da subamostra.
source scripts/hpc/_common.sh

notify "🧭 $EXP: começando Kantz e Wolf (G5)…"
STEP="Kantz e Wolf (G5)"
run $PY -m amazon_chaos.cli descriptors checks "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: Kantz e Wolf (G5) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
