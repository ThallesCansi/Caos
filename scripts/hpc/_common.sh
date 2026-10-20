# Cabeçalho comum dos jobs do HPC; incluído com `source scripts/hpc/_common.sh`.
#
# Define: PY, REGION, EXP, LOG, STEP, notify, run. Trata erro (aviso com as últimas
# linhas do log) e fim de tempo do Slurm (USR1, 10 min antes; reenviar retoma).
# Guia: docs/hpc.md
set -Eeuo pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p logs
JOB_NAME=${SLURM_JOB_NAME:-$(basename "$0" .sbatch)}
LOG="logs/${JOB_NAME}-${SLURM_JOB_ID:-local}.out"
if [[ -z ${SLURM_JOB_ID:-} ]]; then
  exec > >(tee -a "$LOG") 2>&1  # execução direta (tmux no nó de login)
fi

: "${REGION:?defina REGION, por exemplo: sbatch --export=ALL,REGION=xingu $0}"

set -a
[[ -f ~/.edh_env ]] && source ~/.edh_env
[[ -f ~/.telegram_env ]] && source ~/.telegram_env
set +a

PY=.venv/bin/python
export _TYPER_STANDARD_TRACEBACK=1 PYTHONUNBUFFERED=1
EXP=$($PY -c "from amazon_chaos.config import load_region; print(load_region('$REGION')['experiment_id'])")
WHERE="job ${SLURM_JOB_ID:-local} em $(hostname -s)"
STEP="preparação"
CHILD=""

notify() { $PY -m amazon_chaos.cli notify "$1" >/dev/null || true; }

on_error() {
  local code=$?
  notify "❌ $JOB_NAME de $EXP parou na etapa: $STEP ($WHERE, código $code).

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

# Em segundo plano, para que o aviso de fim de tempo (USR1) seja tratado durante a execução.
run() { "$@" & CHILD=$!; wait "$CHILD"; CHILD=""; }
