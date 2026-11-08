#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH -p cpu
#SBATCH -J vegetacao_fogo_memoria
#SBATCH --time=12:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Memória e sensibilidade da floresta depois do fogo (D-033), na subamostra da etapa 3 da
# D-031: pontos com a qualidade estrita tirados dos cubos, dia da queima do MCD64A1, curvas
# Δ(k) com as duas linhas de base, déficit e diferença residual por episódio, modelo de
# mudança de sensibilidade com as variantes e os placebos, seca antecedente e o painel da
# D-031 corrigido. Saída em data/processed/<exp>/vegetacao/fogo_subamostra/memoria.
# Exige os episódios e pontos de vegetacao_fogo_local.sbatch. Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/vegetacao_fogo_memoria.sbatch
#   sbatch --export=ALL,REGION=xingu,FROM=memoria scripts/hpc/vegetacao_fogo_memoria.sbatch
#     (reaproveita os pontos estritos já gravados)
source scripts/hpc/_common.sh
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4} OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}

notify "🔥 $EXP: começando a memória do fogo (D-033)…"
if [ "${FROM:-}" != memoria ]; then
  STEP="pontos com a qualidade estrita"
  run $PY -m amazon_chaos.cli vegetation fire-strict "$REGION"
  notify "🛰️ $EXP: pontos estritos prontos ($((SECONDS / 60)) min)"
fi
STEP="curvas, métricas e modelos"
run $PY -m amazon_chaos.cli vegetation fire-memory "$REGION"
notify "✅ $EXP: memória do fogo (D-033) pronta.
Na máquina local: make pull REGION=$REGION
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
