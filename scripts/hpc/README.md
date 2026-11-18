# Jobs do HPC

As análises mais pesadas do trabalho (download do ERA5, substitutas em todas as células, portões com controles sintéticos, vegetação do MODIS) rodaram num cluster com Slurm. Os scripts desta pasta registram exatamente como cada uma foi feita. Para ler os resultados nada disso é necessário: os cadernos usam os dados já processados.

O passo a passo (acesso, ambiente, segredos, ordem dos jobs) está em [docs/hpc.md](../../docs/hpc.md). Todo job chama a CLI do projeto (`amazon-chaos …`), compartilha o cabeçalho de [`_common.sh`](_common.sh) e se submete da raiz do repositório:

```bash
sbatch --export=ALL,REGION=xingu scripts/hpc/era5.sbatch
```

## Infraestrutura

| Arquivo | Para quê |
|---|---|
| `sync.sh` | ponte entre a máquina local e o HPC (`make pull`, `make hpc-code`, `make hpc-status`) |
| `setup.sh` | prepara ou confere o ambiente no HPC, depois de cada `git pull` |
| `_common.sh` | cabeçalho comum dos jobs: log, avisos no Telegram, erro e retomada |
| `check_edh.py` | diagnostica a chave do Earth Data Hub sem imprimi-la |

## Jobs, por etapa

| Etapa | Jobs |
|---|---|
| Dados do clima e da perturbação | `era5`, `era5_passagem`, `chirps`, `modis`, `disturbance` |
| Validação dos métodos (portões) | `gate`, `gate_realista`, `nulas_celulas`, `estimadores`, `estimadores_checagem` |
| Descritores e substitutas por célula | `descriptors`, `sensitivity`, `atrasos`, `extremos`, `smap`, `multivariado`, `multivariado_ft` |
| Chuva | `precip`, `chuva_dither` |
| Floresta como sistema dinâmico | `vegetacao_fetch`, `vegetacao`, `vegetacao_gate`, `vegetacao_fogo`, `vegetacao_fogo_local`, `vegetacao_fogo_memoria` |

A primeira linha de comentário de cada `.sbatch` descreve o que ele calcula e a decisão do projeto a que responde (os códigos `D-0xx` de [docs/decisoes.md](../../docs/decisoes.md)).
