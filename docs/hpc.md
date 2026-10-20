# HPC: downloads e cálculos em lote

O HPC (`172.20.10.15`, Slurm, partição `cpu`; exige a rede ou a VPN do CNPEM; **cota de 16 CPUs por usuário**, QOS `limit_16c`: jobs que pedem mais ficam pendentes com `QOSMaxCpuPerUserLimit`) roda o que é longo: o ERA5 pelo Earth Data Hub, a agregação das bases de perturbação e os descritores com substitutas por célula. A máquina local roda os cadernos. Nos dois lados o código é o mesmo, um clone deste repositório; os dados não passam pelo Git.

```
local                                        HPC (~/Caos, clone Git)
  git push ───────── make hpc-code ────────►  git pull + scripts/hpc/setup.sh
                                              sbatch --export=ALL,REGION=<slug> scripts/hpc/<etapa>.sbatch
  data/processed ◄── make pull REGION=… ────  data/processed/<experimento>/
```

## 1. Configuração inicial (uma vez)

**Chave SSH (máquina local).** Exige a senha do HPC uma única vez:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
ssh-copy-id thalles24006@172.20.10.15
```

Em `~/.ssh/config`, um alias com conexão reaproveitada:

```
Host hpc
  HostName 172.20.10.15
  User thalles24006
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h:%p
  ControlPersist 10m
```

**Clone no HPC.** O repositório é `https://github.com/ThallesCansi/Caos` (se for privado, o HPC precisa de uma chave SSH ou de um token do GitHub). Para transformar uma cópia antiga feita por `rsync` em clone sem perder `data/`, que é ignorado pelo Git, envie antes as mudanças locais (`git push`):

```bash
cd ~/Caos && git init -q && git remote add origin https://github.com/ThallesCansi/Caos \
  && git fetch origin && git reset --hard origin/main \
  && git branch -m main && git branch -u origin/main
```

**Segredos no HPC.** Nunca vão para o Git. Use permissão 600:

| Arquivo | Conteúdo | Para quê |
|---|---|---|
| `~/.edh_env` | `EDH_TOKEN=…` (DestinE → Earth Data Hub → *Quota & API Keys*) | ERA5 pelo EDH |
| `~/.telegram_env` | `TG_TOKEN=…` e `TG_CHAT_ID=…` (grupo: id começa com `-100`) | avisos dos jobs (opcional) |
| `~/.netrc` | `machine urs.earthdata.nasa.gov login … password …` | MODIS pelo AppEEARS (Etapa 2) |

**Ambiente.**

```bash
cd ~/Caos
command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh
bash scripts/hpc/setup.sh             # ambiente, segredos, chave EDH, regiões
NETWORK=1 bash scripts/hpc/setup.sh   # também testa a rede de um nó de computação
```

O `setup.sh` é idempotente e nunca imprime segredos. Se o nó de computação não tiver rede, rode os downloads no nó de login dentro do `tmux` (§6).

## 2. Rotina

Na máquina local:

```bash
make hpc-code       # git push; no HPC: git pull --ff-only + setup.sh
make hpc-status     # commit, fila (squeue) e espaço em disco no HPC
make pull REGION=tapajos            # traz data/processed/<experimento>/
scripts/hpc/sync.sh pull tapajos --raw   # também os brutos (só para reprocessar localmente)
```

Os alvos usam o alias `hpc`; para outro host, defina `HPC_HOST` (e `HPC_DIR`, padrão `Caos`).

## 3. Adicionar uma região

1. **Configuração.** Copie `configs/regions/_modelo.yaml` para `configs/regions/<slug>.yaml`, com:
   - o limite (`bhb250` com nível e `cod_otto`, ou `bbox`);
   - a caixa `spatial.area` alinhada a 0,25°;
   - a célula de demonstração.

   Para bacias, o `prepare` calcula o envelope e recusa seguir se a caixa estiver errada, mostrando o valor certo.
2. **Preparar.** `uv run amazon-chaos region prepare <slug>` (local) baixa o limite e a cartografia, confere a caixa e grava a grade em `data/processed/<experimento>/basin_grid.geojson`. Confira o mapa no caderno `02_regioes` **antes** de baixar o clima.
3. **Commit e envio** do YAML: `git commit` + `make hpc-code`.
4. **ERA5 no HPC:** `sbatch --export=ALL,REGION=<slug> scripts/hpc/era5.sbatch`. Teste antes com um mês: `…,START=2024-01-01,END=2024-01-31`.
5. **Trazer:** `make pull REGION=<slug>`. Os cadernos com `--region <slug>` passam a funcionar.

Nada de região fica no código: tudo vem do YAML (D-008).

## 4. ERA5 pelo Earth Data Hub

