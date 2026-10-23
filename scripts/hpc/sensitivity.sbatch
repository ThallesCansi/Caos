#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J sensitivity
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# 199 substitutas, τ = 2 e ruído do EDH numa subamostra estratificada de ~60 células
# (D-024). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/sensitivity.sbatch
#
# Cerca de 30 min de CPU por célula no HPC: ~2 h por bacia em 14 núcleos. Retomável por célula.
source scripts/hpc/_common.sh

STEP="sensibilidade numa subamostra"
run $PY -m amazon_chaos.cli descriptors sensitivity "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: sensibilidade (199 substitutas, τ = 2, ruído do EDH) pronta.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
