#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH -p cpu
#SBATCH -J vegetacao_fogo_local
#SBATCH --time=12:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# A floresta depois do fogo (D-031, etapa 3) na subamostra das etapas 1 e 2: episódios e
# controles só nessas células, pontos tirados dos cubos de área já baixados (sem a fila do
# AppEEARS), Δ(k) e resposta ao clima. Saída em data/processed/<exp>/vegetacao/fogo_subamostra.
# Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/vegetacao_fogo_local.sbatch
#   sbatch --export=ALL,REGION=xingu,FROM=fogo scripts/hpc/vegetacao_fogo_local.sbatch
#     (reaproveita episódios e pontos já gravados)
source scripts/hpc/_common.sh

notify "🔥 $EXP: começando o fogo na subamostra (D-031, etapa 3)…"
if [ "${FROM:-}" != fogo ]; then
  STEP="episódios e pontos dos cubos"
  run $PY -m amazon_chaos.cli vegetation episodes "$REGION" --local
fi
STEP="Δ(k) e resposta ao clima"
run $PY -m amazon_chaos.cli vegetation fire "$REGION" --local
notify "✅ $EXP: fogo na subamostra (etapa 3) pronto.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
