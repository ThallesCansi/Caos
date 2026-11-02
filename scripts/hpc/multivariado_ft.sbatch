#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J multivariado_ft
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Temperatura + umidade na subamostra contra 39 FT multivariadas, com o diagnóstico
# do espectro cruzado das FT e IAAFT (G5; complementa F2c). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/multivariado_ft.sbatch
#
# Retomável por célula.
source scripts/hpc/_common.sh

notify "🔗 $EXP: começando T + q contra a FT (G5)…"
STEP="T + q contra a FT (G5)"
run $PY -m amazon_chaos.cli descriptors multivariate-ft "$REGION" \
  --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: T + q contra a FT (G5) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
