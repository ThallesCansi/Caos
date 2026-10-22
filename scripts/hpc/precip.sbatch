#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=15
#SBATCH -p cpu
#SBATCH -J precip
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Descritores ordinais da chuva por célula, no ERA5 e no CHIRPS (D-021). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu,SOURCES=precip_era5 scripts/hpc/precip.sbatch
#   sbatch --export=ALL,REGION=xingu,SOURCES=precip_chirps scripts/hpc/precip.sbatch
#
# Cerca de 45 s de CPU por célula e fonte: ~40 min por bacia e fonte em 15 núcleos (15, e
# não 16, para caber ao lado do chirps.sbatch na cota do usuário). Retomável por bloco.
source scripts/hpc/_common.sh

SOURCES=${SOURCES:-precip_era5,precip_chirps}
STEP="descritores da chuva ($SOURCES)"
run $PY -m amazon_chaos.cli descriptors precip "$REGION" --sources "$SOURCES" \
  --workers "${SLURM_CPUS_PER_TASK:-15}"
notify "✅ $EXP: descritores da chuva prontos ($SOURCES).
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
