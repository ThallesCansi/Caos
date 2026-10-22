# Atalhos do projeto. `make` sem alvo lista os comandos.
REGION ?= xingu
HTML := reports/html

.PHONY: help sync test check notebooks capas bundle site publicar overleaf pull pull-gate hpc-status hpc-code

help:  ## lista os alvos
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

sync:  ## instala o ambiente exatamente como no uv.lock
	uv sync --frozen --dev

test:  ## testes
	uv run --frozen pytest

check:  ## estilo (ruff) e cadernos (marimo check)
	uv run --frozen ruff check .
	uv run --frozen marimo check notebooks/

notebooks:  ## executa todos os cadernos e exporta HTML (reports/html/)
	@mkdir -p $(HTML)
	@rm -f reports/figures/*/index.json reports/tables/*/index.json  # índices refeitos pela execução
	@rm -f $(HTML)/*.html
	@for nb in notebooks/[0-9]*.py; do \
	  name=$$(basename $$nb .py); \
	  echo "→ $$name"; \
	  uv run --frozen marimo export html $$nb -o $(HTML)/$$name.html -f || exit 1; \
	done

capas:  ## capas dos cadernos na galeria do Marimo (depois de make notebooks)
	uv run --frozen python -m amazon_chaos.covers

bundle:  ## pacote de visualização (configs + dados processados) para rodar fora do repositório
	uv run --frozen python -m amazon_chaos.bundle

site: capas bundle  ## galeria pública em site/ (leitura dos capítulos + molab + pacote de dados)
	uv run --frozen python -m amazon_chaos.site

publicar: site  ## envia site/ para o ramo gh-pages (um só commit, substitui o anterior)
	cd site && rm -rf .git && git init -q -b gh-pages && git add -A \
	  && git -c user.name="$$(git -C .. config user.name)" -c user.email="$$(git -C .. config user.email)" commit -q -m "Galeria dos cadernos" \
	  && git push -q -f "$$(git -C .. remote get-url --push origin)" gh-pages && rm -rf .git

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
