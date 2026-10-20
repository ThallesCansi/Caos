#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH -p cpu
#SBATCH -J era5
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# ERA5 horário (Earth Data Hub) → séries diárias de uma região. Guia: docs/hpc.md
#
#   sbatch --export=ALL,REGION=tapajos scripts/hpc/era5.sbatch
#   sbatch --export=ALL,REGION=xingu,START=2024-01-01,END=2024-01-31 scripts/hpc/era5.sbatch
#
# Variáveis: REGION (obrigatória), START, END, VERIFY=auto|1|0, DOWNLOAD=1|0,
# PROCESS=1|0, WORKERS. Reenviar o mesmo comando retoma do último mês validado.
source scripts/hpc/_common.sh

START=${START:-1990-01-01}
END=${END:-2024-12-31}
VERIFY=${VERIFY:-auto}
DOWNLOAD=${DOWNLOAD:-1}
PROCESS=${PROCESS:-1}
WORKERS=${WORKERS:-${SLURM_CPUS_PER_TASK:-16}}
CLI="$PY -m amazon_chaos.cli"

STEP="limite e grade da região"
run $CLI region prepare "$REGION" --no-context

if [[ $VERIFY == auto ]]; then
  # Confere contra o CDS quando houver meses CDS dessa região (D-007).
  compgen -G "data/raw/$EXP/era5/*/manifest.json" >/dev/null && VERIFY=1 || VERIFY=0
fi

if [[ $DOWNLOAD == 1 ]]; then
  STEP="download do Earth Data Hub"
  if [[ $VERIFY == 1 ]]; then verify=--verify; else verify=--no-verify; fi
  run $CLI era5 edh "$REGION" "$START" "$END" --workers "$WORKERS" "$verify"
fi

if [[ $PROCESS == 1 ]]; then
  STEP="séries diárias"
  notify "⚙️ $EXP: gerando as séries diárias, ano a ano…"
  for year in $(seq "${START:0:4}" "${END:0:4}"); do
    first="$year-01-01"; last="$year-12-31"
    [[ $first < $START ]] && first=$START
    [[ $last > $END ]] && last=$END
    STEP="séries diárias de $year"
    run $CLI era5 process "$REGION" "$first" "$last" --source edh
  done
  if [[ $START == 1990-01-01 && $END == 2024-12-31 ]]; then
    STEP="resumo regional"
    run $CLI era5 summarize "$REGION"
  fi
  notify "✅ Tudo pronto: séries diárias de $EXP ($START → $END) em
$PWD/data/processed/$EXP

Na máquina local, na raiz do projeto:
make pull REGION=$REGION

⏱️ Job completo em $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min. Bom trabalho! 🌳"
fi
