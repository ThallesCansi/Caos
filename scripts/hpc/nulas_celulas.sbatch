#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J nulas_celulas
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Nulas realistas (AR(1) sazonal, tendência, SETAR, GARCH por MV) ajustadas em cada
# célula da subamostra, com os oito descritores (39 IAAFT) e o S-map (G2b). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/nulas_celulas.sbatch
#
# Retomável por célula.
source scripts/hpc/_common.sh

notify "🧪 $EXP: começando nulas por célula (G2b)…"
STEP="nulas por célula (G2b)"
run $PY -m amazon_chaos.cli gate cells "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: nulas por célula (G2b) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
