#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J atrasos
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Grade de τ ∈ {1, 2, 3, 5, 7} (+ mínimo da AMI) e atrasos ordinais {1, 2, 4, 7} na
# subamostra de D-024 (F2a, D-027). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/atrasos.sbatch
#
# Retomável por célula.
source scripts/hpc/_common.sh

notify "⏱️ $EXP: começando a grade de atrasos (F2a) na subamostra…"
STEP="grade de atrasos na subamostra"
run $PY -m amazon_chaos.cli descriptors delays "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: grade de atrasos (F2a) pronta.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
