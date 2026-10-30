#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J smap
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# S-map em todas as células: ganho da previsão local sobre o AR linear, horizontes 1, 3 e 7
# dias, teste de Diebold–Mariano (F2g, D-027). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/smap.sbatch
#
# Retomável por bloco.
source scripts/hpc/_common.sh

notify "🔭 $EXP: começando o S-map nas células (F2g)…"
STEP="S-map nas células"
run $PY -m amazon_chaos.cli descriptors smap "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: S-map nas células (F2g) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
