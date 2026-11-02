#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH -p cpu
#SBATCH -J vegetacao_fogo
#SBATCH --time=48:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# A floresta depois do fogo (D-031, etapa 3): episódios no MCD64A1 com a cobertura do
# MCD12Q1, pedido de pontos ao AppEEARS, espera e download, Δ(k) e resposta ao clima.
# Exige os downloads de fogo e cobertura. Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/vegetacao_fogo.sbatch
#   sbatch --export=ALL,REGION=xingu,FROM=pontos scripts/hpc/vegetacao_fogo.sbatch
#     (retoma da espera dos pontos já pedidos, sem refazer os episódios)
source scripts/hpc/_common.sh

notify "🔥 $EXP: começando os episódios de fogo (D-031, etapa 3)…"
if [ "${FROM:-}" != pontos ]; then
  STEP="episódios de fogo"
  run $PY -m amazon_chaos.cli vegetation episodes "$REGION"
fi
STEP="pontos do AppEEARS"
run $PY -m amazon_chaos.cli vegetation fetch-points "$REGION"
STEP="Δ(k) e resposta ao clima"
run $PY -m amazon_chaos.cli vegetation fire "$REGION"
notify "✅ $EXP: fogo (etapa 3) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
