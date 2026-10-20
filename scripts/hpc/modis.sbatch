#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH -p cpu
#SBATCH -J modis
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# MODIS LST (MOD11A2) pelo AppEEARS → tabela por célula (checagem D-011). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/modis.sbatch
#
# Exige ~/.netrc com "machine urs.earthdata.nasa.gov login <usuário> password <senha>".
# O processamento é no servidor da NASA (horas); o job quase não usa CPU enquanto espera.
source scripts/hpc/_common.sh

STEP="pedido e download no AppEEARS"
run $PY -m amazon_chaos.cli modis fetch "$REGION"
STEP="LST por célula"
run $PY -m amazon_chaos.cli modis build "$REGION"
notify "✅ $EXP: MODIS LST por célula pronto. Na máquina local: make pull REGION=$REGION"
