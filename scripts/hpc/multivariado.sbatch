#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J multivariado
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Temperatura + umidade específica: previsão conjunta contra substitutas FT e IAAFT
# multivariadas na série da bacia (199) e IAAFT multivariadas na subamostra (39)
# (F2c, D-027). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/multivariado.sbatch
#
# Retomável por parte (bacia) e por célula da subamostra.
source scripts/hpc/_common.sh

notify "🔗 $EXP: começando temperatura + umidade (F2c)…"
STEP="temperatura + umidade"
run $PY -m amazon_chaos.cli descriptors multivariate "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: temperatura + umidade (F2c) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
