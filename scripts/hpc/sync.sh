#!/usr/bin/env bash
# Ponte entre a máquina local e o HPC. Roda na máquina LOCAL, na raiz do projeto.
#
#   scripts/hpc/sync.sh status                 # commit, fila e espaço no HPC
#   scripts/hpc/sync.sh code                   # git push local + git pull e setup no HPC
#   scripts/hpc/sync.sh pull <região> [--raw]  # traz os processados (e os brutos, com --raw)
#   scripts/hpc/sync.sh push-external <região> # envia limite e grade, se o HPC não tiver rede
#
# HPC_HOST (padrão: hpc, alias do ~/.ssh/config) e HPC_DIR (padrão: Caos, relativo à home).
set -euo pipefail
cd "$(dirname "$0")/../.."
HOST=${HPC_HOST:-hpc}
DIR=${HPC_DIR:-Caos}
RSYNC=(rsync -avh --partial --info=progress2)

exp_of() {
  uv run --frozen python -c \
    "from amazon_chaos.config import load_region; print(load_region('$1')['experiment_id'])"
}

case ${1:-} in
  status)
    ssh "$HOST" "cd $DIR && git log -1 --format='%h %s (%cr)' && echo && \
      (squeue -u \$USER 2>/dev/null || true) && echo && du -sh data/raw/* data/processed/* 2>/dev/null; \
      df -h . | tail -1"
    ;;
  code)
    git push
    ssh "$HOST" "cd $DIR && git pull --ff-only && bash scripts/hpc/setup.sh"
    ;;
  pull)
    region=${2:?região}; exp=$(exp_of "$region")
    mkdir -p "data/processed/$exp"
    "${RSYNC[@]}" "$HOST:$DIR/data/processed/$exp/" "data/processed/$exp/"
    if [[ ${3:-} == --raw ]]; then
      mkdir -p "data/raw/$exp"
      "${RSYNC[@]}" "$HOST:$DIR/data/raw/$exp/" "data/raw/$exp/"
    fi
    ;;
  push-external)
    region=${2:?região}; exp=$(exp_of "$region")
    src=$(uv run --frozen python -c \
      "from amazon_chaos.config import load_region; from pathlib import Path; \
print(Path(load_region('$region')['spatial'].get('basin_source', 'data/external/$region/x')).parent)")
    ssh "$HOST" "mkdir -p $DIR/$src $DIR/data/processed/$exp"
    "${RSYNC[@]}" "$src/" "$HOST:$DIR/$src/"
    "${RSYNC[@]}" "data/processed/$exp/basin_grid.geojson" "$HOST:$DIR/data/processed/$exp/"
    ;;
  *)
    sed -n '2,10p' "$0"; exit 1
    ;;
esac
