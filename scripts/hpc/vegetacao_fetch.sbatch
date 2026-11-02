#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH -p cpu
#SBATCH -J vegetacao_fetch
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Espera e baixa os pedidos do AppEEARS da D-031: LAI e refletâncias na subamostra e área
# queimada (MCD64A1) na bacia. Os pedidos já enviados são reaproveitados. Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/vegetacao_fetch.sbatch
source scripts/hpc/_common.sh

notify "🛰️ $EXP: esperando o AppEEARS (vegetação e fogo, D-031)…"
STEP="download da vegetação"
run $PY -m amazon_chaos.cli vegetation fetch "$REGION" --part vegetacao
STEP="download da área queimada"
run $PY -m amazon_chaos.cli vegetation fetch "$REGION" --part fogo
notify "✅ $EXP: vegetação e área queimada baixadas.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
