#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH -p cpu
#SBATCH -J gate_realista
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# Gate com nulas realistas (AR sazonal, AR com tendência, SETAR, AR-GARCH) e Wolf, Kantz,
# Cao e S-map nos controles do gate (F2f, F2d, F2g, F2h; D-027). Guia: docs/hpc.md
#
#   sbatch scripts/hpc/gate_realista.sbatch
#
# Retomável por série. Resultado em data/processed/gate/realista_<hash>/;
# na máquina local: make pull-gate
NEEDS_REGION=0
source scripts/hpc/_common.sh

notify "🧪 Começando o gate com nulas realistas (F2f, com Wolf, Kantz, Cao e S-map)…"
STEP="gate com nulas realistas"
run $PY -m amazon_chaos.cli gate realistic --workers "${SLURM_CPUS_PER_TASK:-16}"
notify "✅ Gate com nulas realistas (F2f) pronto.
Na máquina local: make pull-gate
⏱️ $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min"