O CDS entrega poucos MB por requisição, com 20 a 60 minutos de fila cada; 1990–2024 levaria semanas. O [Earth Data Hub](https://earthdatahub.destine.eu/collections/era5/datasets/era5-single-levels-atmosphere) espelha o mesmo ERA5 horário em Zarr, sem fila. O comando `amazon-chaos era5 edh` lê o recorte ano a ano e grava um NetCDF por mês com as seis variáveis, **com os mesmos dias, horas UTC e grade das requisições CDS**. A validação é a mesma, com uma regra a mais: nenhum valor ausente. Cada mês tem manifesto com SHA-256, e reenviar o job retoma do último mês validado.

**Precisão.** O EDH não é bit a bit igual ao CDS: tem cerca de 10 bits de mantissa e até 0,125 K na temperatura horária ([D-007](decisoes.md)). Com `VERIFY=auto` (o padrão), o job confere contra os meses CDS da região, se houver algum em `data/raw/<experimento>/era5`, e **para** se alguma variável divergir além do dobro desse arredondamento. Regiões sem meses CDS dependem da conferência já feita no Xingu, que valida o mesmo espelho.

**`scripts/hpc/era5.sbatch`:**

| Variável | Padrão | Efeito |
|---|---|---|
| `REGION` | (obrigatória) | slug da região |
| `START`, `END` | `1990-01-01`, `2024-12-31` | período |
| `VERIFY` | `auto` | `1` exige meses CDS; `0` pula a conferência |
| `DOWNLOAD`, `PROCESS` | `1`, `1` | `0` pula a etapa |
| `WORKERS` | CPUs do job | leituras simultâneas |

As etapas são: limite e grade (`region prepare --no-context`) → download → série diária ano a ano (`era5 process --source edh`) → resumo regional (`era5 summarize`, quando o período é o completo). Se o limite da partição for menor que 24 h, ajuste `#SBATCH --time`: o job avisa 10 minutos antes do fim, e basta reenviá-lo. Não rode duas instâncias da **mesma** região ao mesmo tempo; regiões diferentes podem rodar juntas.

**Telegram:** início (meses já salvos) → conferência com o CDS → um aviso por ano concluído (tamanho, tempo, previsão) → instabilidades de rede (até 5 novas tentativas) → fim → séries diárias prontas, com o comando `make pull`. Em caso de erro ou fim de tempo, chega a etapa e as últimas linhas do log.

## 5. Demais etapas em lote

Todos usam o cabeçalho comum (`scripts/hpc/_common.sh`: avisos no Telegram, tempo esgotado e retomada) e a variável `REGION`:

| Job | O que faz | Duração aproximada |
|---|---|---|
| `disturbance.sbatch` | PRODES, DETER, BDQueimadas e MapBiomas por célula | minutos a 1 h (4 CPUs) |
| `gate.sbatch` (sem `REGION`) | gate F4 em controles sintéticos | 30 min (16 CPUs) |
| `descriptors.sbatch` | descritores pré-registrados por célula, com substitutas | ~6 h por bacia (16 CPUs) |
| `modis.sbatch` | pedido ao AppEEARS, espera, download e LST por célula | horas, quase sem CPU |

Como a cota é de 16 CPUs, encadeie os jobs grandes:

```bash
j=$(sbatch --parsable --export=ALL,REGION=xingu scripts/hpc/descriptors.sbatch)
sbatch --export=ALL,REGION=tapajos --dependency=afterany:$j scripts/hpc/descriptors.sbatch
```

O `descriptors.sbatch` grava blocos de 25 células à medida que terminam, e reenviá-lo continua do primeiro bloco que falta. Ele só roda com o pré-registro congelado.

**MODIS:** o `~/.netrc` precisa ter a linha `machine urs.earthdata.nasa.gov login <usuário> password <senha>`, com permissão 600. O AppEEARS faz login com usuário e senha, não com o token de download do Earthdata.

## 6. Sem Slurm

No nó de login, `tmux new -s era5` e depois `REGION=xingu bash scripts/hpc/era5.sbatch`. `Ctrl-b d` desanexa; `tmux attach -t era5` volta. O log vai para `logs/`.

## 7. Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `HTTP 401` no EDH | chave inválida ou expirada: `bash scripts/hpc/setup.sh` mostra o diagnóstico (`check_edh.py`); gere outra chave |
| `nenhum mês CDS … para conferir` | rode com `VERIFY=0` ou copie os meses CDS para `data/raw/<experimento>/era5` |
| `spatial.area de … deveria ser […]` | a caixa do YAML não é o envelope do limite; copie o valor sugerido |
| TIs da FUNAI com erro de certificado | o servidor omite o intermediário TLS; o código o obtém pelo endereço AIA (`regions.MISSING_INTERMEDIATE`); se o certificado mudar, atualize o endereço |
| job pendente com `QOSMaxCpuPerUserLimit` | pediu mais que 16 CPUs (somando os jobs em execução): reduza `--cpus-per-task` |
| `ssh hpc` trava sem erro (o direto funciona) | conexão compartilhada (ControlMaster) presa, por exemplo depois de cair a VPN: `ssh -O exit hpc` ou apague `~/.ssh/cm-*` |
| nó sem rede (timeout no `NETWORK=1`) | rode no nó de login, dentro do `tmux` (§6) |
