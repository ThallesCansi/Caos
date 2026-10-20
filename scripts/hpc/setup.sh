#!/usr/bin/env bash
# Prepara (ou confere) o projeto no HPC. Idempotente: rode depois de cada `git pull`.
#
#   bash scripts/hpc/setup.sh            # ambiente, segredos, chave EDH
#   NETWORK=1 bash scripts/hpc/setup.sh  # também testa a rede de um nó de computação
#
# Nunca imprime segredos. Guia: docs/hpc.md
set -uo pipefail
cd "$(dirname "$0")/../.."

ok() { printf '  ✅ %s\n' "$1"; }
warn() { printf '  ⚠️  %s\n' "$1"; }
fail() { printf '  ❌ %s\n' "$1"; FAILED=1; }
FAILED=0

echo "Projeto: $PWD ($(git rev-parse --short HEAD 2>/dev/null || echo 'sem git'))"

echo "Git"
if git rev-parse --git-dir >/dev/null 2>&1; then
  [[ -z $(git status --porcelain --untracked-files=no) ]] && ok "árvore limpa" \
    || warn "há arquivos versionados modificados no HPC (git status)"
  git remote get-url origin >/dev/null 2>&1 && ok "origin: $(git remote get-url origin)" \
    || warn "sem remote origin"
else
  fail "não é um clone Git; veja docs/hpc.md, seção 1"
fi

echo "Ambiente Python"
if ! command -v uv >/dev/null; then
  fail "uv ausente: curl -LsSf https://astral.sh/uv/install.sh | sh"
else
  uv sync --frozen --quiet && ok "uv sync --frozen ($(uv --version))" || fail "uv sync falhou"
fi
mkdir -p logs data/raw data/processed data/external data/cache
ok "pastas logs/ e data/"

echo "Segredos (só a presença e as permissões)"
check_secret() {
  local file=$1 what=$2
  if [[ ! -f $file ]]; then
    warn "$file ausente: $what"
  elif [[ $(stat -c %a "$file") != 600 ]]; then
    warn "$file com permissão $(stat -c %a "$file"); use chmod 600 $file"
  else
    ok "$file"
  fi
}
check_secret ~/.edh_env "chave do Earth Data Hub (EDH_TOKEN=...), necessária para era5.sbatch"
check_secret ~/.telegram_env "avisos no Telegram (TG_TOKEN, TG_CHAT_ID); opcional"
check_secret ~/.netrc "login do NASA Earthdata (AppEEARS/MODIS); necessário na Etapa 2"

if [[ -f ~/.edh_env ]] && [[ -x .venv/bin/python ]]; then
  echo "Chave do Earth Data Hub"
  (set -a; source ~/.edh_env; set +a; .venv/bin/python scripts/hpc/check_edh.py) \
    | grep -E "HTTP|❌|⚠️" | sed 's/^/  /'
fi

if [[ ${NETWORK:-0} == 1 ]] && command -v srun >/dev/null; then
  echo "Rede de um nó de computação"
  # Qualquer código HTTP (inclusive 401) prova que há rede; timeout, não.
  srun -p cpu -n1 --time=5 .venv/bin/python -c $'import urllib.request as u, urllib.error as e\ntry:\n    print("  ✅ HTTP", u.urlopen("https://data.earthdatahub.destine.eu", timeout=15).status)\nexcept e.HTTPError as x:\n    print("  ✅ HTTP", x.code)' \
    2>&1 | tail -1 || warn "sem rede no nó: rode os downloads no nó de login, dentro do tmux"
fi

echo "Regiões configuradas"
.venv/bin/python -m amazon_chaos.cli region list | sed 's/^/  /'

exit $FAILED
