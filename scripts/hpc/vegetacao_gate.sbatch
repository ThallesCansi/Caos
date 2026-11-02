#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH -p cpu
#SBATCH -J vegetacao_gate
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Portão das séries de vegetação de 8 dias: controles caóticos e lineares com 1.104 pontos,
# descritores do pré-registro de 8 dias (99 IAAFT), Wolf, Kantz, Cao e S-map (D-031,
# etapa 1). Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=xingu scripts/hpc/vegetacao_gate.sbatch   (REGION só nomeia os avisos)
#
# Retomável por série.
source scripts/hpc/_common.sh

notify "🧪 $EXP: começando o portão da vegetação (D-031)…"
STEP="portão da vegetação"
run $PY -m amazon_chaos.cli vegetation gate --workers "${SLURM_CPUS_PER_TASK:-14}"
notify "✅ $EXP: portão da vegetação pronto.
Na máquina local: make pull-gate
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
