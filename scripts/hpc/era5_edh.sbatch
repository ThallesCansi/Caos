#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH -p cpu
#SBATCH -J era5-edh
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@600
#
# ERA5 horário pelo Earth Data Hub + séries diárias. Guia: docs/HPC_EDH.md
#
#   mkdir -p logs && sbatch scripts/hpc/era5_edh.sbatch
#   CONFIG=configs/tapajos_1990_2024.yaml VERIFY=0 sbatch scripts/hpc/era5_edh.sbatch
#
# Reenviar o mesmo comando retoma do último mês validado.
set -Eeuo pipefail

CONFIG=${CONFIG:-configs/xingu_1990_2024.yaml}
START=${START:-1990-01-01}
END=${END:-2024-12-31}
VERIFY=${VERIFY:-1}
PROCESS=${PROCESS:-1}
WORKERS=${WORKERS:-${SLURM_CPUS_PER_TASK:-16}}

cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p logs
LOG="logs/${SLURM_JOB_NAME:-era5-edh}-${SLURM_JOB_ID:-local}.out"
if [[ -z ${SLURM_JOB_ID:-} ]]; then
  exec > >(tee -a "$LOG") 2>&1  # execução direta (tmux no nó de login)
fi
set -a
source ~/.edh_env
[[ -f ~/.telegram_env ]] && source ~/.telegram_env
set +a

PY=.venv/bin/python
export _TYPER_STANDARD_TRACEBACK=1 PYTHONUNBUFFERED=1
EXP=$($PY -c "from amazon_chaos.config import load_config; print(load_config('$CONFIG')['experiment_id'])")
WHERE="job ${SLURM_JOB_ID:-local} em $(hostname -s)"
STEP="preparação"
CHILD=""

notify() { scripts/hpc/send_telegram.sh "$1" || true; }

on_error() {
  local code=$?
  notify "❌ O job ERA5 de $EXP parou na etapa: $STEP ($WHERE, código $code).

Últimas linhas do log ($LOG):
$(tail -n 8 "$LOG" 2>/dev/null | cut -c1-300)

O que já foi validado continua salvo; corrija e reenvie o sbatch."
  exit "$code"
}

on_timeout() {
  trap - ERR
  notify "⏰ O tempo do $WHERE está acabando (etapa: $STEP).
Tudo o que já foi validado está salvo. Reenvie o mesmo sbatch para continuar de onde parou. 🔁"
  [[ -n $CHILD ]] && kill "$CHILD" 2>/dev/null && wait "$CHILD" 2>/dev/null
  exit 0
}

trap on_error ERR
trap on_timeout USR1

# Em segundo plano para que o aviso de fim de tempo (USR1) seja tratado durante a execução.
run() { "$@" & CHILD=$!; wait "$CHILD"; CHILD=""; }

STEP="download do Earth Data Hub"
if [[ $VERIFY == 1 ]]; then verify=--verify; else verify=--no-verify; fi
run $PY -m amazon_chaos.pilot_cli edh-download "$START" "$END" \
  --config "$CONFIG" --workers "$WORKERS" "$verify"

if [[ $PROCESS == 1 ]]; then
  STEP="séries diárias"
  notify "⚙️ $EXP: gerando as séries diárias, ano a ano…"
  for year in $(seq "${START:0:4}" "${END:0:4}"); do
    first="$year-01-01"; last="$year-12-31"
    [[ $first < $START ]] && first=$START
    [[ $last > $END ]] && last=$END
    STEP="séries diárias de $year"
    run $PY -m amazon_chaos.pilot_cli process "$first" "$last" --config "$CONFIG" --source edh
  done
  notify "✅ Tudo pronto: séries diárias de $EXP ($START → $END) em
$PWD/data/processed/$EXP

Para trazer para a sua máquina (na raiz do projeto local):
rsync -avP --partial $(whoami)@$(hostname -f):$PWD/data/processed/$EXP/ data/processed/$EXP/

⏱️ Job completo em $((SECONDS / 3600)) h $((SECONDS % 3600 / 60)) min. Bom trabalho! 🌳"
fi
