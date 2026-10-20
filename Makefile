# Atalhos do projeto. `make` sem alvo lista os comandos.
REGION ?= xingu
REGIONS ?= xingu tapajos
NOTEBOOKS_BY_REGION := 03_clima
HTML := reports/html

.PHONY: help sync test check notebooks overleaf pull pull-gate hpc-status hpc-code

help:  ## lista os alvos
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

sync:  ## instala o ambiente exatamente como no uv.lock
	uv sync --frozen --dev

test:  ## testes
	uv run --frozen pytest

check:  ## estilo (ruff) e cadernos (marimo check)
	uv run --frozen ruff check .
	uv run --frozen marimo check notebooks/

notebooks:  ## executa todos os cadernos e exporta HTML (um por região quando couber)
	@mkdir -p $(HTML)
	@for nb in notebooks/[0-9]*.py; do \
	  name=$$(basename $$nb .py); \
	  if echo " $(NOTEBOOKS_BY_REGION) " | grep -q " $$name "; then \
	    for r in $(REGIONS); do \
	      echo "→ $$name ($$r)"; \
	      uv run --frozen marimo export html $$nb -o $(HTML)/$${name}_$$r.html -f -- --region $$r || exit 1; \
	    done; \
	  else \
	    echo "→ $$name"; \
	    uv run --frozen marimo export html $$nb -o $(HTML)/$$name.html -f || exit 1; \
	  fi; \
	done

overleaf:  ## copia figuras e tabelas finais para reports/overleaf (nomes estáveis)
	uv run --frozen python -m amazon_chaos.nb overleaf

pull:  ## traz do HPC os processados de REGION (ex.: make pull REGION=tapajos)
	scripts/hpc/sync.sh pull $(REGION)

pull-gate:  ## traz do HPC os resultados do gate F4
	scripts/hpc/sync.sh pull-gate

hpc-status:  ## commit, fila e espaço em disco no HPC
	scripts/hpc/sync.sh status

hpc-code:  ## git push e atualização do código no HPC
	scripts/hpc/sync.sh code
