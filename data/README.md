# Dados locais

O conteúdo destas pastas não é versionado. A organização e os contratos estão em [docs/dados.md](../docs/dados.md).

- `external/<região>/`: limites, grade e cartografia de contexto, com `sources.json` (URL, data, SHA-256).
- `raw/<experimento>/`: bytes originais das fontes, imutáveis, com manifesto por arquivo.
- `processed/<experimento>/`: diários, resumos, perturbação e descritores por célula.
- `cache/`: descartável.

Para guardar os dados fora do repositório (por exemplo, numa área de projeto do HPC), defina `AMAZON_CHAOS_DATA_DIR`.
