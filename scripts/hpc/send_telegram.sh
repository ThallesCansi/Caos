#!/usr/bin/env bash
set -euo pipefail
source ~/.telegram_env

MSG="${1:-Job finalizado.}"

curl -sS -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TG_CHAT_ID}" \
  --data-urlencode "text=${MSG}" \
  --data "disable_web_page_preview=true" \
  >/dev/null
