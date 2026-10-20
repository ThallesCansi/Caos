#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH -p cpu
#SBATCH -J descriptors
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Descritores pré-registrados por célula, com substitutas (Etapa 3). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/descriptors.sbatch
#   sbatch --export=ALL,REGION=tapajos --dependency=afterany:<jobid> scripts/hpc/descriptors.sbatch
#
# Cerca de 440 s de CPU por célula: ~6 h por bacia em 16 núcleos (cota do usuário).
# Retomável: reenviar continua do primeiro bloco de células que falta.
source scripts/hpc/_common.sh

STEP="descritores por célula"
run $PY -m amazon_chaos.cli descriptors run "$REGION" --workers "${SLURM_CPUS_PER_TASK:-16}"
notify "✅ $EXP: descritores por célula prontos.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
