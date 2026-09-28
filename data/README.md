# Dados locais

Estas pastas fazem parte da arquitetura, mas seus conteúdos pesados não são versionados.

- `raw/`: bytes originais das fontes; imutáveis.
- `external/`: dados auxiliares externos.
- `interim/`: recortes/conversões intermediárias.
- `processed/`: dados harmonizados para análise.
- `cache/`: artefatos descartáveis.

Depois de cada aquisição relevante, execute:

```bash
uv run amazon-chaos manifest data/raw --output metadata/manifests/raw_files.csv
```
