#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH -p cpu
#SBATCH -J disturbance
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Perturbação por célula (PRODES, DETER, BDQueimadas, MapBiomas). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/disturbance.sbatch
#
# Retomável: reenviar pula as tabelas já gravadas e conferidas.
source scripts/hpc/_common.sh

STEP="download e agregação por célula"
notify "🌳 $EXP: perturbação por célula (PRODES, DETER, BDQueimadas, MapBiomas)…"
run $PY -m amazon_chaos.cli disturbance fetch "$REGION"
STEP="tabela final"
run $PY -m amazon_chaos.cli disturbance build "$REGION"
notify "✅ $EXP: perturbação por célula pronta. Na máquina local: make pull REGION=$REGION"
