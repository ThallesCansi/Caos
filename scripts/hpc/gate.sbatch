#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH -p cpu
#SBATCH -J gate
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Gate F4: descritores pré-registrados em controles sintéticos. Guia: docs/hpc.md
#
#   sbatch scripts/hpc/gate.sbatch
#
# Resultado em data/processed/gate/<hash do pré-registro>/; na máquina local: make pull-gate
NEEDS_REGION=0
source scripts/hpc/_common.sh

STEP="gate F4"
run $PY -m amazon_chaos.cli gate run --workers "${SLURM_CPUS_PER_TASK:-32}"
