# ERA5 no HPC pelo Earth Data Hub

O CDS entrega poucos MB por requisição e cada uma espera 20–60 min na fila; o plano 1990–2024 levaria semanas. O [Earth Data Hub](https://earthdatahub.destine.eu/collections/era5/datasets/era5-single-levels-atmosphere) (DestinE) espelha o mesmo ERA5 horário em Zarr, organizado para séries longas (blocos de 45 dias × 15° × 15°), sem fila. O comando `edh-download` lê o recorte ano a ano e grava um NetCDF por mês com as seis variáveis, **os mesmos dias, horas UTC e grade das requisições CDS**, validado pelas mesmas regras e mais uma: nenhum valor ausente em nenhuma célula ou hora. Cada mês tem manifesto com SHA-256; reenviar o job retoma do último mês validado.

**Igualdade com o CDS.** Antes do período completo, o job baixa do EDH os anos que já têm meses CDS em `data/raw/<experimento>/era5`, compara valor a valor (mesmas horas e células) e **para** se alguma variável divergir além de arredondamento de float32 (`rtol=1e-6`). A notificação informa, por variável, a porcentagem de valores idênticos e a diferença máxima.

## 1. Preparar (uma vez)

**Chave do Earth Data Hub.** Crie a conta pela DestinE Platform, gere uma chave pessoal no Earth Data Hub e salve no HPC:

```bash
echo 'EDH_TOKEN=cole-a-chave-aqui' > ~/.edh_env && chmod 600 ~/.edh_env
```

**Telegram.** O `~/.telegram_env` é o mesmo do seu `send_telegram.sh` (`TG_TOKEN=…` e `TG_CHAT_ID=…`; para grupo, o id começa com `-100` e o bot precisa estar no grupo). Sem esse arquivo o job roda normalmente, só não avisa.

**Código e dados no HPC.** O código pode ir pelo Git; os dados não, porque `data/` fica fora do Git por decisão do projeto. Por isso a primeira cópia usa `rsync`, que leva também os meses CDS já baixados (usados na conferência) e a máscara da bacia (`data/external/xingu`, `data/processed/xingu-era5-1990-2024/basin_grid.geojson`):

```bash
rsync -avP --exclude .venv --exclude .git --exclude '__pycache__' \
  --exclude .pytest_cache --exclude .ruff_cache \
  ./ thalles24006@172.20.10.15:~/Caos/
```

Depois disso, atualizações de código podem vir por `git pull` no HPC (o repositório é `https://github.com/ThallesCansi/Caos`; se for privado, o HPC precisa de chave SSH ou token do GitHub). Para transformar a cópia existente em clone sem perder `data/`, que é ignorado pelo Git:

```bash
cd ~/Caos && git init -q && git remote add origin https://github.com/ThallesCansi/Caos \
  && git fetch origin && git reset --hard origin/main \
  && git branch -m main && git branch -u origin/main
```

`reset --hard` substitui os arquivos versionados pela versão do GitHub; faça isso só depois de enviar (push) as mudanças locais.

**Ambiente Python** (no HPC, nó de login). Usa `uv`, sem conda:

```bash
cd ~/Caos
command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh   # ou: pip install --user uv
uv sync --frozen
chmod +x scripts/hpc/*.sh
scripts/hpc/send_telegram.sh "🔔 Teste: o HPC consegue falar com o grupo!"
```

**Os nós de computação acessam a internet?**

```bash
srun -p cpu -n1 --time=5 python3 -c "import urllib.request as u; print(u.urlopen('https://data.earthdatahub.destine.eu', timeout=15).status)"
```

Se imprimir um código HTTP (inclusive 401), há rede: use o `sbatch`. Se der timeout, rode no nó de login dentro do `tmux` (passo 2b), caso as regras do cluster permitam; o download quase não usa CPU.

## 2. Executar

**2a. Pelo Slurm** (na raiz do projeto no HPC):

```bash
mkdir -p logs
sbatch scripts/hpc/era5_edh.sbatch                        # Xingu, 1990–2024
tail -f logs/era5-edh-<jobid>.out                         # acompanhar
```

Baixo Tapajós, 1990–2024 (mesma caixa do piloto, 56 células; não há meses CDS dessa caixa para conferir, e a conferência do Xingu vale para o mesmo espelho):

```bash
CONFIG=configs/tapajos_1990_2024.yaml VERIFY=0 sbatch scripts/hpc/era5_edh.sbatch
```

Sugestão: enviar o do Tapajós depois da mensagem "Conferência com o CDS: tudo certo!" do job do Xingu.

Os dois jobs podem rodar ao mesmo tempo (diretórios separados). Não rode duas instâncias do **mesmo** experimento juntas.

**2b. Sem Slurm** (nó de login): `tmux new -s era5`, depois `bash scripts/hpc/era5_edh.sbatch` (mesmas variáveis); `Ctrl-b d` desanexa; `tmux attach -t era5` volta.

Variáveis: `CONFIG`, `START`, `END`, `VERIFY=1|0`, `PROCESS=1|0` (gera `daily_<ano>.nc` mascarado pela bacia após o download), `WORKERS` (downloads simultâneos; padrão = CPUs do job). Se o limite de tempo da partição for menor que 24 h, ajuste `#SBATCH --time`: o job avisa 10 min antes do fim e basta reenviar.

## 3. Mensagens no Telegram

Início (período e meses já salvos) → resultado da conferência com o CDS → um aviso por ano concluído com tamanho, tempo e previsão do restante → avisos de instabilidade de rede (até 5 novas tentativas, com espera crescente) → fim do download → séries diárias prontas, com o `rsync` para trazê-las. Em erro ou fim de tempo, chega a etapa e as últimas linhas do log.

## 4. Trazer para a sua máquina

As séries diárias são pequenas; baixe-as primeiro. Os brutos (~10 GB para o Xingu) só se precisar reprocessar localmente. `--partial` permite retomar transferências interrompidas.

```bash
rsync -avP --partial thalles24006@172.20.10.15:~/Caos/data/processed/xingu-era5-1990-2024/ \
  data/processed/xingu-era5-1990-2024/
rsync -avP --partial thalles24006@172.20.10.15:~/Caos/data/raw/xingu-era5-1990-2024/edh/ \
  data/raw/xingu-era5-1990-2024/edh/
```

Localmente, os brutos do EDH são lidos com `--source edh`:

```bash
uv run python -m amazon_chaos.pilot_cli process 2001-01-01 2001-12-31 \
  --config configs/xingu_1990_2024.yaml --source edh
```
